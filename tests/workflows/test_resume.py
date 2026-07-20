"""Workflow Resume 集成测试"""

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
from masgent.workflows import WorkflowBuilder, WorkflowScheduler, WorkflowCheckpointManager
from masgent.workflows.node import NodeStatus
from masgent.workflows.status import WorkflowStatus
from tests.conftest import wait_until


@pytest.fixture(autouse=True)
def ensure_vasp_registered():
    from masgent.calculators.registry import CalculatorRegistry
    if not CalculatorRegistry._factories.get("vasp"):
        CalculatorRegistry.register("vasp", VaspCalculator)
    yield


@pytest.mark.asyncio
async def test_resume_after_crash(tmp_path):
    """
    场景：relax 已完成，static 未执行（模拟进程崩溃）
    恢复后应跳过 relax，继续执行 static
    """
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

    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_manager = WorkflowCheckpointManager(checkpoint_dir)

    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])

    # 创建工作流
    workflow = (WorkflowBuilder("test_resume")
        .set_calculator(calc)
        .relax(structure, steps=5)
        .static()
        .build()
    )
    graph_id = workflow.graph_id

    # 提交并等待 relax 完成
    scheduler = WorkflowScheduler(
        runner,
        max_concurrent=1,
        checkpoint_manager=checkpoint_manager,
    )
    handle = await scheduler.submit(workflow, structure)

    # 等待 relax 完成（检查点自动保存）
    await wait_until(
        lambda: (checkpoint_dir / graph_id / "nodes" / "relax_001.json").exists(),
        timeout=30.0
    )

    # 验证 checkpoint 中 relax 是 COMPLETED，static 是 PENDING
    graph = await checkpoint_manager.load_checkpoint(graph_id)
    assert graph.nodes["relax_001"].status == NodeStatus.COMPLETED
    assert graph.nodes["static_002"].status == NodeStatus.PENDING

    # 模拟崩溃：删除 scheduler 和 handle，不触发 cancel
    del handle
    del scheduler
    await asyncio.sleep(0.1)

    # 恢复
    scheduler2 = WorkflowScheduler(
        runner,
        max_concurrent=1,
        checkpoint_manager=checkpoint_manager,
    )
    handle2 = await scheduler2.resume(
        graph_id,
        calculators={"vasp": calc}
    )

    # 等待完成
    results = await handle2.wait(timeout=60)

    assert "relax_001" in results and results["relax_001"].success
    assert "static_002" in results and results["static_002"].success
    assert handle2.status() == WorkflowStatus.COMPLETED


@pytest.mark.asyncio
async def test_resume_cancelled_workflow_rejected(tmp_path):
    """
    场景：用户主动取消的工作流，不应被恢复
    """
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

    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_manager = WorkflowCheckpointManager(checkpoint_dir)

    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])

    workflow = (WorkflowBuilder("test_cancel")
        .set_calculator(calc)
        .relax(structure, steps=10)
        .static()
        .build()
    )
    graph_id = workflow.graph_id

    scheduler = WorkflowScheduler(
        runner,
        max_concurrent=1,
        checkpoint_manager=checkpoint_manager,
    )
    handle = await scheduler.submit(workflow, structure)

    # 等待 relax 完成
    await wait_until(
        lambda: (checkpoint_dir / graph_id / "nodes" / "relax_001.json").exists(),
        timeout=30.0
    )

    # 用户主动取消
    handle.cancel()
    await asyncio.sleep(0.5)

    # 验证工作流状态为 CANCELLED
    graph = await checkpoint_manager.load_checkpoint(graph_id)
    assert graph.status == WorkflowStatus.CANCELLED

    # 尝试恢复 → 应拒绝
    scheduler2 = WorkflowScheduler(
        runner,
        max_concurrent=1,
        checkpoint_manager=checkpoint_manager,
    )
    with pytest.raises(RuntimeError, match="CANCELLED and cannot be resumed"):
        await scheduler2.resume(graph_id, calculators={"vasp": calc})