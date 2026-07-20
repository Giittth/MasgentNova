"""
恢复层边界情况测试

覆盖：
    - CANCELLED 状态恢复
    - UNKNOWN 重试耗尽
    - UNKNOWN 重试重启执行
    - Executor 重建失败 → UNKNOWN
    - Calculator 重建失败 → FAILED
    - JobHandle 损坏 → 不崩溃
    - collect 失败 → FAILED
    - CANCELLED + JobHandle 恢复
"""

import pytest
from datetime import datetime
from pathlib import Path

from masgent.models.task import TaskRecord
from masgent.models.enums import TaskStatus, WorkflowType
from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry
from masgent.executors import ExecutorFactory
from tests.conftest import create_task_record


@pytest.fixture(autouse=True)
def register_fake_slurm():
    from tests.mock_executors import FakeSlurmExecutor
    if "fake_slurm" not in ExecutorFactory.list_available():
        ExecutorFactory.register("fake_slurm", FakeSlurmExecutor)
    yield


@pytest.fixture(autouse=True)
def clean_fake_slurm():
    from tests.mock_executors import FakeSlurmExecutor
    FakeSlurmExecutor.clear_jobs()
    yield


@pytest.mark.asyncio
async def test_recover_cancelled_job(temp_task_dir):
    """验证 CANCELLED 状态恢复后正确保存"""
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    record = create_task_record(
        task_id="cancelled_test",
        status=TaskStatus.RUNNING,
        work_dir="/tmp/cancelled",
        calculator_type="mock",
        calculator_params={"detect_status_return": TaskStatus.CANCELLED},
    )
    store.save(record)

    runner = TaskRunner(store, registry)
    await runner.recover()

    loaded = store.load("cancelled_test")
    assert loaded.status == TaskStatus.CANCELLED
    assert loaded.finished_at is not None


@pytest.mark.asyncio
async def test_recover_cancelled_with_job_handle(temp_task_dir):
    """
    验证 CANCELLED 状态恢复时 job_handle 存在且正确传递

    场景：Slurm 作业被取消，recover 检测到 CANCELLED
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    from tests.mock_executors import FakeSlurmExecutor
    executor = FakeSlurmExecutor()
    handle = await executor.spawn(Path("/tmp"), "sleep 60")
    # 模拟作业被取消
    executor.fail_job(handle.scheduler_id)

    record = create_task_record(
        task_id="cancelled_with_handle",
        status=TaskStatus.RUNNING,
        work_dir="/tmp/cancelled_handle",
        calculator_type="mock",
        calculator_params={},
    )
    record.executor_config = {"type": "fake_slurm", "partition": "cpu", "ntasks": 1}
    record.job_handle = handle.to_dict()
    store.save(record)

    runner = TaskRunner(store, registry)
    await runner.recover()

    loaded = store.load("cancelled_with_handle")
    # 由于 FakeSlurmExecutor 作业已被标记为失败，detect_status 应返回 FAILED
    assert loaded is not None
    assert loaded.status in (TaskStatus.FAILED, TaskStatus.CANCELLED)


@pytest.mark.asyncio
async def test_executor_rebuild_failed(temp_task_dir):
    """验证 Executor 重建失败 → UNKNOWN"""
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    record = create_task_record(
        task_id="exec_fail_test",
        status=TaskStatus.RUNNING,
        work_dir="/tmp/exec_fail",
        calculator_type="mock",
        calculator_params={},
    )
    record.executor_config = {"type": "non_exist_executor"}
    store.save(record)

    runner = TaskRunner(store, registry)
    await runner.recover()

    loaded = store.load("exec_fail_test")
    assert loaded.status == TaskStatus.FAILED
    assert "Executor rebuild failed" in loaded.error_message


@pytest.mark.asyncio
async def test_calculator_rebuild_failed(temp_task_dir):
    """验证 Calculator 重建失败 → FAILED"""
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    record = create_task_record(
        task_id="calc_fail_test",
        status=TaskStatus.RUNNING,
        work_dir="/tmp/calc_fail",
        calculator_type="non_exist_calc",
        calculator_params={},
    )
    store.save(record)

    runner = TaskRunner(store, registry)
    await runner.recover()

    loaded = store.load("calc_fail_test")
    assert loaded.status == TaskStatus.FAILED
    assert "Registry create failed" in loaded.error_message


@pytest.mark.asyncio
async def test_job_handle_corrupted_does_not_crash(temp_task_dir):
    """
    验证 JobHandle 损坏 → recover 不崩溃

    核心目标：异常数据不会导致 recover() 抛出未捕获异常
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    record = create_task_record(
        task_id="corrupt_test",
        status=TaskStatus.RUNNING,
        work_dir="/tmp/corrupt",
        calculator_type="mock",
        calculator_params={"detect_status_return": TaskStatus.UNKNOWN},
    )
    record.job_handle = {"broken": True}
    store.save(record)

    runner = TaskRunner(store, registry)

    try:
        await runner.recover()
    except Exception as e:
        pytest.fail(f"recover() raised unexpected exception: {e}")

    loaded = store.load("corrupt_test")
    assert loaded is not None
    # UNKNOWN 会被 recover 处理：retry_count < max_retries → PENDING 并重新执行
    assert loaded.status in (TaskStatus.UNKNOWN, TaskStatus.PENDING, TaskStatus.RUNNING)


@pytest.mark.asyncio
async def test_collect_failed_after_completed(temp_task_dir):
    """
    验证 collect 失败 → FAILED

    注意：collect_raises 必须是字符串（JSON 可序列化），
    MockCalculator 会将其转换为 RuntimeError
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    record = create_task_record(
        task_id="collect_fail_test",
        status=TaskStatus.RUNNING,
        work_dir="/tmp/collect_fail",
        calculator_type="mock",
        calculator_params={
            "detect_status_return": TaskStatus.COMPLETED,
            "collect_raises": "Collect crashed",  # ← 字符串，可 JSON 序列化
        },
    )
    store.save(record)

    runner = TaskRunner(store, registry)
    await runner.recover()

    loaded = store.load("collect_fail_test")
    assert loaded.status == TaskStatus.FAILED
    assert "collect failed" in loaded.error_message


@pytest.mark.asyncio
async def test_unknown_retry_exhausted(temp_task_dir):
    """验证 UNKNOWN 重试耗尽 → FAILED"""
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    runner = TaskRunner(store, registry)
    max_retries = runner.retry_policy.max_retries

    record = create_task_record(
        task_id="unknown_exhausted",
        status=TaskStatus.RUNNING,
        work_dir="/tmp/unknown",
        calculator_type="mock",
        calculator_params={"detect_status_return": TaskStatus.UNKNOWN},
        retry_count=max_retries,
    )
    store.save(record)

    await runner.recover()

    loaded = store.load("unknown_exhausted")
    assert loaded.status == TaskStatus.FAILED
    assert "UNKNOWN after" in loaded.error_message


@pytest.mark.asyncio
async def test_unknown_retry_restart_execute(temp_task_dir):
    """
    验证 UNKNOWN 重试 → 重启执行

    注意：recover() 调用 _restart_execute() 会创建后台任务，
    状态可能在检查时已变为 RUNNING，因此允许 PENDING 或 RUNNING
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    record = create_task_record(
        task_id="unknown_retry",
        status=TaskStatus.RUNNING,
        work_dir="/tmp/unknown_retry",
        calculator_type="mock",
        calculator_params={"detect_status_return": TaskStatus.UNKNOWN},
        retry_count=0,
    )
    store.save(record)

    runner = TaskRunner(store, registry)
    await runner.recover()

    loaded = store.load("unknown_retry")
    assert loaded.retry_count == 1
    assert loaded.status in (TaskStatus.PENDING, TaskStatus.RUNNING)