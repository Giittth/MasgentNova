"""
测试文件锁 + TaskRunner 集成
"""

import pytest
import asyncio
import json
from pathlib import Path
from datetime import datetime

from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry
from masgent.models.enums import TaskStatus, WorkflowType, UnknownStrategy
from masgent.models.task import TaskRecord
from masgent.models.job import JobHandle
from tests.mock_calculator import RunningCalculator
from tests.mock_executors import FakeSlurmExecutor


@pytest.fixture(autouse=True)
def register_running_calculator():
    from masgent.calculators.registry import CalculatorRegistry
    if not CalculatorRegistry._factories.get("running_mock"):
        CalculatorRegistry.register("running_mock", RunningCalculator)
    yield


@pytest.fixture(autouse=True)
def ensure_fake_slurm():
    from masgent.executors.factory import ExecutorFactory
    if "fake_slurm" not in ExecutorFactory._registry:
        ExecutorFactory.register("fake_slurm", FakeSlurmExecutor)
    yield


@pytest.fixture(autouse=True)
def clear_fake_slurm_jobs():
    FakeSlurmExecutor.clear_jobs()
    yield


def create_running_record(task_id: str, work_dir: Path):
    """创建 RUNNING 任务的测试记录"""
    FakeSlurmExecutor.GLOBAL_JOBS["9999"] = {
        "status": "RUNNING",
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
    return TaskRecord(
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


@pytest.mark.asyncio
async def test_file_lock_prevents_duplicate_recovery(temp_task_dir):
    """
    核心集成测试：两个 TaskRunner 同时 recover 同一 RUNNING 任务
    验证文件锁确保只有一个执行恢复，另一个跳过
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    task_id = "file_lock_dup_test"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    record = create_running_record(task_id, work_dir)
    store.save(record)

    # 创建两个 TaskRunner 实例
    runner1 = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.AUTO)
    runner2 = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.AUTO)

    # 并发执行 recover
    await asyncio.gather(
        runner1.recover(),
        runner2.recover(),
        return_exceptions=True
    )

    # 验证事件：只有一个 restart_poll，一个 skipped
    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()
    with open(events_file, "r") as f:
        events = [json.loads(line) for line in f.readlines()]

    task_events = [e for e in events if e["task_id"] == task_id]
    actions = [e["action"] for e in task_events]
    assert actions.count("restart_poll") == 1
    assert actions.count("skipped") == 1

    # 验证锁失败事件（使用 error.code）
    skipped = [e for e in task_events if e["action"] == "skipped"]
    assert any(
        e.get("error", {}).get("code") in ("lock_acquire_failed", "file_lock_failed")
        for e in skipped
    )

    await runner1.shutdown()
    await runner2.shutdown()


@pytest.mark.asyncio
async def test_recover_single_file_lock_failed(temp_task_dir, monkeypatch):
    """
    场景：FileLock.acquire() 返回 False
    预期：任务被跳过，事件包含 file_lock_failed
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    task_id = "file_lock_fail_test"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    record = create_running_record(task_id, work_dir)
    store.save(record)

    runner = TaskRunner(store, registry)

    # 模拟 FileLock.acquire 返回 False
    from masgent.tasks import file_lock

    def mock_acquire(self, timeout=0.0):
        return False

    monkeypatch.setattr(file_lock.FileLock, "acquire", mock_acquire)

    await runner.recover()

    # 验证任务被跳过
    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()
    with open(events_file, "r") as f:
        events = [json.loads(line) for line in f.readlines()]
    task_events = [e for e in events if e["task_id"] == task_id]
    assert len(task_events) == 1
    assert task_events[0]["action"] == "skipped"
    assert task_events[0]["error"]["code"] == "file_lock_failed"

    await runner.shutdown()
    monkeypatch.undo()