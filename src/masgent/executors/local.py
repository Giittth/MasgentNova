"""本地执行器 —— 支持命令别名注入，日志持久化，进程追踪"""

import asyncio
import subprocess
import uuid
from pathlib import Path
from typing import Optional, Dict, Tuple, TextIO

import psutil

from masgent.executors.base import Executor
from masgent.models.job import JobHandle
from masgent.models.executor import CommandResult


class LocalExecutor(Executor):
    def __init__(self, aliases: Optional[Dict[str, str]] = None):
        self._processes: Dict[str, subprocess.Popen] = {}
        self._log_files: Dict[str, Tuple[TextIO, TextIO]] = {}
        self.aliases = aliases or {}

    def _resolve_command(self, command: str) -> str:
        return self.aliases.get(command, command)

    def _close_logs(self, job_id: str) -> None:
        """安全关闭日志文件句柄"""
        files = self._log_files.pop(job_id, None)
        if files:
            for f in files:
                try:
                    f.close()
                except Exception:
                    pass

    async def spawn(
        self,
        work_dir: Path,
        command: str,
        env: Optional[Dict[str, str]] = None,
    ) -> JobHandle:
        actual_command = self._resolve_command(command)
        job_id = f"local_{uuid.uuid4().hex[:8]}"

        # 日志文件路径
        stdout_path = work_dir / "stdout.log"
        stderr_path = work_dir / "stderr.log"

        # 使用 line-buffering (buffering=1) 确保实时写入
        stdout_file = open(stdout_path, "w", buffering=1, encoding="utf-8")
        stderr_file = open(stderr_path, "w", buffering=1, encoding="utf-8")

        try:
            proc = subprocess.Popen(
                actual_command,
                shell=True,
                cwd=work_dir,
                env=env,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
            )
        except Exception:
            # Popen 失败时，关闭文件句柄并重新抛出
            stdout_file.close()
            stderr_file.close()
            raise

        self._processes[job_id] = proc
        self._log_files[job_id] = (stdout_file, stderr_file)

        return JobHandle(
            job_id=job_id,
            backend="local",
            pid=proc.pid,
            submitted_at=JobHandle.now(),
            metadata={"command": actual_command},
        )

    async def is_running(self, job_id: str, pid: Optional[int] = None) -> bool:
        proc = self._processes.get(job_id)
        if proc is not None:
            return proc.poll() is None
        if pid is not None:
            try:
                return psutil.pid_exists(pid)
            except Exception:
                return False
        return False

    async def wait(self, job_id: str, timeout: Optional[int] = None) -> int:
        proc = self._processes.get(job_id)
        if proc is None:
            return -1
        try:
            if timeout is not None:
                ret = proc.wait(timeout=timeout)
            else:
                ret = proc.wait()
            return ret
        except subprocess.TimeoutExpired:
            return -2
        finally:
            self._close_logs(job_id)

    async def kill(self, job_id: str) -> bool:
        """
        强制终止进程及其所有子进程（进程树）
        使用 psutil 递归终止，避免残留子进程
        """
        proc = self._processes.get(job_id)
        if proc is None:
            return False

        try:
            parent = psutil.Process(proc.pid)
            children = parent.children(recursive=True)

            # 先终止子进程
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass

            # 再终止父进程
            try:
                parent.terminate()
            except psutil.NoSuchProcess:
                pass

            # 等待所有进程结束
            all_procs = [parent] + children
            gone, alive = psutil.wait_procs(all_procs, timeout=5)

            # 强制 kill 仍然存活的
            for p in alive:
                try:
                    p.kill()
                except psutil.NoSuchProcess:
                    pass

            # 再次等待确保全部退出
            if alive:
                psutil.wait_procs(alive, timeout=3)

            return True
        except psutil.NoSuchProcess:
            return True
        except Exception:
            return False
        finally:
            self._processes.pop(job_id, None)
            self._close_logs(job_id)

    async def run(
        self,
        work_dir: Path,
        command: str,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        actual_command = self._resolve_command(command)
        proc = subprocess.run(
            actual_command,
            shell=True,
            cwd=work_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        # 写入日志文件（与 spawn 格式保持一致）
        stdout_path = work_dir / "stdout.log"
        stderr_path = work_dir / "stderr.log"
        stdout_path.write_text(proc.stdout, encoding="utf-8")
        stderr_path.write_text(proc.stderr, encoding="utf-8")
        return CommandResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    def health_check(self) -> tuple[bool, str]:
        import shutil
        shell = shutil.which("bash") or shutil.which("sh")
        if not shell:
            return False, "No shell found"
        return True, f"Local shell available ({shell})"

    def get_init_params(self) -> dict:
        """返回可序列化的配置，用于恢复时重建 LocalExecutor"""
        return {
            "type": "local",
            "aliases": self.aliases,
        }

    def get_config(self) -> dict:
        return {
            "type": "local",
            "aliases": {
                k: str(v) for k, v in self.aliases.items()
            },
        }

    def validate(self) -> bool:
        """LocalExecutor 总是有效"""
        return True