"""
测试 _execute() 路径的 RecoveryLock 生命周期
验证 restart_execute 完成后锁被正确释放
"""

import pytest
import asyncio
import json
from pathlib import Path
from datetime import datetime

from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry
from masgent.models.enums import TaskStatus, WorkflowType, UnknownStrategy
from masgent.models.task import TaskRecord
from masgent.models.calculator import CalculationResult
from masgent.calculators.base import Calculator
from tests.mock_calculator import MockCalculator


# 定义用于此测试的 Calculator：第一次 detect_status 返回 UNKNOWN，之后返回 COMPLETED
class UnknownThenCompletedCalculator(MockCalculator):
    TYPE = "unknown_then_completed"

    async def detect_status(self, work_dir, job=None):
        counter_file = work_dir / ".detect_count"
        count = 0
        if counter_file.exists():
            count = int(counter_file.read_text())
        count += 1
        counter_file.write_text(str(count))
        if count == 1:
            return TaskStatus.UNKNOWN
        return TaskStatus.COMPLETED

    async def collect(self, work_dir, workflow_type):
        return CalculationResult(
            success=True,
            workflow_type=workflow_type,
            data={"energy": -10.5},
            metadata={"calculator": "unknown_then_completed"},
        )


@pytest.fixture(autouse=True)
def register_unknown_then_completed():
    from masgent.calculators.registry import CalculatorRegistry
    if not CalculatorRegistry._factories.get("unknown_then_completed"):
        CalculatorRegistry.register("unknown_then_completed", UnknownThenCompletedCalculator)
    yield


@pytest.mark.asyncio
async def test_restart_execute_releases_lock(temp_task_dir):
    """
    场景：UNKNOWN 任务通过 EXECUTE 策略恢复，_execute 完成后锁被释放
    预期：锁释放，_running_tasks 清理，任务状态 COMPLETED，restart_execute 只记录一次
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    task_id = "execute_lock_test"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # 创建 UNKNOWN 状态任务，使用自定义 Calculator
    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.UNKNOWN,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="unknown_then_completed",
        calculator_params={},
        workflow_params={},
        retry_count=0,
    )
    store.save(record)

    runner = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.EXECUTE)

    # 执行恢复
    await runner.recover()

    # 等待 _execute 完成（轮询检测）
    for _ in range(30):
        if task_id not in runner._running_tasks:
            break
        await asyncio.sleep(0.1)

    # 验证锁已释放
    assert not runner._recovery_lock.is_locked(task_id)

    # 验证 running_tasks 已清理
    assert task_id not in runner._running_tasks

    # 验证任务状态为 COMPLETED
    record = store.load(task_id)
    assert record.status == TaskStatus.COMPLETED

    # 验证 RecoveryEvent：restart_execute 只出现一次
    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()
    with open(events_file, "r") as f:
        events = [json.loads(line) for line in f.readlines()]
    task_events = [e for e in events if e["task_id"] == task_id]
    actions = [e["action"] for e in task_events]
    assert actions.count("restart_execute") == 1

    await runner.shutdown()