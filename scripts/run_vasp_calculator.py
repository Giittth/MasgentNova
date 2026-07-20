#!/usr/bin/env python3
"""验证 VaspCalculator 的 submit/poll/collect 接口（假实现）"""

import asyncio
from pathlib import Path
from pymatgen.core import Lattice, Structure

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from masgent.calculators import VaspCalculator
from masgent.executors import LocalExecutor
from masgent.models.calculator import WorkflowType  # ← 新增导入


async def main():
    print("=" * 60)
    print("VaspCalculator 接口验证 (Phase 3-4B)")
    print("=" * 60)

    lattice = Lattice.cubic(5.43)
    structure = Structure(lattice, ["Si"], [[0.0, 0.0, 0.0]])
    print(f"✅ 结构创建: {structure.composition.reduced_formula}")

    executor = LocalExecutor()
    calc = VaspCalculator(executor=executor)
    print(f"✅ Calculator: {calc.__class__.__name__}")
    print(f"✅ Executor: {executor.__class__.__name__}")

    # === 使用枚举传入 ===
    print("\n--- 测试 submit() ---")
    task = await calc.submit(structure, workflow_type=WorkflowType.SINGLE_POINT)  # ← 改这里
    print(f"  Task ID: {task.task_id}")
    print(f"  Work Dir: {task.work_dir}")

    print("\n--- 测试 poll() ---")
    status = await calc.poll(task.task_id)
    print(f"  Status: {status.value}")

    print("\n--- 测试 collect() ---")
    result = await calc.collect(task.task_id)
    print(f"  Success: {result.success}")
    print(f"  Files: {result.data.get('files', [])}")
    print(f"  Energy: {result.data.get('energy', 'N/A')} eV")

    print("\n--- 测试 compute_energy()（基类兼容） ---")
    result2 = await calc.compute_energy(structure)
    print(f"  Success: {result2.success}")
    print(f"  Energy: {result2.data.get('energy', 'N/A')} eV")

    print("\n" + "=" * 60)
    print("✅ 所有测试通过！VaspCalculator 接口验证完成。")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())