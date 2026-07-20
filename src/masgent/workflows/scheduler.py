"""工作流调度器 —— v0.6.1 稳定版"""

import asyncio
import logging
from typing import Dict, Optional, List, Any

from pymatgen.core import Structure
from pymatgen.core import Structure

from masgent.workflows.graph import WorkflowGraph
from masgent.workflows.node import WorkflowNode, NodeStatus
from masgent.workflows.handle import WorkflowHandle
from masgent.workflows.status import WorkflowStatus
from masgent.tasks.task_runner import TaskRunner
from masgent.models.enums import TaskStatus
from masgent.models.calculator import CalculationResult
from masgent.models.task import _deserialize_result


class WorkflowScheduler:
    """
    工作流调度器

    执行 DAG 工作流：
        1. 提交就绪节点
        2. 监控运行中节点
        3. 处理完成/失败/跳过
        4. 支持并发执行
    """

    def __init__(
        self,
        task_runner: TaskRunner,
        max_concurrent: int = 4,
        poll_interval: float = 2.0,
        checkpoint_manager: Optional[WorkflowCheckpointManager] = None,
    ):
        self.task_runner = task_runner
        self.max_concurrent = max_concurrent
        self.poll_interval = poll_interval
        self._handles: Dict[str, WorkflowHandle] = {}
        self.checkpoint_manager = checkpoint_manager

    async def submit(
        self,
        graph: WorkflowGraph,
        initial_structure: Optional[Structure] = None,
    ) -> WorkflowHandle:
        """提交工作流，返回句柄"""
        graph.set_running()
        handle = WorkflowHandle(graph)
        task = asyncio.create_task(self._run_and_manage(graph, initial_structure, handle))
        handle.set_task(task)
        self._handles[graph.graph_id] = handle
        return handle

    async def _run_and_manage(
        self,
        graph: WorkflowGraph,
        initial_structure: Optional[Structure],
        handle: WorkflowHandle,
    ) -> Dict[str, Any]:
        """实际执行并更新状态"""
        try:
            results = await self.run(graph, initial_structure)
            graph.set_completed()
            # 保存最终状态
            if self.checkpoint_manager:
                await self.checkpoint_manager.save_checkpoint(graph)
            return results
        except asyncio.CancelledError:
            graph.set_cancelled()
            if self.checkpoint_manager:
                await self.checkpoint_manager.save_checkpoint(graph)
            raise
        except Exception as e:
            graph.set_failed()
            if self.checkpoint_manager:
                await self.checkpoint_manager.save_checkpoint(graph)
            raise


    async def resume(self, graph_id: str, calculators: Dict[str, Calculator]) -> WorkflowHandle:
        if self.checkpoint_manager is None:
            raise RuntimeError("CheckpointManager not configured")

        graph = await self.checkpoint_manager.load_checkpoint(graph_id)
        if graph is None:
            raise ValueError(f"Checkpoint for {graph_id} not found")

        if graph.status == WorkflowStatus.COMPLETED:
            raise RuntimeError(f"Workflow {graph_id} is already COMPLETED")
        if graph.status == WorkflowStatus.CANCELLED:
            raise RuntimeError(f"Workflow {graph_id} was CANCELLED and cannot be resumed")

        # 更新恢复元数据
        graph.mark_resumed()

        # 注入 calculator
        for node in graph.nodes.values():
            if node.calculator is None and node.calculator_type:
                if node.calculator_type in calculators:
                    node.calculator = calculators[node.calculator_type]
                else:
                    raise ValueError(f"Calculator type '{node.calculator_type}' not provided")

        # 检查 RUNNING 节点
        for node in graph.get_running_nodes():
            if node.task_id:
                status = await self.task_runner.poll(node.task_id)
                if status == TaskStatus.COMPLETED:
                    result = await self.task_runner.collect(node.task_id)
                    from masgent.models.calculator import CalculationResult
                    node.result = CalculationResult(
                        success=True,
                        workflow_type=node.workflow_type,
                        data=result.get("data", {}),
                        metadata=result.get("metadata", {}),
                    )
                    node.set_completed(node.result)
                elif status == TaskStatus.RUNNING:
                    pass
                elif status == TaskStatus.FAILED:
                    node.set_failed(f"Task {node.task_id} failed")
                elif status == TaskStatus.CANCELLED:
                    node.set_cancelled()

        # 保存检查点（记录恢复状态）
        if self.checkpoint_manager:
            await self.checkpoint_manager.save_checkpoint(graph)

        graph.set_running()
        handle = WorkflowHandle(graph)
        task = asyncio.create_task(self._run_and_manage(graph, None, handle))
        handle.set_task(task)
        self._handles[graph.graph_id] = handle

        return handle


    async def cancel(self, graph_id: str) -> bool:
        """取消工作流"""
        handle = self._handles.get(graph_id)
        if handle is None:
            return False
        handle.cancel()
        return True

    async def run(
        self,
        graph: WorkflowGraph,
        initial_structure: Optional[Structure] = None,
    ) -> Dict[str, CalculationResult]:
        """
        执行工作流（内部方法，由 submit 调用）

        执行流程：
            1. 验证 DAG 合法性
            2. 收集已完成节点的结果（支持 Resume）
            3. 初始化第一个节点的 structure
            4. 主循环：提交就绪节点 → 监控运行节点 → 收集结果
            5. 返回所有节点结果

        每个 run 调用有自己的 running_tasks，互不干扰。
        节点完成后自动保存检查点（如果配置了 checkpoint_manager）。

        Args:
            graph: 工作流图
            initial_structure: 初始结构（用于第一个节点）

        Returns:
            Dict[str, CalculationResult]: 节点 ID → 计算结果
        """
        # ========== 1. 验证 DAG ==========
        valid, error = graph.validate_dag()
        if not valid:
            raise ValueError(f"Invalid DAG: {error}")

        # ========== 2. 收集已完成节点的结果（Resume 核心） ==========
        # 当工作流从检查点恢复时，部分节点可能已经 COMPLETED
        # 需要将这些节点的结果预先填充到 results 中
        # 这样下游节点可以从 results 获取上游结果，handle.wait() 也能返回完整结果
        results: Dict[str, CalculationResult] = {}
        for node in graph.nodes.values():
            if node.status == NodeStatus.COMPLETED and node.result:
                results[node.node_id] = node.result

        # ========== 3. 初始化第一个节点的 structure ==========
        if initial_structure:
            ready = graph.get_ready_nodes()
            for node in ready:
                if node.structure is None:
                    node.structure = initial_structure

        # ========== 4. 主循环 ==========
        running_tasks: Dict[str, asyncio.Task] = {}

        while True:
            # 4.0 退出条件：所有节点已完成且没有运行任务
            if graph.is_complete() and not running_tasks:
                break

            # 4.1 检查失败传播
            failed = graph.get_failed_nodes()

            if failed:
                for n in failed:
                    raise RuntimeError(
                        f"Workflow failed at nodes: {[n.node_id for n in failed]}"
                    )

            # 4.2 提交就绪节点
            ready = graph.get_ready_nodes()
            available_slots = self.max_concurrent - len(running_tasks)

            for node in ready[:available_slots]:
                if node.node_id not in running_tasks:
                    task = asyncio.create_task(self._execute_node(graph, node))
                    running_tasks[node.node_id] = task

            # 4.3 监控运行中节点
            if running_tasks:
                done, pending = await asyncio.wait(
                    running_tasks.values(),
                    timeout=self.poll_interval,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in done:
                    # 找到对应的 node_id
                    node_id = None
                    for nid, t in running_tasks.items():
                        if t == task:
                            node_id = nid
                            break

                    if node_id:
                        node = graph.nodes[node_id]
                        try:
                            result = task.result()
                            results[node_id] = result

                            # 节点完成 → 保存检查点
                            if self.checkpoint_manager:
                                await self.checkpoint_manager.save_checkpoint(graph)

                        except Exception as e:
                            import traceback

                            traceback.print_exc()

                            print(
                                f"\n[SCHEDULER ERROR] "
                                f"node={node.node_id} "
                                f"type={type(e).__name__} "
                                f"msg={e}\n"
                            )

                            node.set_failed(str(e))

                            results[node_id] = CalculationResult(
                                success=False,
                                workflow_type=node.workflow_type,
                                error_message=str(e),
                            )

                            # 失败也保存检查点（保留失败状态）
                            if self.checkpoint_manager:
                                await self.checkpoint_manager.save_checkpoint(graph)

                        finally:
                            running_tasks.pop(node_id, None)

                # 如果没有任务完成，休眠一下避免忙等
                if not done:
                    await asyncio.sleep(self.poll_interval)

            else:
                # 没有运行任务，也没有就绪节点，但图未完成 → 死锁
                if not graph.is_complete():
                    pending_nodes = [n for n in graph.nodes.values() if n.status == NodeStatus.PENDING]
                    if pending_nodes:
                        dep_status = {}
                        for node in pending_nodes:
                            dep_status[node.node_id] = {
                                dep: graph.nodes[dep].status
                                for dep in node.dependencies
                                if dep in graph.nodes
                            }
                        raise RuntimeError(
                            f"Workflow deadlocked: {len(pending_nodes)} pending nodes with unmet dependencies. "
                            f"Dependency status: {dep_status}"
                        )
                    else:
                        raise RuntimeError("Workflow deadlocked: no ready nodes, no running nodes, and no pending nodes")

                # 如果 graph.is_complete() 为 True，但 running_tasks 为空，会在循环顶部退出
                await asyncio.sleep(self.poll_interval)

        # ========== 5. 返回结果 ==========
        return results


    async def _execute_node(self, graph: WorkflowGraph, node: WorkflowNode) -> CalculationResult:
        """
        执行单个节点，返回计算结果

        流程：
            1. 获取输入结构（从 node.structure 或上游节点结果）
            2. 确保结构为 pymatgen.core.Structure 类型
            3. 提交任务到 TaskRunner
            4. 轮询等待完成
            5. 收集结果并返回
        """
        # ========== 获取输入结构 ==========
        structure = node.structure
        if structure is None:
            for dep_id in node.dependencies:
                dep = graph.nodes.get(dep_id)
                if dep and dep.result and dep.result.success:
                    dep_structure = dep.result.data.get("structure")
                    if dep_structure:
                        if not isinstance(dep_structure, Structure):
                            dep_structure = _deserialize_result(dep_structure)
                        structure = dep_structure
                        break

        if structure is None:
            raise ValueError(f"No structure available for node {node.node_id}")
        if not isinstance(structure, Structure):
            structure = _deserialize_result(structure)

        # ========== 提交任务 ==========
        node.set_running()
        try:
            task_info = await self.task_runner.submit(
                node.calculator,
                structure,
                node.workflow_type,
                **node.params,
            )
        except Exception as e:
            node.set_failed(str(e))
            raise RuntimeError(f"Task submission failed for node {node.node_id}: {e}")

        node.task_id = task_info.task_id

        # ========== 轮询等待 ==========
        while True:
            status = await self.task_runner.poll(task_info.task_id)
            if status.is_terminal:
                break
            await asyncio.sleep(self.poll_interval)

        # ========== 收集结果 ==========
        if status == TaskStatus.COMPLETED:
            # 关键修复：正确解析 TaskRunner.collect 返回的格式
            result = await self.task_runner.collect(task_info.task_id)
            if result is None:
                raise RuntimeError(f"Empty result from task {task_info.task_id}")

            data = result.get("data", {})
            metadata = result.get("metadata", {})

            # 确保 structure 是 Structure 对象（兜底）
            final_structure = data.get("structure")
            if final_structure is None:
                final_structure = structure
            elif not isinstance(final_structure, Structure):
                final_structure = _deserialize_result(final_structure)
            data["structure"] = final_structure

            calc_result = CalculationResult(
                success=True,
                workflow_type=node.workflow_type,
                data=data,
                metadata=metadata,
            )
            node.set_completed(calc_result)
            return calc_result
        else:
            error = f"Task {task_info.task_id} ended with status {status.value}"
            node.set_failed(error)
            raise RuntimeError(error)

    def _propagate_failure(self, graph: WorkflowGraph, failed_nodes: List[WorkflowNode]) -> None:
        """传播失败：标记下游节点为 SKIPPED"""
        failed_ids = {n.node_id for n in failed_nodes}

        def mark_skipped(node_id: str) -> None:
            node = graph.nodes.get(node_id)
            if node and node.status == NodeStatus.PENDING:
                node.set_skipped(f"Depends on failed node(s): {', '.join(failed_ids)}")
            for dep_id in graph.get_dependents(node_id):
                mark_skipped(dep_id)

        for failed_id in failed_ids:
            mark_skipped(failed_id)