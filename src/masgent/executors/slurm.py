"""Slurm 执行器 —— 通过 sbatch/squeue/scancel/sacct 管理 HPC 作业"""

import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

from masgent.executors.base import Executor
from masgent.models.job import JobHandle
from masgent.models.executor import CommandResult


class SlurmExecutor(Executor):
    """
    Slurm 执行器

    通过 sbatch 提交作业，squeue 查询状态，scancel 取消作业，
    sacct 获取退出码。
    """

    # Slurm 作业运行中状态集合
    RUNNING_STATUSES = {
        "PENDING",
        "CONFIGURING",
        "RUNNING",
        "SUSPENDED",
        "COMPLETING",
    }

    def __init__(
        self,
        partition: Optional[str] = None,
        account: Optional[str] = None,
        qos: Optional[str] = None,
        nodes: int = 1,
        ntasks: int = 8,
        cpus_per_task: int = 1,
        walltime: str = "01:00:00",
        jobname: str = "masgent_job",
        modules: Optional[list[str]] = None,
        poll_interval: float = 5.0,
        extra_sbatch_args: Optional[Dict[str, str]] = None,
    ):
        self.partition = partition or "normal"
        self.account = account
        self.qos = qos
        self.nodes = nodes
        self.ntasks = ntasks
        self.cpus_per_task = cpus_per_task
        self.walltime = walltime
        self.jobname = jobname
        self.modules = modules or []
        self.poll_interval = poll_interval
        self.extra_sbatch_args = extra_sbatch_args or {}

        # 保存原始配置（包含用户传入的值，即使是 None）
        self._config = {
            "type": "slurm",
            "partition": partition,
            "account": account,
            "qos": qos,
            "nodes": nodes,
            "ntasks": ntasks,
            "cpus_per_task": cpus_per_task,
            "walltime": walltime,
            "jobname": jobname,
            "modules": self.modules,
            "poll_interval": poll_interval,
            "extra_sbatch_args": self.extra_sbatch_args,
        }

    def _generate_sbatch_script(self, work_dir: Path, command: str, env: Optional[Dict[str, str]] = None) -> str:
        """生成 Slurm 提交脚本内容"""
        env_lines = [f"export {k}='{v}'" for k, v in (env or {}).items()]
        module_lines = [f"module load {m}" for m in self.modules]
        extra_args = [f"#SBATCH --{k}={v}" for k, v in self.extra_sbatch_args.items()]

        return f"""#!/bin/bash
#SBATCH --partition={self.partition}
#SBATCH --nodes={self.nodes}
#SBATCH --ntasks={self.ntasks}
#SBATCH --cpus-per-task={self.cpus_per_task}
#SBATCH --time={self.walltime}
#SBATCH --job-name={self.jobname}
#SBATCH --output=slurm.out
#SBATCH --error=slurm.err
{'' if not self.account else f'#SBATCH --account={self.account}'}
{'' if not self.qos else f'#SBATCH --qos={self.qos}'}
{'' if not extra_args else '\n'.join(extra_args)}

# 环境变量
{'' if not env_lines else '\n'.join(env_lines)}

# 模块加载
{'' if not module_lines else '\n'.join(module_lines)}

cd {work_dir}
echo "Job started at $(date)"
time {command}
echo "Job finished at $(date)"
"""

    async def _run_cmd(self, *args) -> tuple[int, str, str]:
        """执行命令并返回 (returncode, stdout, stderr)"""
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode().strip(), stderr.decode().strip()

    async def spawn(self, work_dir: Path, command: str, env: Optional[Dict[str, str]] = None) -> JobHandle:
        """
        提交 Slurm 作业

        Args:
            work_dir: 工作目录
            command: 要执行的命令
            env: 环境变量

        Returns:
            JobHandle: 包含 scheduler_id
        """
        work_dir.mkdir(parents=True, exist_ok=True)

        script_content = self._generate_sbatch_script(work_dir, command, env)
        script_path = work_dir / "job.sbatch"
        script_path.write_text(script_content)
        script_path.chmod(0o755)

        rc, stdout, stderr = await self._run_cmd("sbatch", str(script_path))
        if rc != 0:
            raise RuntimeError(f"sbatch failed: {stderr or stdout}")

        output = stdout.strip()
        match = re.search(r"Submitted batch job (\d+)", output)
        if not match:
            raise RuntimeError(f"Failed to parse job ID from: {output}")
        job_id = match.group(1)

        return JobHandle(
            job_id=f"slurm_{job_id}",
            backend="slurm",
            scheduler_id=job_id,
            submitted_at=datetime.now().isoformat(),
            metadata={
                "partition": self.partition,
                "jobname": self.jobname,
                "nodes": self.nodes,
                "ntasks": self.ntasks,
                "walltime": self.walltime,
            },
        )

    async def is_running(self, job_id: str, pid: Optional[int] = None) -> bool:
        """检查作业是否仍在运行"""
        # 若传入 job_id 是 slurm_{id} 格式，提取数字部分
        if job_id.startswith("slurm_"):
            job_id = job_id[6:]

        rc, stdout, _ = await self._run_cmd("squeue", "-j", job_id, "-h", "-o", "%T")
        if rc != 0 or not stdout:
            return False

        status = stdout.strip()
        return status in self.RUNNING_STATUSES

    async def _get_exit_code(self, job_id: str) -> int:
        """
        通过 sacct 获取作业退出码

        Returns:
            int: 0 表示成功，1 表示失败，-1 表示无法获取
        """
        if job_id.startswith("slurm_"):
            job_id = job_id[6:]

        rc, stdout, stderr = await self._run_cmd(
            "sacct", "-j", job_id, "--format=State,ExitCode", "-P", "-n"
        )
        if rc != 0 or not stdout:
            return -1

        lines = [l for l in stdout.split("\n") if l.strip()]
        if not lines:
            return -1

        # 取最后一行（通常为主作业）
        parts = lines[-1].split("|")
        if len(parts) >= 2:
            state = parts[0].strip()
            # 支持 COMPLETED, COMPLETED+, COMPLETED batch 等变体
            if state.startswith("COMPLETED"):
                return 0
            # 其他状态视为失败
            return 1

        return -1

    async def wait(self, job_id: str, timeout: Optional[int] = None) -> int:
        """
        等待作业完成，返回退出码

        Returns:
            int: 0 成功，非 0 失败，-2 超时，-1 无法获取退出码
        """
        if job_id.startswith("slurm_"):
            job_id = job_id[6:]

        start = asyncio.get_event_loop().time()
        while True:
            if timeout is not None and (asyncio.get_event_loop().time() - start) > timeout:
                return -2
            if not await self.is_running(job_id):
                return await self._get_exit_code(job_id)
            await asyncio.sleep(self.poll_interval)

    async def kill(self, job_id: str) -> bool:
        """取消作业"""
        if job_id.startswith("slurm_"):
            job_id = job_id[6:]

        rc, _, _ = await self._run_cmd("scancel", job_id)
        return rc == 0

    async def run(self, work_dir: Path, command: str, env: Optional[Dict[str, str]] = None) -> CommandResult:
        """同步执行（使用 sbatch --wait）"""
        work_dir.mkdir(parents=True, exist_ok=True)

        script_content = self._generate_sbatch_script(work_dir, command, env)
        script_path = work_dir / "job.sbatch"
        script_path.write_text(script_content)
        script_path.chmod(0o755)

        rc, stdout, stderr = await self._run_cmd("sbatch", "--wait", str(script_path))
        return CommandResult(returncode=rc, stdout=stdout, stderr=stderr)

    def health_check(self) -> tuple[bool, str]:
        """检查 Slurm 命令是否全部可用"""
        import shutil

        required = ["sbatch", "squeue", "scancel", "sacct"]
        missing = [cmd for cmd in required if not shutil.which(cmd)]

        if missing:
            return False, f"Missing Slurm commands: {', '.join(missing)}"
        return True, "All Slurm commands available"

    def get_config(self) -> dict:
        return self._config.copy()

    def validate(self) -> bool:
        """验证 Slurm 配置是否完整有效（基于原始配置）"""
        config = self.get_config()
        if not config.get("partition"):
            return False
        if config.get("ntasks", 0) <= 0:
            return False
        if config.get("nodes", 0) <= 0:
            return False
        if config.get("cpus_per_task", 0) <= 0:
            return False
        walltime = config.get("walltime")
        if walltime:
            import re
            if not re.match(r"^\d{1,2}:\d{2}:\d{2}$", walltime):
                return False
        return True