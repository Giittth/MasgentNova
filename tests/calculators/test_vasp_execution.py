"""VaspCalculator + LocalExecutor 完整执行测试（使用 fake_vasp）"""

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
    """确保 VaspCalculator 已注册（用于 recover 测试）"""
    from masgent.calculators.registry import CalculatorRegistry
    if not CalculatorRegistry._factories.get("vasp"):
        CalculatorRegistry.register("vasp", VaspCalculator)
    yield


@pytest.mark.asyncio
async def test_vasp_complete_execution_cycle(tmp_path):
    """测试 1：完整执行链路（fake_vasp 正常完成）"""
    fake_vasp = Path(__file__).parent.parent.parent / "src/masgent/scripts/fake_vasp.sh"
    assert fake_vasp.exists(), f"fake_vasp.sh not found at {fake_vasp}"

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
    info = await runner.submit(calc, structure, WorkflowType.SINGLE_POINT)

    await wait_until(
        lambda: store.load(info.task_id).status == TaskStatus.COMPLETED,
        timeout=30.0
    )

    result = await runner.collect(info.task_id)
    assert result is not None
    assert "energy" in result["data"]
    assert abs(result["data"]["energy"] - (-10.532)) < 0.001


@pytest.mark.asyncio
async def test_vasp_execution_failure(tmp_path):
    """测试 2：fake_vasp 失败（EXIT_CODE=1）"""
    fake_vasp = Path(__file__).parent.parent.parent / "src/masgent/scripts/fake_vasp.sh"
    assert fake_vasp.exists()

    executor = LocalExecutor(aliases={
        "vasp_std": f"{fake_vasp} 2 1"
    })

    store = JSONTaskStore(tmp_path / "tasks")
    registry = CalculatorRegistry()

    calc = VaspCalculator(
        executor=executor,
        workdir_manager=WorkDirManager(base_dir=tmp_path / "runs"),
        vasp_command="vasp_std",
    )
    runner = TaskRunner(store, registry)

    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])
    info = await runner.submit(calc, structure, WorkflowType.SINGLE_POINT)

    await wait_until(
        lambda: store.load(info.task_id).status == TaskStatus.FAILED,
        timeout=30.0
    )

    record = store.load(info.task_id)
    assert record.status == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_vasp_json_recovery(tmp_path):
    """
    测试 3：JSON 恢复（不依赖进程跨实例恢复）
    
    场景：
        1. 提交任务，等待完成
        2. 创建新 TaskRunner（使用同一 store）
        3. recover() 读取 JSON，发现任务已完成
        4. 直接收集结果
    
    这是 LocalExecutor 能支持的真实恢复场景。
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

    # ===== Phase 1: 提交并完成 =====
    runner1 = TaskRunner(store, registry)
    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])
    info = await runner1.submit(calc, structure, WorkflowType.SINGLE_POINT)

    await wait_until(
        lambda: store.load(info.task_id).status == TaskStatus.COMPLETED,
        timeout=30.0
    )

    # 验证结果已保存
    record = store.load(info.task_id)
    assert record.result is not None
    assert "energy" in record.result["data"]

    # ===== Phase 2: 模拟重启 =====
    # 取消 runner1 的任务（避免影响）
    for t in runner1._running_tasks.values():
        t.cancel()
    await asyncio.sleep(0.1)
    del runner1

    # ===== Phase 3: 恢复 =====
    runner2 = TaskRunner(store, registry)
    await runner2.recover()

    # 验证任务状态不变，结果未丢失
    record = store.load(info.task_id)
    assert record.status == TaskStatus.COMPLETED
    assert record.result is not None
    assert "energy" in record.result["data"]
    assert abs(record.result["data"]["energy"] - (-10.532)) < 0.001