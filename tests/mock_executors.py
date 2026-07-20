"""Mock Executors 用于测试（不注册到生产 Factory）"""

from pathlib import Path
from typing import Optional, Dict
import uuid
from datetime import datetime

from masgent.executors.base import Executor
from masgent.models.job import JobHandle
from masgent.models.executor import CommandResult
from masgent.executors.factory import ExecutorFactory


class FakeSlurmExecutor(Executor):
    """模拟 Slurm 执行器，用于测试 HPC 恢复链路（全局状态持久化）"""

    # 全局作业字典（模拟 Slurm 服务器持久化）
    GLOBAL_JOBS: Dict[str, Dict] = {}
    GLOBAL_COUNTER: int = 1000

    def __init__(
        self,
        partition: str = "cpu",
        ntasks: int = 1,
        account: Optional[str] = None,
        qos: Optional[str] = None,
        walltime: Optional[str] = None,
        **kwargs
    ):
        self.partition = partition
        self.ntasks = ntasks
        self.account = account
        self.qos = qos
        self.walltime = walltime
        self.extra_config = kwargs  # 保留其他未明确定义的参数
        self.jobs = FakeSlurmExecutor.GLOBAL_JOBS

    def _normalize_id(self, job_id: str) -> str:
        """提取 scheduler_id"""
        if job_id.startswith("fake_slurm_"):
            return job_id.replace("fake_slurm_", "")
        if job_id.startswith("slurm_"):
            return job_id.replace("slurm_", "")
        return job_id

    @classmethod
    def clear_jobs(cls):
        """清空全局作业（测试隔离）"""
        cls.GLOBAL_JOBS.clear()
        cls.GLOBAL_COUNTER = 1000  # 重置计数器

    async def spawn(self, work_dir: Path, command: str, env=None) -> JobHandle:
        scheduler_id = str(FakeSlurmExecutor.GLOBAL_COUNTER)
        FakeSlurmExecutor.GLOBAL_COUNTER += 1
        self.jobs[scheduler_id] = {
            "status": "RUNNING",
            "exit_code": None,
            "command": command,
            "work_dir": str(work_dir),
        }
        return JobHandle(
            job_id=f"slurm_{scheduler_id}",
            backend="slurm",
            scheduler_id=scheduler_id,
            submitted_at=datetime.now().isoformat(),
            metadata={},
        )

    async def is_running(self, job_id: str, pid=None) -> bool:
        jid = self._normalize_id(job_id)
        print(f"[FAKE SLURM] is_running({jid}), GLOBAL_JOBS={self.jobs}")
        job = self.jobs.get(jid)
        if not job:
            return False
        # 只返回当前状态，不自动推进
        return job["status"] in {"PENDING", "RUNNING"}

    async def wait(self, job_id: str, timeout=None) -> int:
        jid = self._normalize_id(job_id)
        job = self.jobs.get(jid)
        if not job:
            return -1
        if job["status"] == "RUNNING":
            job["status"] = "COMPLETED"
            job["exit_code"] = 0
        return job["exit_code"] if job["exit_code"] is not None else -1

    async def kill(self, job_id: str) -> bool:
        jid = self._normalize_id(job_id)
        job = self.jobs.get(jid)
        if job:
            job["status"] = "CANCELLED"
            job["exit_code"] = 1
        return True

    async def run(
        self,
        work_dir: Path,
        command: str,
        env=None
    ) -> CommandResult:
        """
        Fake 执行接口（满足 Executor 抽象方法）
        真实 Slurm: spawn → sbatch → poll
        测试: 不真正执行命令，只模拟成功
        """
        return CommandResult(
            returncode=0,
            stdout="Fake Slurm run OK",
            stderr="",
        )

    async def _get_exit_code(self, job_id: str) -> int:
        jid = self._normalize_id(job_id)
        job = self.jobs.get(jid)
        if not job:
            return -1
        return job["exit_code"] if job["exit_code"] is not None else -1

    # 状态控制接口（测试专用）
    def complete_job(self, job_id: str):
        jid = self._normalize_id(job_id)
        if jid in self.jobs:
            self.jobs[jid]["status"] = "COMPLETED"
            self.jobs[jid]["exit_code"] = 0

    def fail_job(self, job_id: str):
        jid = self._normalize_id(job_id)
        if jid in self.jobs:
            self.jobs[jid]["status"] = "FAILED"
            self.jobs[jid]["exit_code"] = 1

    def get_config(self) -> dict:
        """返回完整的配置，包括新增字段"""
        config = {
            "type": "fake_slurm",
            "partition": self.partition,
            "ntasks": self.ntasks,
        }
        if self.account is not None:
            config["account"] = self.account
        if self.qos is not None:
            config["qos"] = self.qos
        if self.walltime is not None:
            config["walltime"] = self.walltime
        # 合并额外参数
        config.update(self.extra_config)
        return config

    def validate(self) -> bool:
        """FakeSlurmExecutor 默认有效"""
        return True


class FailingPollExecutor(FakeSlurmExecutor):
    """
    模拟 Slurm 执行器：前 fail_after 次调用成功，之后每次调用抛出异常
    用于测试恢复后轮询过程中出现持续性故障的场景
    """

    def __init__(self, fail_after: int = 0, **kwargs):
        """
        Args:
            fail_after: 前 N 次 is_running 调用正常返回，第 N+1 次及以后抛出异常
            **kwargs: 传递给 FakeSlurmExecutor 的参数
        """
        super().__init__(**kwargs)
        self.fail_after = fail_after
        self.calls = 0

    async def is_running(self, job_id: str, pid: Optional[int] = None) -> bool:
        """
        前 fail_times 次调用抛出 RuntimeError，模拟 Slurm 服务不可用
        之后调用父类方法正常返回状态
        """
        self.calls += 1
        if self.calls > self.fail_after:
            raise RuntimeError(f"Slurm unavailable (call {self.calls})")
        return await super().is_running(job_id, pid)

    def get_config(self) -> dict:
        """返回完整配置，确保恢复时能重建 FailingPollExecutor"""
        # 先获取父类配置，然后覆盖 type 和添加 fail_times
        config = super().get_config()
        config["type"] = "failing_slurm"
        config["fail_after"] = self.fail_after
        return config

    def validate(self) -> bool:
        """FakeSlurmExecutor 默认有效"""
        return True

# 注册到 ExecutorFactory（供 recover 重建）
if "fake_slurm" not in ExecutorFactory._registry:
    ExecutorFactory.register("fake_slurm", FakeSlurmExecutor)