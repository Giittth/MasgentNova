"""
测试 Executor 配置验证逻辑
"""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime

from masgent.models.enums import TaskStatus, WorkflowType
from masgent.models.task import TaskRecord
from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry
from tests.conftest import wait_until


@pytest.mark.asyncio
async def test_recover_invalid_executor_config(temp_task_dir):
    """
    场景：executor_config 缺少必要参数（partition）
    预期：任务立即标记为 FAILED
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry)

    task_id = "invalid_executor_task"
    work_dir = temp_task_dir / "invalid_executor"
    work_dir.mkdir(parents=True, exist_ok=True)

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="mock",
        calculator_params={},
        workflow_params={},
        executor_config={"type": "slurm", "ntasks": 1},  # 缺少 partition
        retry_count=0,
    )
    store.save(record)

    await runner.recover()
    await asyncio.sleep(0.2)  # 给异步操作完成时间

    record = store.load(task_id)
    assert record.status == TaskStatus.FAILED
    assert "Executor rebuild failed" in record.error_message or "validation" in record.error_message

    await runner.shutdown()


@pytest.mark.asyncio
async def test_recover_executor_type_not_exists(temp_task_dir):
    """
    场景：executor_config 中 type 不存在
    预期：任务立即标记为 FAILED
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry)

    task_id = "unknown_type_task"
    work_dir = temp_task_dir / "unknown_type"
    work_dir.mkdir(parents=True, exist_ok=True)

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="mock",
        calculator_params={},
        workflow_params={},
        executor_config={"type": "nonexistent_executor"},
        retry_count=0,
    )
    store.save(record)

    await runner.recover()
    await asyncio.sleep(0.2)

    record = store.load(task_id)
    assert record.status == TaskStatus.FAILED
    assert "Executor rebuild failed" in record.error_message

    await runner.shutdown()


@pytest.mark.asyncio
async def test_recover_valid_executor_passes(temp_task_dir):
    """
    场景：executor_config 完整有效
    预期：任务正常恢复，不会标记 FAILED
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry)

    task_id = "valid_executor_task"
    work_dir = temp_task_dir / "valid_executor"
    work_dir.mkdir(parents=True, exist_ok=True)

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="mock",
        calculator_params={},
        workflow_params={},
        executor_config={"type": "slurm", "partition": "cpu", "ntasks": 1},
        retry_count=0,
    )
    store.save(record)

    await runner.recover()
    await asyncio.sleep(0.2)

    record = store.load(task_id)
    # 只验证没有被标记为 FAILED，具体状态取决于异步执行
    assert record.status != TaskStatus.FAILED

    await runner.shutdown()