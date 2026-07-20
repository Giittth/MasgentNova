"""WorkflowScheduler 单元测试"""

import pytest
import asyncio
from pathlib import Path
from pymatgen.core import Structure, Lattice

from masgent.calculators.vasp import VaspCalculator
from masgent.executors.local import LocalExecutor
from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry
from masgent.utils.workdir_manager import WorkDirManager
from masgent.workflows import WorkflowBuilder, WorkflowScheduler
from masgent.models.enums import WorkflowType
from tests.conftest import wait_until


@pytest.fixture(autouse=True)
def ensure_vasp_registered():
    from masgent.calculators.registry import CalculatorRegistry
    if not CalculatorRegistry._factories.get("vasp"):
        CalculatorRegistry.register("vasp", VaspCalculator)
    yield


@pytest.mark.asyncio
async def test_scheduler_single_node(tmp_path):
    """测试单节点执行"""
    fake_vasp = Path(__file__).parent.parent.parent / "src/masgent/scripts/fake_vasp.sh"
    assert fake_vasp.exists()

    store = JSONTaskStore(tmp_path / "tasks")
    registry = CalculatorRegistry()
    executor = LocalExecutor(aliases={"vasp_std": str(fake_vasp)})
    calc = VaspCalculator(
        executor=executor,
        workdir_manager=WorkDirManager(base_dir=tmp_path / "runs"),
        vasp_command="vasp_std",
    )
    runner = TaskRunner(store, registry)

    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])

    # 构建单节点工作流
    workflow = (WorkflowBuilder("test_single")
        .set_calculator(calc)
        .static()
        .build()
    )

    scheduler = WorkflowScheduler(runner, max_concurrent=1)
    results = await scheduler.run(workflow, structure)

    assert "static_001" in results
    assert results["static_001"].success is True
    assert "energy" in results["static_001"].data


@pytest.mark.asyncio
async def test_scheduler_chain(tmp_path):
    """测试链式 DAG: relax → static → dos"""
    fake_vasp = Path(__file__).parent.parent.parent / "src/masgent/scripts/fake_vasp.sh"
    assert fake_vasp.exists()

    store = JSONTaskStore(tmp_path / "tasks")
    registry = CalculatorRegistry()
    executor = LocalExecutor(aliases={"vasp_std": str(fake_vasp)})
    calc = VaspCalculator(
        executor=executor,
        workdir_manager=WorkDirManager(base_dir=tmp_path / "runs"),
        vasp_command="vasp_std",
    )
    runner = TaskRunner(store, registry)

    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])

    workflow = (WorkflowBuilder("test_chain")
        .set_calculator(calc)
        .relax(structure, fmax=0.05, steps=100)
        .static()
        .dos(nedos=5000)
        .build()
    )

    scheduler = WorkflowScheduler(runner, max_concurrent=1)
    results = await scheduler.run(workflow, structure)

    assert "relax_001" in results
    assert "static_002" in results
    assert "dos_003" in results
    assert results["relax_001"].success is True
    assert results["static_002"].success is True
    assert results["dos_003"].success is True


@pytest.mark.asyncio
async def test_scheduler_parallel(tmp_path):
    """测试并行 DAG: A → (B, C) → D"""
    fake_vasp = Path(__file__).parent.parent.parent / "src/masgent/scripts/fake_vasp.sh"
    assert fake_vasp.exists()

    store = JSONTaskStore(tmp_path / "tasks")
    registry = CalculatorRegistry()
    executor = LocalExecutor(aliases={"vasp_std": str(fake_vasp)})
    calc = VaspCalculator(
        executor=executor,
        workdir_manager=WorkDirManager(base_dir=tmp_path / "runs"),
        vasp_command="vasp_std",
    )
    runner = TaskRunner(store, registry)

    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])

    # 手动构建并行 DAG（Builder 目前只支持线性链，需要手动添加）
    from masgent.workflows import WorkflowGraph, WorkflowNode

    graph = WorkflowGraph("test_parallel")

    node_a = WorkflowNode("A", calc, WorkflowType.SINGLE_POINT)
    node_b = WorkflowNode("B", calc, WorkflowType.SINGLE_POINT, dependencies=["A"])
    node_c = WorkflowNode("C", calc, WorkflowType.SINGLE_POINT, dependencies=["A"])
    node_d = WorkflowNode("D", calc, WorkflowType.SINGLE_POINT, dependencies=["B", "C"])

    # 存储 structure
    node_a.structure = structure

    graph.add_node(node_a).add_node(node_b).add_node(node_c).add_node(node_d)

    scheduler = WorkflowScheduler(runner, max_concurrent=2)
    results = await scheduler.run(graph)

    assert "A" in results and results["A"].success
    assert "B" in results and results["B"].success
    assert "C" in results and results["C"].success
    assert "D" in results and results["D"].success