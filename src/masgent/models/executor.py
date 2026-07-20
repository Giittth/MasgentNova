"""Executor 层数据模型：统一命令执行结果"""

from dataclasses import dataclass


@dataclass
class CommandResult:
    """统一的命令执行结果——适配所有 Executor 后端"""

    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.returncode == 0

    def __str__(self) -> str:
        return f"CommandResult(returncode={self.returncode}, stdout_len={len(self.stdout)}, stderr_len={len(self.stderr)})"