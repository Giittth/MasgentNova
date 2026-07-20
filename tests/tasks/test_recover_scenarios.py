"""TaskRunner.recover() 场景测试

测试 recover 在任务运行中、已完成、失败三种场景下的行为。
其中 running 场景模拟 TaskRunner 进程崩溃但外部计算进程仍存活。
"""

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
    """确保 VaspCalculator 已注册（recover 依赖 registry）"""
    from masgent.calculators.registry import CalculatorRegistry
    if not CalculatorRegistry._factories.get("vasp"):
        CalculatorRegistry.register("vasp", VaspCalculator)
    yield


@pytest.mark.asyncio
async def test_recover_running_task_to_completion(tmp_path):
    """
    场景1：任务运行中，TaskRunner 崩溃（内存丢失），但外部进程仍运行 → recover 接管并完成

    关键：不取消 asyncio 任务，只清空 runner 内部状态，
    模拟进程崩溃但子进程继续运行的真实场景。
    """
    fake_vasp = Path(__file__).parent.parent.parent / "src/masgent/scripts/fake_vasp.sh"
    assert fake_vasp.exists()

    store = JSONTaskStore(tmp_path / "tasks")
    registry = CalculatorRegistry()
    # 使用 5 秒运行，足够 recover 接管
    executor = LocalExecutor(aliases={
        "vasp_std": f"{fake_vasp} 5 0"
    })

    calc = VaspCalculator(
        executor=executor,
        workdir_manager=WorkDirManager(base_dir=tmp_path / "runs"),
        vasp_command="vasp_std",
    )

    # Phase 1: 提交任务
    runner1 = TaskRunner(store, registry)
    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])
    info = await runner1.submit(calc, structure, WorkflowType.SINGLE_POINT)

    # 等待进入 RUNNING（确保子进程已启动）
    await wait_until(
        lambda: store.load(info.task_id).status == TaskStatus.RUNNING,
        timeout=10.0
    )

    # 额外等待，确保子进程稳定运行
    await asyncio.sleep(0.5)

    # Phase 2: 模拟 TaskRunner 崩溃
    # 注意：不取消协程！只清空内部状态，模拟内存丢失
    runner1._running_tasks.clear()
    runner1._executors.clear()
    del runner1
    await asyncio.sleep(0.1)

    # Phase 3: 恢复（新 runner 应接管运行中的任务）
    runner2 = TaskRunner(store, registry)
    await runner2.recover()

    # 等待完成（recover 接管后应继续轮询直到完成）
    await wait_until(
        lambda: store.load(info.task_id).status == TaskStatus.COMPLETED,
        timeout=30.0
    )

    # 验证结果
    result = await runner2.collect(info.task_id)
    assert result is not None
    assert "energy" in result["data"]
    assert abs(result["data"]["energy"] - (-10.532)) < 0.001


@pytest.mark.asyncio
async def test_recover_completed_task_does_not_rerun(tmp_path):
    """场景2：任务已完成 → recover 不重复提交"""
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

    runner1 = TaskRunner(store, registry)
    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])
    info = await runner1.submit(calc, structure, WorkflowType.SINGLE_POINT)

    await wait_until(
        lambda: store.load(info.task_id).status == TaskStatus.COMPLETED,
        timeout=30.0
    )

    # 模拟重启
    runner1._running_tasks.clear()
    runner1._executors.clear()
    del runner1

    runner2 = TaskRunner(store, registry)
    await runner2.recover()

    record = store.load(info.task_id)
    assert record.status == TaskStatus.COMPLETED
    assert info.task_id not in runner2._running_tasks


@pytest.mark.asyncio
async def test_recover_failed_task_does_not_restart(tmp_path):
    """场景3：任务失败 → recover 不重启"""
    fake_vasp = Path(__file__).parent.parent.parent / "src/masgent/scripts/fake_vasp.sh"
    assert fake_vasp.exists()

    store = JSONTaskStore(tmp_path / "tasks")
    registry = CalculatorRegistry()
    executor = LocalExecutor(aliases={
        "vasp_std": f"{fake_vasp} 2 1"  # 模拟失败
    })

    calc = VaspCalculator(
        executor=executor,
        workdir_manager=WorkDirManager(base_dir=tmp_path / "runs"),
        vasp_command="vasp_std",
    )

    runner1 = TaskRunner(store, registry)
    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])
    info = await runner1.submit(calc, structure, WorkflowType.SINGLE_POINT)

    await wait_until(
        lambda: store.load(info.task_id).status == TaskStatus.FAILED,
        timeout=30.0
    )

    # 模拟重启
    runner1._running_tasks.clear()
    runner1._executors.clear()
    del runner1

    runner2 = TaskRunner(store, registry)
    await runner2.recover()

    record = store.load(info.task_id)
    assert record.status == TaskStatus.FAILED
    assert info.task_id not in runner2._running_tasks


@pytest.mark.asyncio
async def test_recover_finished_process_with_result(tmp_path):
    """
    场景4：外部进程已结束且结果存在，但 TaskRunner 崩溃（未 collect）
    recover 应直接收集结果，标记为 COMPLETED

    关键：等待 OUTCAR 生成（进程完成），但不等待 TaskStatus 变为 COMPLETED
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

    # Phase 1: 提交任务
    runner1 = TaskRunner(store, registry)
    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])
    info = await runner1.submit(calc, structure, WorkflowType.SINGLE_POINT)

    work_dir = Path(info.work_dir)

    # 等待外部进程完成（OUTCAR 生成），但 runner1 尚未收集结果
    # 注意：这里不等待 TaskStatus.COMPLETED，只等待文件生成
    await wait_until(
        lambda: (
            work_dir.exists()
            and (work_dir / "OUTCAR").exists()
            and (work_dir / "vasprun.xml").exists()
        ),
        timeout=30.0
    )

    # 验证：此时任务状态可能还是 RUNNING（poll 还没来得及更新）
    record = store.load(info.task_id)
    assert record.status in (TaskStatus.RUNNING, TaskStatus.PENDING)

    # Phase 2: 模拟 TaskRunner 崩溃（内存丢失），但结果文件已存在
    runner1._running_tasks.clear()
    runner1._executors.clear()
    del runner1
    await asyncio.sleep(0.1)

    # Phase 3: 恢复
    runner2 = TaskRunner(store, registry)
    await runner2.recover()

    # recover 应检测到 COMPLETED（因为文件存在）并保存结果
    record = store.load(info.task_id)
    assert record.status == TaskStatus.COMPLETED
    assert record.result is not None
    assert "energy" in record.result["data"]
    assert abs(record.result["data"]["energy"] - (-10.532)) < 0.001