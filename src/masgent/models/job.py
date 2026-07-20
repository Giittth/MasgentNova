"""作业句柄 —— 统一表示 Executor 返回的任务标识"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class JobHandle:
    """
    作业句柄，用于跟踪 Executor 启动的进程/作业
    """
    job_id: str
    backend: str
    pid: Optional[int] = None
    scheduler_id: Optional[str] = None
    submitted_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "JobHandle":
        """兼容旧数据：使用 get 提供默认值"""
        return cls(
            job_id=data["job_id"],
            backend=data.get("backend", "local"),
            pid=data.get("pid"),
            scheduler_id=data.get("scheduler_id"),
            submitted_at=data.get("submitted_at"),
            metadata=data.get("metadata", {}),
        )

    @staticmethod
    def now() -> str:
        return datetime.now().isoformat()