"""
任务状态管理 —— 持久化与状态迁移
"""

from datetime import datetime
from typing import Optional, Dict, Any

from masgent.models.task import TaskRecord
from masgent.models.enums import TaskStatus
from masgent.tasks.task_store import TaskStore
from masgent.utils.logger import logger


class TaskStateManager:
    """任务状态管理：唯一负责 TaskRecord 的状态变更和持久化"""

    def __init__(self, task_store: TaskStore):
        self._task_store = task_store

    def load(self, task_id: str) -> Optional[TaskRecord]:
        return self._task_store.load(task_id)

    def save(self, record: TaskRecord) -> None:
        self._task_store.save(record)

    def set_status(
        self,
        task_id: str,
        status: TaskStatus,
        error_message: Optional[str] = None,
    ) -> Optional[TaskRecord]:
        """设置任务状态，自动更新时间戳"""
        record = self._task_store.load(task_id)
        if record is None:
            return None

        record.status = status
        record.updated_at = datetime.now()
        if error_message:
            record.error_message = error_message
        if status.is_terminal:
            record.finished_at = datetime.now()

        self._task_store.save(record)
        return record

    def set_completed(self, task_id: str, result: Dict[str, Any]) -> Optional[TaskRecord]:
        """标记任务完成"""
        record = self._task_store.load(task_id)
        if record is None:
            return None

        try:
            record.set_status(TaskStatus.COMPLETED)
        except ValueError:
            pass
        record.status = TaskStatus.COMPLETED
        record.updated_at = datetime.now()
        record.finished_at = datetime.now()
        record.result = {
            "data": result.get("data", {}),
            "metadata": result.get("metadata", {}),
        }
        self._task_store.save(record)
        return record

    def get_active_tasks(self) -> list[TaskRecord]:
        """获取所有活跃任务（PENDING, RUNNING, UNKNOWN）"""
        return [t for t in self._task_store.get_active_tasks() if t.status.is_active]