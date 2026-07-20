"""Workflow 控制句柄 —— 类似 Celery AsyncResult 或 Ray ObjectRef"""

import asyncio
from typing import Dict, Any, Optional

from masgent.workflows.graph import WorkflowGraph
from masgent.workflows.node import NodeStatus
from masgent.workflows.status import WorkflowStatus


class WorkflowHandle:
    """
    工作流句柄，用于控制异步执行的工作流

    支持：
        - wait() 等待完成
        - status() 查询状态
        - cancel() 取消执行
        - result() 获取结果
        - progress() 获取进度
    """

    def __init__(self, graph: WorkflowGraph):
        self.graph = graph
        self._task: Optional[asyncio.Task] = None
        self._result: Optional[Dict[str, Any]] = None
        self._exception: Optional[Exception] = None

    def set_task(self, task: asyncio.Task) -> None:
        """设置后台任务（由 Scheduler 调用）"""
        self._task = task

    async def wait(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        等待工作流完成
        Args:
            timeout: 超时时间（秒），None 表示无限等待
        Returns:
            Dict[str, Any]: 节点 ID → 结果
        Raises:
            TimeoutError: 超时
            asyncio.CancelledError: 任务被取消
            Exception: 工作流执行异常
        """
        if self._task is None:
            raise RuntimeError("Workflow not submitted yet")

        if timeout is None:
            self._result = await self._task
        else:
            self._result = await asyncio.wait_for(self._task, timeout=timeout)

        return self._result

    def status(self) -> WorkflowStatus:
        """获取工作流状态"""
        # 如果任务已取消
        if self._task and self._task.cancelled():
            return WorkflowStatus.CANCELLED

        # 统计节点状态
        nodes = self.graph.nodes.values()
        if not nodes:
            return WorkflowStatus.CREATED

        terminal_count = sum(1 for n in nodes if n.is_terminal)
        failed_count = sum(1 for n in nodes if n.status == NodeStatus.FAILED)
        cancelled_count = sum(1 for n in nodes if n.status == NodeStatus.CANCELLED)
        running_count = sum(1 for n in nodes if n.status == NodeStatus.RUNNING)
        pending_count = sum(1 for n in nodes if n.status == NodeStatus.PENDING)

        if cancelled_count > 0:
            return WorkflowStatus.CANCELLED
        if failed_count > 0:
            return WorkflowStatus.FAILED
        if terminal_count == len(nodes):
            return WorkflowStatus.COMPLETED
        if running_count > 0 or pending_count > 0:
            return WorkflowStatus.RUNNING
        return WorkflowStatus.CREATED

    def progress(self) -> tuple[int, int]:
        """获取进度 (completed, total)"""
        nodes = self.graph.nodes.values()
        completed = sum(1 for n in nodes if n.status == NodeStatus.COMPLETED)
        return completed, len(nodes)

    def cancel(self) -> None:
        """取消工作流执行"""
        if self._task and not self._task.done():
            self._task.cancel()
            # 标记所有非终态节点为 CANCELLED
            for node in self.graph.nodes.values():
                if not node.is_terminal:
                    node.set_cancelled()
            self.graph.set_cancelled()

    def result(self) -> Dict[str, Any]:
        """获取结果（如果已完成）"""
        if self._result is None:
            # 尝试从 graph 中收集已完成的节点结果
            results = {}
            for node_id, node in self.graph.nodes.items():
                if node.result and node.status == NodeStatus.COMPLETED:
                    results[node_id] = node.result
            return results
        return self._result