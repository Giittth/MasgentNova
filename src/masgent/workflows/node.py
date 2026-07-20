"""工作流节点定义"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum

from pymatgen.core import Structure

from masgent.models.enums import TaskStatus, WorkflowType
from masgent.models.calculator import CalculationResult
from masgent.calculators.base import Calculator


class NodeStatus(str, Enum):
    """节点执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class WorkflowNode:
    """
    工作流节点——代表一个独立的计算任务

    Attributes:
        node_id: 节点唯一标识
        calculator: 计算器实例
        workflow_type: 工作流类型
        params: 计算参数
        dependencies: 依赖的 node_id 列表
        status: 节点状态
        task_id: 关联的 TaskRunner task_id
        result: 计算结果
        error_message: 错误信息
        structure: 输入结构（可能来自上游节点）
    """
    node_id: str
    calculator: Calculator
    workflow_type: WorkflowType
    params: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)

    status: NodeStatus = NodeStatus.PENDING
    task_id: Optional[str] = None
    result: Optional[CalculationResult] = None
    error_message: Optional[str] = None
    structure: Optional[Structure] = None
    calculator_type: Optional[str] = None 

    def __post_init__(self):
        """初始化后自动设置 calculator_type"""
        if self.calculator_type is None and self.calculator is not None:
            self.calculator_type = self.calculator.TYPE

    @property
    def is_terminal(self) -> bool:
        """节点是否处于终态（COMPLETED / FAILED / SKIPPED）"""
        return self.status in (
            NodeStatus.COMPLETED,
            NodeStatus.FAILED,
            NodeStatus.SKIPPED,
            NodeStatus.CANCELLED,
        )

    @property
    def is_ready(self) -> bool:
        """节点是否准备就绪（可执行）"""
        return self.status == NodeStatus.PENDING

    def set_running(self) -> None:
        self.status = NodeStatus.RUNNING

    def set_completed(self, result: CalculationResult):
        """
        标记节点为已完成，保存计算结果

        重要：直接保存 CalculationResult 对象，不进行序列化。
        序列化仅在 CheckpointManager.save_checkpoint() 中进行。
        """
        self.status = NodeStatus.COMPLETED
        self.result = result  # ✅ 直接保存对象引用
        self.error_message = None

    def set_failed(self, error: str) -> None:
        self.status = NodeStatus.FAILED
        self.error_message = error

    def set_skipped(self, reason: str) -> None:
        self.status = NodeStatus.SKIPPED
        self.error_message = reason

    def can_execute(self) -> bool:
        """节点是否可以执行（状态为 PENDING 且依赖已满足，但由 Scheduler 判断）"""
        return self.status == NodeStatus.PENDING

    def set_cancelled(self):
        self.status = NodeStatus.CANCELLED
        self.error_message = "Cancelled by user"

    def to_task_status(self) -> TaskStatus:
        """映射到 TaskRunner 状态"""
        mapping = {
            NodeStatus.PENDING: TaskStatus.PENDING,
            NodeStatus.RUNNING: TaskStatus.RUNNING,
            NodeStatus.COMPLETED: TaskStatus.COMPLETED,
            NodeStatus.FAILED: TaskStatus.FAILED,
            NodeStatus.SKIPPED: TaskStatus.CANCELLED,
        }
        return mapping.get(self.status, TaskStatus.PENDING)

    def to_dict(self) -> dict:
        data = {
            "node_id": self.node_id,
            "calculator_type": self.calculator_type,
            "workflow_type": self.workflow_type.value,
            "params": self.params,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "task_id": self.task_id,
            "error_message": self.error_message,
        }
        if self.result:
            from masgent.models.task import _serialize_result
            data["result"] = {
                "success": self.result.success,
                "workflow_type": self.result.workflow_type.value,
                "data": _serialize_result(self.result.data),
                "metadata": _serialize_result(self.result.metadata),
                "fingerprint": self.result.fingerprint,
                "error_message": self.result.error_message,
            }
        if self.structure:
            data["structure"] = _serialize_result(self.structure)
        return data


    @classmethod
    def from_dict(cls, data: dict, calculator: Optional[Calculator] = None) -> "WorkflowNode":
        """从字典反序列化，优先使用传入的 calculator"""
        calc = calculator
        if calc is None and data.get("calculator_type"):
            # 如果没有传入 calculator，需要外部通过 registry 重建
            # 这里只保存 calculator_type，实际注入由 Scheduler 负责
            pass

        node = cls(
            node_id=data["node_id"],
            calculator=calc,  # 可能为 None
            workflow_type=WorkflowType(data["workflow_type"]),
            params=data.get("params", {}),
            dependencies=data.get("dependencies", []),
        )
        node.calculator_type = data.get("calculator_type")
        node.status = NodeStatus(data.get("status", NodeStatus.PENDING.value))
        node.task_id = data.get("task_id")
        node.error_message = data.get("error_message")

        # 恢复 result
        if data.get("result"):
            from masgent.models.calculator import CalculationResult
            result_data = data["result"]
            node.result = CalculationResult(
                success=result_data["success"],
                workflow_type=WorkflowType(result_data["workflow_type"]),
                data=result_data.get("data", {}),
                metadata=result_data.get("metadata", {}),
                fingerprint=result_data.get("fingerprint"),
                error_message=result_data.get("error_message"),
            )

        return node