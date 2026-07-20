"""
进程级崩溃恢复测试
"""

import pytest
import asyncio
from pathlib import Path
import sys

from pymatgen.core import Structure, Lattice

from masgent.models.task import TaskRecord
from masgent.models.enums import TaskStatus, WorkflowType
from masgent.models.calculator import CalculationResult
from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry
from masgent.executors import ExecutorFactory
from tests.conftest import create_task_record, wait_until
from tests.mock_executors import FakeSlurmExecutor
from tests.mock_calculator import MockCalculator


@pytest.fixture(autouse=True)
def register_fake_slurm():
    if "fake_slurm" not in ExecutorFactory.list_available():
        ExecutorFactory.register("fake_slurm", FakeSlurmExecutor)
    yield


@pytest.fixture
def clean_fake_slurm_after():
    yield
    FakeSlurmExecutor.clear_jobs()


@pytest.mark.asyncio
async def test_process_restart_running_task(temp_task_dir, clean_fake_slurm_after):
    """
    场景1：RUNNING 任务 → 进程崩溃 → recover → 继续执行
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    executor = FakeSlurmExecutor(partition="cpu", ntasks=1)
    calc = MockCalculator(
        executor=executor,
        detect_status_return=TaskStatus.RUNNING,
    )

    runner1 = TaskRunner(store, registry)
    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])
    info = await runner1.submit(calc, structure, WorkflowType.SINGLE_POINT)

    await wait_until(
        lambda: (
            store.load(info.task_id) is not None
            and store.load(info.task_id).job_handle is not None
            and store.load(info.task_id).status == TaskStatus.RUNNING
        ),
        timeout=10.0
    )
    
    # 从 store 中获取实际的 scheduler_id
    record = store.load(info.task_id)
    print("BEFORE CRASH")
    print("status =", record.status)
    print("job_handle =", record.job_handle)
    print("executor_config =", record.executor_config)
    sys.stdout.flush()
    assert record.executor_config is not None

    # 模拟进程崩溃：清空内存状态，但不要调用 cancel()
    runner1._running_tasks.clear()
    runner1._executors.clear()
    await asyncio.sleep(0.1)
    del runner1

    runner2 = TaskRunner(store, registry)
    await runner2.recover()

    # 等待后台任务启动
    await asyncio.sleep(0.1)

    # 验证 _running_tasks 包含恢复的任务
    print(f"DEBUG: _running_tasks = {runner2._running_tasks}")
    sys.stdout.flush()
    assert info.task_id in runner2._running_tasks

    # 主动让作业完成，以便 _poll_loop 退出

    scheduler_id = record.job_handle["scheduler_id"]  # 或 record.job_handle.scheduler_id（取决于 dict 还是对象）
    executor = runner2._executors[info.task_id]
    executor.complete_job(scheduler_id)

    # 等待任务完成
    await wait_until(
        lambda: store.load(info.task_id).status == TaskStatus.COMPLETED,
        timeout=30.0
    )

    result = await runner2.collect(info.task_id)
    assert result is not None
    assert "energy" in result["data"]


@pytest.mark.asyncio
async def test_process_restart_collect_completed(temp_task_dir, clean_fake_slurm_after):
    """
    场景2：底层作业已完成但 TaskRunner 未收集 → recover → 自动 collect
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    executor = FakeSlurmExecutor()
    calc = MockCalculator(
        executor=executor,
        detect_status_return=TaskStatus.COMPLETED,
    )

    runner1 = TaskRunner(store, registry)
    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])
    info = await runner1.submit(calc, structure, WorkflowType.SINGLE_POINT)

    await wait_until(
        lambda: (
            store.load(info.task_id) is not None
            and store.load(info.task_id).job_handle is not None
            and store.load(info.task_id).status == TaskStatus.RUNNING
        ),
        timeout=10.0
    )

    record = store.load(info.task_id)
    scheduler_id = record.job_handle["scheduler_id"]
    executor.complete_job(scheduler_id)

    # 模拟进程崩溃：不调用 cancel()
    runner1._running_tasks.clear()
    runner1._executors.clear()
    await asyncio.sleep(0.1)
    del runner1

    runner2 = TaskRunner(store, registry)
    await runner2.recover()

    # 给事件循环时间处理
    await asyncio.sleep(0.1)

    record = store.load(info.task_id)
    assert record.status == TaskStatus.COMPLETED
    assert record.result is not None
    assert "energy" in record.result["data"]


@pytest.mark.asyncio
async def test_process_restart_executor_state_lost(temp_task_dir, clean_fake_slurm_after):
    """
    场景3：Executor 状态丢失 → recover → 重建 executor
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    config = {"type": "fake_slurm", "partition": "cpu", "ntasks": 1}
    record = create_task_record(
        task_id="exec_rebuild_test",
        status=TaskStatus.RUNNING,
        work_dir="/tmp/exec_rebuild",
        calculator_type="mock",
        calculator_params={"detect_status_return": TaskStatus.RUNNING},
    )
    record.executor_config = config
    store.save(record)

    runner1 = TaskRunner(store, registry)
    runner1._executors = {}

    await runner1.recover()

    assert "exec_rebuild_test" in runner1._executors
    executor = runner1._executors["exec_rebuild_test"]
    assert isinstance(executor, FakeSlurmExecutor)
    assert executor.partition == "cpu"
    assert executor.ntasks == 1


@pytest.mark.asyncio
async def test_process_restart_multiple_tasks(temp_task_dir, clean_fake_slurm_after):
    """
    场景4：多任务混合恢复
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    executor = FakeSlurmExecutor()

    calc_a = MockCalculator(
        executor=executor,
        detect_status_return=TaskStatus.RUNNING,
    )
    runner1 = TaskRunner(store, registry)
    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])
    info_a = await runner1.submit(calc_a, structure, WorkflowType.SINGLE_POINT)

    await wait_until(
        lambda: store.load(info_a.task_id).status == TaskStatus.RUNNING,
        timeout=10.0
    )

    record_b = create_task_record(
        task_id="task_b",
        status=TaskStatus.RUNNING,
        work_dir="/tmp/task_b",
        calculator_type="mock",
        calculator_params={
            "detect_status_return": TaskStatus.COMPLETED,
        },
    )
    store.save(record_b)

    record_c = create_task_record(
        task_id="task_c",
        status=TaskStatus.RUNNING,
        work_dir="/tmp/task_c",
        calculator_type="mock",
        calculator_params={
            "detect_status_return": TaskStatus.FAILED,
        },
    )
    store.save(record_c)

    # 模拟进程崩溃：不调用 cancel()
    runner1._running_tasks.clear()
    runner1._executors.clear()
    await asyncio.sleep(0.1)
    del runner1

    runner2 = TaskRunner(store, registry)
    await runner2.recover()

    await asyncio.sleep(0.1)

    # 验证 Task A 恢复
    assert info_a.task_id in runner2._running_tasks

    # 验证 Task B 自动 collect
    record_b_loaded = store.load("task_b")
    assert record_b_loaded.status == TaskStatus.COMPLETED
    assert record_b_loaded.result is not None

    # 验证 Task C 标记 FAILED
    record_c_loaded = store.load("task_c")
    assert record_c_loaded.status == TaskStatus.FAILED

    # 清理：取消 Task A
    executor_a = runner2._executors[info_a.task_id]
    executor_a.complete_job("1000")  # 完成作业，让 poll loop 退出
    await wait_until(
        lambda: store.load(info_a.task_id).status == TaskStatus.COMPLETED,
        timeout=30.0
    )
    await runner2.cancel(info_a.task_id)