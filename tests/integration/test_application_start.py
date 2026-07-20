"""
测试 Application 启动自动恢复
"""

import pytest
import asyncio
import json
from pathlib import Path
from datetime import datetime

from masgent.app import Application
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry
from masgent.models.enums import TaskStatus, WorkflowType, UnknownStrategy
from masgent.models.task import TaskRecord
from masgent.models.job import JobHandle
from tests.mock_calculator import UnknownCalculator, RunningCalculator
from tests.mock_executors import FakeSlurmExecutor


@pytest.fixture(autouse=True)
def register_calculators():
    from masgent.calculators.registry import CalculatorRegistry
    if not CalculatorRegistry._factories.get("unknown_calc"):
        CalculatorRegistry.register("unknown_calc", UnknownCalculator)
    if not CalculatorRegistry._factories.get("running_mock"):
        CalculatorRegistry.register("running_mock", RunningCalculator)
    yield


@pytest.fixture(autouse=True)
def ensure_fake_slurm():
    from masgent.executors.factory import ExecutorFactory
    if "fake_slurm" not in ExecutorFactory._registry:
        ExecutorFactory.register("fake_slurm", FakeSlurmExecutor)
    yield


@pytest.mark.asyncio
async def test_application_start_recovers_running_task(temp_task_dir):
    """
    场景：应用启动时，有 RUNNING 任务未完成
    预期：recover() 被自动调用，任务继续执行
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    task_id = "app_recover_test"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    executor = FakeSlurmExecutor(partition="cpu")
    FakeSlurmExecutor.GLOBAL_JOBS["1234"] = {
        "status": "RUNNING",
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": str(work_dir),
    }

    # 使用完整的 JobHandle 构造
    job_handle = JobHandle(
        job_id="slurm_1234",
        backend="slurm",
        scheduler_id="1234",
        submitted_at=datetime.now().isoformat(),
    )

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="running_mock",
        calculator_params={},
        workflow_params={},
        job_handle=job_handle.to_dict(),
        executor_config={"type": "fake_slurm", "partition": "cpu", "ntasks": 1},
        retry_count=0,
    )
    store.save(record)

    app = Application(
        task_store=store,
        calculator_registry=registry,
        unknown_strategy=UnknownStrategy.AUTO,
        auto_recover=True,
    )

    await app.start()

    assert task_id in app.task_runner._running_tasks

    record = store.load(task_id)
    assert record.status == TaskStatus.RUNNING

    await app.shutdown()


@pytest.mark.asyncio
async def test_application_start_with_auto_recover_disabled(temp_task_dir):
    """
    场景：auto_recover=False，应用启动时不自动恢复
    预期：任务保持原状态，不启动轮询
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    task_id = "no_recover_test"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="running_mock",
        calculator_params={},
        workflow_params={},
        retry_count=0,
    )
    store.save(record)

    app = Application(
        task_store=store,
        calculator_registry=registry,
        auto_recover=False,
    )

    await app.start()

    assert task_id not in app.task_runner._running_tasks
    record = store.load(task_id)
    assert record.status == TaskStatus.RUNNING

    await app.shutdown()


@pytest.mark.asyncio
async def test_application_start_is_idempotent(temp_task_dir):
    """
    场景：多次调用 start()，只有第一次执行恢复
    预期：后续调用被忽略
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    task_id = "idempotent_test"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="running_mock",
        calculator_params={},
        workflow_params={},
        retry_count=0,
    )
    store.save(record)

    app = Application(
        task_store=store,
        calculator_registry=registry,
        auto_recover=True,
    )

    # 第一次启动
    await app.start()
    assert task_id in app.task_runner._running_tasks
    assert app._started is True

    # 第二次启动（应被跳过）
    await app.start()
    # 只有一个任务在运行
    assert len(app.task_runner._running_tasks) == 1

    await app.shutdown()


@pytest.mark.asyncio
async def test_application_unknown_strategy_passed_to_runner(temp_task_dir):
    """
    验证 unknown_strategy 正确传递给 TaskRunner
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    app = Application(
        task_store=store,
        calculator_registry=registry,
        unknown_strategy=UnknownStrategy.POLL,
    )

    assert app.task_runner.unknown_strategy == UnknownStrategy.POLL

    # 测试其他策略
    app2 = Application(
        task_store=store,
        calculator_registry=registry,
        unknown_strategy="execute",
    )
    assert app2.task_runner.unknown_strategy == UnknownStrategy.EXECUTE

    await app.shutdown()
    await app2.shutdown()