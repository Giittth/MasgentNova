"""WorkflowGraph 单元测试"""

import pytest

from masgent.workflows.node import WorkflowNode, NodeStatus
from masgent.workflows.graph import WorkflowGraph
from masgent.models.enums import WorkflowType
from tests.mock_calculator import MockCalculator


@pytest.fixture
def mock_calc():
    return MockCalculator()


class TestWorkflowGraph:
    def test_linear_dag_topological_order(self, mock_calc):
        """线性 DAG: A → B → C"""
        graph = WorkflowGraph("test_linear")

        node_a = WorkflowNode(
            node_id="A",
            calculator=mock_calc,
            workflow_type=WorkflowType.SINGLE_POINT,
        )
        node_b = WorkflowNode(
            node_id="B",
            calculator=mock_calc,
            workflow_type=WorkflowType.SINGLE_POINT,
            dependencies=["A"],
        )
        node_c = WorkflowNode(
            node_id="C",
            calculator=mock_calc,
            workflow_type=WorkflowType.SINGLE_POINT,
            dependencies=["B"],
        )

        graph.add_node(node_a).add_node(node_b).add_node(node_c)

        order = graph.topological_order()
        assert order == ["A", "B", "C"]

    def test_parallel_dag_ready_nodes(self, mock_calc):
        """并行 DAG: A → (B, C) → D"""
        graph = WorkflowGraph("test_parallel")

        node_a = WorkflowNode(
            node_id="A",
            calculator=mock_calc,
            workflow_type=WorkflowType.SINGLE_POINT,
        )
        node_b = WorkflowNode(
            node_id="B",
            calculator=mock_calc,
            workflow_type=WorkflowType.SINGLE_POINT,
            dependencies=["A"],
        )
        node_c = WorkflowNode(
            node_id="C",
            calculator=mock_calc,
            workflow_type=WorkflowType.SINGLE_POINT,
            dependencies=["A"],
        )
        node_d = WorkflowNode(
            node_id="D",
            calculator=mock_calc,
            workflow_type=WorkflowType.SINGLE_POINT,
            dependencies=["B", "C"],
        )

        graph.add_node(node_a).add_node(node_b).add_node(node_c).add_node(node_d)

        # 初始：只有 A 就绪
        ready = graph.get_ready_nodes()
        assert len(ready) == 1
        assert ready[0].node_id == "A"

        # 标记 A 完成
        node_a.set_completed(mock_calc.collect_return)

        # 现在 B 和 C 就绪
        ready = graph.get_ready_nodes()
        assert len(ready) == 2
        assert {n.node_id for n in ready} == {"B", "C"}

        # 标记 B 完成
        node_b.set_completed(mock_calc.collect_return)

        # C 未完成，D 不应就绪
        ready = graph.get_ready_nodes()
        assert len(ready) == 1
        assert ready[0].node_id == "C"

        # 标记 C 完成
        node_c.set_completed(mock_calc.collect_return)

        # D 就绪
        ready = graph.get_ready_nodes()
        assert len(ready) == 1
        assert ready[0].node_id == "D"

    def test_is_complete_property(self, mock_calc):
        """验证 is_complete() 使用 node.is_terminal"""
        graph = WorkflowGraph("test_complete")

        node = WorkflowNode(
            node_id="A",
            calculator=mock_calc,
            workflow_type=WorkflowType.SINGLE_POINT,
        )
        graph.add_node(node)

        # PENDING → 未完成
        assert graph.is_complete() is False

        # COMPLETED → 完成
        node.set_completed(mock_calc.collect_return)
        assert graph.is_complete() is True

        # FAILED → 完成（终态）
        node.set_failed("Test failure")
        assert graph.is_complete() is True

        # SKIPPED → 完成（终态）
        node.set_skipped("Test skip")
        assert graph.is_complete() is True

    def test_validate_dag_detects_cycle(self, mock_calc):
        """验证 DAG 检测循环依赖"""
        graph = WorkflowGraph("test_cycle")

        node_a = WorkflowNode(
            node_id="A",
            calculator=mock_calc,
            workflow_type=WorkflowType.SINGLE_POINT,
        )
        node_b = WorkflowNode(
            node_id="B",
            calculator=mock_calc,
            workflow_type=WorkflowType.SINGLE_POINT,
            dependencies=["A"],
        )

        graph.add_node(node_a).add_node(node_b)

        # 添加循环：B → A
        # 这需要通过 add_dependency 方法，但注意 add_dependency 目前防重复，
        # 我们直接操作 _edges 来模拟循环
        graph._edges["A"].add("B")
        graph.nodes["A"].dependencies.append("B")

        valid, error = graph.validate_dag()
        assert valid is False
        assert "Cycle detected" in error

    def test_add_dependency_prevents_duplicate(self, mock_calc):
        """验证 add_dependency 防重复"""
        graph = WorkflowGraph("test_dedup")

        node_a = WorkflowNode(
            node_id="A",
            calculator=mock_calc,
            workflow_type=WorkflowType.SINGLE_POINT,
        )
        node_b = WorkflowNode(
            node_id="B",
            calculator=mock_calc,
            workflow_type=WorkflowType.SINGLE_POINT,
        )

        graph.add_node(node_a).add_node(node_b)

        # 第一次添加依赖
        graph.add_dependency("A", "B")
        assert node_b.dependencies == ["A"]
        assert graph._edges["B"] == {"A"}

        # 第二次相同依赖 → 不应重复
        graph.add_dependency("A", "B")
        assert node_b.dependencies == ["A"]
        assert graph._edges["B"] == {"A"}

    def test_node_to_dict_from_dict(self, mock_calc):
        """验证节点序列化/反序列化"""
        original = WorkflowNode(
            node_id="test_node",
            calculator=mock_calc,
            workflow_type=WorkflowType.RELAX,
            params={"fmax": 0.05, "steps": 100},
            dependencies=["dep1", "dep2"],
            status=NodeStatus.RUNNING,
            task_id="task_123",
            error_message=None,
        )

        data = original.to_dict()
        restored = WorkflowNode.from_dict(data, mock_calc)

        assert restored.node_id == original.node_id
        assert restored.workflow_type == original.workflow_type
        assert restored.params == original.params
        assert restored.dependencies == original.dependencies
        assert restored.status == original.status
        assert restored.task_id == original.task_id
        assert restored.error_message == original.error_message