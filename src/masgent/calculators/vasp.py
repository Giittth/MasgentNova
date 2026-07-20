"""
VASP Calculator —— Phase 4.3 纯无状态版本

职责边界：
    - prepare:     准备 VASP 输入文件（INCAR, KPOINTS, POTCAR, POSCAR）
    - launch:      启动 VASP 计算（通过 Executor）
    - detect_status: 检测任务状态（基于文件 + 可选的 JobHandle）
    - collect:     收集计算结果（能量、结构等）
    - cancel:      取消正在运行的 VASP 作业

不关心：
    - task_id
    - 持久化（TaskStore）
    - 调度逻辑（TaskRunner）
    - 重试策略

设计原则：
    - 所有方法参数仅为 work_dir / JobHandle，不包含 task_id
    - 通过 TYPE = "vasp" 提供稳定的持久化标识符
    - 通过 get_init_params() 支持恢复时重建
"""

import asyncio
import hashlib
import json
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from pymatgen.core import Structure
from pymatgen.io.vasp import Poscar
from pymatgen.io.vasp.sets import MPStaticSet, MPRelaxSet, MPMDSet
from pymatgen.io.vasp.outputs import Vasprun

from masgent.calculators.base import Calculator
from masgent.calculators.helpers import run_blocking
from masgent.calculators.registry import CalculatorRegistry
from masgent.executors.base import Executor
from masgent.executors.factory import ExecutorFactory
from masgent.models.calculator import CalculationResult
from masgent.models.enums import WorkflowType, TaskStatus
from masgent.models.job import JobHandle
from masgent.utils.workdir_manager import WorkDirManager
from masgent.utils.fingerprint import structure_hash
from masgent.utils.workdir_manager import WorkDirManager


@dataclass
class VaspExecutionResult:
    """
    VASP 内部执行结果（用于同步执行模式）

    Attributes:
        success: 是否成功完成
        work_dir: 工作目录
        returncode: 进程退出码
        stdout: 标准输出
        stderr: 标准错误
        duration: 运行时间（秒）
        error_message: 错误信息（失败时）
    """
    success: bool
    work_dir: Path
    returncode: int
    stdout: str
    stderr: str
    duration: float = 0.0
    error_message: Optional[str] = None


class VaspCalculator(Calculator):
    """
    VASP 计算器 —— 纯无状态

    稳定标识符 TYPE = "vasp" 用于持久化恢复，
    即使类重命名，历史任务仍可正常恢复。

    Attributes:
        executor: 底层执行器（Local/Slurm/PBS）
        workdir_manager: 工作目录管理器
        incar_template: INCAR 模板参数
        vasp_command: VASP 可执行文件命令
        nprocs: 并行核数
    """

    # ========== 稳定标识符 ==========
    TYPE: str = "vasp"

    def __init__(
        self,
        executor: Executor,
        workdir_manager: Optional[WorkDirManager] = None,
        incar_template: Dict[str, Any] = None,
        vasp_command: str = "vasp_std",
        nprocs: int = 4,
        task_store=None,          # ← 保持向后兼容
        **kwargs,                 # ← 吸收额外参数
    ):
        """
        初始化 VASP 计算器

        Args:
            executor: 执行器实例
            workdir_manager: 工作目录管理器（默认自动创建）
            incar_template: INCAR 模板参数，如 {"ISMEAR": 0, "SIGMA": 0.05}
            vasp_command: VASP 命令，如 "vasp_std" 或 "srun vasp_gpu"
            nprocs: 并行核数（目前仅用于信息，实际由 Executor 控制）
        """
        # 如果 executor 未传入，尝试从 kwargs 重建
        if executor is None:
            executor_config = kwargs.get("executor")
            if executor_config:
                executor = ExecutorFactory.create(executor_config)
            else:
                raise ValueError("executor is required for VaspCalculator")

        # 如果 workdir_manager 未传入，尝试从 kwargs 重建
        if workdir_manager is None:
            wm_config = kwargs.get("workdir_manager")
            if wm_config:
                base_dir = Path(wm_config.get("base_dir", "."))
                workdir_manager = WorkDirManager(base_dir=base_dir)

        self.executor = executor
        self.workdir_manager = workdir_manager or WorkDirManager()
        self.incar_template = incar_template or {}
        self.vasp_command = vasp_command
        self.nprocs = nprocs
        self.task_store = task_store  # 保存但不使用（职责已移给 TaskRunner）

    # ========== 内部辅助方法 ==========

    def _build_vasp_set(self, structure: Structure, workflow_type: WorkflowType):
        """
        根据工作流类型构建对应的 VASP 输入集
        """
        if workflow_type == WorkflowType.RELAX:
            return MPRelaxSet(structure, user_incar_settings=self.incar_template)
        elif workflow_type == WorkflowType.AIMD:
            return MPMDSet(structure, user_incar_settings=self.incar_template)
        else:
            return MPStaticSet(structure, user_incar_settings=self.incar_template)

    def _get_work_dir_fingerprint(
        self,
        structure: Structure,
        workflow_type: WorkflowType,
        **kwargs,
    ) -> str:
        """
        生成工作目录的确定性指纹
        """
        params = {**self.incar_template, **kwargs}
        clean_params = {}
        for k, v in params.items():
            if isinstance(v, (str, int, float, bool, type(None))):
                clean_params[k] = v
            else:
                clean_params[k] = str(v)

        data = {
            "structure_hash": structure_hash(structure),
            "workflow_type": workflow_type.value,
            "params": clean_params,
            "vasp_command": self.vasp_command,
            "calculator": "vasp",
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]

    def _prepare_inputs(
        self,
        structure: Structure,
        workflow_type: WorkflowType,
        **kwargs,
    ) -> Path:
        """
        准备 VASP 输入文件（同步，在线程池中执行）
        """
        fp = self._get_work_dir_fingerprint(structure, workflow_type, **kwargs)
        subdir = kwargs.get("subdir")
        subdir = f"{subdir}_{fp}" if subdir else fp

        work_dir = self.workdir_manager.create(
            structure=structure,
            workflow_type=workflow_type,
            mode="reuse",
            subdir=subdir,
        )

        # 已存在输入文件则直接复用
        if (work_dir / "INCAR").exists() and (work_dir / "KPOINTS").exists() and (work_dir / "POSCAR").exists():
            return work_dir

        vis = self._build_vasp_set(structure, workflow_type)

        try:
            vis.write_input(work_dir, potcar_spec=True)
        except TypeError:
            Poscar(structure).write_file(work_dir / "POSCAR")
            vis.incar.write_file(work_dir / "INCAR")
            vis.kpoints.write_file(work_dir / "KPOINTS")
            if hasattr(vis, "potcar_symbols"):
                (work_dir / "POTCAR.spec").write_text("\n".join(vis.potcar_symbols))

        return work_dir

    def _is_vasp_completed(self, work_dir: Path) -> bool:
        """
        检查 VASP 是否正常完成
        """
        outcar_path = work_dir / "OUTCAR"
        if not outcar_path.exists():
            return False

        try:
            with open(outcar_path, "r") as f:
                tail = deque(f, maxlen=200)
                content = "".join(tail).lower()

            fatal_keywords = ["very bad news", "internal error", "segmentation fault"]
            for kw in fatal_keywords:
                if kw in content:
                    return False

            if "general timing and accounting informations" in content:
                return True
            return False
        except Exception:
            return False

    def _is_completed(self, work_dir: Path) -> bool:
        """
        判断 VASP 是否正常完成（基于标准输出文件）
        不依赖 COMPLETED 文件，适配真实 VASP
        """
        # 1. 有 vasprun.xml 即可认为完成（pymatgen 可解析）
        if (work_dir / "vasprun.xml").exists():
            return True

        # 2. 降级：OUTCAR 包含 TOTEN 且包含完成标志
        outcar = work_dir / "OUTCAR"
        if outcar.exists():
            try:
                text = outcar.read_text()
                return (
                    "TOTEN" in text
                    and "Voluntary context switches" in text
                )
            except Exception:
                return False

        return False

    def _mark_completed(self, work_dir: Path) -> None:
        """写入 COMPLETED 标记文件"""
        (work_dir / "COMPLETED").write_text(f"Completed at {datetime.now().isoformat()}")

    def _parse_energy(self, work_dir: Path) -> Optional[float]:
        """
        综合解析能量（优先 pymatgen，降级到正则 fallback）
        支持：
            - 真实 VASP: vasprun.xml / OUTCAR（pymatgen）
            - fake_vasp: OUTCAR 中 TOTEN 行（正则）
        """
        from pymatgen.io.vasp.outputs import Vasprun, Outcar
        import re

        # 1. vasprun.xml（pymatgen）
        vasprun_path = work_dir / "vasprun.xml"
        if vasprun_path.exists():
            try:
                v = Vasprun(str(vasprun_path), parse_dos=False, parse_eigen=False)
                return v.final_energy
            except Exception:
                pass

        # 2. OUTCAR（pymatgen）
        outcar_path = work_dir / "OUTCAR"
        if outcar_path.exists():
            try:
                outcar = Outcar(str(outcar_path))
                return outcar.final_energy
            except Exception:
                pass

        # 3. OUTCAR 正则 fallback（支持 fake_vasp 简化输出）
        if outcar_path.exists():
            try:
                text = outcar_path.read_text()
                # 匹配 TOTEN = -10.532 或 free energy TOTEN = -10.532
                match = re.search(r"TOTEN\s*=\s*([-+]?\d*\.\d+)", text)
                if match:
                    return float(match.group(1))
                # 也尝试匹配 energy without entropy
                match = re.search(r"energy without entropy\s*=\s*([-+]?\d*\.\d+)", text)
                if match:
                    return float(match.group(1))
            except Exception:
                pass

        return None


    def _parse_structure(self, work_dir: Path) -> Optional[Structure]:
        """
        从 CONTCAR 解析最终结构（用于 RELAX 工作流）
        """
        contcar_path = work_dir / "CONTCAR"
        if not contcar_path.exists():
            return None
        try:
            return Structure.from_file(contcar_path)
        except Exception:
            return None

    # ========== 内部执行（异步） ==========

    async def _execute(
        self,
        work_dir: Path,
    ) -> VaspExecutionResult:
        """
        异步执行 VASP（通过 executor.run）
        """
        import time
        start = time.time()

        result = await self.executor.run(
            work_dir=work_dir,
            command=self.vasp_command,
            timeout=None,
        )

        duration = time.time() - start
        success = result.returncode == 0 and self._is_vasp_completed(work_dir)

        if success:
            self._mark_completed(work_dir)

        return VaspExecutionResult(
            success=success,
            work_dir=work_dir,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration=duration,
            error_message=None if success else f"VASP failed with returncode {result.returncode}",
        )

    def _collect_from_workdir(self, work_dir: Path, workflow_type: WorkflowType) -> CalculationResult:
        energy = self._parse_energy(work_dir)

        if energy is None:
            return CalculationResult(
                success=False,
                workflow_type=workflow_type,
                data={"work_dir": str(work_dir)},
                error_message="Failed to parse energy from vasprun.xml or OUTCAR",
            )

        result_data = {"energy": energy, "work_dir": str(work_dir)}

        if workflow_type == WorkflowType.RELAX:
            structure = self._parse_structure(work_dir)
            if structure:
                # 关键修复：直接保存 Structure 对象，不要调用 .as_dict()
                result_data["structure"] = structure
                print(
                    "[DEBUG VASP collect]",
                    type(result_data["structure"])
                )
        return CalculationResult(
            success=True,
            workflow_type=workflow_type,
            data=result_data,
            metadata={"calculator": "vasp"},
        )

    # ========== Calculator 接口实现 ==========

    async def prepare(
        self,
        structure: Structure,
        workflow_type: WorkflowType,
        **kwargs,
    ) -> Path:
        return await run_blocking(
            lambda: self._prepare_inputs(structure, workflow_type, **kwargs)
        )

    async def launch(self, work_dir: Path) -> JobHandle:
        return await self.executor.spawn(
            work_dir=work_dir,
            command=self.vasp_command,
        )

    async def detect_status(
        self,
        work_dir: Path,
        job: Optional[JobHandle] = None,
    ) -> TaskStatus:
        """
        检测 VASP 任务状态

        优先级：
            COMPLETED（结果文件存在）
                ↓
            RUNNING（进程存活）
                ↓
            FAILED（进程结束且有错误输出）
                ↓
            PENDING / UNKNOWN（无文件或状态不明）

        关键原则：
            - 结果文件优先于进程状态（进程可能已结束但结果已生成）
            - 无 JobHandle 时，仅凭文件不能推断 RUNNING
        """
        # 1. 结果优先：只要有完成文件，就是 COMPLETED
        if self._is_completed(work_dir):
            return TaskStatus.COMPLETED

        outcar = work_dir / "OUTCAR"

        # 2. 错误检测（OUTCAR 存在时检查致命错误）
        if outcar.exists():
            try:
                content = outcar.read_text(errors="ignore").lower()
                fatal_keywords = [
                    "very bad news",
                    "internal error",
                    "segmentation fault",
                ]
                if any(kw in content for kw in fatal_keywords):
                    return TaskStatus.FAILED
            except Exception:
                pass

        # 3. 有 JobHandle → 检查进程状态
        if job:
            try:
                running = await self.executor.is_running(job.job_id, job.pid)
                if running:
                    return TaskStatus.RUNNING
            except Exception:
                pass

            # 进程已退出，二次确认是否有结果
            if self._is_completed(work_dir):
                return TaskStatus.COMPLETED

            # 有 OUTCAR 且非空 → 可能是失败
            if outcar.exists() and outcar.stat().st_size > 100:
                return TaskStatus.FAILED

            # 进程已退出但没有任何有效输出
            return TaskStatus.FAILED

        # 4. 无 JobHandle → 只能基于文件做保守判断
        if not outcar.exists():
            return TaskStatus.PENDING

        # OUTCAR 存在但没有 job 信息 → 不能确认运行状态
        return TaskStatus.UNKNOWN

    async def collect(
        self,
        work_dir: Path,
        workflow_type: WorkflowType,
    ) -> CalculationResult:
        return self._collect_from_workdir(work_dir, workflow_type)

    async def cancel(self, job: JobHandle) -> bool:
        return await self.executor.kill(job.job_id)

    def get_init_params(self) -> dict:
        return {
            "vasp_command": self.vasp_command,
            "nprocs": self.nprocs,
            "incar_template": self.incar_template,
        }

    def health_check(self) -> dict:
        executor_ok, executor_msg = self.executor.health_check()
        return {
            "healthy": executor_ok,
            "status": "ok" if executor_ok else "error",
            "message": executor_msg if executor_ok else f"Executor error: {executor_msg}",
            "details": {
                "executor": self.executor.__class__.__name__,
                "vasp_command": self.vasp_command,
                "calculator": "vasp",
                "phase": "4.3",
            },
        }

    # ========== 同步兼容接口（Phase 4.1 风格） ==========

    async def compute_energy(self, structure: Structure) -> CalculationResult:
        """
        同步风格的单点能量计算（带缓存检查）
        """
        work_dir = await self.prepare(structure, WorkflowType.SINGLE_POINT)

        # 缓存命中：直接返回已收集的结果（不重复执行）
        if self._is_completed(work_dir):
            result = await self.collect(work_dir, WorkflowType.SINGLE_POINT)
            # 标记为缓存命中
            result.metadata["cached"] = True
            return result

        # 执行计算
        exec_result = await self._execute(work_dir)

        if not exec_result.success:
            return CalculationResult(
                success=False,
                workflow_type=WorkflowType.SINGLE_POINT,
                data={"work_dir": str(work_dir)},
                error_message=exec_result.error_message,
            )

        result = await self.collect(work_dir, WorkflowType.SINGLE_POINT)
        result.metadata["cached"] = False
        return result

    async def relax(
        self,
        structure: Structure,
        fmax: float = 0.1,
        steps: int = 500,
    ) -> CalculationResult:
        """
        同步风格的结构优化（带缓存检查）
        """
        work_dir = await self.prepare(
            structure,
            WorkflowType.RELAX,
            fmax=fmax,
            steps=steps,
        )

        # 缓存命中
        if self._is_completed(work_dir):
            result = await self.collect(work_dir, WorkflowType.RELAX)
            result.metadata["cached"] = True
            return result

        exec_result = await self._execute(work_dir)

        if not exec_result.success:
            return CalculationResult(
                success=False,
                workflow_type=WorkflowType.RELAX,
                data={"work_dir": str(work_dir)},
                error_message=exec_result.error_message,
            )

        result = await self.collect(work_dir, WorkflowType.RELAX)
        result.metadata["cached"] = False
        return result

    async def compute_forces(self, structure: Structure) -> CalculationResult:
        return CalculationResult(
            success=False,
            workflow_type=WorkflowType.FORCES,
            error_message="compute_forces() not yet implemented",
            data={"structure": structure},
        )

    def get_init_params(self) -> dict:
        """返回可序列化的初始化参数，用于恢复时重建"""
        return {
            "vasp_command": self.vasp_command,
            "nprocs": self.nprocs,
            "incar_template": self.incar_template,
            "executor": self.executor.get_init_params(),
            "workdir_manager": {
                "base_dir": str(self.workdir_manager.base_dir),
            },
        }


# ========== 注册到 CalculatorRegistry ==========
CalculatorRegistry.register("vasp", VaspCalculator)