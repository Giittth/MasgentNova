"""
文件锁 —— 跨进程恢复锁

使用 fcntl.flock 实现跨进程互斥。
支持陈旧锁检测与强制夺取（持有进程死亡 或 同进程协程被 cancel）。
注意：仅支持 POSIX 系统（Linux/macOS），Windows 不支持。

核心设计：
    - acquire(): 创建锁文件 → 获取 flock → 写 PID
    - release(): 释放 flock → 关闭 fd → 删除锁文件
    - is_stale(): 文件不存在 → False；PID 无效/死亡 → True；flock 不存在 → True；flock 存在 → False
    - force_acquire(): 仅当 is_stale() 为 True 时，删除旧锁文件并重新创建
"""

import os
import fcntl
import time
from pathlib import Path
from typing import Optional


class FileLock:
    def __init__(self, task_id: str, lock_dir: Path):
        self.task_id = task_id
        self.lock_dir = Path(lock_dir).resolve()
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self._lock_file: Optional[Path] = None
        self._fd: Optional[int] = None
        self._acquired = False

    def _get_lock_path(self) -> Path:
        safe_name = self.task_id.replace("/", "_").replace("\\", "_")
        return self.lock_dir / f"{safe_name}.lock"

    def _read_owner_pid(self) -> Optional[int]:
        lock_path = self._get_lock_path()
        try:
            content = lock_path.read_text().strip()
            return int(content) if content else None
        except (OSError, ValueError):
            return None

    def _write_owner_pid(self) -> None:
        if self._fd is not None:
            try:
                os.ftruncate(self._fd, 0)
                os.lseek(self._fd, 0, os.SEEK_SET)
                os.write(self._fd, str(os.getpid()).encode())
            except OSError:
                pass

    def _is_pid_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    def is_stale(self) -> bool:
        """
        检查锁是否陈旧。

        判定规则：
            1. 锁文件不存在 → False（无锁）
            2. PID 无效（文件为空或非数字）→ True（陈旧）
            3. 持有进程已死亡 → True（陈旧）
            4. flock 不存在 → True（陈旧）
            5. flock 存在 → False（有效锁）

        不使用 pid == os.getpid() 判断，而是通过 flock 探测确认是否真的持有锁。
        """
        lock_path = self._get_lock_path()

        # 1. 文件不存在 → 没有锁
        if not lock_path.exists():
            return False

        # 2. 读取 PID
        pid = self._read_owner_pid()

        # 3. 文件存在但内容无效 → 陈旧
        if pid is None:
            return True

        # 4. 持有进程已死亡 → 陈旧
        if not self._is_pid_alive(pid):
            return True

        # 5. 核心：PID 存活，检查 flock 是否仍被持有
        fd = None
        try:
            fd = os.open(str(lock_path), os.O_RDWR)

            # 尝试非阻塞获取锁
            # 如果能成功获取 flock，说明没有其它进程真正持有锁
            # 锁文件是陈旧状态
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # 能获取 flock → 没有其它进程持有 → 陈旧
                return True
            except BlockingIOError:
                # flock 被其它进程持有 → 有效锁
                return False

        except OSError:
            # 文件被删除或无法打开 → 视为陈旧
            return True
        finally:
            if fd is not None:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except Exception:
                    pass
                try:
                    os.close(fd)
                except Exception:
                    pass

    def force_acquire(self) -> bool:
        """
        强制夺取陈旧锁，仅在 is_stale() 为 True 后调用。
        """
        if not self.is_stale():
            return False

        self._close_fd()
        lock_path = self._get_lock_path()
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass
        return self.acquire(timeout=0.0)

    def acquire(self, timeout: float = 0.0) -> bool:
        if self._acquired:
            return True

        lock_path = self._get_lock_path()
        try:
            self._fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
        except OSError:
            return False

        self._lock_file = lock_path

        try:
            if timeout == 0:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                start = time.time()
                while True:
                    try:
                        fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.time() - start > timeout:
                            self._close_fd()
                            return False
                        time.sleep(0.05)
        except BlockingIOError:
            self._close_fd()
            return False
        except Exception:
            self._close_fd()
            return False

        self._write_owner_pid()
        self._acquired = True
        return True

    def release(self) -> None:
        if not self._acquired:
            return
        self._acquired = False
        self._close_fd()

        # 删除锁文件
        try:
            self._get_lock_path().unlink(missing_ok=True)
        except Exception:
            pass

    def is_locked(self) -> bool:
        return self._acquired

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def _close_fd(self) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None
            self._lock_file = None