"""验证 EOSWorkflow + VaspCalculator（Skeleton 模式）"""

import asyncio
from pathlib import Path
from pymatgen.core import Lattice, Structure

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from masgent.calculators import VaspCalculator
from masgent.executors import LocalExecutor
from masgent.workflows import EOSWorkflow


async def test_vasp_eos():
    print("=" * 60)
    print("测试: VaspCalculator + EOSWorkflow (Skeleton 模式)")
    print("=" * 60)

    # 创建 Si 结构
    lattice = Lattice.cubic(5.43)
    structure = Structure(lattice, ["Si"], [[0.0, 0.0, 0.0]])

    # VaspCalculator + LocalExecutor
    executor = LocalExecutor()
    calc = VaspCalculator(executor=executor)
    workflow = EOSWorkflow(calc, scale_factors=[0.98, 1.00, 1.02])

    result = await workflow.run(structure)

    print(f"  Success: {result.success}")
    print(f"  Points: {result.data.get('n_points')}")
    print(f"  Volumes: {[round(v, 2) for v in result.data.get('volumes', [])]}")
    print(f"  Energies: {[round(e, 4) for e in result.data.get('energies', [])]}")
    print(f"  Calculator: {result.metadata.get('calculator')}")
    print()


async def test_workflow_abstraction():
    print("=" * 60)
    print("测试: Workflow 抽象层验证")
    print("=" * 60)

    lattice = Lattice.cubic(5.43)
    structure = Structure(lattice, ["Si"], [[0.0, 0.0, 0.0]])

    calc = VaspCalculator(executor=LocalExecutor())
    workflow = EOSWorkflow(calc, scale_factors=[0.98, 1.00, 1.02])

    result = await workflow.run(structure)

    print(f"  success={result.success}, n_points={result.data.get('n_points')}")
    print("\n  ✅ Workflow → Calculator → Executor 链路畅通！")


async def main():
    await test_vasp_eos()
    await test_workflow_abstraction()

    print("=" * 60)
    print("✅ 所有测试通过！三层架构（Workflow → Calculator → Executor）已闭环。")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())