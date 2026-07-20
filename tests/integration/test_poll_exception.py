"""
异常轮询恢复测试

验证当恢复后的轮询过程中 is_running 抛出异常时，
任务被正确标记为 FAILED。
"""

import pytest
import asyncio

from pymatgen.core import Structure, Lattice

from masgent.models.enums import TaskStatus, WorkflowType
from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry
from masgent.executors import ExecutorFactory
from tests.conftest import wait_until
from tests.mock_executors import FailingPollExecutor
from tests.mock_calculator import MockCalculator


@pytest.fixture(autouse=True)
def register_failing_executor():
    """注册 FailingPollExecutor 到 ExecutorFactory，供 recover 重建"""
    if "failing_slurm" not in ExecutorFactory.list_available():
        ExecutorFactory.register("failing_slurm", FailingPollExecutor)
    yield


@pytest.mark.asyncio
async def test_recovered_task_poll_executor_failure(temp_task_dir):
    """
    场景：恢复后的轮询中，is_running 在第一次轮询时抛出异常
    预期：任务被标记为 FAILED，并记录错误信息

    使用 fail_after=2，因为：
        - 第1次调用：submit 阶段 detect_status
        - 第2次调用：recover 阶段 detect_status
        - 第3次调用：恢复后的 _poll_loop 第一次轮询 → 触发异常
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    executor = FailingPollExecutor(fail_after=2, partition="cpu")
    calc = MockCalculator(
        executor=executor,
        detect_status_return=TaskStatus.RUNNING,
    )

    runner1 = TaskRunner(store, registry)
    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])
    info = await runner1.submit(calc, structure, WorkflowType.SINGLE_POINT)

    await wait_until(
        lambda: store.load(info.task_id) is not None and store.load(info.task_id).status == TaskStatus.RUNNING,
        timeout=10.0
    )

    runner1._running_tasks.clear()
    runner1._executors.clear()
    await asyncio.sleep(0.1)
    del runner1

    runner2 = TaskRunner(store, registry)
    await runner2.recover()

    executor2 = runner2._executors.get(info.task_id)
    assert executor2 is not None
    assert isinstance(executor2, FailingPollExecutor)

    await wait_until(
        lambda: store.load(info.task_id).status == TaskStatus.FAILED,
        timeout=5.0,
        interval=0.2
    )

    record = store.load(info.task_id)
    assert "Slurm unavailable" in record.error_message

    await runner2.shutdown()