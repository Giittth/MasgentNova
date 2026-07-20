"""
恢复锁 —— 防止多个 TaskRunner 实例同时恢复同一任务

使用模块级全局变量 _GLOBAL_LOCKS 和 _GLOBAL_GUARD，
确保同一 Python 进程内所有 TaskRunner 实例共享同一锁字典。
"""

import threading
from typing import Dict, Optional

# 模块级全局变量（进程内唯一）
_GLOBAL_LOCKS: Dict[str, threading.Lock] = {}
_GLOBAL_GUARD = threading.Lock()


class RecoveryLock:
    """
    任务级恢复锁

    基于 threading.Lock 实现，适用于同一进程内多个 TaskRunner 实例。
    跨进程锁（文件锁）将在 v0.6.5 实现。
    """

    async def acquire(self, task_id: str, timeout: float = 0.0) -> bool:
        """
        尝试获取任务锁

        Args:
            task_id: 任务 ID
            timeout: 等待超时时间（秒），0 表示非阻塞

        Returns:
            True 表示获取成功，False 表示获取失败
        """
        # 使用 guard 保护字典修改
        with _GLOBAL_GUARD:
            lock = _GLOBAL_LOCKS.setdefault(task_id, threading.Lock())

        if timeout == 0:
            return lock.acquire(blocking=False)
        return lock.acquire(blocking=True, timeout=timeout)

    def release(self, task_id: str) -> None:
        """释放任务锁"""
        lock = _GLOBAL_LOCKS.get(task_id)
        if lock and lock.locked():
            lock.release()

    def is_locked(self, task_id: str) -> bool:
        """检查任务是否被锁定"""
        lock = _GLOBAL_LOCKS.get(task_id)
        return lock is not None and lock.locked()

    def clear(self) -> None:
        """清理所有锁（仅测试使用）"""
        _GLOBAL_LOCKS.clear()


# 调试函数（测试用）
def debug_lock_count() -> int:
    """返回当前全局锁字典的大小（测试用）"""
    return len(_GLOBAL_LOCKS)


def debug_has_lock(task_id: str) -> bool:
    """检查指定任务是否在全局锁字典中（测试用）"""
    return task_id in _GLOBAL_LOCKS