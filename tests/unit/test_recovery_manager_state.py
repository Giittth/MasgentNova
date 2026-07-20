"""
测试 RecoveryManager 无状态 ownership
"""

import pytest
from pathlib import Path

from masgent.tasks.recovery_manager import RecoveryManager
from masgent.tasks.task_state import TaskStateManager
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry


def test_recovery_manager_has_no_ownership_state(temp_task_dir):
    """验证 RecoveryManager 不持有 _calculators 和 _executors"""
    store = JSONTaskStore(temp_task_dir)
    state = TaskStateManager(store)
    registry = CalculatorRegistry()

    rm = RecoveryManager(
        state_manager=state,
        calculator_registry=registry,
        lock_dir=temp_task_dir / ".locks",
    )

    assert not hasattr(rm, "_calculators"), "RecoveryManager should not own _calculators"
    assert not hasattr(rm, "_executors"), "RecoveryManager should not own _executors"