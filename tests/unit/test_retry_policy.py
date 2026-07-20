"""RetryPolicy 单元测试"""

import pytest

from masgent.tasks.retry import RetryPolicy
from masgent.models.enums import TaskStatus
from tests.conftest import create_task_record


def test_retry_policy_should_retry_default():
    """默认策略：UNKNOWN 且 retry_count < max_retries 应返回 True"""
    policy = RetryPolicy(max_retries=3)
    record = create_task_record(
        "retry_test",
        TaskStatus.UNKNOWN,
        retry_count=0,
    )
    assert policy.should_retry(record) is True


def test_retry_policy_should_not_retry_exhausted():
    """达到 max_retries 时不应重试"""
    policy = RetryPolicy(max_retries=3)
    record = create_task_record(
        "retry_test",
        TaskStatus.UNKNOWN,
        retry_count=3,
    )
    assert policy.should_retry(record) is False


def test_retry_policy_is_exhausted():
    """is_exhausted 在 retry_count >= max_retries 时返回 True"""
    policy = RetryPolicy(max_retries=3)
    record = create_task_record(
        "retry_test",
        TaskStatus.UNKNOWN,
        retry_count=3,
    )
    assert policy.is_exhausted(record) is True


def test_retry_policy_not_exhausted():
    """retry_count < max_retries 时 is_exhausted 返回 False"""
    policy = RetryPolicy(max_retries=3)
    record = create_task_record(
        "retry_test",
        TaskStatus.UNKNOWN,
        retry_count=2,
    )
    assert policy.is_exhausted(record) is False


def test_retry_policy_custom_status():
    """自定义 retryable_statuses"""
    policy = RetryPolicy(
        max_retries=2,
        retryable_statuses={TaskStatus.RUNNING},
    )
    record = create_task_record(
        "running_retry",
        TaskStatus.RUNNING,
        retry_count=0,
    )
    assert policy.should_retry(record) is True

    # UNKNOWN 不应被重试
    record2 = create_task_record(
        "unknown_retry",
        TaskStatus.UNKNOWN,
        retry_count=0,
    )
    assert policy.should_retry(record2) is False


def test_retry_policy_custom_max_retries():
    """自定义 max_retries"""
    policy = RetryPolicy(max_retries=1)
    record = create_task_record(
        "retry_test",
        TaskStatus.UNKNOWN,
        retry_count=1,
    )
    assert policy.is_exhausted(record) is True
    assert policy.should_retry(record) is False