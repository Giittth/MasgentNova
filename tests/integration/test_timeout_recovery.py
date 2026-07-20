"""
测试 Timeout Recovery（基于 recovery_started_at）
"""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime

from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.tasks.retry import RetryPolicy
from masgent.calculators.registry import CalculatorRegistry
from masgent.models.enums import TaskStatus, WorkflowType, UnknownStrategy
from masgent.models.task import TaskRecord
from masgent.models.job import JobHandle
from masgent.models.enums import UnknownStrategy
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
async def test_timeout_recovery_running_task_times_out(temp_task_dir):
    """
    场景：RUNNING 任务持续超过 recovery_timeout（设为 1 秒），应标记 FAILED
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry, recovery_timeout=1.0)  # 1秒超时

    task_id = "timeout_test"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

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

    await runner.recover()
    assert task_id in runner._running_tasks

    # 轮询等待超时状态
    for _ in range(30):  # 最多等待 3 秒
        record = store.load(task_id)
        if record.status == TaskStatus.FAILED:
            break
        await asyncio.sleep(0.1)

    # 验证任务被标记为 FAILED
    record = store.load(task_id)
    assert record.status == TaskStatus.FAILED
    assert "Recovery timeout" in record.error_message

    # 验证 running_tasks 已清理
    assert task_id not in runner._running_tasks

    await runner.shutdown()


@pytest.mark.asyncio
async def test_timeout_recovery_disabled(temp_task_dir):
    """
    场景：recovery_timeout=0 表示禁用超时，任务应持续 RUNNING
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry, recovery_timeout=0)  # 禁用超时

    task_id = "timeout_disabled"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    FakeSlurmExecutor.GLOBAL_JOBS["3333"] = {
        "status": "RUNNING",
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": str(work_dir),
    }

    job_handle = JobHandle(
        job_id="slurm_3333",
        backend="slurm",
        scheduler_id="3333",
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

    await runner.recover()
    assert task_id in runner._running_tasks

    # 等待超过普通超时时间（但超时被禁用）
    await asyncio.sleep(1.5)

    # 验证任务仍然是 RUNNING（未被超时杀死）
    record = store.load(task_id)
    assert record.status == TaskStatus.RUNNING

    # 清理
    await runner.shutdown()

@pytest.mark.asyncio
async def test_timeout_recovery_completed_before_timeout(temp_task_dir):
    """
    场景：RUNNING 任务在超时前完成，应标记 COMPLETED 而非失败
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry, recovery_timeout=5.0)  # 5秒超时

    task_id = "complete_before_timeout"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    FakeSlurmExecutor.GLOBAL_JOBS["4444"] = {
        "status": "RUNNING",
        "exit_code": None,
        "command": "sleep 1",
        "work_dir": str(work_dir),
    }

    job_handle = JobHandle(
        job_id="slurm_4444",
        backend="slurm",
        scheduler_id="4444",
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

    await runner.recover()
    assert task_id in runner._running_tasks

    # 模拟快速完成（0.3秒后标记完成，远小于5秒超时）
    await asyncio.sleep(0.3)
    FakeSlurmExecutor.GLOBAL_JOBS["4444"]["status"] = "COMPLETED"
    FakeSlurmExecutor.GLOBAL_JOBS["4444"]["exit_code"] = 0

    # 等待 poll 检测到完成
    for _ in range(30):
        record = store.load(task_id)
        if record.status == TaskStatus.COMPLETED:
            break
        await asyncio.sleep(0.1)

    record = store.load(task_id)
    assert record.status == TaskStatus.COMPLETED
    assert record.error_message is None or "Recovery timeout" not in record.error_message

    await runner.shutdown()

@pytest.mark.asyncio
async def test_timeout_recovery_running_before_timeout(temp_task_dir):
    """
    Case 1: RUNNING 任务持续运行，但恢复时间未超过 timeout
    预期：任务保持 RUNNING，不触发超时失败
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry, recovery_timeout=5.0)

    task_id = "running_before_timeout"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    FakeSlurmExecutor.GLOBAL_JOBS["5555"] = {
        "status": "RUNNING",
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": str(work_dir),
    }

    job_handle = JobHandle(
        job_id="slurm_5555",
        backend="slurm",
        scheduler_id="5555",
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

    await runner.recover()
    assert task_id in runner._running_tasks

    # 等待 1 秒（小于 timeout=5 秒）
    await asyncio.sleep(1.0)

    # 验证任务仍然 RUNNING（未超时）
    record = store.load(task_id)
    assert record.status == TaskStatus.RUNNING

    await runner.shutdown()


@pytest.mark.asyncio
async def test_unknown_retry_exhausted(temp_task_dir):
    """
    Case 3: UNKNOWN 持续恢复失败，retry_count 达到 max_retries 后 FAILED
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    # max_retries=3：允许 3 次尝试，第 3 次失败后标记 FAILED
    policy = RetryPolicy(max_retries=3)
    runner = TaskRunner(
        store,
        registry,
        retry_policy=policy,
        unknown_strategy=UnknownStrategy.EXECUTE,
        recovery_timeout=3600.0,
    )

    task_id = "unknown_retry_test"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    from tests.mock_calculator import UnknownCalculator
    if not registry._factories.get("unknown"):
        registry.register("unknown", UnknownCalculator)

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.UNKNOWN,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="unknown",
        calculator_params={},
        workflow_params={},
        retry_count=0,
    )
    store.save(record)

    # ---------- retry 1 ----------
    await runner.recover()

    for _ in range(30):
        record = store.load(task_id)
        if record.status == TaskStatus.RUNNING:
            break
        await asyncio.sleep(0.1)

    assert record.retry_count == 1
    assert record.status == TaskStatus.RUNNING

    # 模拟恢复失败
    task = runner._running_tasks.get(task_id)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    record.status = TaskStatus.UNKNOWN
    record.updated_at = datetime.now()
    store.save(record)

    # ---------- retry 2 ----------
    await runner.recover()

    for _ in range(30):
        record = store.load(task_id)
        if record.status == TaskStatus.RUNNING:
            break
        await asyncio.sleep(0.1)

    assert record.retry_count == 2
    assert record.status == TaskStatus.RUNNING

    # 再次模拟恢复失败
    task = runner._running_tasks.get(task_id)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    record.status = TaskStatus.UNKNOWN
    record.updated_at = datetime.now()
    store.save(record)

    # ---------- retry 3 exhausted ----------
    await runner.recover()

    for _ in range(30):
        record = store.load(task_id)
        if record.status == TaskStatus.FAILED:
            break
        await asyncio.sleep(0.1)

    assert record.status == TaskStatus.FAILED
    assert "UNKNOWN after 3 retries" in record.error_message

    await runner.shutdown()


@pytest.mark.asyncio
async def test_failed_timeout_not_recovered_again(temp_task_dir):
    """
    Case 4: FAILED 状态的任务，recover 时应该被忽略（不恢复）
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry, recovery_timeout=0.5)

    task_id = "failed_after_timeout"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # 创建已 FAILED 的任务
    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.FAILED,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="running_mock",
        calculator_params={},
        workflow_params={},
        retry_count=0,
    )
    store.save(record)

    # recover 应该忽略 FAILED 任务
    await runner.recover()
    assert task_id not in runner._running_tasks

    # 等待一段时间
    await asyncio.sleep(1.0)

    # 验证任务仍然是 FAILED
    record = store.load(task_id)
    assert record.status == TaskStatus.FAILED

    await runner.shutdown()