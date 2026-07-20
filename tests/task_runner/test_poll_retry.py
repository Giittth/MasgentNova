"""
测试 _poll_loop 的异常重试机制

核心场景：
    1. 检测失败后重试成功 → COMPLETED
    2. 检测失败超过重试限制 → FAILED
"""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime

from masgent.models.enums import TaskStatus, WorkflowType
from masgent.models.task import TaskRecord
from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry
from masgent.tasks.retry import RetryPolicy
from tests.conftest import wait_until
from tests.mock_calculator import MockCalculator


class FailThenSuccessCalculator(MockCalculator):
    """
    前 fail_count 次 detect_status 抛出异常，之后返回 COMPLETED
    用于测试重试恢复场景
    """
    TYPE = "fail_then_success"

    def __init__(self, fail_count: int = 1, **kwargs):
        super().__init__(**kwargs)
        self.fail_count = fail_count

    async def detect_status(self, work_dir: Path, job=None):
        counter_file = work_dir / ".detect_count"
        count = 0
        if counter_file.exists():
            count = int(counter_file.read_text())
        count += 1
        counter_file.write_text(str(count))
        if count <= self.fail_count:
            raise RuntimeError(f"Simulated poll error (attempt {count})")
        return TaskStatus.COMPLETED


@pytest.fixture(autouse=True)
def register_fail_then_success():
    from masgent.calculators.registry import CalculatorRegistry
    if not CalculatorRegistry._factories.get("fail_then_success"):
        CalculatorRegistry.register("fail_then_success", FailThenSuccessCalculator)
    yield


@pytest.mark.asyncio
async def test_poll_retry_success_after_failure(temp_task_dir):
    """
    场景：detect_status 前两次异常，第三次成功
    预期：任务最终 COMPLETED，不失败

    使用 max_retries=2 表示允许连续失败2次，第3次仍然尝试
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    retry_policy = RetryPolicy(max_retries=2)

    runner = TaskRunner(store, registry, retry_policy=retry_policy)

    task_id = "poll_retry_test"
    work_dir = temp_task_dir / "poll_retry"
    work_dir.mkdir(parents=True, exist_ok=True)

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="fail_then_success",
        calculator_params={"fail_count": 2},  # 前2次失败，第3次成功
        workflow_params={},
        retry_count=0,
    )
    store.save(record)

    calc_instance = FailThenSuccessCalculator(fail_count=2)
    runner._calculators[task_id] = calc_instance
    await runner._restart_poll(record, calc_instance, work_dir, None)

    await wait_until(
        lambda: store.load(task_id).status == TaskStatus.COMPLETED,
        timeout=10.0,
        interval=0.2
    )

    record = store.load(task_id)
    assert record.status == TaskStatus.COMPLETED
    assert record.result is not None
    assert record.result["data"] is not None

    await runner.shutdown()


@pytest.mark.asyncio
async def test_poll_retry_exhausted(temp_task_dir):
    """
    场景：detect_status 失败次数超过重试限制
    预期：任务 FAILED
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    retry_policy = RetryPolicy(max_retries=2)

    runner = TaskRunner(store, registry, retry_policy=retry_policy)

    task_id = "poll_retry_exhausted"
    work_dir = temp_task_dir / "poll_retry_exhausted"
    work_dir.mkdir(parents=True, exist_ok=True)

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="fail_then_success",
        calculator_params={"fail_count": 3},  # 前3次失败，但 max_retries=2 → 第3次判失败
        workflow_params={},
        retry_count=0,
    )
    store.save(record)

    calc_instance = FailThenSuccessCalculator(fail_count=3)
    runner._calculators[task_id] = calc_instance
    await runner._restart_poll(record, calc_instance, work_dir, None)

    await wait_until(
        lambda: store.load(task_id).status == TaskStatus.FAILED,
        timeout=10.0,
        interval=0.2
    )

    record = store.load(task_id)
    assert record.status == TaskStatus.FAILED
    assert "poll failed" in record.error_message

    await runner.shutdown()