"""测试取消后 collect 行为"""

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
from masgent.models.enums import WorkflowType, TaskStatus
from tests.conftest import wait_until


@pytest.fixture(autouse=True)
def ensure_vasp_registered():
    from masgent.calculators.registry import CalculatorRegistry
    if not CalculatorRegistry._factories.get("vasp"):
        CalculatorRegistry.register("vasp", VaspCalculator)
    yield


@pytest.mark.asyncio
async def test_collect_cancelled_task(tmp_path):
    """验证取消后 collect 返回 None"""
    fake_vasp = Path(__file__).parent.parent.parent / "src/masgent/scripts/fake_vasp.sh"
    assert fake_vasp.exists()

    store = JSONTaskStore(tmp_path / "tasks")
    registry = CalculatorRegistry()
    executor = LocalExecutor(aliases={
        "vasp_std": f"{fake_vasp} 60 0"
    })

    calc = VaspCalculator(
        executor=executor,
        workdir_manager=WorkDirManager(base_dir=tmp_path / "runs"),
        vasp_command="vasp_std",
    )
    runner = TaskRunner(store, registry)

    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])
    info = await runner.submit(calc, structure, WorkflowType.SINGLE_POINT)

    await wait_until(
        lambda: store.load(info.task_id).status == TaskStatus.RUNNING,
        timeout=10.0
    )

    # 取消任务
    result = await runner.cancel(info.task_id)
    assert result is True

    await asyncio.sleep(0.5)

    # 验证状态为 CANCELLED
    record = store.load(info.task_id)
    assert record.status == TaskStatus.CANCELLED

    # collect 应返回 None（无结果）
    collect_result = await runner.collect(info.task_id)
    assert collect_result is None