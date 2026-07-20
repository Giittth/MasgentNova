"""任务重试策略"""

from dataclasses import dataclass, field
from typing import Set

from masgent.models.enums import TaskStatus
from masgent.models.task import TaskRecord


@dataclass
class RetryPolicy:
    """
    任务恢复重试策略

    默认：
        UNKNOWN 状态最多重试 3 次
    """

    max_retries: int = 3
    retryable_statuses: Set[TaskStatus] = field(
        default_factory=lambda: {
            TaskStatus.UNKNOWN,
        }
    )

    def should_retry(self, record: TaskRecord) -> bool:
        """
        判断当前任务是否允许重试

        Args:
            record: 任务记录

        Returns:
            bool: 是否允许重试
        """
        return (
            record.status in self.retryable_statuses
            and record.retry_count < self.max_retries
        )

    def is_exhausted(self, record: TaskRecord) -> bool:
        """
        是否达到最大重试次数

        Args:
            record: 任务记录

        Returns:
            bool: 是否已耗尽重试机会
        """
        return record.retry_count >= self.max_retries