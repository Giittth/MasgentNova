"""
进程级 Crash E2E 恢复测试

模拟真实进程崩溃场景：
    - Process A: TaskRunner 运行中崩溃（内存状态丢失）
    - Process B: 新 TaskRunner 接管并恢复

覆盖场景：
    1. 崩溃时作业还在运行 → 接管轮询 → 完成
    2. 崩溃时作业已完成 → 直接收集结果
"""

import pytest
import asyncio
import gc
from pathlib import Path
from datetime import datetime

from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry
from masgent.models.enums import TaskStatus, WorkflowType, UnknownStrategy
from masgent.models.task import TaskRecord
from masgent.models.job import JobHandle
from tests.mock_calculator import RunningCalculator, CompletedCalculator
from tests.mock_executors import FakeSlurmExecutor


@pytest.fixture(autouse=True)
def register_calculators():
    from masgent.calculators.registry import CalculatorRegistry
    if not CalculatorRegistry._factories.get("running_mock"):
        CalculatorRegistry.register("running_mock", RunningCalculator)
    if not CalculatorRegistry._factories.get("completed"):
        CalculatorRegistry.register("completed", CompletedCalculator)
    yield


@pytest.fixture(autouse=True)
def ensure_fake_slurm():
    from masgent.executors.factory import ExecutorFactory
    if "fake_slurm" not in ExecutorFactory._registry:
        ExecutorFactory.register("fake_slurm", FakeSlurmExecutor)
    yield


@pytest.fixture(autouse=True)
def clear_fake_slurm_jobs():
    FakeSlurmExecutor.clear_jobs()
    yield


@pytest.mark.asyncio
async def test_crash_recovery_job_still_running(temp_task_dir):
    """
    场景：TaskRunner 崩溃时，底层作业还在运行
    预期：新 TaskRunner 接管轮询，最终作业完成
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    task_id = "crash_running"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # ---- Process A: 运行中 ----
    # 1. 创建 Slurm 作业（RUNNING）
    FakeSlurmExecutor.GLOBAL_JOBS["1111"] = {
        "status": "RUNNING",
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": str(work_dir),
    }

    job_handle = JobHandle(
        job_id="slurm_1111",
        backend="slurm",
        scheduler_id="1111",
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

    # 2. Process A 启动并接管任务
    runner_a = TaskRunner(
        store,
        registry,
        poll_interval=0.1,
        unknown_strategy=UnknownStrategy.AUTO,
        recovery_timeout=3600.0,
    )

    await runner_a.recover()

    # 验证 Process A 已接管
    assert task_id in runner_a._running_tasks
    assert runner_a._recovery_lock.is_locked(task_id)

    # ---- 模拟进程崩溃（kill -9） ----
    # 取消所有后台任务（模拟 event loop 销毁）
    for task in list(runner_a._running_tasks.values()):
        if not task.done():
            task.cancel()
    # 清空内存状态
    runner_a._running_tasks.clear()
    runner_a._executors.clear()
    runner_a._calculators.clear()
    runner_a._recovery_started_at.clear()
    # 锁是类级别的，清除（模拟进程死亡，所有锁丢失）
    runner_a._recovery_lock.clear()
    del runner_a
    gc.collect()  # 帮助清理可能残留的引用

    # ---- Process B: 接管 ----
    runner_b = TaskRunner(
        store,
        registry,
        poll_interval=0.1,
        unknown_strategy=UnknownStrategy.AUTO,
        recovery_timeout=3600.0,
    )

    await runner_b.recover()

    # 验证 Process B 成功接管
    assert task_id in runner_b._running_tasks
    # 验证 executor 被正确重建并存储
    assert task_id in runner_b._executors

    # 验证作业仍然存活
    assert FakeSlurmExecutor.GLOBAL_JOBS["1111"]["status"] == "RUNNING"

    # ---- 模拟作业完成 ----
    await asyncio.sleep(0.3)
    FakeSlurmExecutor.GLOBAL_JOBS["1111"]["status"] = "COMPLETED"
    FakeSlurmExecutor.GLOBAL_JOBS["1111"]["exit_code"] = 0

    # 等待任务完成
    for _ in range(50):
        record = store.load(task_id)
        if record.status == TaskStatus.COMPLETED:
            break
        await asyncio.sleep(0.1)

    record = store.load(task_id)
    assert record.status == TaskStatus.COMPLETED
    assert task_id not in runner_b._running_tasks

    # 验证没有创建额外的作业（只应有最初的一个）
    assert len(FakeSlurmExecutor.GLOBAL_JOBS) == 1

    await runner_b.shutdown()


@pytest.mark.asyncio
async def test_crash_recovery_job_already_completed(temp_task_dir):
    """
    场景：TaskRunner 崩溃期间，底层作业已经完成
    预期：新 TaskRunner 恢复时直接收集结果，标记 COMPLETED
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    task_id = "crash_completed"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # ---- Process A: 运行中 ----
    FakeSlurmExecutor.GLOBAL_JOBS["2222"] = {
        "status": "RUNNING",
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": str(work_dir),
    }

    job_handle = JobHandle(
        job_id="slurm_2222",
        backend="slurm",
        scheduler_id="2222",
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

    # Process A 启动并接管
    runner_a = TaskRunner(
        store,
        registry,
        poll_interval=0.1,
        unknown_strategy=UnknownStrategy.AUTO,
        recovery_timeout=3600.0,
    )

    await runner_a.recover()
    assert task_id in runner_a._running_tasks

    # ---- 模拟进程崩溃 ----
    for task in list(runner_a._running_tasks.values()):
        if not task.done():
            task.cancel()
    runner_a._running_tasks.clear()
    runner_a._executors.clear()
    runner_a._calculators.clear()
    runner_a._recovery_started_at.clear()
    runner_a._recovery_lock.clear()
    del runner_a
    gc.collect()

    # ---- 崩溃期间，作业在 Slurm 端完成 ----
    FakeSlurmExecutor.GLOBAL_JOBS["2222"]["status"] = "COMPLETED"
    FakeSlurmExecutor.GLOBAL_JOBS["2222"]["exit_code"] = 0

    # ---- Process B: 接管 ----
    runner_b = TaskRunner(
        store,
        registry,
        poll_interval=0.1,
        unknown_strategy=UnknownStrategy.AUTO,
        recovery_timeout=3600.0,
    )

    await runner_b.recover()

    # 验证任务直接完成（无需轮询）
    for _ in range(30):
        record = store.load(task_id)
        if record.status == TaskStatus.COMPLETED:
            break
        await asyncio.sleep(0.1)

    record = store.load(task_id)
    assert record.status == TaskStatus.COMPLETED

    # 验证没有残留轮询任务
    assert task_id not in runner_b._running_tasks

    # 验证没有创建额外的作业
    assert len(FakeSlurmExecutor.GLOBAL_JOBS) == 1

    await runner_b.shutdown()