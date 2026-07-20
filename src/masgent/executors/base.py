"""Executor 抽象基类 —— 进程/作业执行接口"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict

from masgent.models.job import JobHandle
from masgent.models.executor import CommandResult


class Executor(ABC):
    @abstractmethod
    async def spawn(
        self,
        work_dir: Path,
        command: str,
        env: Optional[Dict[str, str]] = None,
    ) -> JobHandle:
        pass

    @abstractmethod
    async def is_running(self, job_id: str, pid: Optional[int] = None) -> bool:
        """检查作业是否存活，支持通过 PID 降级检测"""
        pass

    @abstractmethod
    async def wait(self, job_id: str, timeout: Optional[int] = None) -> int:
        pass

    @abstractmethod
    async def kill(self, job_id: str) -> bool:
        pass

    @abstractmethod
    async def run(
        self,
        work_dir: Path,
        command: str,
        env: Optional[Dict[str, str]] = None,
    ) -> CommandResult:
        pass

    def health_check(self) -> tuple[bool, str]:
        return True, "OK"

    def get_init_params(self) -> dict:
        """返回 Executor 的可序列化配置，用于恢复时重建"""
        return {}
    
    def get_config(self) -> dict:
        """
        返回可序列化的配置，用于持久化和恢复。

        子类必须重写此方法，返回完整的构造参数。
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.get_config() must be implemented"
        )
        
    def validate(self) -> bool:
        """
        验证 Executor 配置是否完整有效。

        子类应重写此方法，检查必要的配置字段（如 partition、ntasks 等）。
        默认返回 True。
        """
        return True