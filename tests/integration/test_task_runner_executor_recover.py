"""
TaskRunner.recover() 重建 Executor 集成测试

验证：
    TaskRunner.recover() → 读取 executor_config → 重建 executor → 继续任务
"""

import pytest
import asyncio
from datetime import datetime
from pathlib import Path

from masgent.models.task import TaskRecord
from masgent.models.enums import TaskStatus, WorkflowType
from masgent.executors import LocalExecutor, ExecutorFactory
from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry
from tests.conftest import create_task_record


@pytest.mark.asyncio
async def test_task_runner_recover_rebuilds_executor(temp_task_dir):
    """
    验证：recover() 从 executor_config 重建 executor，并继续运行任务
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    # 创建带有 executor_config 的 RUNNING 任务
    # ★ 关键：设置 detect_status_return 为 RUNNING，让 recover 认为任务仍在运行
    config = {"type": "local", "aliases": {"vasp_std": "/fake/vasp"}}

    record = create_task_record(
        task_id="recover_exec_test",
        status=TaskStatus.RUNNING,
        work_dir="/tmp/recover_test",
        calculator_type="mock",
        calculator_params={
            "detect_status_return": TaskStatus.RUNNING,  # ★ 让 recover 不跳过
        },
    )
    record.executor_config = config
    store.save(record)

    # 创建 TaskRunner 并恢复
    runner = TaskRunner(store, registry)
    await runner.recover()

    # 验证：executor 已重建并保存到 _executors
    assert "recover_exec_test" in runner._executors
    executor = runner._executors["recover_exec_test"]
    assert isinstance(executor, LocalExecutor)
    assert executor.aliases["vasp_std"] == "/fake/vasp"

    # 验证：任务已进入 _running_tasks（因为 detect_status 返回 RUNNING）
    assert "recover_exec_test" in runner._running_tasks