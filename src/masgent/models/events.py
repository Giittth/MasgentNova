"""事件模型定义，用于审计和可观测性"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from masgent.models.enums import TaskStatus
from masgent.models.error_codes import RecoveryError


@dataclass
class RecoveryEvent:
    """
    恢复事件记录，用于追踪 TaskRunner.recover() 的执行过程
    所有错误必须使用结构化 RecoveryError，不再允许自由字符串。
    """
    task_id: str
    old_status: TaskStatus
    action: str
    retry_count: int
    error: Optional[RecoveryError] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """序列化为字典（用于 JSON 日志）"""
        result = {
            "task_id": self.task_id,
            "old_status": self.old_status.value,
            "action": self.action,
            "retry_count": self.retry_count,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.error:
            result["error"] = self.error.to_dict()
        return result

    def has_error(self) -> bool:
        return self.error is not None

    def error_code(self) -> Optional[str]:
        return self.error.code.value if self.error else None

    def error_category(self) -> Optional[str]:
        return self.error.category.value if self.error else None