"""
错误码协议 —— Recovery 系统结构化错误定义

所有恢复相关的错误必须使用此协议，禁止使用自由字符串。
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Any


class ErrorCode(str, Enum):
    """错误码枚举 —— 每个错误有唯一标识符"""
    # 锁相关
    LOCK_ACQUIRE_FAILED = "lock_acquire_failed"
    FILE_LOCK_FAILED = "file_lock_failed"
    FILE_LOCK_STALE = "file_lock_stale"
    FILE_LOCK_FORCE_ACQUIRE_FAILED = "file_lock_force_acquire_failed"
    # 恢复相关
    EXECUTOR_REBUILD_FAILED = "executor_rebuild_failed"
    CALCULATOR_REBUILD_FAILED = "calculator_rebuild_failed"
    DETECT_STATUS_FAILED = "detect_status_failed"
    COLLECT_FAILED = "collect_failed"
    RECOVERY_TIMEOUT = "recovery_timeout"
    # 重试相关
    UNKNOWN_RETRY_EXHAUSTED = "unknown_retry_exhausted"
    POLL_ERROR_EXHAUSTED = "poll_error_exhausted"
    # 任务状态相关
    JOB_REPORTED_FAILED = "job_reported_failed"
    JOB_REPORTED_CANCELLED = "job_reported_cancelled"
    # 任务已存在
    TASK_ALREADY_RUNNING = "task_already_running"
    # 未知
    UNKNOWN_ERROR = "unknown_error"


class ErrorCategory(str, Enum):
    """错误分类 —— 决定恢复策略"""
    TRANSIENT = "transient"   # 临时错误，可重试（网络超时、锁竞争）
    PERMANENT = "permanent"   # 永久错误，不可重试，直接 FAILED（配置错误、类型不存在）
    INFRA = "infra"           # 基础设施问题（锁、executor 不可用）


class ErrorSource(str, Enum):
    """错误来源 —— 定位问题归属"""
    RUNNER = "runner"
    RECOVERY = "recovery"
    LOCK = "lock"
    EXECUTOR = "executor"
    CALCULATOR = "calculator"
    TASK_STORE = "task_store"
    UNKNOWN = "unknown"


@dataclass
class RecoveryError:
    """
    结构化恢复错误

    所有 recovery 错误必须使用此结构，禁止使用自由字符串。

    Attributes:
        code: 错误码（唯一标识）
        category: 错误分类（影响恢复策略）
        source: 错误来源（定位问题）
        detail: 人类可读的详细描述（用于日志）
        context: 可选的上下文信息（用于调试）
    """
    code: ErrorCode
    category: ErrorCategory
    source: ErrorSource
    detail: str
    context: Optional[dict] = None

    def to_dict(self) -> dict:
        """序列化为字典（用于 JSON 日志）"""
        result = {
            "code": self.code.value,
            "category": self.category.value,
            "source": self.source.value,
            "detail": self.detail,
        }
        if self.context:
            result["context"] = self.context
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "RecoveryError":
        """从字典反序列化"""
        return cls(
            code=ErrorCode(data["code"]),
            category=ErrorCategory(data["category"]),
            source=ErrorSource(data["source"]),
            detail=data["detail"],
            context=data.get("context"),
        )

    # 工厂方法：常用错误
    @classmethod
    def lock_acquire_failed(cls, detail: str = "Memory recovery lock busy") -> "RecoveryError":
        return cls(
            code=ErrorCode.LOCK_ACQUIRE_FAILED,
            category=ErrorCategory.TRANSIENT,
            source=ErrorSource.LOCK,
            detail=detail,
        )

    @classmethod
    def file_lock_failed(cls, detail: str = "File lock busy") -> "RecoveryError":
        return cls(
            code=ErrorCode.FILE_LOCK_FAILED,
            category=ErrorCategory.TRANSIENT,
            source=ErrorSource.LOCK,
            detail=detail,
        )

    @classmethod
    def executor_rebuild_failed(cls, detail: str) -> "RecoveryError":
        return cls(
            code=ErrorCode.EXECUTOR_REBUILD_FAILED,
            category=ErrorCategory.PERMANENT,
            source=ErrorSource.EXECUTOR,
            detail=detail,
        )

    @classmethod
    def calculator_rebuild_failed(cls, detail: str) -> "RecoveryError":
        return cls(
            code=ErrorCode.CALCULATOR_REBUILD_FAILED,
            category=ErrorCategory.PERMANENT,
            source=ErrorSource.CALCULATOR,
            detail=detail,
        )

    @classmethod
    def detect_status_failed(cls, detail: str) -> "RecoveryError":
        return cls(
            code=ErrorCode.DETECT_STATUS_FAILED,
            category=ErrorCategory.TRANSIENT,
            source=ErrorSource.CALCULATOR,
            detail=detail,
        )

    @classmethod
    def collect_failed(cls, detail: str) -> "RecoveryError":
        return cls(
            code=ErrorCode.COLLECT_FAILED,
            category=ErrorCategory.PERMANENT,
            source=ErrorSource.CALCULATOR,
            detail=detail,
        )

    @classmethod
    def recovery_timeout(cls, detail: str) -> "RecoveryError":
        return cls(
            code=ErrorCode.RECOVERY_TIMEOUT,
            category=ErrorCategory.PERMANENT,
            source=ErrorSource.RECOVERY,
            detail=detail,
        )

    @classmethod
    def unknown_retry_exhausted(cls, detail: str) -> "RecoveryError":
        return cls(
            code=ErrorCode.UNKNOWN_RETRY_EXHAUSTED,
            category=ErrorCategory.PERMANENT,
            source=ErrorSource.RECOVERY,
            detail=detail,
        )

    @classmethod
    def poll_error_exhausted(cls, detail: str) -> "RecoveryError":
        return cls(
            code=ErrorCode.POLL_ERROR_EXHAUSTED,
            category=ErrorCategory.PERMANENT,
            source=ErrorSource.CALCULATOR,
            detail=detail,
        )

    @classmethod
    def job_reported_failed(cls) -> "RecoveryError":
        return cls(
            code=ErrorCode.JOB_REPORTED_FAILED,
            category=ErrorCategory.PERMANENT,
            source=ErrorSource.EXECUTOR,
            detail="Recovered job reported FAILED",
        )

    @classmethod
    def job_reported_cancelled(cls) -> "RecoveryError":
        return cls(
            code=ErrorCode.JOB_REPORTED_CANCELLED,
            category=ErrorCategory.PERMANENT,
            source=ErrorSource.EXECUTOR,
            detail="Recovered job reported CANCELLED",
        )


# 模块导出
__all__ = [
    "ErrorCode",
    "ErrorCategory",
    "ErrorSource",
    "RecoveryError",
]