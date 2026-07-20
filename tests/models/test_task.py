# tests/models/test_task.py
"""TaskRecord 数据模型测试"""

import pytest
from datetime import datetime

from masgent.models.task import TaskRecord
from masgent.models.enums import TaskStatus, WorkflowType


class TestTaskRecord:
    def test_status_enum_roundtrip(self):
        """验证 TaskRecord 序列化/反序列化后 status 保持为枚举"""
        record = TaskRecord(
            task_id="test_enum",
            workflow_type=WorkflowType.SINGLE_POINT,
            status=TaskStatus.COMPLETED,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            work_dir="/tmp/test",
            calculator_type="mock",
        )
        data = record.to_dict()
        restored = TaskRecord.from_dict(data)

        # 验证 status 是枚举对象，不是字符串
        assert isinstance(restored.status, TaskStatus)
        assert restored.status == TaskStatus.COMPLETED
        assert restored.status.value == "completed"

        # 验证 workflow_type 也是枚举
        assert isinstance(restored.workflow_type, WorkflowType)
        assert restored.workflow_type == WorkflowType.SINGLE_POINT