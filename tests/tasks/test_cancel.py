"""TaskRunner.cancel() 集成测试 —— 验证真正 kill 子进程"""

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
async def test_cancel_kills_subprocess(tmp_path):
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

    record = store.load(info.task_id)
    assert record.job_handle is not None
    job_id = record.job_handle["job_id"]
    pid = record.job_handle.get("pid")

    assert await executor.is_running(job_id, pid) is True

    result = await runner.cancel(info.task_id)
    assert result is True

    await asyncio.sleep(1)

    assert await executor.is_running(job_id, pid) is False

    record = store.load(info.task_id)
    assert record.status == TaskStatus.CANCELLED