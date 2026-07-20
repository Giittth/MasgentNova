"""
UNKNOWN Auto Strategy 集成测试
"""

import pytest
import asyncio
import json
from pathlib import Path
from datetime import datetime

from masgent.models.enums import TaskStatus, WorkflowType, UnknownStrategy
from masgent.models.task import TaskRecord
from masgent.models.job import JobHandle
from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry
from tests.mock_calculator import MockCalculator, UnknownCalculator
from tests.mock_executors import FakeSlurmExecutor


@pytest.fixture(autouse=True)
def register_calculators():
    from masgent.calculators.registry import CalculatorRegistry
    if not CalculatorRegistry._factories.get("unknown_calc"):
        CalculatorRegistry.register("unknown_calc", UnknownCalculator)
    if not CalculatorRegistry._factories.get("mock"):
        CalculatorRegistry.register("mock", MockCalculator)
    yield


@pytest.fixture(autouse=True)
def ensure_fake_slurm():
    from masgent.executors.factory import ExecutorFactory
    if "fake_slurm" not in ExecutorFactory._registry:
        ExecutorFactory.register("fake_slurm", FakeSlurmExecutor)
    yield


@pytest.mark.asyncio
async def test_unknown_auto_job_alive(temp_task_dir):
    """
    auto 策略：job_handle 存在 + is_running()=True → restart_poll
    使用 UnknownCalculator 确保进入 UNKNOWN 分支
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.AUTO)

    task_id = "auto_alive"
    work_dir = temp_task_dir / "auto_alive"
    work_dir.mkdir(parents=True, exist_ok=True)

    executor = FakeSlurmExecutor(partition="cpu")
    FakeSlurmExecutor.GLOBAL_JOBS["1234"] = {
        "status": "RUNNING",
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": str(work_dir),
    }

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
        calculator_type="unknown_calc",  # 使用 UnknownCalculator
        calculator_params={},
        workflow_params={},
        job_handle=job_handle.to_dict(),
        executor_config=executor.get_config(),
        retry_count=0,
    )
    store.save(record)

    calc = UnknownCalculator(executor=executor) 
    runner._executors[task_id] = executor
    runner._calculators[task_id] = calc

    await runner.recover()
    await asyncio.sleep(0.2)

    # 验证走的是 poll 分支
    assert task_id in runner._running_tasks

    # 验证 RecoveryEvent
    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()
    with open(events_file, "r") as f:
        lines = f.readlines()
    events = [json.loads(line) for line in lines]
    task_events = [e for e in events if e["task_id"] == task_id]
    actions = [e["action"] for e in task_events]

    assert "probe" in actions
    assert "restart_poll" in actions  # _restart_poll 内部已加日志

    await runner.shutdown()


@pytest.mark.asyncio
async def test_unknown_auto_job_dead(temp_task_dir):
    """
    auto 策略：job_handle 存在 + is_running()=False → restart_execute
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.AUTO)

    task_id = "auto_dead"
    work_dir = temp_task_dir / "auto_dead"
    work_dir.mkdir(parents=True, exist_ok=True)

    executor = FakeSlurmExecutor(partition="cpu")
    FakeSlurmExecutor.GLOBAL_JOBS["5678"] = {
        "status": "COMPLETED",
        "exit_code": 0,
        "command": "echo done",
        "work_dir": str(work_dir),
    }

    job_handle = JobHandle(
        job_id="slurm_5678",
        backend="slurm",
        scheduler_id="5678",
        submitted_at=datetime.now().isoformat(),
    )

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="unknown_calc",
        calculator_params={},
        workflow_params={},
        job_handle=job_handle.to_dict(),
        executor_config=executor.get_config(),
        retry_count=0,
    )
    store.save(record)

    calc = UnknownCalculator(executor=executor)
    runner._executors[task_id] = executor
    runner._calculators[task_id] = calc

    await runner.recover()
    await asyncio.sleep(0.2)

    # 验证走的是 execute 分支 → 任务重新提交
    record = store.load(task_id)
    assert record.status in (TaskStatus.RUNNING, TaskStatus.FAILED)

    # 验证 RecoveryEvent（不检查 probe，因为 dead 情况下 classify 返回 execute 不会记录 probe）
    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()
    with open(events_file, "r") as f:
        lines = f.readlines()
    events = [json.loads(line) for line in lines]
    task_events = [e for e in events if e["task_id"] == task_id]
    actions = [e["action"] for e in task_events]

    assert "retry" in actions
    assert "restart_execute" in actions

    await runner.shutdown()


@pytest.mark.asyncio
async def test_unknown_strategy_execute_force(temp_task_dir):
    """
    execute 策略：强制重新执行，不探测
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.EXECUTE)

    task_id = "force_execute"
    work_dir = temp_task_dir / "force_execute"
    work_dir.mkdir(parents=True, exist_ok=True)

    executor = FakeSlurmExecutor(partition="cpu")
    FakeSlurmExecutor.GLOBAL_JOBS["9999"] = {
        "status": "RUNNING",  # 即使是 RUNNING，execute 策略也忽略
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": str(work_dir),
    }

    job_handle = JobHandle(
        job_id="slurm_9999",
        backend="slurm",
        scheduler_id="9999",
        submitted_at=datetime.now().isoformat(),
    )

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="unknown_calc",
        calculator_params={},
        workflow_params={},
        job_handle=job_handle.to_dict(),
        executor_config=executor.get_config(),
        retry_count=0,
    )
    store.save(record)

    calc = UnknownCalculator(executor=executor)
    runner._executors[task_id] = executor
    runner._calculators[task_id] = calc

    await runner.recover()
    await asyncio.sleep(0.2)

    record = store.load(task_id)
    assert record.status in (TaskStatus.RUNNING, TaskStatus.FAILED)

    events_file = temp_task_dir / "recovery_events.jsonl"
    if events_file.exists():
        with open(events_file, "r") as f:
            lines = f.readlines()
        events = [json.loads(line) for line in lines]
        task_events = [e for e in events if e["task_id"] == task_id]
        actions = [e["action"] for e in task_events]
        # execute 策略没有 probe
        assert "probe" not in actions
        assert "restart_execute" in actions

    await runner.shutdown()


@pytest.mark.asyncio
async def test_unknown_strategy_poll_force(temp_task_dir):
    """
    poll 策略：强制轮询，不探测
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.POLL)

    task_id = "force_poll"
    work_dir = temp_task_dir / "force_poll"
    work_dir.mkdir(parents=True, exist_ok=True)

    executor = FakeSlurmExecutor(partition="cpu")
    FakeSlurmExecutor.GLOBAL_JOBS["8888"] = {
        "status": "COMPLETED",  # 即使是 COMPLETED，poll 策略也忽略
        "exit_code": 0,
        "command": "echo done",
        "work_dir": str(work_dir),
    }

    job_handle = JobHandle(
        job_id="slurm_8888",
        backend="slurm",
        scheduler_id="8888",
        submitted_at=datetime.now().isoformat(),
    )

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="unknown_calc",
        calculator_params={},
        workflow_params={},
        job_handle=job_handle.to_dict(),
        executor_config=executor.get_config(),
        retry_count=0,
    )
    store.save(record)

    calc = UnknownCalculator(executor=executor)
    runner._executors[task_id] = executor
    runner._calculators[task_id] = calc

    await runner.recover()
    await asyncio.sleep(0.2)

    # poll 策略强制进入 _running_tasks
    assert task_id in runner._running_tasks

    events_file = temp_task_dir / "recovery_events.jsonl"
    if events_file.exists():
        with open(events_file, "r") as f:
            lines = f.readlines()
        events = [json.loads(line) for line in lines]
        task_events = [e for e in events if e["task_id"] == task_id]
        actions = [e["action"] for e in task_events]
        # poll 策略没有 probe
        assert "probe" not in actions
        assert "restart_poll" in actions

    await runner.shutdown()

@pytest.mark.asyncio
async def test_unknown_auto_retry_exhausted(temp_task_dir):
    """
    场景：UNKNOWN 重试次数耗尽 → FAILED
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.AUTO)

    task_id = "unknown_exhausted"
    work_dir = temp_task_dir / "unknown_exhausted"
    work_dir.mkdir(parents=True, exist_ok=True)

    # retry_count = max_retries（默认 RetryPolicy max_retries=3）
    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="unknown_calc",
        calculator_params={},
        workflow_params={},
        retry_count=3,  # 已达上限
    )
    store.save(record)

    calc = UnknownCalculator()
    runner._calculators[task_id] = calc

    await runner.recover()
    await asyncio.sleep(0.2)

    record = store.load(task_id)
    assert record.status == TaskStatus.FAILED
    assert "UNKNOWN after 4 retries" in record.error_message

    # 验证 RecoveryEvent（只有 failed，没有 retry）
    events_file = temp_task_dir / "recovery_events.jsonl"
    if events_file.exists():
        with open(events_file, "r") as f:
            lines = f.readlines()
        events = [json.loads(line) for line in lines]
        task_events = [e for e in events if e["task_id"] == task_id]
        actions = [e["action"] for e in task_events]
        assert "failed" in actions

    await runner.shutdown()

@pytest.mark.asyncio
async def test_unknown_auto_no_job_handle(temp_task_dir):
    """
    场景：UNKNOWN + job_handle=None → restart_execute
    AUTO 策略流程：
        UNKNOWN
          ↓
        retry
          ↓
        probe(classify -> execute)
          ↓
        restart_execute
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(
        store,
        registry,
        unknown_strategy=UnknownStrategy.AUTO,
    )

    task_id = "unknown_no_handle"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.RUNNING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="unknown_calc",
        calculator_params={},
        workflow_params={},
        job_handle=None,
        retry_count=0,
    )
    store.save(record)

    calc = UnknownCalculator()
    runner._calculators[task_id] = calc

    await runner.recover()
    await asyncio.sleep(0.2)

    assert task_id in runner._running_tasks

    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()

    with open(events_file, "r") as f:
        events = [json.loads(line) for line in f.readlines()]

    actions = [e["action"] for e in events if e["task_id"] == task_id]

    # 验证事件顺序（完整列表比较）
    assert actions == [
        "retry",
        "probe",
        "restart_execute",
    ]
    await runner.shutdown()
