"""
测试 Cancel 语义 —— 三种取消来源行为不同
"""

import pytest
import asyncio
from datetime import datetime

from masgent.models.cancel import CancelSource, CancelInfo
from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry
from masgent.models.enums import TaskStatus, WorkflowType
from masgent.models.task import TaskRecord
from tests.mock_calculator import MockCalculator
from tests.mock_executors import FakeSlurmExecutor


@pytest.fixture(autouse=True)
def register_mock():
    from masgent.calculators.registry import CalculatorRegistry
    if not CalculatorRegistry._factories.get("mock"):
        CalculatorRegistry.register("mock", MockCalculator)
    yield


@pytest.mark.asyncio
async def test_cancel_user_writes_cancelled(temp_task_dir):
    """用户取消 → 写 CANCELLED 状态"""
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry)

    # 创建一个 PENDING 任务
    record = TaskRecord(
        task_id="cancel_user_test",
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.PENDING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir="/tmp/test",
        calculator_type="mock",
        calculator_params={},
        workflow_params={},
        retry_count=0,
    )
    store.save(record)

    # 模拟任务已在运行
    runner._running_tasks["cancel_user_test"] = asyncio.create_task(asyncio.sleep(10))

    # 用户取消
    await runner.cancel("cancel_user_test")

    # 验证状态为 CANCELLED
    record = store.load("cancel_user_test")
    assert record.status == TaskStatus.CANCELLED

    # 验证 CancelInfo 记录
    assert "cancel_user_test" in runner._cancel_info
    info = runner._cancel_info["cancel_user_test"]
    assert info.source == CancelSource.USER

    await runner.shutdown()


@pytest.mark.asyncio
async def test_cancel_shutdown_no_state_change(temp_task_dir):
    """shutdown 取消 → 不写 CANCELLED 状态"""
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry)

    record = TaskRecord(
        task_id="cancel_shutdown_test",
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir="/tmp/test",
        calculator_type="mock",
        calculator_params={},
        workflow_params={},
        retry_count=0,
    )
    store.save(record)

    # 模拟任务运行
    runner._running_tasks["cancel_shutdown_test"] = asyncio.create_task(asyncio.sleep(10))

    # shutdown
    await runner.shutdown(timeout=1.0)

    # 验证状态不是 CANCELLED
    record = store.load("cancel_shutdown_test")
    assert record.status != TaskStatus.CANCELLED

    # 验证 CancelInfo 记录
    assert "cancel_shutdown_test" in runner._cancel_info
    info = runner._cancel_info["cancel_shutdown_test"]
    assert info.source == CancelSource.SHUTDOWN

@pytest.mark.asyncio
async def test_cancel_internal_cleanup(temp_task_dir):
    """INTERNAL 取消 → 不写 CANCELLED 状态，CancelInfo 存在"""
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry)

    task_id = "internal_cancel_test"
    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir="/tmp/test",
        calculator_type="mock",
        calculator_params={},
        workflow_params={},
        retry_count=0,
    )
    store.save(record)

    # 模拟任务运行
    runner._running_tasks[task_id] = asyncio.create_task(asyncio.sleep(10))

    # 模拟 INTERNAL 取消（如 recovery 清理）
    runner._cancel_info[task_id] = CancelInfo(
        source=CancelSource.INTERNAL,
        timestamp=datetime.now(),
        reason="Internal cleanup",
    )
    runner._running_tasks[task_id].cancel()

    # 等待任务被取消
    await asyncio.sleep(0.1)

    # 验证状态不是 CANCELLED
    record = store.load(task_id)
    assert record.status != TaskStatus.CANCELLED

    # 验证 CancelInfo 存在
    assert task_id in runner._cancel_info
    assert runner._cancel_info[task_id].source == CancelSource.INTERNAL

    await runner.shutdown()


@pytest.mark.asyncio
async def test_cancel_semantic_invariant(temp_task_dir):
    """
    Cancel 语义不变性测试：
    - USER → 写 CANCELLED
    - SHUTDOWN → 不写 CANCELLED
    - INTERNAL → 不写 CANCELLED
    - CancelInfo 一致
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry)

    # 创建 3 个任务，分别对应 3 种取消来源
    task_ids = ["user_task", "shutdown_task", "internal_task"]

    for tid in task_ids:
        record = TaskRecord(
            task_id=tid,
            workflow_type=WorkflowType.SINGLE_POINT,
            status=TaskStatus.RUNNING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            work_dir=f"/tmp/{tid}",
            calculator_type="mock",
            calculator_params={},
            workflow_params={},
            retry_count=0,
        )
        store.save(record)
        runner._running_tasks[tid] = asyncio.create_task(asyncio.sleep(10))

    # USER: 用户取消 → 应写 CANCELLED
    await runner.cancel("user_task")
    await asyncio.sleep(0.1)
    record = store.load("user_task")
    assert record.status == TaskStatus.CANCELLED

    # SHUTDOWN: 在 shutdown 中处理
    # 在 shutdown 中会设置 _cancel_info 但不写状态
    await runner.shutdown(timeout=1.0)

    # 验证 shutdown_task 不是 CANCELLED（shutdown 不应该写状态）
    record = store.load("shutdown_task")
    assert record.status != TaskStatus.CANCELLED

    # 验证 internal_task 不是 CANCELLED
    record = store.load("internal_task")
    assert record.status != TaskStatus.CANCELLED

    # 验证 CancelInfo 存在
    assert "user_task" in runner._cancel_info
    assert "shutdown_task" in runner._cancel_info