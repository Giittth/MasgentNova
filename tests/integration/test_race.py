"""
Race Tests —— 高并发恢复场景测试

验证 TaskRunner 在高并发和异常场景下的正确性：
    Case 1: 同一任务被 10 个 Runner 同时恢复 → 只有 1 个成功
    Case 2: 100 个不同任务同时恢复 → 全部成功，无死锁
    Case 3: 恢复过程中 shutdown → 所有锁正确释放（可重新获取）
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
from masgent.tasks.file_lock import FileLock
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


def create_running_record(task_id: str, work_dir: Path, scheduler_id: str = "9999"):
    """创建 RUNNING 任务的测试记录"""
    FakeSlurmExecutor.GLOBAL_JOBS[scheduler_id] = {
        "status": "RUNNING",
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": str(work_dir),
    }
    job_handle = JobHandle(
        job_id=f"slurm_{scheduler_id}",
        backend="slurm",
        scheduler_id=scheduler_id,
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
async def test_race_case_1_same_task_10_runners(temp_task_dir):
    """
    Race Case 1: 同一任务被 10 个 Runner 同时恢复
    预期：只有 1 个成功恢复，其余被跳过
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    task_id = "race_same_task"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    record = create_running_record(task_id, work_dir, scheduler_id="1111")
    store.save(record)

    runners = [
        TaskRunner(store, registry, unknown_strategy=UnknownStrategy.AUTO)
        for _ in range(10)
    ]

    await asyncio.gather(
        *[runner.recover() for runner in runners],
        return_exceptions=True
    )

    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()
    with open(events_file, "r") as f:
        events = [json.loads(line) for line in f.readlines()]

    task_events = [e for e in events if e["task_id"] == task_id]
    actions = [e["action"] for e in task_events]

    # 兼容未来策略变化：无论是 restart_poll 还是 restart_execute，只应该有一个
    recovery_actions = ["restart_poll", "restart_execute"]
    recovery_count = sum(1 for a in actions if a in recovery_actions)
    assert recovery_count == 1

    assert actions.count("skipped") >= 9

    for runner in runners:
        await runner.shutdown()


@pytest.mark.asyncio
async def test_race_case_2_100_different_tasks(temp_task_dir):
    """
    Race Case 2: 100 个不同任务同时恢复
    预期：全部成功恢复，无死锁（timeout 验证）
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    task_count = 100
    task_ids = [f"race_task_{i:03d}" for i in range(task_count)]

    for idx, task_id in enumerate(task_ids):
        work_dir = temp_task_dir / task_id
        work_dir.mkdir(parents=True, exist_ok=True)
        scheduler_id = str(2000 + idx)
        record = create_running_record(task_id, work_dir, scheduler_id=scheduler_id)
        store.save(record)

    runners = [
        TaskRunner(store, registry, unknown_strategy=UnknownStrategy.AUTO)
        for _ in range(10)
    ]

    # ★ 增加 timeout 验证无死锁
    try:
        await asyncio.wait_for(
            asyncio.gather(*[runner.recover() for runner in runners]),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        pytest.fail("Recovery timed out - possible deadlock")

    # 验证每个任务都完成了一次恢复
    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()
    with open(events_file, "r") as f:
        events = [json.loads(line) for line in f.readlines()]

    recovery_actions = {"restart_poll", "restart_execute"}
    recovered_count = 0
    for task_id in task_ids:
        task_events = [e for e in events if e["task_id"] == task_id]
        actions = [e["action"] for e in task_events]
        if any(a in recovery_actions for a in actions):
            recovered_count += 1

    assert recovered_count == task_count

    for runner in runners:
        await runner.shutdown()


@pytest.mark.asyncio
async def test_race_case_3_recover_interrupted_by_shutdown(temp_task_dir):
    """
    Race Case 3: 恢复过程中执行 shutdown
    验证：所有锁被正确释放（通过能否重新获取锁来验证）
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    # 创建 10 个任务
    task_count = 10
    task_ids = [f"race_shutdown_{i:03d}" for i in range(task_count)]

    for idx, task_id in enumerate(task_ids):
        work_dir = temp_task_dir / task_id
        work_dir.mkdir(parents=True, exist_ok=True)
        scheduler_id = str(3000 + idx)
        record = create_running_record(task_id, work_dir, scheduler_id=scheduler_id)
        store.save(record)

    # 使用 Event 精确控制恢复进度
    gate = asyncio.Event()
    original_recover_task = TaskRunner._recover_task

    async def controlled_recover_task(self, record):
        # 只对第一个任务卡住
        if record.task_id == task_ids[0]:
            await gate.wait()
        await original_recover_task(self, record)

    # Monkeypatch
    import types
    runner = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.AUTO)
    runner._recover_task = types.MethodType(controlled_recover_task, runner)

    # 启动恢复
    recover_task = asyncio.create_task(runner.recover())

    # 等待恢复开始（确保至少第一个任务卡在 gate）
    await asyncio.sleep(0.1)

    # shutdown（会取消所有任务）
    await runner.shutdown(timeout=2.0)

    # 释放 gate（让 recover 继续，但此时 runner 已 shutdown）
    gate.set()

    # 等待 recover 完成
    try:
        await recover_task
    except asyncio.CancelledError:
        pass

    # 验证锁已释放：尝试重新获取所有任务的 FileLock
    lock_dir = runner._lock_dir
    for task_id in task_ids:
        lock = FileLock(task_id, lock_dir)
        assert lock.acquire(timeout=0), f"Lock still held for task {task_id}"
        lock.release()

    # 验证 _running_tasks 已清理
    assert len(runner._running_tasks) == 0

    await runner.shutdown()