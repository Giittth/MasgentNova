"""
TaskRunner.recover() 各种场景测试

测试内容：
    - 恢复已完成任务（COMPLETED）：自动 collect 并保存结果
    - 恢复运行任务（RUNNING）：重新启动 poll_loop
    - 恢复待处理任务（PENDING）：重新启动 execute
    - 恢复未知状态（UNKNOWN）：重试机制，超过阈值标记 FAILED
    - 终态任务（FAILED/CANCELLED）被忽略
"""

import pytest
import asyncio
from datetime import datetime

from masgent.models.enums import TaskStatus, WorkflowType
from masgent.models.job import JobHandle
from masgent.models.calculator import CalculationResult
from tests.mock_calculator import MockCalculator, BlockingCalculator, UnknownCalculator
from tests.conftest import wait_until, create_task_record

pytestmark = pytest.mark.asyncio


class TestTaskRunnerRecover:
    @pytest.fixture
    def task_runner(self, temp_task_dir):
        from masgent.tasks.task_runner import TaskRunner
        from masgent.tasks.task_store import JSONTaskStore
        from masgent.calculators.registry import CalculatorRegistry
        store = JSONTaskStore(temp_task_dir)
        registry = CalculatorRegistry()
        return TaskRunner(store, registry)

    async def test_recover_completed_task(self, task_runner):
        """恢复已完成的任务 → 自动 collect 并保存结果"""
        # 创建一个处于 RUNNING 的记录，但实际检测会返回 COMPLETED
        store = task_runner.task_store
        record = create_task_record(
            task_id="completed_task",
            status=TaskStatus.RUNNING,
            work_dir="/tmp/complete_work",
            calculator_type="completed",  # 使用注册的类型
            calculator_params={},
        )
        store.save(record)
        await task_runner.recover()
        # 等待任务完成（因为 detect_status 返回 COMPLETED，会立即 collect）
        await asyncio.sleep(0.1)
        record = store.load("completed_task")
        assert record.status == TaskStatus.COMPLETED

    async def test_recover_running_task_restarts_poll(self, task_runner):
        """恢复运行中的任务 → 重新启动 poll_loop"""
        # 创建一个 RUNNING 记录，并包含 job_handle
        store = task_runner.task_store
        record = create_task_record(
            task_id="running_task",
            status=TaskStatus.RUNNING,
            work_dir="/tmp/running_work",
            calculator_type="running_mock",  # 专用类型，返回 RUNNING
            calculator_params={},
        )
        store.save(record)

        await task_runner.recover()
        await asyncio.sleep(0.1)  # 给事件循环调度时间

        assert "running_task" in task_runner._running_tasks
        record = store.load("running_task")
        assert record.status == TaskStatus.RUNNING

    async def test_recover_pending_task_restarts_execute(self, task_runner):
        """恢复 PENDING 任务 → 重新启动 execute"""
        store = task_runner.task_store
        record = create_task_record(
            task_id="pending_task",
            status=TaskStatus.PENDING,
            work_dir="/tmp/pending_work",
            calculator_type="pending_mock",  # 返回 PENDING，触发 _restart_execute
            calculator_params={},
        )
        store.save(record)

        await task_runner.recover()
        await asyncio.sleep(0.1)

        assert "pending_task" in task_runner._running_tasks
        record = store.load("pending_task")
        # _execute 会立即将状态设为 RUNNING，所以可能是 PENDING 或 RUNNING
        assert record.status in (TaskStatus.PENDING, TaskStatus.RUNNING)

    async def test_recover_unknown_retry_mechanism(self, task_runner):
        """
        UNKNOWN 恢复重试机制（v0.6.1-rc）

        行为：
            - 第一次 recover：UNKNOWN → retry_count=1 → PENDING → 重新执行
            - 任务被重新调度，状态变为 PENDING 或 RUNNING
        """
        store = task_runner.task_store
        record = create_task_record(
            task_id="unknown_task",
            status=TaskStatus.RUNNING,
            work_dir="/tmp/unknown_work",
            calculator_type="unknown",  # UnknownCalculator
            calculator_params={},
            retry_count=0,
        )
        store.save(record)

        await task_runner.recover()
        await asyncio.sleep(0.1)

        record = store.load("unknown_task")
        # 由于竞态，状态可能是 PENDING 或 RUNNING，且 retry_count 应增加
        assert record.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
        assert record.retry_count == 1

    async def test_recover_unknown_exceed_retry_limit(self, task_runner):
        """
        测试 UNKNOWN 达到重试上限后标记为 FAILED

        场景：
            - retry_count=2
            - recover 触发 retry_count=3
            - 达到上限 → 标记 FAILED
        """
        from masgent.calculators.registry import CalculatorRegistry
        if not CalculatorRegistry._factories.get("unknown"):
            from tests.mock_calculator import UnknownCalculator
            CalculatorRegistry.register("unknown", UnknownCalculator)

        record = create_task_record(
            "unknown_failed_task",
            TaskStatus.UNKNOWN,
            work_dir="/tmp/unknown_failed",
            calculator_type="unknown",
            retry_count=2,
        )
        task_runner.task_store.save(record)

        await task_runner.recover()

        record = task_runner.task_store.load("unknown_failed_task")
        assert record.retry_count == 3
        assert record.status == TaskStatus.FAILED
        assert "UNKNOWN after 3 retries" in record.error_message

    async def test_recover_failed_task_ignored(self, task_runner):
        """FAILED 任务被忽略，不重新执行"""
        record = create_task_record(
            "failed_task",
            TaskStatus.FAILED,
        )
        task_runner.task_store.save(record)

        await task_runner.recover()

        # 状态不应改变，且不在 _running_tasks 中
        record = task_runner.task_store.load("failed_task")
        assert record.status == TaskStatus.FAILED
        assert "failed_task" not in task_runner._running_tasks

    async def test_recover_cancelled_task_ignored(self, task_runner):
        """CANCELLED 任务被忽略"""
        record = create_task_record(
            "cancelled_task",
            TaskStatus.CANCELLED,
        )
        task_runner.task_store.save(record)

        await task_runner.recover()

        record = task_runner.task_store.load("cancelled_task")
        assert record.status == TaskStatus.CANCELLED
        assert "cancelled_task" not in task_runner._running_tasks

    async def test_recover_with_corrupted_calculator_params(self, task_runner):
        """calculator_params 损坏时，任务应标记 FAILED"""
        record = create_task_record(
            "bad_calc_task",
            TaskStatus.PENDING,
            calculator_type="mock",
            calculator_params={"invalid": "params"},  # 实际 MockCalculator 不需要参数，但如果有参数不匹配，会报错
        )
        # 但 MockCalculator 接受任意 kwargs，所以不会报错。为了模拟失败，我们使用一个不存在的 calculator_type
        record.calculator_type = "nonexistent"
        task_runner.task_store.save(record)

        await task_runner.recover()

        record = task_runner.task_store.load("bad_calc_task")
        assert record.status == TaskStatus.FAILED
        assert "Registry create failed" in record.error_message