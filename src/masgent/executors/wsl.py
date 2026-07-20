"""Windows WSL 执行器——通过 wsl.exe 调用，不负责路径转换"""

import subprocess
from pathlib import Path
from typing import Optional, Dict

from masgent.executors.base import Executor
from masgent.models.executor import CommandResult


class WSLExecutor(Executor):
    """
    Windows WSL 执行器
    
    注意：work_dir 必须是 WSL 内部的绝对路径（如 /home/user/run_001），
    不负责将 Windows 路径转换为 WSL 路径。
    """

    def __init__(self, distro: str = "Ubuntu"):
        self.distro = distro

    def run(
        self,
        work_dir: Path,
        command: str,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        # 校验：必须是 WSL 绝对路径
        work_dir_str = str(work_dir)
        if not work_dir_str.startswith("/"):
            raise ValueError(
                f"WSLExecutor requires absolute WSL path, got: {work_dir_str}. "
                "Please use WSL internal paths like /home/user/run_001"
            )

        wsl_cmd = [
            "wsl",
            "-d",
            self.distro,
            "bash",
            "-lc",
            f"cd '{work_dir_str}' && {command}",
        ]

        proc = subprocess.run(
            wsl_cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
            check=False,
        )

        return CommandResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    def health_check(self) -> tuple[bool, str]:
        try:
            # 基础连通性检查
            result = subprocess.run(
                ["wsl", "-d", self.distro, "echo", "OK"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            if result.returncode != 0:
                return False, result.stderr or "WSL command failed"

            # 获取 WSL 发行版信息
            uname_result = subprocess.run(
                ["wsl", "-d", self.distro, "uname", "-a"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            if uname_result.returncode == 0 and uname_result.stdout.strip():
                return True, f"WSL OK ({uname_result.stdout.strip()})"

            # 降级：只返回发行版名称
            lsb_result = subprocess.run(
                ["wsl", "-d", self.distro, "lsb_release", "-ds"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            if lsb_result.returncode == 0 and lsb_result.stdout.strip():
                return True, f"WSL OK ({lsb_result.stdout.strip()})"

            return True, f"WSL OK ({self.distro})"

        except subprocess.TimeoutExpired as e:
            return False, f"WSL health check timeout: {e}"
        except FileNotFoundError:
            return False, "WSL command not found (is WSL installed?)"
        except Exception as e:
            return False, f"WSL health check failed: {e}"