"""CachedCalculator——基于 TaskStore 的缓存装饰器"""

from typing import Callable, Awaitable, TypeVar
from pymatgen.core import Structure

from masgent.calculators.base import Calculator
from masgent.models.calculator import CalculationResult
from masgent.models.enums import WorkflowType
from masgent.tasks.task_store import TaskStore
from masgent.utils.fingerprint import calculation_fingerprint

T = TypeVar("T")


class CachedCalculator(Calculator):
    def __init__(self, calculator: Calculator, task_store: TaskStore):
        self.calculator = calculator
        self.task_store = task_store

    def _get_fingerprint(self, structure: Structure, workflow_type: WorkflowType, **kwargs) -> str:
        params = kwargs
        if workflow_type == WorkflowType.RELAX:
            params = {"fmax": kwargs.get("fmax", 0.1), "steps": kwargs.get("steps", 500)}
        return calculation_fingerprint(
            structure=structure,
            workflow_type=workflow_type,
            params=params,
            calculator_type=self.calculator.__class__.__name__,
        )

    async def _cached_call(
        self,
        structure: Structure,
        workflow_type: WorkflowType,
        fn: Callable[[], Awaitable[CalculationResult]],
        params: dict = None,
    ) -> CalculationResult:
        fp = self._get_fingerprint(structure, workflow_type, **(params or {}))
        cached_task = self.task_store.find_by_fingerprint(fp)
        if cached_task and cached_task.result:
            return CalculationResult(
                success=True,
                workflow_type=workflow_type,
                data=cached_task.result.get("data", {}),
                metadata={**cached_task.result.get("metadata", {}), "cached": True},
                fingerprint=fp,  # ← 携带 fingerprint
            )
        result = await fn()
        if result.success:
            result.fingerprint = fp  # ← 缓存未命中时也设置 fingerprint
            self.task_store.save_cache(
                fingerprint=fp,
                workflow_type=workflow_type,
                result={"data": result.data, "metadata": result.metadata},
                metadata={"cached": True, "calculator_type": self.calculator.__class__.__name__},
            )
        return result

    async def compute_energy(self, structure: Structure) -> CalculationResult:
        return await self._cached_call(
            structure,
            WorkflowType.SINGLE_POINT,
            lambda: self.calculator.compute_energy(structure),
        )

    async def relax(self, structure: Structure, fmax: float = 0.1, steps: int = 500) -> CalculationResult:
        return await self._cached_call(
            structure,
            WorkflowType.RELAX,
            lambda: self.calculator.relax(structure, fmax, steps),
            params={"fmax": fmax, "steps": steps},
        )

    async def compute_forces(self, structure: Structure) -> CalculationResult:
        return await self.calculator.compute_forces(structure)

    def get_info(self) -> dict:
        return {
            "name": "CachedCalculator",
            "backend": self.calculator.__class__.__name__,
            "task_store": self.task_store.__class__.__name__,
        }

    def health_check(self) -> dict:
        return {
            "status": "ok",
            "cached_calculator": True,
            "backend": self.calculator.health_check(),
        }

    def clear_cache(self) -> None:
        for task in self.task_store.list_tasks():
            if task.metadata.get("cached"):
                self.task_store.delete(task.task_id)