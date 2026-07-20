"""EOS 工作流——使用 pymatgen.analysis.eos 进行 Birch-Murnaghan 拟合"""

import numpy as np
from pymatgen.core import Structure
from pymatgen.analysis.eos import EOS

from masgent.workflows.base import Workflow
from masgent.models.calculator import CalculationResult
from masgent.models.enums import WorkflowType


class EOSWorkflow(Workflow):
    """EOS（状态方程）工作流"""

    def __init__(
        self,
        calculator,
        scale_factors: list = None,
        relax_first: bool = False,
    ):
        super().__init__(calculator)
        self.scale_factors = scale_factors or [0.94, 0.96, 0.98, 1.00, 1.02, 1.04, 1.06]
        self.relax_first = relax_first

    def _build_result(
        self,
        scale_factors: list,
        volumes: list,
        energies: list,
        fit_result: dict,
    ) -> CalculationResult:
        return CalculationResult(
            success=True,
            workflow_type=WorkflowType.EOS,
            data={
                "scale_factors": scale_factors,
                "volumes": volumes,
                "energies": energies,
                "n_points": len(volumes),
                "fit": fit_result,
            },
            metadata={
                "workflow": "EOSWorkflow",
                "calculator": self.calculator.__class__.__name__,
                "relax_first": self.relax_first,
            },
        )

    async def run(self, structure: Structure) -> CalculationResult:
        volumes = []
        energies = []
        scale_factors_used = []

        for scale in self.scale_factors:
            scaled = structure.copy()
            scaled.scale_lattice(structure.volume * scale)

            if self.relax_first:
                relax_result = await self.calculator.relax(scaled, fmax=0.01, steps=200)
                if not relax_result.success:
                    return CalculationResult(
                        success=False,
                        workflow_type=WorkflowType.EOS,
                        data={},
                        error_message=f"Relax failed at scale {scale}: {relax_result.error_message}",
                    )
                # 修正：使用 data.get()
                if relax_result.success and relax_result.data:
                    scaled = relax_result.data.get("structure", scaled)
                energy = relax_result.data.get("energy")
                if energy is None:
                    energy_result = await self.calculator.compute_energy(scaled)
                    if not energy_result.success:
                        return energy_result
                    energy = energy_result.data.get("energy")
            else:
                energy_result = await self.calculator.compute_energy(scaled)
                if not energy_result.success:
                    return energy_result
                energy = energy_result.data.get("energy")

            volumes.append(scaled.volume)
            energies.append(energy)
            scale_factors_used.append(scale)

        volumes = np.array(volumes)
        energies = np.array(energies)
        sort_idx = np.argsort(volumes)
        volumes = volumes[sort_idx]
        energies = energies[sort_idx]

        energy_span = np.max(energies) - np.min(energies)
        if energy_span < 1e-4:
            return self._build_result(
                scale_factors_used,
                volumes.tolist(),
                energies.tolist(),
                {
                    "error": (
                        "Energy variation too small for EOS fitting. "
                        "This usually means a mock/skeleton calculator "
                        "or unconverged calculation is being used."
                    ),
                    "fit_function": "none",
                },
            )

        if len(volumes) >= 3:
            try:
                eos = EOS("birch_murnaghan")
                fit = eos.fit(volumes, energies)

                fit_result = {
                    "E0": float(getattr(fit, "e0", getattr(fit, "E0", None))),
                    "V0": float(getattr(fit, "v0", getattr(fit, "V0", None))),
                    "fit_function": "Birch-Murnaghan (pymatgen)",
                    "fit_model": type(fit).__name__,
                }

                b0 = getattr(fit, "b0", None) or getattr(fit, "B0", None) or getattr(fit, "b0_GPa", None)
                if b0 is not None:
                    fit_result["B0"] = float(b0)

                b1 = getattr(fit, "b1", None) or getattr(fit, "B1", None)
                if b1 is not None:
                    fit_result["B1"] = float(b1)

            except Exception as e:
                fit_result = {
                    "error": str(e),
                    "fit_function": "none",
                }
        else:
            fit_result = {
                "error": "Need at least 3 data points for fitting",
                "fit_function": "none",
            }

        return self._build_result(
            scale_factors_used,
            volumes.tolist(),
            energies.tolist(),
            fit_result,
        )

    def get_info(self) -> dict:
        return {
            "name": "EOSWorkflow",
            "calculator": self.calculator.__class__.__name__,
            "scale_factors": self.scale_factors,
            "relax_first": self.relax_first,
        }