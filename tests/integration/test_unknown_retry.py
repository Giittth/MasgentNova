"""测试 UNKNOWN 状态的重试机制（直接构造 UNKNOWN 任务）"""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime

from masgent.calculators.base import Calculator
from masgent.models.calculator import CalculationResult
from masgent.models.enums import TaskStatus, WorkflowType
from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry
from masgent.utils.workdir_manager import WorkDirManager
from masgent.models.task import TaskRecord
from tests.mock_calculator import MockCalculator
from tests.conftest import wait_until, create_task_record


class UnknownThenCompletedCalculator(Calculator):
    """
    模拟 Calculator：
        - 第一次 detect_status 返回 UNKNOWN
        - 之后返回 COMPLETED
    使用文件记录调用次数，避免恢复后计数器重置
    """
    TYPE = "unknown_test"

    def __init__(self, executor=None, workdir_manager=None, **kwargs):
        self.executor = executor
        self.workdir_manager = workdir_manager or WorkDirManager()

    async def prepare(self, structure, workflow_type, **kwargs):
        return self.workdir_manager.create(structure, workflow_type)

    async def launch(self, work_dir):
        return None

    async def detect_status(self, work_dir, job=None):
        counter_file = Path(work_dir) / ".detect_count"
        count = 0
        if counter_file.exists():
            count = int(counter_file.read_text())
        count += 1
        counter_file.write_text(str(count))
        if count == 1:
            return TaskStatus.UNKNOWN
        return TaskStatus.COMPLETED

    async def collect(self, work_dir, workflow_type):
        return CalculationResult(
            success=True,
            workflow_type=workflow_type,
            data={"energy": -10.5, "work_dir": str(work_dir)},
            metadata={"calculator": "unknown_test"},
        )

    async def cancel(self, job):
        return True

    def get_init_params(self):
        return {}


@pytest.fixture
def register_unknown_test_calculator():
    """注册测试专用的 Calculator（非 autouse，避免污染其他测试）"""
    from masgent.calculators.registry import CalculatorRegistry
    if not CalculatorRegistry._factories.get("unknown_test"):
        CalculatorRegistry.register("unknown_test", UnknownThenCompletedCalculator)
    yield


@pytest.mark.asyncio
async def test_unknown_retry_and_resume(
    task_runner,
    register_unknown_test_calculator,
    temp_task_dir,
):
    """
    直接构造 UNKNOWN 任务记录，验证重试后完成

    流程：
        1. 创建 UNKNOWN 状态的任务记录（retry_count=0）
        2. recover 检测到 UNKNOWN
        3. retry_count=1，状态变为 PENDING，重新执行
        4. 第二次 detect_status 返回 COMPLETED
        5. 验证状态为 COMPLETED，retry_count=1，结果存在
    """
    store = task_runner.task_store

    # 确保工作目录存在
    work_dir = temp_task_dir / "unknown_retry"
    work_dir.mkdir(parents=True, exist_ok=True)

    record = create_task_record(
        task_id="unknown_retry_task",
        status=TaskStatus.RUNNING,  # 初始状态 RUNNING，recover 会调用 detect_status
        work_dir=str(work_dir),
        calculator_type="unknown_test",
        calculator_params={},
        retry_count=0,
    )
    store.save(record)

    await task_runner.recover()

    # 等待重试机制生效，最终变为 COMPLETED
    await wait_until(
        lambda: store.load("unknown_retry_task").status == TaskStatus.COMPLETED,
        timeout=5.0,
    )

    record = store.load("unknown_retry_task")
    assert record.status == TaskStatus.COMPLETED
    assert record.retry_count == 1  # 重试了一次
    assert record.result is not None
    assert "energy" in record.result["data"]
    assert record.result["data"]["energy"] == -10.5