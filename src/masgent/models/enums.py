"""共享枚举定义"""

from enum import Enum


class UnknownStrategy(str, Enum):
    """UNKNOWN 状态恢复策略"""
    AUTO = "auto"      # 探测作业状态后决定
    POLL = "poll"      # 强制轮询
    EXECUTE = "execute"  # 强制重新执行

class TaskStatus(str, Enum):
    """任务状态（含 UNKNOWN）"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"

    @property
    def is_terminal(self) -> bool:
        return self in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)

    @property
    def is_active(self) -> bool:
        return self in (TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.UNKNOWN)


class WorkflowType(str, Enum):
    SINGLE_POINT = "single_point"
    FORCES = "forces"
    RELAX = "relax"
    EOS = "eos"
    ELASTIC = "elastic"
    AIMD = "aimd"
    NEB = "neb"
    PHONON = "phonon"
    DOS = "dos"                     
    BAND_STRUCTURE = "band_structure" # 确保存在（根据之前的代码）