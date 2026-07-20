from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, Union, List
import numpy as np
from pymatgen.core import Structure
from monty.json import MontyDecoder

from masgent.models.enums import TaskStatus, WorkflowType


# ========== 状态迁移表 ==========
VALID_TRANSITIONS = {
    TaskStatus.PENDING: {
        TaskStatus.RUNNING,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
        TaskStatus.UNKNOWN,
        TaskStatus.COMPLETED,
    },
    TaskStatus.RUNNING: {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
        TaskStatus.UNKNOWN,
    },
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
    TaskStatus.UNKNOWN: {
        TaskStatus.RUNNING,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.PENDING,  
    },
}


# ========== Result 序列化/反序列化（支持科学对象） ==========
def _serialize_result(obj: Any) -> Any:
    """
    递归序列化 result 字段

    支持：
        - pymatgen 对象（Monty 格式）
        - numpy 数组和数值
        - datetime
        - dict / list / tuple
    """
    # 1. Monty 可序列化对象（as_dict 方法）
    if hasattr(obj, "as_dict") and callable(obj.as_dict):
        try:
            data = obj.as_dict()
            if isinstance(data, dict):
                # 确保是 Monty 格式（包含 @module 和 @class）
                if "@module" in data and "@class" in data:
                    return data
                # 如果不是 Monty 格式，也返回数据（兜底）
                return data
        except Exception:
            pass

    # 2. numpy ndarray
    if isinstance(obj, np.ndarray):
        return {"__type__": "ndarray", "data": obj.tolist()}

    # 3. numpy 标量
    if isinstance(obj, (np.float32, np.float64)):
        return float(obj)

    # 4. datetime
    if isinstance(obj, datetime):
        return obj.isoformat()

    # 5. dict
    if isinstance(obj, dict):
        return {k: _serialize_result(v) for k, v in obj.items()}

    # 6. list / tuple
    if isinstance(obj, (list, tuple)):
        return [_serialize_result(v) for v in obj]

    # 7. 其他（保持原样）
    return obj


def _deserialize_result(obj: Any) -> Any:
    """
    递归反序列化 result 字段

    支持：
        - Monty 格式（@module/@class）
        - 自定义 __type__ 格式（ndarray）
        - 普通 dict / list
    """
    if isinstance(obj, dict):
        # 1. Monty 格式
        if "@module" in obj and "@class" in obj:
            try:
                return MontyDecoder().process_decoded(obj)
            except Exception:
                pass

        # 2. 自定义 __type__ 格式（向后兼容）
        if obj.get("__type__") == "ndarray":
            try:
                return np.array(obj["data"])
            except Exception:
                return obj

        # 3. 普通 dict（递归处理）
        return {k: _deserialize_result(v) for k, v in obj.items()}

    elif isinstance(obj, list):
        return [_deserialize_result(v) for v in obj]

    return obj


# ========== TaskRecord ==========
@dataclass
class TaskRecord:
    """
    任务持久化记录

    包含任务的所有元数据、状态、参数和结果。
    支持序列化到 JSON 并恢复，包括 pymatgen Structure 等复杂对象。
    """
    task_id: str
    workflow_type: WorkflowType
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    work_dir: str

    # 计算器信息
    calculator_type: str
    calculator_params: Dict[str, Any] = field(default_factory=dict)
    workflow_params: Dict[str, Any] = field(default_factory=dict)

    # 作业句柄（序列化后的 JobHandle）
    job_handle: Optional[Dict[str, Any]] = None

    # 重试计数（仅 UNKNOWN 状态使用）
    retry_count: int = 0

    # 执行器配置（用于恢复时重建 executor）
    executor_config: Optional[Dict[str, Any]] = None

    # 结果与错误
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    # 缓存指纹（可选）
    fingerprint: Optional[str] = None

    # 完成时间
    finished_at: Optional[datetime] = None

    def validate_transition(self, new_status: TaskStatus) -> None:
        """验证状态迁移是否合法"""
        allowed = VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {self.status.value} -> {new_status.value}. "
                f"Allowed: {[s.value for s in allowed] if allowed else 'none'}"
            )

    def set_status(self, new_status: TaskStatus) -> None:
        """更新状态（带验证），自动更新 updated_at 和 finished_at"""
        self.validate_transition(new_status)
        self.status = new_status
        self.updated_at = datetime.now()
        if new_status.is_terminal:
            self.finished_at = datetime.now()

    def to_dict(self) -> dict:
        data = {
            "task_id": self.task_id,
            "workflow_type": self.workflow_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "work_dir": self.work_dir,
            "calculator_type": self.calculator_type,
            "calculator_params": self.calculator_params,
            "workflow_params": self.workflow_params,
            "job_handle": self.job_handle,
            "retry_count": self.retry_count,
            "executor_config": self.executor_config,
            "result": _serialize_result(self.result),
            "error_message": self.error_message,
            "fingerprint": self.fingerprint,
        }
        if self.finished_at:
            data["finished_at"] = self.finished_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "TaskRecord":
        """从字典反序列化（从 JSON 恢复）"""
        return cls(
            task_id=data["task_id"],
            workflow_type=WorkflowType(data["workflow_type"]),
            status=TaskStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            work_dir=data["work_dir"],
            calculator_type=data["calculator_type"],
            calculator_params=data.get("calculator_params", {}),
            workflow_params=data.get("workflow_params", {}),
            job_handle=data.get("job_handle"),
            retry_count=data.get("retry_count", 0),
            executor_config=data.get("executor_config"),
            result=_deserialize_result(data.get("result")),
            error_message=data.get("error_message"),
            fingerprint=data.get("fingerprint"),
            finished_at=datetime.fromisoformat(data["finished_at"]) if data.get("finished_at") else None,
        )


@dataclass
class TaskInfo:
    """
    任务信息（轻量级，用于 submit 返回）
    与 TaskRecord 不同，TaskInfo 不持久化，仅用于 API 响应。
    """
    task_id: str
    status: TaskStatus
    work_dir: str
    workflow_type: WorkflowType
    created_at: datetime = field(default_factory=datetime.now)