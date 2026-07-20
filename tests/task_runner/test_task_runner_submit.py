"""
TaskRunner.submit() 核心流程测试

测试内容：
    - 提交任务是否创建记录
    - 正常执行流程（PENDING → RUNNING → COMPLETED）
    - launch 失败处理
    - detect_status 失败处理
    - collect 异常处理
    - poll 和 collect 接口
"""

import pytest
from pymatgen.core import Structure, Lattice

from masgent.models.enums import TaskStatus, WorkflowType
from masgent.models.calculator import CalculationResult
from tests.mock_calculator import MockCalculator
from tests.conftest import wait_until


# 标记所有测试为异步
pytestmark = pytest.mark.asyncio


class TestTaskRunnerSubmit:
    @pytest.fixture
    def si_structure(self):
        return Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])

    async def test_submit_creates_record(self, task_runner, mock_calc, si_structure):
        """提交任务应创建 TaskRecord 并存储"""
        mock_calc.detect_status_return = TaskStatus.RUNNING  # 新增
        info = await task_runner.submit(
            mock_calc,
            si_structure,
            WorkflowType.SINGLE_POINT,
            fmax=0.1,
        )

        assert info.task_id is not None
        assert info.status in (TaskStatus.PENDING, TaskStatus.RUNNING)

        record = task_runner.task_store.load(info.task_id)
        assert record is not None
        assert record.task_id == info.task_id
        assert record.calculator_type == "mock"
        assert record.workflow_params.get("fmax") == 0.1
        assert record.status in (TaskStatus.PENDING, TaskStatus.RUNNING)

    async def test_submit_completes_normally(self, task_runner, mock_calc, si_structure):
        """正常执行：PENDING → RUNNING → COMPLETED，结果被保存"""
        mock_calc.detect_status_return = TaskStatus.COMPLETED
        mock_calc.collect_return = CalculationResult(
            success=True,
            workflow_type=WorkflowType.SINGLE_POINT,
            data={"energy": -10.5},
            metadata={"method": "mock"},
        )

        info = await task_runner.submit(
            mock_calc,
            si_structure,
            WorkflowType.SINGLE_POINT,
        )

        # 等待完成（最多 5 秒）
        await wait_until(
            lambda: task_runner.task_store.load(info.task_id).status == TaskStatus.COMPLETED
        )

        record = task_runner.task_store.load(info.task_id)
        assert record.status == TaskStatus.COMPLETED
        assert record.result is not None
        assert record.result["data"]["energy"] == -10.5
        assert record.result["metadata"]["method"] == "mock"

        # 验证所有必要方法被调用
        assert mock_calc.prepare_called
        assert mock_calc.launch_called
        assert mock_calc.detect_status_called
        assert mock_calc.collect_called

    async def test_submit_handles_launch_failure(self, task_runner, mock_calc, si_structure):
        """launch 抛出异常 → 任务 FAILED"""
        mock_calc.launch_raises = RuntimeError("Launch failed")

        info = await task_runner.submit(
            mock_calc,
            si_structure,
            WorkflowType.SINGLE_POINT,
        )

        await wait_until(
            lambda: task_runner.task_store.load(info.task_id).status == TaskStatus.FAILED
        )

        record = task_runner.task_store.load(info.task_id)
        assert record.status == TaskStatus.FAILED
        assert "Launch failed" in record.error_message

    async def test_submit_handles_detect_status_failure(self, task_runner, mock_calc, si_structure):
        """detect_status 返回 FAILED → 任务 FAILED"""
        mock_calc.detect_status_return = TaskStatus.FAILED

        info = await task_runner.submit(
            mock_calc,
            si_structure,
            WorkflowType.SINGLE_POINT,
        )

        await wait_until(
            lambda: task_runner.task_store.load(info.task_id).status == TaskStatus.FAILED
        )

        record = task_runner.task_store.load(info.task_id)
        assert record.status == TaskStatus.FAILED
        assert "Task ended with status failed" in record.error_message

    async def test_submit_handles_collect_exception(self, task_runner, mock_calc, si_structure):
        """collect 抛出异常 → 任务 FAILED"""
        mock_calc.detect_status_return = TaskStatus.COMPLETED
        mock_calc.collect_raises = RuntimeError("Collect crashed")

        info = await task_runner.submit(
            mock_calc,
            si_structure,
            WorkflowType.SINGLE_POINT,
        )

        await wait_until(
            lambda: task_runner.task_store.load(info.task_id).status == TaskStatus.FAILED
        )

        record = task_runner.task_store.load(info.task_id)
        assert record.status == TaskStatus.FAILED
        assert "Collect crashed" in record.error_message

    async def test_poll_returns_status(self, task_runner, mock_calc, si_structure):
        """poll 应返回存储中的状态"""
        mock_calc.detect_status_return = TaskStatus.RUNNING
        info = await task_runner.submit(mock_calc, si_structure, WorkflowType.SINGLE_POINT)
        status = await task_runner.poll(info.task_id)
        assert status in (TaskStatus.PENDING, TaskStatus.RUNNING)
        mock_calc.detect_status_return = TaskStatus.COMPLETED
        await wait_until(lambda: task_runner.task_store.load(info.task_id).status == TaskStatus.COMPLETED)

    async def test_collect_returns_result(self, task_runner, mock_calc, si_structure):
        """collect 应返回保存的结果"""
        mock_calc.detect_status_return = TaskStatus.COMPLETED
        mock_calc.collect_return = CalculationResult(
            success=True,
            workflow_type=WorkflowType.SINGLE_POINT,
            data={"energy": -9.8},
        )

        info = await task_runner.submit(
            mock_calc,
            si_structure,
            WorkflowType.SINGLE_POINT,
        )

        await wait_until(
            lambda: task_runner.task_store.load(info.task_id).status == TaskStatus.COMPLETED
        )

        result = await task_runner.collect(info.task_id)
        assert result is not None
        assert result["data"]["energy"] == -9.8