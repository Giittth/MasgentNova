"""使用 MockEOSCalculator 验证 EOSWorkflow + Birch-Murnaghan 拟合"""

import asyncio
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pymatgen.core import Lattice, Structure
from masgent.calculators import MockEOSCalculator
from masgent.workflows import EOSWorkflow


async def main():
    print("=" * 60)
    print("MockEOSCalculator + EOSWorkflow 验证")
    print("=" * 60)

    # 1. 创建 Si 结构
    lattice = Lattice.cubic(5.43)
    structure = Structure(lattice, ["Si"], [[0.0, 0.0, 0.0]])

    # 2. 创建 Mock Calculator（预期 V0 ≈ 160, B0 > 0）
    calc = MockEOSCalculator(E0=-10.0, V0=160.0, a=0.001)

    # 3. 创建 EOSWorkflow
    workflow = EOSWorkflow(
        calc,
        scale_factors=[0.94, 0.96, 0.98, 1.00, 1.02, 1.04, 1.06],
    )

    # 4. 运行
    result = await workflow.run(structure)

    print(f"\n  Success: {result.success}")
    print(f"  Points: {result.data.get('n_points')}")

    volumes = result.data.get("volumes", [])
    energies = result.data.get("energies", [])
    print(f"  Volumes: {[round(v, 2) for v in volumes]}")
    print(f"  Energies: {[round(e, 5) for e in energies]}")

    fit = result.data.get("fit", {})
    if "error" in fit:
        print(f"  ⚠️  Fit error: {fit.get('error')}")
    else:
        print(f"\n  ✅ 拟合成功:")
        print(f"     E0: {fit.get('E0', 'N/A'):.6f} eV")
        print(f"     V0: {fit.get('V0', 'N/A'):.4f} Å³")
        print(f"     B0: {fit.get('B0', 'N/A'):.4f} GPa")
        print(f"     B1: {fit.get('B1', 'N/A'):.4f}")
        print(f"     Fit function: {fit.get('fit_function')}")

    print("\n" + "=" * 60)
    print("✅ Mock EOS 验证完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())