#!/usr/bin/env python3
"""VaspCalculator 单元测试（使用 FakeExecutor，不需要真实 VASP）"""

import pytest
from pathlib import Path

from pymatgen.core import Lattice, Structure

from masgent.calculators import VaspCalculator
from masgent.calculators.helpers import run_blocking
from masgent.executors.base import Executor
from masgent.models.executor import CommandResult
from masgent.models.job import JobHandle
from masgent.models.enums import WorkflowType
from masgent.utils.workdir_manager import WorkDirManager


class FakeExecutor(Executor):
    """模拟执行器：不实际运行 VASP，生成假输出文件"""

    def __init__(self, success: bool = True, energy: float = -10.5, returncode: int = 0):
        self.success = success
        self.energy = energy
        self.returncode = returncode
        self._called = False
        self._running = False
        self._job_id = "fake-job-123"

    # ========== 实现所有抽象方法 ==========

    async def spawn(self, work_dir: Path, command: str, env=None) -> JobHandle:
        """模拟启动进程"""
        self._called = True
        self._running = True
        # 生成输入文件（如果有 prepare 的话，但这里由调用方负责）
        return JobHandle(
            job_id=self._job_id,
            backend="fake",
            pid=12345,
            submitted_at=JobHandle.now(),
        )

    async def is_running(self, job_id: str, pid: int = None) -> bool:
        """模拟检查运行状态"""
        return self._running

    async def wait(self, job_id: str, timeout: int = None) -> int:
        """模拟等待进程结束"""
        self._running = False
        return self.returncode

    async def kill(self, job_id: str) -> bool:
        """模拟终止进程"""
        self._running = False
        return True

    async def run(self, work_dir: Path, command: str, env=None, timeout=None) -> CommandResult:
        """同步执行（兼容旧接口）"""
        self._called = True
        self._running = False

        # 生成 vasprun.xml（合法格式）
        vasprun_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<modeling>
    <calculation>
        <energy>
            <i name="e_fr_energy"> {self.energy:.8f}</i>
            <i name="e_wo_entrp"> {self.energy:.8f}</i>
        </energy>
    </calculation>
</modeling>"""
        (work_dir / "vasprun.xml").write_text(vasprun_content)

        # 生成 OUTCAR
        outcar_content = f"""
 free energy   TOTEN  =    {self.energy:.8f} eV
 General timing and accounting informations
"""
        (work_dir / "OUTCAR").write_text(outcar_content)

        # 生成 CONTCAR（复制 POSCAR，模拟优化结构）
        if (work_dir / "POSCAR").exists():
            (work_dir / "CONTCAR").write_text((work_dir / "POSCAR").read_text())

        # COMPLETED 标记由 VaspCalculator 写入，这里不写

        return CommandResult(
            returncode=self.returncode,
            stdout="VASP finished",
            stderr="",
        )

    def health_check(self):
        return True, "FakeExecutor always available"

    def get_info(self):
        return {"name": "FakeExecutor", "available": True}


@pytest.fixture
def fake_executor():
    return FakeExecutor(success=True, energy=-10.5)


@pytest.fixture
def fake_executor_fail():
    return FakeExecutor(success=False, energy=0.0, returncode=1)


@pytest.fixture
def si_structure():
    lattice = Lattice.cubic(5.43)
    return Structure(lattice, ["Si"], [[0.0, 0.0, 0.0]])


@pytest.mark.asyncio
async def test_vasp_calculator_compute_energy_success(tmp_path, fake_executor, si_structure):
    calc = VaspCalculator(
        executor=fake_executor,
        workdir_manager=WorkDirManager(base_dir=tmp_path),
        vasp_command="vasp_std",
    )

    result = await calc.compute_energy(si_structure)

    assert result.success is True
    assert result.data["energy"] == -10.5
    assert "work_dir" in result.data
    assert fake_executor._called is True

    work_dir = Path(result.data["work_dir"])
    assert work_dir.exists()
    for f in ["POSCAR", "INCAR", "KPOINTS", "POTCAR.spec"]:
        assert (work_dir / f).exists()
    assert (work_dir / "COMPLETED").exists()


@pytest.mark.asyncio
async def test_vasp_calculator_compute_energy_failure(tmp_path, fake_executor_fail, si_structure):
    calc = VaspCalculator(
        executor=fake_executor_fail,
        workdir_manager=WorkDirManager(base_dir=tmp_path),
        vasp_command="vasp_std",
    )

    result = await calc.compute_energy(si_structure)

    assert result.success is False
    assert "failed" in result.error_message.lower()
    assert fake_executor_fail._called is True


@pytest.mark.asyncio
async def test_vasp_calculator_compute_energy_cached(tmp_path, fake_executor, si_structure):
    """第一次执行 → 写入 COMPLETED → 第二次不调用 Executor"""
    calc = VaspCalculator(
        executor=fake_executor,
        workdir_manager=WorkDirManager(base_dir=tmp_path),
        vasp_command="vasp_std",
    )

    # 第一次：执行计算
    result1 = await calc.compute_energy(si_structure)
    assert result1.success is True
    assert fake_executor._called is True

    # 重置调用计数
    fake_executor._called = False

    # 第二次：应该命中缓存（COMPLETED + OUTCAR 均正常）
    result2 = await calc.compute_energy(si_structure)
    assert result2.success is True
    assert result2.data["energy"] == result1.data["energy"]
    assert fake_executor._called is False
    assert result2.metadata.get("cached") is True


@pytest.mark.asyncio
async def test_vasp_calculator_prepare_inputs(tmp_path, fake_executor, si_structure):
    calc = VaspCalculator(
        executor=fake_executor,
        workdir_manager=WorkDirManager(base_dir=tmp_path),
        vasp_command="vasp_std",
    )

    work_dir = await run_blocking(
        lambda: calc._prepare_inputs(si_structure, WorkflowType.SINGLE_POINT)
    )

    assert work_dir.exists()
    for f in ["POSCAR", "INCAR", "KPOINTS", "POTCAR.spec"]:
        assert (work_dir / f).exists()

    potcar_spec = work_dir / "POTCAR.spec"
    assert "Si" in potcar_spec.read_text()


@pytest.mark.asyncio
async def test_vasp_calculator_fingerprint_with_params(tmp_path, fake_executor, si_structure):
    calc1 = VaspCalculator(
        executor=fake_executor,
        workdir_manager=WorkDirManager(base_dir=tmp_path / "calc1"),
        vasp_command="vasp_std",
        incar_template={"ENCUT": 520},
    )
    calc2 = VaspCalculator(
        executor=fake_executor,
        workdir_manager=WorkDirManager(base_dir=tmp_path / "calc2"),
        vasp_command="vasp_std",
        incar_template={"ENCUT": 600},
    )

    dir1 = await run_blocking(lambda: calc1._prepare_inputs(si_structure, WorkflowType.SINGLE_POINT))
    dir2 = await run_blocking(lambda: calc2._prepare_inputs(si_structure, WorkflowType.SINGLE_POINT))

    assert str(dir1) != str(dir2)


@pytest.mark.asyncio
async def test_vasp_calculator_health_check(fake_executor):
    calc = VaspCalculator(executor=fake_executor, vasp_command="vasp_std")
    health = calc.health_check()
    assert health["healthy"] is True
    assert health["status"] == "ok"


@pytest.mark.asyncio
async def test_vasp_calculator_relax_returns_structure(tmp_path, fake_executor, si_structure):
    """测试 relax 返回能量 + CONTCAR 结构"""
    calc = VaspCalculator(
        executor=fake_executor,
        workdir_manager=WorkDirManager(base_dir=tmp_path),
        vasp_command="vasp_std",
    )

    result = await calc.relax(si_structure, fmax=0.05, steps=100)

    assert result.success is True
    assert result.data["energy"] is not None
    assert result.data["structure"] is not None

    # 验证结构类型
    from pymatgen.core import Structure
    assert isinstance(result.data["structure"], Structure)
    assert len(result.data["structure"]) == len(si_structure)


@pytest.mark.asyncio
async def test_vasp_calculator_completed_skip_execute(tmp_path, fake_executor, si_structure):
    """第二次调用不执行 Executor（COMPLETED + OUTCAR 双保险）"""
    calc = VaspCalculator(
        executor=fake_executor,
        workdir_manager=WorkDirManager(base_dir=tmp_path),
        vasp_command="vasp_std",
    )

    # 第一次：执行
    await calc.compute_energy(si_structure)
    assert fake_executor._called is True

    # 重置
    fake_executor._called = False

    # 第二次：跳过
    await calc.compute_energy(si_structure)
    assert fake_executor._called is False


@pytest.mark.asyncio
async def test_vasp_calculator_relax_params_in_fingerprint(tmp_path, fake_executor, si_structure):
    calc = VaspCalculator(
        executor=fake_executor,
        workdir_manager=WorkDirManager(base_dir=tmp_path),
        vasp_command="vasp_std",
    )

    dir1 = await run_blocking(lambda: calc._prepare_inputs(si_structure, WorkflowType.RELAX, fmax=0.05, steps=100))
    dir2 = await run_blocking(lambda: calc._prepare_inputs(si_structure, WorkflowType.RELAX, fmax=0.01, steps=200))

    assert str(dir1) != str(dir2)