"""Workflow 检查点管理器 —— 持久化工作流状态"""

import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from masgent.workflows.graph import WorkflowGraph
from masgent.workflows.node import WorkflowNode, NodeStatus
from masgent.models.calculator import CalculationResult


class WorkflowCheckpointManager:
    """
    工作流检查点管理器

    职责：
        - 保存工作流状态到磁盘
        - 从磁盘恢复工作流状态
        - 管理 checkpoint 目录结构

    目录结构：
        checkpoints/
            {graph_id}/
                graph.json
                nodes/
                    {node_id}.json
    """

    def __init__(self, checkpoint_dir: Path):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _graph_dir(self, graph_id: str) -> Path:
        """获取工作流对应的目录"""
        return self.checkpoint_dir / graph_id

    def _nodes_dir(self, graph_id: str) -> Path:
        """获取节点文件目录"""
        return self._graph_dir(graph_id) / "nodes"

    def _graph_path(self, graph_id: str) -> Path:
        """获取 graph.json 文件路径"""
        return self._graph_dir(graph_id) / "graph.json"

    def _node_path(self, graph_id: str, node_id: str) -> Path:
        """获取节点 JSON 文件路径"""
        return self._nodes_dir(graph_id) / f"{node_id}.json"

    async def save_checkpoint(self, graph: WorkflowGraph) -> None:
        """
        保存工作流检查点

        保存内容：
            - graph.json: 工作流元数据（graph_id, name, status, node 引用）
            - nodes/*.json: 每个节点的详细状态
        """
        graph_id = graph.graph_id
        graph_dir = self._graph_dir(graph_id)
        nodes_dir = self._nodes_dir(graph_id)

        # 创建目录
        graph_dir.mkdir(parents=True, exist_ok=True)
        nodes_dir.mkdir(parents=True, exist_ok=True)

        # 保存 graph.json（含 metadata）
        graph_data = {
            "graph_id": graph.graph_id,
            "name": graph.name,
            "created_at": graph.created_at,
            "status": graph.status.value,
            "metadata": graph.metadata,
            "node_ids": list(graph.nodes.keys()),
            "updated_at": datetime.now().isoformat(),
        }
        with open(self._graph_path(graph_id), "w", encoding="utf-8") as f:
            json.dump(graph_data, f, indent=2, ensure_ascii=False)

        # 保存节点（不变）
        for node in graph.nodes.values():
            node_data = node.to_dict()
            with open(self._node_path(graph_id, node.node_id), "w", encoding="utf-8") as f:
                json.dump(node_data, f, indent=2, ensure_ascii=False)

    async def load_checkpoint(self, graph_id: str) -> Optional[WorkflowGraph]:
        """
        从检查点恢复工作流

        Args:
            graph_id: 工作流 ID

        Returns:
            WorkflowGraph: 恢复的工作流图，如果不存在则返回 None
        """
        graph_path = self._graph_path(graph_id)
        if not graph_path.exists():
            return None

        # 1. 加载 graph.json
        with open(graph_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)

        # 2. 创建空图
        from masgent.workflows.graph import WorkflowGraph
        from masgent.workflows.status import WorkflowStatus

        graph = WorkflowGraph(name=graph_data["name"])
        graph.graph_id = graph_data["graph_id"]
        graph.created_at = graph_data["created_at"]
        graph.metadata = graph_data.get("metadata", {}) 
        graph.status = WorkflowStatus(graph_data["status"])

        for node_id in graph_data["node_ids"]:
            node_path = self._node_path(graph_id, node_id)
            if not node_path.exists():
                continue
            with open(node_path, "r", encoding="utf-8") as f:
                node_data = json.load(f)
            node = self._create_node_from_dict(node_data)
            if node:
                graph.add_node(node)

        return graph

    def _serialize_result(self, result: CalculationResult) -> dict:
        """序列化 CalculationResult（支持 Structure）"""
        from masgent.models.task import _serialize_result

        return {
            "success": result.success,
            "workflow_type": result.workflow_type.value,
            "data": _serialize_result(result.data),
            "metadata": _serialize_result(result.metadata),
            "fingerprint": result.fingerprint,
            "error_message": result.error_message,
        }

    def _create_node_from_dict(self, data: dict) -> Optional[WorkflowNode]:
        """从字典创建节点（恢复时使用）"""
        from masgent.workflows.node import WorkflowNode
        from masgent.models.enums import WorkflowType
        from masgent.models.calculator import CalculationResult
        from masgent.models.task import _deserialize_result

        try:
            node = WorkflowNode(
                node_id=data["node_id"],
                calculator=None,
                workflow_type=WorkflowType(data["workflow_type"]),
                params=data.get("params", {}),
                dependencies=data.get("dependencies", []),
            )
            node.calculator_type = data.get("calculator_type")
            node.status = NodeStatus(data.get("status", NodeStatus.PENDING.value))
            node.task_id = data.get("task_id")
            node.error_message = data.get("error_message")

            # 恢复 structure
            if data.get("structure"):
                node.structure = _deserialize_result(data["structure"])

            # 恢复 result（data 和 metadata 都必须反序列化）
            if data.get("result"):
                result_data = data["result"]
                node.result = CalculationResult(
                    success=result_data["success"],
                    workflow_type=WorkflowType(result_data["workflow_type"]),
                    data=_deserialize_result(result_data.get("data", {})),
                    metadata=_deserialize_result(result_data.get("metadata", {})),
                    fingerprint=result_data.get("fingerprint"),
                    error_message=result_data.get("error_message"),
                )

            return node
        except Exception:
            return None

    def checkpoint_exists(self, graph_id: str) -> bool:
        """检查工作流是否有保存的检查点"""
        return self._graph_path(graph_id).exists()

    def list_checkpoints(self) -> list:
        """列出所有可用的检查点"""
        checkpoints = []
        for graph_dir in self.checkpoint_dir.iterdir():
            if graph_dir.is_dir() and (graph_dir / "graph.json").exists():
                try:
                    with open(graph_dir / "graph.json", "r", encoding="utf-8") as f:
                        data = json.load(f)
                    checkpoints.append({
                        "graph_id": data["graph_id"],
                        "name": data["name"],
                        "status": data.get("status", "unknown"),
                        "updated_at": data.get("updated_at"),
                    })
                except Exception:
                    continue
        return checkpoints