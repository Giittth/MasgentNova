"""
Slurm 任务恢复测试（使用 FakeSlurmExecutor，不需要真实 HPC）

覆盖场景：
    1. RUNNING 任务恢复 → 继续轮询
    2. COMPLETED 任务恢复 → 自动收集结果
    3. FAILED 任务恢复 → 标记失败
"""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime

from masgent.models.task import TaskRecord
from masgent.models.enums import TaskStatus, WorkflowType
from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry
from masgent.executors import ExecutorFactory
from tests.conftest import create_task_record
from tests.mock_executors import FakeSlurmExecutor


@pytest.fixture(autouse=True)
def register_fake_slurm():
    """确保 FakeSlurmExecutor 在测试中可用"""
    if "fake_slurm" not in ExecutorFactory.list_available():
        ExecutorFactory.register("fake_slurm", FakeSlurmExecutor)
    yield


@pytest.fixture(autouse=True)
def clean_fake_slurm_jobs():
    """每个测试前清理全局作业状态，避免测试间污染"""
    FakeSlurmExecutor.clear_jobs()
    yield


@pytest.mark.asyncio
async def test_recover_running_slurm_job(temp_task_dir):
    """
    场景1：任务在 Slurm 上 RUNNING，TaskRunner 崩溃后恢复
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    # 1. 提交任务
    executor = FakeSlurmExecutor(partition="cpu", ntasks=1)
    work_dir = Path("/tmp/slurm_test")
    handle = await executor.spawn(work_dir, "sleep 60")

    # 2. 保存 TaskRecord
    record = create_task_record(
        task_id="slurm_running_test",
        status=TaskStatus.RUNNING,
        work_dir=str(work_dir),
        calculator_type="mock",
        calculator_params={
            "detect_status_return": TaskStatus.RUNNING,
        },
    )
    record.executor_config = executor.get_config()
    record.job_handle = handle.to_dict() 
    store.save(record)

    # 3. 模拟重启（新 TaskRunner，新 executor 实例）
    runner = TaskRunner(store, registry)
    await runner.recover()

    # 4. 验证 executor 恢复（应该指向全局 jobs）
    assert "slurm_running_test" in runner._executors
    restored_executor = runner._executors["slurm_running_test"]
    assert isinstance(restored_executor, FakeSlurmExecutor)
    assert restored_executor.partition == "cpu"
    assert restored_executor.ntasks == 1
    # 验证作业仍在全局字典中
    assert handle.scheduler_id in restored_executor.jobs
    assert restored_executor.jobs[handle.scheduler_id]["status"] == "RUNNING"

    # 5. 验证任务已进入 _running_tasks（因为 detect_status 返回 RUNNING）
    assert "slurm_running_test" in runner._running_tasks


@pytest.mark.asyncio
async def test_recover_completed_slurm_job(temp_task_dir):
    """
    场景2：Slurm 作业已完成（COMPLETED），但 TaskRunner 尚未收集结果
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    # 1. 提交并完成
    executor = FakeSlurmExecutor()
    work_dir = Path("/tmp/slurm_done")
    handle = await executor.spawn(work_dir, "echo done")
    executor.complete_job(handle.scheduler_id)

    # 2. 保存 TaskRecord（状态仍为 RUNNING，但作业已完成）
    record = create_task_record(
        task_id="slurm_completed_test",
        status=TaskStatus.RUNNING,
        work_dir=str(work_dir),
        calculator_type="mock",
        calculator_params={},
    )
    record.executor_config = executor.get_config()
    record.job_handle = handle.to_dict()
    store.save(record)

    # 3. 模拟重启
    runner = TaskRunner(store, registry)
    await runner.recover()

    # 4. 验证：状态变为 COMPLETED，结果已保存
    loaded = store.load("slurm_completed_test")
    assert loaded.status == TaskStatus.COMPLETED
    # 结果可能已通过 collect 保存（根据 Calculator 实现）
    # 这里只要状态正确即可


@pytest.mark.asyncio
async def test_recover_failed_slurm_job(temp_task_dir):
    """
    场景3：Slurm 作业失败（FAILED）
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    # 1. 提交并失败
    executor = FakeSlurmExecutor()
    work_dir = Path("/tmp/slurm_fail")
    handle = await executor.spawn(work_dir, "exit 1")
    executor.fail_job(handle.scheduler_id)

    # 2. 保存 TaskRecord
    record = create_task_record(
        task_id="slurm_failed_test",
        status=TaskStatus.RUNNING,
        work_dir=str(work_dir),
        calculator_type="mock",
        calculator_params={},
    )
    record.executor_config = executor.get_config()
    record.job_handle = handle.to_dict()
    store.save(record)

    # 3. 模拟重启
    runner = TaskRunner(store, registry)
    await runner.recover()

    # 4. 验证：状态变为 FAILED
    loaded = store.load("slurm_failed_test")
    assert loaded.status == TaskStatus.FAILED