"""
任务恢复辅助函数
"""

from typing import Optional

from masgent.models.job import JobHandle
from masgent.executors.base import Executor


async def classify_unknown_task(
    executor: Optional[Executor],
    job_handle: Optional[JobHandle],
) -> str:
    """
    判断 UNKNOWN 任务应该 poll 还是 execute

    Args:
        executor: 执行器实例（可能为 None）
        job_handle: 作业句柄（可能为 None）

    Returns:
        "poll" 或 "execute"

    逻辑：
        - 无 job_handle → execute
        - 无 executor → execute（无法探测）
        - is_running() = True → poll
        - is_running() = False → execute
        - is_running() 异常 → execute（保守处理）
    """
    if not job_handle:
        return "execute"

    if not executor or not hasattr(executor, "is_running"):
        return "execute"

    try:
        scheduler_id = job_handle.scheduler_id or job_handle.job_id
        alive = await executor.is_running(scheduler_id)
        return "poll" if alive else "execute"
    except Exception:
        # 探测失败，保守执行（避免无限等待）
        return "execute"