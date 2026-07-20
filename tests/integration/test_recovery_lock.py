"""
测试 Recovery Lock —— 防止同一任务被多个 TaskRunner 实例同时恢复
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
from masgent.models.job import JobHandle
from masgent.tasks.recovery_lock import debug_has_lock
from tests.mock_calculator import UnknownCalculator, RunningCalculator
from tests.mock_executors import FakeSlurmExecutor


@pytest.fixture(autouse=True)
def register_calculators():
    from masgent.calculators.registry import CalculatorRegistry
    if not CalculatorRegistry._factories.get("unknown_calc"):
        CalculatorRegistry.register("unknown_calc", UnknownCalculator)
    if not CalculatorRegistry._factories.get("running_mock"):
        CalculatorRegistry.register("running_mock", RunningCalculator)
    yield


@pytest.fixture(autouse=True)
def ensure_fake_slurm():
    from masgent.executors.factory import ExecutorFactory
    if "fake_slurm" not in ExecutorFactory._registry:
        ExecutorFactory.register("fake_slurm", FakeSlurmExecutor)
    yield


@pytest.mark.asyncio
async def test_recovery_lock_prevents_double_recovery(temp_task_dir):
    """
    场景：两个 TaskRunner 实例同时 recover 同一个 RUNNING 任务
    预期：只有一个实例成功恢复（进入 _running_tasks），另一个被锁跳过
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    task_id = "lock_test"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # 1. 准备 FakeSlurm 环境
    executor = FakeSlurmExecutor(partition="cpu")
    FakeSlurmExecutor.GLOBAL_JOBS["1234"] = {
        "status": "RUNNING",
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": str(work_dir),
    }

    job_handle = JobHandle(
        job_id="slurm_1234",
        backend="slurm",
        scheduler_id="1234",
        submitted_at=datetime.now().isoformat(),
    )

    # 2. 创建一个 RUNNING 任务记录
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
        job_handle=job_handle.to_dict(),
        executor_config={"type": "fake_slurm", "partition": "cpu", "ntasks": 1},
        retry_count=0,
    )
    store.save(record)

    # 3. 创建两个 TaskRunner 实例（共享同一个 TaskStore）
    runner1 = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.AUTO)
    runner2 = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.AUTO)

    # 4. 并发执行 recover
    await asyncio.gather(
        runner1.recover(),
        runner2.recover(),
        return_exceptions=True
    )

    # 5. 验证：合计只有一个任务被恢复（进入 _running_tasks）
    running_count = len(runner1._running_tasks) + len(runner2._running_tasks)
    assert running_count == 1

    # 6. 验证该任务的锁存在于全局锁字典中（不依赖数量）
    assert debug_has_lock(task_id)

    # 7. 验证 RecoveryEvent 日志
    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()

    with open(events_file, "r") as f:
        events = [json.loads(line) for line in f.readlines()]

    # 过滤出该任务的 events
    task_events = [e for e in events if e["task_id"] == task_id]
    actions = [e["action"] for e in task_events]

    # 应该有一个 restart_poll 和一个 skipped
    assert actions.count("restart_poll") == 1
    assert actions.count("skipped") == 1

    # 验证 skipped 事件包含 lock_acquire_failed
    skipped = [e for e in task_events if e["action"] == "skipped"]
    assert len(skipped) == 1
    assert skipped[0].get("error", {}).get("code") == "lock_acquire_failed"

    # 8. 清理
    await runner1.shutdown()
    await runner2.shutdown()


@pytest.mark.asyncio
async def test_recovery_lock_releases_after_recovery(temp_task_dir):
    """
    场景：RUNNING 任务恢复后，锁应保持直到任务完成
    验证：恢复期间锁被持有，任务完成后锁被释放
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    task_id = "lock_release_test"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # 准备 FakeSlurm 环境（RUNNING 状态）
    executor = FakeSlurmExecutor(partition="cpu")
    FakeSlurmExecutor.GLOBAL_JOBS["5678"] = {
        "status": "RUNNING",
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": str(work_dir),
    }

    job_handle = JobHandle(
        job_id="slurm_5678",
        backend="slurm",
        scheduler_id="5678",
        submitted_at=datetime.now().isoformat(),
    )

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
        job_handle=job_handle.to_dict(),
        executor_config={"type": "fake_slurm", "partition": "cpu", "ntasks": 1},
        retry_count=0,
    )
    store.save(record)

    runner = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.AUTO)

    # 第一次恢复
    await runner.recover()

    # 验证：恢复期间锁被持有（RUNNING 任务进入轮询）
    assert runner._recovery_lock.is_locked(task_id)

    # 模拟任务完成，让 _poll_loop 退出
    FakeSlurmExecutor.GLOBAL_JOBS["5678"]["status"] = "COMPLETED"
    FakeSlurmExecutor.GLOBAL_JOBS["5678"]["exit_code"] = 0

    # 等待 _poll_loop 检测到完成并退出
    await asyncio.sleep(0.3)

    # 验证：任务完成后锁被释放
    assert not runner._recovery_lock.is_locked(task_id)

    # 验证 _running_tasks 已被清理
    assert task_id not in runner._running_tasks

    await runner.shutdown()