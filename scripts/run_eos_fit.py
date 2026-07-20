"""验证 EOSWorkflow + Birch-Murnaghan 拟合"""

import asyncio
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pymatgen.core import Lattice, Structure
from masgent.calculators import VaspCalculator
from masgent.executors import LocalExecutor
from masgent.workflows import EOSWorkflow


async def main():
    print("=" * 60)
    print("EOSWorkflow + Birch-Murnaghan 拟合测试")
    print("=" * 60)

    lattice = Lattice.cubic(5.43)
    structure = Structure(lattice, ["Si"], [[0.0, 0.0, 0.0]])

    calc = VaspCalculator(executor=LocalExecutor())
    workflow = EOSWorkflow(
        calc,
        scale_factors=[0.94, 0.96, 0.98, 1.00, 1.02, 1.04, 1.06],
    )

    result = await workflow.run(structure)

    print(f"  Success: {result.success}")
    print(f"  Points: {result.data.get('n_points')}")
    print(f"  Volumes: {[round(v, 2) for v in result.data.get('volumes', [])]}")
    print(f"  Energies: {[round(e, 4) for e in result.data.get('energies', [])]}")

    fit = result.data.get("fit", {})
    if "error" in fit:
        print(f"  Fit error: {fit.get('error')}")
    else:
        print(f"  E0 (V=0): {fit.get('E0', 'N/A')}")
        print(f"  V0 (equilibrium): {fit.get('V0', 'N/A')}")
        print(f"  B0 (bulk modulus): {fit.get('B0', 'N/A')}")
        print(f"  B1 (derivative): {fit.get('B1', 'N/A')}")
        print(f"  Fit function: {fit.get('fit_function')}")

    print("\n" + "=" * 60)
    print("✅ EOSWorkflow 拟合验证完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())