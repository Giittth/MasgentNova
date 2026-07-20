"""RecoveryEvent 单元测试"""

import pytest
from datetime import datetime

from masgent.models.events import RecoveryEvent
from masgent.models.enums import TaskStatus
from masgent.models.error_codes import RecoveryError, ErrorCode, ErrorCategory, ErrorSource


def test_recovery_event_to_dict():
    """验证 RecoveryEvent.to_dict() 正确序列化"""
    event = RecoveryEvent(
        task_id="task_1",
        old_status=TaskStatus.UNKNOWN,
        action="retry",
        retry_count=1,
    )
    data = event.to_dict()
    assert data["task_id"] == "task_1"
    assert data["old_status"] == TaskStatus.UNKNOWN.value
    assert data["action"] == "retry"
    assert data["retry_count"] == 1
    assert data.get("error") is None
    assert "timestamp" in data


def test_recovery_event_with_error():
    """验证带 error 的 RecoveryEvent 序列化"""
    error = RecoveryError(
        code=ErrorCode.UNKNOWN_ERROR,
        category=ErrorCategory.INFRA,
        source=ErrorSource.UNKNOWN,
        detail="test error",
    )
    event = RecoveryEvent(
        task_id="task_1",
        old_status=TaskStatus.UNKNOWN,
        action="retry",
        retry_count=1,
        error=error,
    )
    data = event.to_dict()
    assert data["task_id"] == "task_1"
    assert data["action"] == "retry"
    assert data["error"]["code"] == "unknown_error"
    assert data["error"]["detail"] == "test error"


def test_recovery_event_timestamp_auto():
    """测试 timestamp 自动生成"""
    event = RecoveryEvent(
        task_id="task_3",
        old_status=TaskStatus.PENDING,
        action="restart_execute",
        retry_count=0,
    )
    assert event.timestamp is not None
    # 可以验证是最近的时间
    now = datetime.now()
    delta = now - event.timestamp
    assert delta.total_seconds() < 1.0