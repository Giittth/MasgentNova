"""
测试 RecoveryEvent 持久化（写入 JSONL 文件）
"""

import json
import pytest
import asyncio
from pathlib import Path
from datetime import datetime

from masgent.models.enums import TaskStatus, WorkflowType
from masgent.models.task import TaskRecord
from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry
from tests.conftest import wait_until


@pytest.mark.asyncio
async def test_recovery_event_persistence_on_executor_failure(temp_task_dir):
    """
    场景：executor 配置非法 → recover 失败 → 事件被持久化
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry)

    task_id = "event_executor_fail"
    work_dir = temp_task_dir / "event_executor_fail"
    work_dir.mkdir(parents=True, exist_ok=True)

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="mock",
        calculator_params={},
        workflow_params={},
        executor_config={"type": "slurm", "ntasks": 1},  # 缺少 partition
        retry_count=0,
    )
    store.save(record)

    await runner.recover()
    await asyncio.sleep(0.2)

    # 读取 recovery_events.jsonl
    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()

    with open(events_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) > 0

    # 解析最后一行，使用 error.code 验证
    last_event = json.loads(lines[-1])
    assert last_event["error"]["code"] == "executor_rebuild_failed"

    await runner.shutdown()


@pytest.mark.asyncio
async def test_recovery_event_persistence_on_restart_poll(temp_task_dir):
    """
    场景：RUNNING 任务恢复 → restart_poll 事件被持久化
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry)

    task_id = "event_restart_poll"
    work_dir = temp_task_dir / "event_restart_poll"
    work_dir.mkdir(parents=True, exist_ok=True)

    # 使用 RunningCalculator（需要注册）
    from tests.mock_calculator import RunningCalculator

    # 注册（如果未注册）
    if not registry._factories.get("running_mock"):
        registry.register("running_mock", RunningCalculator)

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="running_mock",
        calculator_params={},
        workflow_params={},
        executor_config={"type": "fake_slurm", "partition": "cpu", "ntasks": 1},
        retry_count=0,
    )
    store.save(record)

    # 预先注入 executor 和 calculator（模拟恢复过程）
    from tests.mock_executors import FakeSlurmExecutor
    executor = FakeSlurmExecutor(partition="cpu")
    calc = RunningCalculator(executor=executor)
    runner._executors[task_id] = executor
    runner._calculators[task_id] = calc

    await runner.recover()
    await asyncio.sleep(0.2)

    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()

    with open(events_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) > 0

    # 至少包含一个 restart_poll 事件
    actions = [json.loads(line)["action"] for line in lines]
    assert "restart_poll" in actions

    await runner.shutdown()


@pytest.mark.asyncio
async def test_recovery_event_order(temp_task_dir):
    """
    验证 UNKNOWN 恢复时产生 retry 事件
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry)

    task_id = "event_order"
    work_dir = temp_task_dir / "event_order"
    work_dir.mkdir(parents=True, exist_ok=True)

    from tests.mock_calculator import UnknownCalculator
    if not registry._factories.get("unknown"):
        registry.register("unknown", UnknownCalculator)

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="unknown",
        calculator_params={},
        workflow_params={},
        retry_count=0,
        executor_config={"type": "fake_slurm", "partition": "cpu", "ntasks": 1},
    )
    store.save(record)

    from tests.mock_executors import FakeSlurmExecutor
    executor = FakeSlurmExecutor(partition="cpu")
    calc = UnknownCalculator(executor=executor)
    runner._executors[task_id] = executor
    runner._calculators[task_id] = calc

    await runner.recover()
    await asyncio.sleep(0.2)

    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()

    with open(events_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    events = [json.loads(line) for line in lines]

    task_events = [e for e in events if e["task_id"] == task_id]
    # 至少包含 retry 事件
    assert len(task_events) >= 1
    actions = [e["action"] for e in task_events]
    assert "retry" in actions

    await runner.shutdown()