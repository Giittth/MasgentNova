"""VaspCalculator RELAX 工作流测试"""

import pytest
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
async def test_relax_returns_structure(tmp_path):
    """验证 RELAX 工作流返回优化后的 Structure"""
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
    info = await runner.submit(
        calc,
        structure,
        WorkflowType.RELAX,
        fmax=0.05,
        steps=100,
    )

    # 等待任务结束（COMPLETED 或 FAILED）
    await wait_until(
        lambda: (
            store.load(info.task_id) is not None
            and store.load(info.task_id).status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
        ),
        timeout=30.0
    )

    # 检查记录是否仍然存在
    record = store.load(info.task_id)
    assert record is not None, f"Task record {info.task_id} disappeared after execution!"

    # 如果任务失败，打印错误信息并失败
    if record.status == TaskStatus.FAILED:
        pytest.fail(f"Task failed with error: {record.error_message}")

    # 收集结果
    result = await runner.collect(info.task_id)
    assert result is not None
    assert "energy" in result["data"]
    assert "structure" in result["data"]

    struct = result["data"]["structure"]
    assert isinstance(struct, Structure)
    # 使用 reduced_formula 更稳定
    assert struct.composition.reduced_formula == "Si"
    assert len(struct) == len(structure)


@pytest.mark.asyncio
async def test_relax_workflow_params_in_fingerprint(tmp_path):
    """验证 RELAX 参数 (fmax, steps) 会影响工作目录指纹"""
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

    info1 = await runner.submit(calc, structure, WorkflowType.RELAX, fmax=0.05, steps=100)
    info2 = await runner.submit(calc, structure, WorkflowType.RELAX, fmax=0.01, steps=200)

    # 等待两个任务完成
    for info in [info1, info2]:
        await wait_until(
            lambda: (
                store.load(info.task_id) is not None
                and store.load(info.task_id).status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
            ),
            timeout=30.0
        )
        record = store.load(info.task_id)
        assert record is not None, f"Task record {info.task_id} disappeared!"
        if record.status == TaskStatus.FAILED:
            pytest.fail(f"Task {info.task_id} failed with error: {record.error_message}")

    record1 = store.load(info1.task_id)
    record2 = store.load(info2.task_id)

    assert record1.work_dir != record2.work_dir