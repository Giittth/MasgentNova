"""验证 CachedCalculator"""

import asyncio
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pymatgen.core import Lattice, Structure
from masgent.calculators import VaspCalculator, CachedCalculator
from masgent.executors import LocalExecutor
from masgent.utils.task_store import JSONTaskStore


async def main():
    print("=" * 60)
    print("CachedCalculator 验证")
    print("=" * 60)

    # 创建结构
    lattice = Lattice.cubic(5.43)
    structure = Structure(lattice, ["Si"], [[0.0, 0.0, 0.0]])

    # 创建 TaskStore 和 Calculator
    store = JSONTaskStore(Path("./test_tasks"))
    backend = VaspCalculator(executor=LocalExecutor())
    cached = CachedCalculator(calculator=backend, task_store=store)

    print(f" 缓存目录: {store.tasks_dir}")

    # 第一次计算（缓存 miss）
    print("\n--- 第一次计算 (cache miss) ---")
    result1 = await cached.compute_energy(structure)
    print(f"  Success: {result1.success}")
    print(f"  Cached: {result1.metadata.get('cached', False)}")

    # 第二次计算（缓存 hit）
    print("\n--- 第二次计算 (cache hit) ---")
    result2 = await cached.compute_energy(structure)
    print(f"  Success: {result2.success}")
    print(f"  Cached: {result2.metadata.get('cached', False)}")

    # 缓存统计
    print("\n--- 缓存统计 ---")
    stats = store.get_stats()
    print(f"  Total tasks: {stats['total']}")
    print(f"  Completed: {stats['completed']}")

    print("\n" + "=" * 60)
    print("✅ CachedCalculator 验证完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())