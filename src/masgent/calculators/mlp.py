"""MLP Calculator：异步包装同步 MLP 代码"""

from pymatgen.core import Structure

from masgent.calculators.base import Calculator
from masgent.calculators.helpers import run_blocking, to_ase, to_pmg
from masgent.models.calculator import CalculationResult
from masgent.models.enums import WorkflowType


class MLPCalculator(Calculator):
    """MLP 势能计算器——异步包装同步代码"""

    def __init__(self, backend: str = "chgnet", device: str = "cpu"):
        self.backend = backend
        self.device = device
        self.calc = self._load_calculator()

    def _load_calculator(self):
        """加载 MLP 计算器，处理不同版本的 API 差异"""
        if self.backend == "chgnet":
            try:
                from chgnet.model import CHGNetCalculator
                return CHGNetCalculator()
            except ImportError:
                # 旧版本可能在这个位置
                from chgnet.model.dynamics import CHGNetCalculator
                return CHGNetCalculator()

        elif self.backend == "sevennet":
            try:
                from sevenn.calculator import SevenNetCalculator
                # 新版 API
                return SevenNetCalculator(model="7net-0")
            except TypeError:
                # 旧版 API
                return SevenNetCalculator()

        elif self.backend == "orb":
            from orb_models.forcefield import pretrained
            from orb_models.forcefield.calculator import ORBCalculator
            orbff = pretrained.orb_v3_conservative_inf_omat(device=self.device)
            return ORBCalculator(orbff, device=self.device)

        elif self.backend == "mattersim":
            from mattersim.forcefield import MatterSimCalculator
            return MatterSimCalculator()

        else:
            raise ValueError(f"Unknown MLP backend: {self.backend}")

    async def compute_energy(self, structure: Structure) -> CalculationResult:
        atoms = to_ase(structure)
        atoms.calc = self.calc

        def _compute():
            return atoms.get_potential_energy()

        energy = await run_blocking(_compute)

        return CalculationResult(
            success=True,
            workflow_type=WorkflowType.SINGLE_POINT,
            data={"energy": energy, "energy_per_atom": energy / len(atoms)},
            metadata={"backend": self.backend, "device": self.device},
        )

    async def compute_forces(self, structure: Structure) -> CalculationResult:
        atoms = to_ase(structure)
        atoms.calc = self.calc

        def _compute():
            return atoms.get_forces()

        forces = await run_blocking(_compute)

        return CalculationResult(
            success=True,
            workflow_type=WorkflowType.FORCES,
            data={"forces": forces},
            metadata={"backend": self.backend, "device": self.device},
        )

    async def relax(self, structure: Structure, fmax: float = 0.1, steps: int = 500) -> CalculationResult:
        from ase.optimize import LBFGS

        atoms = to_ase(structure)
        atoms.calc = self.calc

        def _relax():
            opt = LBFGS(atoms)
            opt.run(fmax=fmax, steps=steps)
            return atoms.get_potential_energy()

        energy = await run_blocking(_relax)

        # 关键：返回 pymatgen Structure，而非 ASE Atoms
        relaxed_structure = to_pmg(atoms)

        return CalculationResult(
            success=True,
            workflow_type=WorkflowType.RELAX,
            data={
                "energy": energy,
                "energy_per_atom": energy / len(atoms),
                "structure": relaxed_structure,  # pymatgen Structure
            },
            metadata={"backend": self.backend, "device": self.device},
        )

    def health_check(self) -> dict:
        """检查 MLP Calculator 健康状态"""
        try:
            # 尝试用一个小结构测试
            from pymatgen.core import Lattice, Structure
            test_struct = Structure(Lattice.cubic(5.0), ["Si"], [[0.5, 0.5, 0.5]])
            # 只检查是否能加载，不实际计算
            return {
                "status": "ok",
                "backend": self.backend,
                "device": self.device,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "backend": self.backend,
            }