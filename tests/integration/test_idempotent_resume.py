"""
测试 TaskRunner.recover() 的幂等性
验证多次调用 recover 不会产生重复的轮询任务或恢复操作
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
from tests.mock_calculator import RunningCalculator
from tests.mock_executors import FakeSlurmExecutor


@pytest.fixture(autouse=True)
def register_running_calculator():
    from masgent.calculators.registry import CalculatorRegistry
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
async def test_idempotent_resume_multiple_calls(temp_task_dir):
    """
    场景：连续多次调用 recover()，同一个 RUNNING 任务
    预期：只有第一次创建轮询任务，后续调用直接跳过
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    task_id = "idempotent_test"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # 准备 FakeSlurm 环境
    FakeSlurmExecutor.GLOBAL_JOBS["9999"] = {
        "status": "RUNNING",
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": str(work_dir),
    }

    job_handle = JobHandle(
        job_id="slurm_9999",
        backend="slurm",
        scheduler_id="9999",
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

    # 多次调用 recover
    await runner.recover()
    task1 = runner._running_tasks.get(task_id)

    await runner.recover()
    task2 = runner._running_tasks.get(task_id)

    await runner.recover()
    task3 = runner._running_tasks.get(task_id)

    await runner.recover()
    task4 = runner._running_tasks.get(task_id)

    # 验证是同一个 Task 对象（不是新创建的）
    assert task1 is task2
    assert task2 is task3
    assert task3 is task4

    # 验证 _running_tasks 中只有一个任务
    assert len(runner._running_tasks) == 1

    # 验证 RecoveryEvent 只有一次 restart_poll
    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()
    with open(events_file, "r") as f:
        events = [json.loads(line) for line in f.readlines()]
    task_events = [e for e in events if e["task_id"] == task_id]
    actions = [e["action"] for e in task_events]
    assert actions.count("restart_poll") == 1

    await runner.shutdown()


@pytest.mark.asyncio
async def test_recover_after_poll_finished(temp_task_dir):
    """
    场景：poll 任务完成后，再次调用 recover 能重新创建轮询
    验证 running_tasks 生命周期闭环：创建 → 清理 → 可重新创建
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    task_id = "poll_finished_test"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # 准备 FakeSlurm 环境（初始 RUNNING）
    FakeSlurmExecutor.GLOBAL_JOBS["7777"] = {
        "status": "RUNNING",
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": str(work_dir),
    }

    job_handle = JobHandle(
        job_id="slurm_7777",
        backend="slurm",
        scheduler_id="7777",
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
    assert task_id in runner._running_tasks
    assert runner._recovery_lock.is_locked(task_id)

    # 模拟任务完成，让 _poll_loop 退出
    FakeSlurmExecutor.GLOBAL_JOBS["7777"]["status"] = "COMPLETED"
    FakeSlurmExecutor.GLOBAL_JOBS["7777"]["exit_code"] = 0

    # ★ 等待 _poll_loop 检测到完成并清理（轮询等待，避免 sleep 不稳定）
    for _ in range(30):  # 最多等待 3 秒
        if task_id not in runner._running_tasks:
            break
        await asyncio.sleep(0.1)
    assert task_id not in runner._running_tasks
    assert not runner._recovery_lock.is_locked(task_id)

    # 重新创建任务记录（模拟新任务或任务状态回退）
    record.status = TaskStatus.RUNNING
    record.updated_at = datetime.now()
    FakeSlurmExecutor.GLOBAL_JOBS["7777"]["status"] = "RUNNING"
    FakeSlurmExecutor.GLOBAL_JOBS["7777"]["exit_code"] = None
    store.save(record)

    # ★ 再次调用 recover，应该能重新创建轮询任务
    await runner.recover()

    # ★ 验证新的轮询任务被创建
    assert task_id in runner._running_tasks
    assert runner._recovery_lock.is_locked(task_id)

    # 验证事件：应该有两次 restart_poll
    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()
    with open(events_file, "r") as f:
        events = [json.loads(line) for line in f.readlines()]
    task_events = [e for e in events if e["task_id"] == task_id]
    actions = [e["action"] for e in task_events]
    assert actions.count("restart_poll") == 2

    await runner.shutdown()