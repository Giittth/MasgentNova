"""Mock Calculator——用于测试 EOSWorkflow 和拟合逻辑"""

from pymatgen.core import Structure

from masgent.calculators.base import Calculator
from masgent.models.calculator import CalculationResult
from masgent.models.enums import WorkflowType


class MockEOSCalculator(Calculator):
    """
    Mock EOS Calculator

    返回抛物线形式的能量：
        E(V) = E0 + a * (V - V0)^2

    用于验证 EOSWorkflow + Birch-Murnaghan 拟合的正确性。
    """

    def __init__(self, E0: float = -10.0, V0: float = 160.0, a: float = 0.001):
        self.E0 = E0
        self.V0 = V0
        self.a = a

    async def compute_energy(self, structure: Structure) -> CalculationResult:
        """计算能量：E(V) = E0 + a * (V - V0)^2"""
        V = structure.volume
        energy = self.E0 + self.a * (V - self.V0) ** 2

        return CalculationResult(
            success=True,
            workflow_type=WorkflowType.SINGLE_POINT,
            data={
                "energy": energy,
                "energy_per_atom": energy / len(structure),
                "volume": V,
            },
            metadata={
                "calculator": "MockEOSCalculator",
                "E0": self.E0,
                "V0": self.V0,
                "a": self.a,
            },
        )

    async def compute_forces(self, structure: Structure) -> CalculationResult:
        # 未实现
        return CalculationResult(
            success=False,
            workflow_type=WorkflowType.FORCES,
            error_message="Not implemented in MockEOSCalculator",
        )

    async def relax(self, structure: Structure, fmax: float = 0.1, steps: int = 500) -> CalculationResult:
        # 直接返回原结构 + 能量
        result = await self.compute_energy(structure)
        return CalculationResult(
            success=True,
            workflow_type=WorkflowType.RELAX,
            data={
                "structure": structure,
                "energy": result.data.get("energy"),
            },
            metadata={"calculator": "MockEOSCalculator"},
        )

    def get_info(self) -> dict:
        return {
            "name": "MockEOSCalculator",
            "E0": self.E0,
            "V0": self.V0,
            "a": self.a,
        }

    def health_check(self) -> dict:
        return {"status": "ok", "calculator": "MockEOSCalculator"}