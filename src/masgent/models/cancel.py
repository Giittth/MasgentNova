"""取消语义模型 —— 追踪取消来源"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class CancelSource(str, Enum):
    """取消来源"""
    USER = "user"          # 用户主动取消 → 写 CANCELLED
    SHUTDOWN = "shutdown"  # 系统关闭 → 不写状态
    INTERNAL = "internal"  # 内部取消 → 不写状态


@dataclass
class CancelInfo:
    """取消信息"""
    source: CancelSource
    timestamp: datetime
    reason: Optional[str] = None

    def to_dict(self) -> dict:
        result = {
            "source": self.source.value,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.reason:
            result["reason"] = self.reason
        return result