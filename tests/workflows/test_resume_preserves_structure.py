"""验证 Resume 后 Structure 类型正确"""

import asyncio
import pytest
from pymatgen.core import Structure, Lattice

from masgent.workflows import WorkflowBuilder, WorkflowScheduler, WorkflowCheckpointManager
from tests.conftest import wait_until


@pytest.mark.asyncio
async def test_resume_preserves_structure(tmp_path, vasp_calc, task_runner):
    """验证 checkpoint 恢复后 result.data["structure"] 仍是 Structure 对象"""
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_manager = WorkflowCheckpointManager(checkpoint_dir)

    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])

    workflow = (WorkflowBuilder("test")
        .set_calculator(vasp_calc)
        .relax(structure, steps=5)
        .static()
        .build()
    )
    graph_id = workflow.graph_id

    scheduler = WorkflowScheduler(
        task_runner,
        max_concurrent=1,
        checkpoint_manager=checkpoint_manager,
    )
    handle = await scheduler.submit(workflow, structure)

    # 等待 relax 完成
    await wait_until(
        lambda: (checkpoint_dir / graph_id / "nodes" / "relax_001.json").exists(),
        timeout=30.0
    )

    # 取消并等待清理
    handle.cancel()
    await asyncio.sleep(0.5)
    del scheduler
    del handle

    # 加载检查点
    graph = await checkpoint_manager.load_checkpoint(graph_id)
    relax_node = graph.nodes["relax_001"]

    # 验证 structure 是真正的 Structure 对象
    assert relax_node.result is not None
    assert "structure" in relax_node.result.data
    assert isinstance(relax_node.result.data["structure"], Structure)
    assert relax_node.result.data["structure"].composition.reduced_formula == "Si"