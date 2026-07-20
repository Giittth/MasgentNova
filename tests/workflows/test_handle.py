import pytest
import asyncio
from pymatgen.core import Structure, Lattice

from masgent.workflows import WorkflowBuilder, WorkflowScheduler
from masgent.workflows.status import WorkflowStatus


@pytest.mark.asyncio
async def test_handle_submit_and_wait(tmp_path, vasp_calc, task_runner):
    """测试 handle 的 submit 和 wait"""
    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])

    workflow = (
        WorkflowBuilder()
        .set_calculator(vasp_calc)
        .static()
        .build()
    )

    scheduler = WorkflowScheduler(task_runner)
    handle = await scheduler.submit(workflow, structure)

    assert handle.status() == WorkflowStatus.RUNNING

    results = await handle.wait(timeout=60)
    assert "static_001" in results
    assert results["static_001"].success

    assert handle.status() == WorkflowStatus.COMPLETED
    assert handle.progress() == (1, 1)


@pytest.mark.asyncio
async def test_handle_cancel(tmp_path, vasp_calc, task_runner):
    """测试 handle 的 cancel"""
    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])

    workflow = (
        WorkflowBuilder()
        .set_calculator(vasp_calc)
        .relax(structure, steps=1000)  # 长时间运行，给 cancel 留时间
        .build()
    )

    scheduler = WorkflowScheduler(task_runner, max_concurrent=1)
    handle = await scheduler.submit(workflow, structure)

    # 等待任务开始运行
    await asyncio.sleep(0.5)

    # 取消
    handle.cancel()

    # 等待取消完成
    with pytest.raises(asyncio.CancelledError):
        await handle.wait()

    assert handle.status() == WorkflowStatus.CANCELLED