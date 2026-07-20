"""
工作流 DAG 图

管理节点和依赖关系，提供：
    - 节点 CRUD
    - DAG 无环验证
    - 就绪节点查询（支持 Resume）
    - 拓扑排序
    - 状态管理
    - 序列化（to_dict / from_dict）
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from collections import deque

from masgent.workflows.node import WorkflowNode, NodeStatus
from masgent.workflows.status import WorkflowStatus


class WorkflowGraph:
    """
    工作流 DAG 图

    核心职责：
        1. 管理 WorkflowNode 及其依赖关系
        2. 提供 DAG 验证（循环依赖检测）
        3. 查询就绪节点（依赖已满足的 PENDING 节点）
        4. 管理工作流整体状态
        5. 支持序列化/反序列化（Checkpoint）
    """
    def __init__(self, name: str = "workflow"):
        """
        初始化工作流图

        Args:
            name: 工作流名称（用于标识）
        """
        # 唯一标识（用于 Checkpoint 恢复）
        self.graph_id = uuid.uuid4().hex[:12]
        self.name = name
        self.created_at = datetime.now().isoformat()

        # 扩展元数据（resume_count, last_resume_at, executor_type 等）
        # 使用 dict 而非独立字段，避免频繁修改类结构
        self.metadata: Dict[str, any] = {}

        # 节点存储：node_id → WorkflowNode
        self.nodes: Dict[str, WorkflowNode] = {}

        # 依赖边：node_id → {依赖的 node_id 集合}
        # 用于快速查询依赖关系
        self._edges: Dict[str, Set[str]] = {}

        # 工作流整体状态
        self.status = WorkflowStatus.CREATED

    # ========== 节点管理 ==========
    def add_node(self, node: WorkflowNode) -> "WorkflowGraph":
        """
        添加节点到图中

        Args:
            node: 工作流节点

        Returns:
            self（支持链式调用）
        """
        self.nodes[node.node_id] = node
        self._edges[node.node_id] = set(node.dependencies)
        return self

    def add_dependency(self, from_id: str, to_id: str) -> "WorkflowGraph":
        """
        添加依赖关系：from_id → to_id
        表示 to_id 依赖 from_id，from_id 完成后 to_id 才能执行

        防重复：如果依赖已存在，不重复添加

        Args:
            from_id: 被依赖的节点 ID
            to_id: 依赖 from_id 的节点 ID

        Returns:
            self（支持链式调用）

        Raises:
            ValueError: 任一节点不存在
        """
        if from_id not in self.nodes:
            raise ValueError(f"Node {from_id} not found")
        if to_id not in self.nodes:
            raise ValueError(f"Node {to_id} not found")

        # 防重复添加
        if from_id not in self._edges[to_id]:
            self._edges[to_id].add(from_id)
            self.nodes[to_id].dependencies.append(from_id)

        return self

    def get_dependencies(self, node_id: str) -> List[str]:
        """获取节点的所有依赖（直接依赖）"""
        return list(self._edges.get(node_id, []))

    def get_dependents(self, node_id: str) -> List[str]:
        """
        获取所有依赖该节点的下游节点列表

        Args:
            node_id: 节点 ID

        Returns:
            List[str]: 依赖 node_id 的所有节点 ID
        """
        return [nid for nid, deps in self._edges.items() if node_id in deps]

    # ========== DAG 验证 ==========
    def validate_dag(self) -> Tuple[bool, Optional[str]]:
        """
        验证是否为有效的 DAG（有向无环图）

        使用 DFS + 三色标记法检测循环依赖

        Returns:
            Tuple[bool, Optional[str]]:
                - (True, None): 有效 DAG
                - (False, error_msg): 存在循环依赖
        """
        visited = set()    # 已完全处理的节点
        visiting = set()   # 当前 DFS 栈中的节点

        def dfs(node_id: str) -> bool:
            """递归检测循环，返回 False 表示发现环"""
            if node_id in visiting:
                return False  # 发现环
            if node_id in visited:
                return True   # 已确认无环

            visiting.add(node_id)
            for dep in self._edges.get(node_id, []):
                if dep in self.nodes:
                    if not dfs(dep):
                        return False
                else:
                    # 依赖的节点不在图中 → 无效
                    return False
            visiting.remove(node_id)
            visited.add(node_id)
            return True

        for node_id in self.nodes:
            if node_id not in visited:
                if not dfs(node_id):
                    return False, f"Cycle detected involving node: {node_id}"

        return True, None

    # ========== 状态查询 ==========
    def get_ready_nodes(self) -> List[WorkflowNode]:
        """
        获取所有就绪节点（依赖已满足且状态为 PENDING）

        Resume 关键：只有 PENDING 节点会被调度。
        COMPLETED/RUNNING/FAILED/CANCELLED 节点均被跳过。

        Returns:
            List[WorkflowNode]: 所有就绪的 PENDING 节点
        """
        ready = []
        for node in self.nodes.values():
            # ★ Resume 核心：只调度 PENDING 节点
            # COMPLETED 节点永不重新提交，RUNNING/FAILED/CANCELLED 由其他逻辑处理
            if node.status != NodeStatus.PENDING:
                continue

            # 检查所有依赖是否已完成
            all_deps_completed = all(
                self.nodes[dep].status == NodeStatus.COMPLETED
                for dep in node.dependencies
                if dep in self.nodes
            )

            if all_deps_completed:
                ready.append(node)

        return ready

    def get_running_nodes(self) -> List[WorkflowNode]:
        """获取所有运行中的节点（状态为 RUNNING）"""
        return [n for n in self.nodes.values() if n.status == NodeStatus.RUNNING]

    def get_failed_nodes(self) -> List[WorkflowNode]:
        """获取所有失败的节点（状态为 FAILED）"""
        return [n for n in self.nodes.values() if n.status == NodeStatus.FAILED]

    def is_complete(self) -> bool:
        """
        检查工作流是否已完成

        完成条件：所有节点均处于终态
        （COMPLETED / FAILED / SKIPPED / CANCELLED）
        """
        return all(
            node.is_terminal
            for node in self.nodes.values()
        )

    def is_successful(self) -> bool:
        """检查工作流是否全部成功（所有节点均为 COMPLETED）"""
        return all(n.status == NodeStatus.COMPLETED for n in self.nodes.values())

    def topological_order(self) -> List[str]:
        """
        拓扑排序（Kahn 算法）

        用于：显示执行顺序、生成执行计划

        Returns:
            List[str]: 拓扑有序的节点 ID 列表
        """
        in_degree = {nid: len(deps) for nid, deps in self._edges.items()}
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        result = []

        while queue:
            nid = queue.popleft()
            result.append(nid)
            for child in self.get_dependents(nid):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        return result

    # ========== 状态设置 ==========
    def set_running(self):
        """设置工作流状态为 RUNNING（开始执行）"""
        self.status = WorkflowStatus.RUNNING

    def set_completed(self):
        """设置工作流状态为 COMPLETED（全部成功）"""
        self.status = WorkflowStatus.COMPLETED

    def set_failed(self):
        """设置工作流状态为 FAILED（有节点失败）"""
        self.status = WorkflowStatus.FAILED

    def set_cancelled(self):
        """设置工作流状态为 CANCELLED（用户取消）"""
        self.status = WorkflowStatus.CANCELLED

    # ========== Resume 元数据 ==========
    def mark_resumed(self):
        """
        标记工作流被恢复

        更新元数据：
            - resume_count: 恢复次数 +1
            - last_resume_at: 最近一次恢复时间

        用于审计和追踪：工作流经历了多少次恢复才最终完成
        """
        self.metadata["resume_count"] = self.metadata.get("resume_count", 0) + 1
        self.metadata["last_resume_at"] = datetime.now().isoformat()

    # ========== 序列化 ==========
    def to_dict(self) -> dict:
        """
        序列化为字典（用于内存传输或测试）

        注意：CheckpointManager 使用独立的序列化格式（graph.json + nodes/*.json）
        此方法主要用于测试和调试。

        Returns:
            dict: 完整的图数据
        """
        return {
            "graph_id": self.graph_id,
            "name": self.name,
            "created_at": self.created_at,
            "status": self.status.value,
            "metadata": self.metadata,
            "nodes": {
                nid: node.to_dict()
                for nid, node in self.nodes.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict, calculators: Dict[str, "Calculator"]) -> "WorkflowGraph":
        """
        从字典反序列化

        Args:
            data: to_dict() 生成的字典
            calculators: calculator_type → Calculator 实例映射
                         用于恢复节点中的 calculator

        Returns:
            WorkflowGraph: 恢复的工作流图
        """
        graph = cls(name=data.get("name", "workflow"))
        graph.graph_id = data.get("graph_id", uuid.uuid4().hex[:12])
        graph.created_at = data.get("created_at", datetime.now().isoformat())
        graph.metadata = data.get("metadata", {})
        graph.status = WorkflowStatus(data.get("status", WorkflowStatus.CREATED.value))

        for node_id, node_data in data.get("nodes", {}).items():
            calc_type = node_data.get("calculator_type")
            calc = calculators.get(calc_type) if calc_type else None
            node = WorkflowNode.from_dict(node_data, calc)
            graph.add_node(node)

        return graph