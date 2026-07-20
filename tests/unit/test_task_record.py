"""
TaskRecord 状态机测试 —— 验证 VALID_TRANSITIONS

纯单元测试，无异步，无外部依赖。
"""

import pytest
from datetime import datetime

from masgent.models.task import TaskRecord
from masgent.models.enums import TaskStatus, WorkflowType


class TestTaskRecordStatusTransitions:
    """测试所有合法和非法状态转换"""

    @pytest.fixture
    def record(self):
        """创建一个 PENDING 状态的任务记录"""
        return TaskRecord(
            task_id="test_001",
            workflow_type=WorkflowType.SINGLE_POINT,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            work_dir="/tmp/work",
            calculator_type="mock",
        )

    # ---------- PENDING ----------
    def test_pending_to_running(self, record):
        record.set_status(TaskStatus.RUNNING)
        assert record.status == TaskStatus.RUNNING

    def test_pending_to_failed(self, record):
        record.set_status(TaskStatus.FAILED)
        assert record.status == TaskStatus.FAILED

    def test_pending_to_cancelled(self, record):
        record.set_status(TaskStatus.CANCELLED)
        assert record.status == TaskStatus.CANCELLED

    def test_pending_to_unknown(self, record):
        """Phase 4.3 新增：PENDING → UNKNOWN 必须合法（恢复场景）"""
        record.set_status(TaskStatus.UNKNOWN)
        assert record.status == TaskStatus.UNKNOWN

    # ---------- RUNNING ----------
    def test_running_to_completed(self, record):
        record.set_status(TaskStatus.RUNNING)
        record.set_status(TaskStatus.COMPLETED)
        assert record.status == TaskStatus.COMPLETED

    def test_running_to_failed(self, record):
        record.set_status(TaskStatus.RUNNING)
        record.set_status(TaskStatus.FAILED)
        assert record.status == TaskStatus.FAILED

    def test_running_to_cancelled(self, record):
        record.set_status(TaskStatus.RUNNING)
        record.set_status(TaskStatus.CANCELLED)
        assert record.status == TaskStatus.CANCELLED

    def test_running_to_unknown(self, record):
        record.set_status(TaskStatus.RUNNING)
        record.set_status(TaskStatus.UNKNOWN)
        assert record.status == TaskStatus.UNKNOWN

    # ---------- UNKNOWN ----------
    def test_unknown_to_running(self, record):
        record.set_status(TaskStatus.UNKNOWN)
        record.set_status(TaskStatus.RUNNING)
        assert record.status == TaskStatus.RUNNING

    def test_unknown_to_completed(self, record):
        record.set_status(TaskStatus.UNKNOWN)
        record.set_status(TaskStatus.COMPLETED)
        assert record.status == TaskStatus.COMPLETED

    def test_unknown_to_failed(self, record):
        record.set_status(TaskStatus.UNKNOWN)
        record.set_status(TaskStatus.FAILED)
        assert record.status == TaskStatus.FAILED

    # ---------- 终态不可转换 ----------
    def test_completed_cannot_transition(self, record):
        record.set_status(TaskStatus.COMPLETED)
        with pytest.raises(ValueError, match="Invalid transition"):
            record.set_status(TaskStatus.RUNNING)

    def test_failed_cannot_transition(self, record):
        record.set_status(TaskStatus.FAILED)
        with pytest.raises(ValueError, match="Invalid transition"):
            record.set_status(TaskStatus.RUNNING)

    def test_cancelled_cannot_transition(self, record):
        record.set_status(TaskStatus.CANCELLED)
        with pytest.raises(ValueError, match="Invalid transition"):
            record.set_status(TaskStatus.RUNNING)

    # ---------- 终态自动设置 finished_at ----------
    def test_terminal_sets_finished_at(self, record):
        assert record.finished_at is None
        record.set_status(TaskStatus.COMPLETED)
        assert record.finished_at is not None

    def test_failed_sets_finished_at(self, record):
        assert record.finished_at is None
        record.set_status(TaskStatus.FAILED)
        assert record.finished_at is not None

    # ---------- 序列化/反序列化 ----------
    def test_to_dict_from_dict_roundtrip(self, record):
        """验证序列化/反序列化完整保留所有字段"""
        # 先修改一些字段以测试完整性
        record.calculator_params = {"param1": "value1"}
        record.workflow_params = {"fmax": 0.1}
        record.retry_count = 3
        record.fingerprint = "abc123"
        record.result = {"energy": -10.5}
        record.error_message = "Something went wrong"

        data = record.to_dict()
        restored = TaskRecord.from_dict(data)

        # 比较所有字段
        assert restored.task_id == record.task_id
        assert restored.workflow_type == record.workflow_type
        assert restored.status == record.status
        assert restored.created_at == record.created_at
        assert restored.updated_at == record.updated_at
        assert restored.work_dir == record.work_dir
        assert restored.calculator_type == record.calculator_type
        assert restored.calculator_params == record.calculator_params
        assert restored.workflow_params == record.workflow_params
        assert restored.retry_count == record.retry_count
        assert restored.fingerprint == record.fingerprint
        assert restored.result == record.result
        assert restored.error_message == record.error_message
        assert restored.finished_at == record.finished_at