#!/usr/bin/env python3
"""
测试 Phase 4.1 VaspCalculator 真实 VASP 执行

运行前请确保：
1. VASP 可执行文件在 PATH 中（或通过 vasp_command 指定）
2. PMG_VASP_PSP_DIR 已正确配置
3. 有足够的计算资源（建议 4 核以上）
"""

import asyncio
import sys
import shutil
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pymatgen.core import Lattice, Structure
from masgent.calculators import VaspCalculator
from masgent.executors import LocalExecutor
from masgent.models.enums import WorkflowType
from masgent.calculators.helpers import run_blocking


async def main():
    print("=" * 60)
    print("VaspCalculator Phase 4.1 真实 VASP 执行测试")
    print("=" * 60)

    # 1. 创建测试结构（Si 单胞）
    lattice = Lattice.cubic(5.43)
    structure = Structure(lattice, ["Si"], [[0.0, 0.0, 0.0]])
    print(f"\n 结构: {structure.composition.reduced_formula}")
    print(f" 晶胞体积: {structure.volume:.2f} Å³")

    # 2. 创建 Calculator
    executor = LocalExecutor()
    calc = VaspCalculator(
        executor=executor,
        vasp_command="vasp_std",
        nprocs=4,
        incar_template={"ISMEAR": 0, "SIGMA": 0.05},
    )
    print(f"\n Calculator: {calc.__class__.__name__}")
    print(f" Executor: {executor.__class__.__name__}")
    print(f" VASP 命令: {calc.vasp_command}")

    # 3. 健康检查
    health = calc.health_check()
    print(f"\n 健康检查: {health['status']}")
    print(f"   {health['message']}")

    # 4. 检测 VASP 是否可用（直接检查 PATH，不依赖 health_check）
    vasp_available = shutil.which(calc.vasp_command) is not None
    print(f"\n VASP 检测: {'✅ 找到' if vasp_available else '❌ 未找到'}")

    if not vasp_available:
        print("\n⚠️  VASP 未安装或不在 PATH 中")
        print("   跳过真实 VASP 执行测试")
        print("   如需测试，请安装 VASP 或设置 vasp_command 参数")

        # 演示：只测试输入文件生成（不执行 VASP）
        print("\n--- 演示：只生成输入文件（不执行 VASP） ---")
        work_dir = await run_blocking(
            lambda: calc._prepare_inputs(structure, WorkflowType.SINGLE_POINT)
        )
        print(f"  ✅ 输入文件生成成功")
        print(f"  工作目录: {work_dir}")

        # 检查生成的文件
        files_ok = True
        for f in ["POSCAR", "INCAR", "KPOINTS", "POTCAR.spec"]:
            if (Path(work_dir) / f).exists():
                print(f"    ✅ {f}")
            else:
                print(f"    ❌ {f} (缺失)")
                files_ok = False

        # POTCAR 检查（额外诊断）
        print("\n--- POTCAR 诊断 ---")
        potcar_spec = Path(work_dir) / "POTCAR.spec"
        if potcar_spec.exists():
            content = potcar_spec.read_text().strip()
            print(f"  POTCAR.spec 内容: {content}")
            print(f"  需要的赝势: {content.split() if content else '(空)'}")
        else:
            print("  ⚠️  POTCAR.spec 未生成")

        # 检查 PMG_VASP_PSP_DIR
        import os
        potcar_dir = os.environ.get("PMG_VASP_PSP_DIR", "")
        if potcar_dir:
            print(f"  PMG_VASP_PSP_DIR: {potcar_dir}")
            if Path(potcar_dir).exists():
                print(f"    ✅ 目录存在")
            else:
                print(f"    ❌ 目录不存在")
        else:
            print("  ⚠️  PMG_VASP_PSP_DIR 未设置")
            print("    VASP 真实执行将失败，但输入生成不受影响")

        print("\n" + "=" * 60)
        print("✅ Phase 4.1 测试完成（仅输入生成模式）")
        print("=" * 60)
        return

    # 5. 执行单点计算（仅当 VASP 可用时）
    print("\n--- 运行 compute_energy() ---")
    print("  预计运行时间: 1-5 分钟 (取决于机器性能)")
    print("  请耐心等待...")
    result = await calc.compute_energy(structure)

    # 6. 输出结果
    print("\n--- 计算结果 ---")
    if result.success:
        energy = result.data.get("energy")
        work_dir = result.data.get("work_dir")
        source = result.metadata.get("source", "unknown")
        cached = result.metadata.get("cached", False)

        print(f"  ✅ 成功")
        print(f"  能量: {energy:.6f} eV")
        print(f"  工作目录: {work_dir}")
        print(f"  数据来源: {source}")
        print(f"  缓存命中: {cached}")

        if work_dir:
            outcar = Path(work_dir) / "OUTCAR"
            if outcar.exists():
                size = outcar.stat().st_size / 1024
                print(f"  OUTCAR 大小: {size:.1f} KB")
            vasprun = Path(work_dir) / "vasprun.xml"
            if vasprun.exists():
                size = vasprun.stat().st_size / 1024
                print(f"  vasprun.xml 大小: {size:.1f} KB")
    else:
        print(f"  ❌ 失败")
        print(f"  错误: {result.error_message}")

    print("\n" + "=" * 60)
    print("✅ Phase 4.1 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())