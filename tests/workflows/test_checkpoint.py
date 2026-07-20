"""WorkflowCheckpointManager 单元测试"""

import pytest
import asyncio
from pathlib import Path
from pymatgen.core import Structure, Lattice

from masgent.workflows import WorkflowBuilder, WorkflowScheduler, WorkflowCheckpointManager
from masgent.workflows.status import WorkflowStatus
from tests.conftest import wait_until


@pytest.mark.asyncio
async def test_checkpoint_save_load(tmp_path, vasp_calc, task_runner):
    """验证检查点保存和加载"""
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_manager = WorkflowCheckpointManager(checkpoint_dir)

    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])

    # 创建工作流
    workflow = (WorkflowBuilder("test")
        .set_calculator(vasp_calc)
        .relax(structure, steps=5)
        .static()
        .build()
    )

    # 保存检查点
    await checkpoint_manager.save_checkpoint(workflow)

    # 验证文件存在
    graph_id = workflow.graph_id
    assert checkpoint_manager.checkpoint_exists(graph_id)
    assert (checkpoint_dir / graph_id / "graph.json").exists()
    assert (checkpoint_dir / graph_id / "nodes" / "relax_001.json").exists()

    # 加载检查点
    loaded_graph = await checkpoint_manager.load_checkpoint(graph_id)
    assert loaded_graph is not None
    assert loaded_graph.graph_id == graph_id
    assert loaded_graph.name == "test"
    assert len(loaded_graph.nodes) == 2


@pytest.mark.asyncio
async def test_scheduler_auto_checkpoint(tmp_path, vasp_calc, task_runner):
    """验证 Scheduler 自动保存检查点"""
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_manager = WorkflowCheckpointManager(checkpoint_dir)

    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])

    workflow = (WorkflowBuilder("test")
        .set_calculator(vasp_calc)
        .relax(structure, steps=5)
        .static()
        .build()
    )

    scheduler = WorkflowScheduler(
        task_runner,
        max_concurrent=1,
        checkpoint_manager=checkpoint_manager
    )

    graph_id = workflow.graph_id
    handle = await scheduler.submit(workflow, structure)

    # 等待完成
    await handle.wait(timeout=60)

    # 验证检查点已保存
    assert checkpoint_manager.checkpoint_exists(graph_id)

    # 验证 graph.json 中的状态
    graph_path = checkpoint_dir / graph_id / "graph.json"
    import json
    with open(graph_path, "r") as f:
        data = json.load(f)
    assert data["status"] == "completed"