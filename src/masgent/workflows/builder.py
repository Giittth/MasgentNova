# src/masgent/workflows/builder.py

"""工作流构建器 —— 链式 DSL 式 API，支持并行 DAG"""

from typing import Optional, Dict, Any, List, Union
from pymatgen.core import Structure

from masgent.workflows.node import WorkflowNode
from masgent.workflows.graph import WorkflowGraph
from masgent.models.enums import WorkflowType
from masgent.calculators.base import Calculator


class WorkflowBuilder:
    """
    工作流构建器

    提供链式 API 构建工作流，支持线性链和并行 DAG。

    线性链（默认）：
        workflow = (WorkflowBuilder("my_workflow")
            .set_calculator(calc)
            .relax(structure, fmax=0.05)
            .static()
            .dos()
            .build()
        )

    并行 DAG（显式依赖）：
        workflow = (WorkflowBuilder("my_workflow")
            .set_calculator(calc)
            .add("relax", WorkflowType.RELAX, params={"fmax": 0.05})
            .add("static", WorkflowType.SINGLE_POINT, depends_on=["relax"])
            .add("dos", WorkflowType.DOS, depends_on=["static"])
            .add("band", WorkflowType.BAND_STRUCTURE, depends_on=["static"])
            .build()
        )
    """

    def __init__(self, name: str = "workflow"):
        self.name = name
        self.graph = WorkflowGraph(name)
        self._calculator: Optional[Calculator] = None
        self._last_node_id: Optional[str] = None
        self._nodes: List[WorkflowNode] = []
        self._structure: Optional[Structure] = None

    # ========== 核心方法 ==========

    def set_calculator(self, calculator: Calculator) -> "WorkflowBuilder":
        """设置计算器（所有节点共享）"""
        self._calculator = calculator
        return self

    def add(
        self,
        node_id: str,
        workflow_type: WorkflowType,
        params: Optional[Dict[str, Any]] = None,
        depends_on: Optional[List[str]] = None,
    ) -> "WorkflowBuilder":
        """
        添加节点（支持多依赖，用于并行 DAG）

        Args:
            node_id: 节点唯一标识
            workflow_type: 工作流类型
            params: 计算参数
            depends_on: 依赖的 node_id 列表（支持多个）

        Returns:
            self
        """
        node = WorkflowNode(
            node_id=node_id,
            calculator=self._get_calculator(),
            workflow_type=workflow_type,
            params=params or {},
            dependencies=depends_on or [],
        )
        # calculator_type 由 node.__post_init__ 自动设置
        self._nodes.append(node)
        self.graph.add_node(node)
        self._last_node_id = node_id
        return self

    # ========== 便捷方法（线性链，自动依赖上一个节点） ==========
    def relax(
        self,
        structure: Optional[Structure] = None,
        fmax: float = 0.05,
        steps: int = 200,
        **kwargs,
    ) -> "WorkflowBuilder":
        """添加 relax 节点（线性链）"""
        if structure is not None:
            self._structure = structure
        node_id = f"relax_{len(self._nodes) + 1:03d}"
        params = {"fmax": fmax, "steps": steps, **kwargs}
        deps = [self._last_node_id] if self._last_node_id else []
        return self.add(node_id, WorkflowType.RELAX, params, deps)

    def static(self, **kwargs) -> "WorkflowBuilder":
        """添加静态计算节点（线性链）"""
        node_id = f"static_{len(self._nodes) + 1:03d}"
        deps = [self._last_node_id] if self._last_node_id else []
        return self.add(node_id, WorkflowType.SINGLE_POINT, kwargs, deps)

    def dos(self, nedos: int = 5000, **kwargs) -> "WorkflowBuilder":
        """添加 DOS 计算节点（线性链）"""
        node_id = f"dos_{len(self._nodes) + 1:03d}"
        params = {"nedos": nedos, **kwargs}
        deps = [self._last_node_id] if self._last_node_id else []
        return self.add(node_id, WorkflowType.DOS, params, deps)

    def band(self, symmetry_path: str = "G-X-W-K", **kwargs) -> "WorkflowBuilder":
        """添加能带计算节点（线性链）"""
        node_id = f"band_{len(self._nodes) + 1:03d}"
        params = {"symmetry_path": symmetry_path, **kwargs}
        deps = [self._last_node_id] if self._last_node_id else []
        return self.add(node_id, WorkflowType.BAND_STRUCTURE, params, deps)

    def eos(
        self,
        scale_factors: Optional[List[float]] = None,
        **kwargs,
    ) -> "WorkflowBuilder":
        """添加 EOS 计算节点（线性链）"""
        node_id = f"eos_{len(self._nodes) + 1:03d}"
        params = {
            "scale_factors": scale_factors or [0.94, 0.96, 0.98, 1.00, 1.02, 1.04, 1.06],
            **kwargs,
        }
        deps = [self._last_node_id] if self._last_node_id else []
        return self.add(node_id, WorkflowType.EOS, params, deps)

    def forces(self, **kwargs) -> "WorkflowBuilder":
        """添加受力计算节点（线性链）"""
        node_id = f"forces_{len(self._nodes) + 1:03d}"
        deps = [self._last_node_id] if self._last_node_id else []
        return self.add(node_id, WorkflowType.FORCES, kwargs, deps)

    def aimd(self, temperature: int = 1000, steps: int = 1000, **kwargs) -> "WorkflowBuilder":
        """添加 AIMD 节点（线性链）"""
        node_id = f"aimd_{len(self._nodes) + 1:03d}"
        params = {"temperature": temperature, "steps": steps, **kwargs}
        deps = [self._last_node_id] if self._last_node_id else []
        return self.add(node_id, WorkflowType.AIMD, params, deps)

    def neb(self, num_images: int = 5, **kwargs) -> "WorkflowBuilder":
        """添加 NEB 节点（线性链）"""
        node_id = f"neb_{len(self._nodes) + 1:03d}"
        params = {"num_images": num_images, **kwargs}
        deps = [self._last_node_id] if self._last_node_id else []
        return self.add(node_id, WorkflowType.NEB, params, deps)

    def phonon(self, **kwargs) -> "WorkflowBuilder":
        """添加声子计算节点（线性链）"""
        node_id = f"phonon_{len(self._nodes) + 1:03d}"
        deps = [self._last_node_id] if self._last_node_id else []
        return self.add(node_id, WorkflowType.PHONON, kwargs, deps)

    # ========== 显式依赖控制 ==========
    def depends_on(self, node_id: str) -> "WorkflowBuilder":
        """
        显式设置当前最后一个节点依赖某个节点
        用于在链式构建中插入额外依赖

        示例：
            builder.relax(...).static().depends_on("another_node").dos()
        """
        if self._last_node_id:
            self.graph.add_dependency(node_id, self._last_node_id)
        return self

    # ========== 构建 ==========
    def get_structure(self) -> Optional[Structure]:
        """获取当前存储的结构"""
        return self._structure

    def _get_calculator(self) -> Calculator:
        if self._calculator is None:
            raise ValueError("Calculator not set. Call set_calculator() first.")
        return self._calculator

    def build(self) -> WorkflowGraph:
        """构建并返回工作流图（验证 DAG）"""
        valid, error = self.graph.validate_dag()
        if not valid:
            raise ValueError(f"Invalid DAG: {error}")
        return self.graph