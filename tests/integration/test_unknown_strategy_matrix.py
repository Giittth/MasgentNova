"""
UNKNOWN Strategy Matrix —— 完整覆盖所有 UNKNOWN 处理策略
"""

import pytest
import asyncio
import json
from pathlib import Path
from datetime import datetime

from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.tasks.retry import RetryPolicy
from masgent.calculators.registry import CalculatorRegistry
from masgent.models.enums import TaskStatus, WorkflowType, UnknownStrategy
from masgent.models.task import TaskRecord
from masgent.models.job import JobHandle
from tests.mock_executors import FakeSlurmExecutor
from tests.mock_calculator import UnknownCalculator, RunningCalculator, CompletedCalculator, MockCalculator


@pytest.fixture(autouse=True)
def register_unknown_calculator():
    from masgent.calculators.registry import CalculatorRegistry
    if not CalculatorRegistry._factories.get("unknown"):
        CalculatorRegistry.register("unknown", UnknownCalculator)
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


@pytest.mark.asyncio
async def test_unknown_auto_alive_restart_poll(temp_task_dir):
    """
    Case 1: AUTO + UNKNOWN + job_handle alive → restart_poll
    事件链：retry → probe → restart_poll
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.AUTO)

    task_id = "unknown_auto_alive"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # 伪造 RUNNING 作业
    FakeSlurmExecutor.GLOBAL_JOBS["1111"] = {
        "status": "RUNNING",
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": str(work_dir),
    }

    job_handle = JobHandle(
        job_id="slurm_1111",
        backend="slurm",
        scheduler_id="1111",
        submitted_at=datetime.now().isoformat(),
    )

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.UNKNOWN,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="unknown",
        calculator_params={},
        workflow_params={},
        job_handle=job_handle.to_dict(),
        executor_config={"type": "fake_slurm", "partition": "cpu", "ntasks": 1},
        retry_count=0,
    )
    store.save(record)

    await runner.recover()
    await asyncio.sleep(0.2)

    assert task_id in runner._running_tasks

    # 验证事件链
    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()
    with open(events_file, "r") as f:
        events = [json.loads(line) for line in f.readlines()]
    task_events = [e for e in events if e["task_id"] == task_id]
    actions = [e["action"] for e in task_events]

    assert actions == ["retry", "probe", "restart_poll"]

    await runner.shutdown()


@pytest.mark.asyncio
async def test_unknown_auto_dead_restart_execute(temp_task_dir):
    """
    Case 2: AUTO + UNKNOWN + job_handle dead → restart_execute
    事件链：retry → probe → restart_execute
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.AUTO)

    task_id = "unknown_auto_dead"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    FakeSlurmExecutor.GLOBAL_JOBS["2222"] = {
        "status": "COMPLETED",  # 作业已死
        "exit_code": 0,
        "command": "echo done",
        "work_dir": str(work_dir),
    }

    job_handle = JobHandle(
        job_id="slurm_2222",
        backend="slurm",
        scheduler_id="2222",
        submitted_at=datetime.now().isoformat(),
    )

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.UNKNOWN,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="unknown",
        calculator_params={},
        workflow_params={},
        job_handle=job_handle.to_dict(),
        executor_config={"type": "fake_slurm", "partition": "cpu", "ntasks": 1},
        retry_count=0,
    )
    store.save(record)

    await runner.recover()
    await asyncio.sleep(0.2)

    # 验证进入 execute 分支（任务被重新执行）
    # 注意：因为 UnknownCalculator 持续返回 UNKNOWN，retry_count 会递增
    record = store.load(task_id)
    assert record.retry_count == 1

    # 验证事件链（没有 probe，因为 dead 分支 classify 直接返回 execute）
    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()
    with open(events_file, "r") as f:
        events = [json.loads(line) for line in f.readlines()]
    task_events = [e for e in events if e["task_id"] == task_id]
    actions = [e["action"] for e in task_events]

    # AUTO 分支会记录 probe（即使 classify 返回 execute）
    assert actions == ["retry", "probe", "restart_execute"]

    await runner.shutdown()


@pytest.mark.asyncio
async def test_unknown_auto_no_job_handle_execute(temp_task_dir):
    """
    Case 3: AUTO + UNKNOWN + 无 job_handle → restart_execute
    事件链：retry → probe → restart_execute
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.AUTO)

    task_id = "unknown_no_handle"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.UNKNOWN,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="unknown",
        calculator_params={},
        workflow_params={},
        retry_count=0,
    )
    store.save(record)

    await runner.recover()
    await asyncio.sleep(0.2)

    record = store.load(task_id)
    assert record.retry_count == 1

    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()
    with open(events_file, "r") as f:
        events = [json.loads(line) for line in f.readlines()]
    task_events = [e for e in events if e["task_id"] == task_id]
    actions = [e["action"] for e in task_events]

    # AUTO 无条件记录 probe
    assert actions == ["retry", "probe", "restart_execute"]

    await runner.shutdown()


@pytest.mark.asyncio
async def test_unknown_strategy_execute_always(temp_task_dir):
    """
    Case 4: EXECUTE 策略 → 强制 restart_execute（不探测）
    事件链：retry → restart_execute
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.EXECUTE)

    task_id = "unknown_execute"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    FakeSlurmExecutor.GLOBAL_JOBS["4444"] = {
        "status": "RUNNING",  # 即使作业存活，EXECUTE 也忽略
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": str(work_dir),
    }

    job_handle = JobHandle(
        job_id="slurm_4444",
        backend="slurm",
        scheduler_id="4444",
        submitted_at=datetime.now().isoformat(),
    )

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.UNKNOWN,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="unknown",
        calculator_params={},
        workflow_params={},
        job_handle=job_handle.to_dict(),
        executor_config={"type": "fake_slurm", "partition": "cpu", "ntasks": 1},
        retry_count=0,
    )
    store.save(record)

    await runner.recover()
    await asyncio.sleep(0.2)

    record = store.load(task_id)
    assert record.retry_count == 1

    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()
    with open(events_file, "r") as f:
        events = [json.loads(line) for line in f.readlines()]
    task_events = [e for e in events if e["task_id"] == task_id]
    actions = [e["action"] for e in task_events]

    # EXECUTE 策略不记录 probe
    assert actions == ["retry", "restart_execute"]

    await runner.shutdown()


@pytest.mark.asyncio
async def test_unknown_strategy_poll_always(temp_task_dir):
    """
    Case 5: POLL 策略 → 强制 restart_poll（不探测）
    事件链：retry → restart_poll
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()
    runner = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.POLL)

    task_id = "unknown_poll"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    # 即使没有 job_handle，POLL 也尝试轮询（但会失败）
    # 但这里我们给一个 job_handle
    FakeSlurmExecutor.GLOBAL_JOBS["5555"] = {
        "status": "RUNNING",
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": str(work_dir),
    }

    job_handle = JobHandle(
        job_id="slurm_5555",
        backend="slurm",
        scheduler_id="5555",
        submitted_at=datetime.now().isoformat(),
    )

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.UNKNOWN,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="unknown",
        calculator_params={},
        workflow_params={},
        job_handle=job_handle.to_dict(),
        executor_config={"type": "fake_slurm", "partition": "cpu", "ntasks": 1},
        retry_count=0,
    )
    store.save(record)

    await runner.recover()
    await asyncio.sleep(0.2)

    assert task_id in runner._running_tasks

    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()
    with open(events_file, "r") as f:
        events = [json.loads(line) for line in f.readlines()]
    task_events = [e for e in events if e["task_id"] == task_id]
    actions = [e["action"] for e in task_events]

    # POLL 策略不记录 probe
    assert actions == ["retry", "restart_poll"]

    await runner.shutdown()


@pytest.mark.asyncio
async def test_unknown_retry_exhausted_to_failed(temp_task_dir):
    """
    Case 6: UNKNOWN + retry exhausted → FAILED
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    policy = RetryPolicy(max_retries=3)
    runner = TaskRunner(
        store,
        registry,
        retry_policy=policy,
        unknown_strategy=UnknownStrategy.AUTO,
    )

    task_id = "unknown_exhausted"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    FakeSlurmExecutor.GLOBAL_JOBS["6666"] = {
        "status": "RUNNING",
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": str(work_dir),
    }

    job_handle = JobHandle(
        job_id="slurm_6666",
        backend="slurm",
        scheduler_id="6666",
        submitted_at=datetime.now().isoformat(),
    )

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.UNKNOWN,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="unknown",
        calculator_params={},
        workflow_params={},
        job_handle=job_handle.to_dict(),
        executor_config={"type": "fake_slurm", "partition": "cpu", "ntasks": 1},
        retry_count=0,
    )
    store.save(record)

    # 模拟多次 recover 直到 exhausted
    # 第 1 次：retry_count=1
    await runner.recover()
    await asyncio.sleep(0.2)
    record = store.load(task_id)
    assert record.retry_count == 1

    # 第 2 次：retry_count=2
    # 需要先清理 _running_tasks 才能再次 recover
    # 因为 UnknownCalculator 会一直返回 UNKNOWN，任务不会自动结束
    task = runner._running_tasks.pop(task_id, None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await runner.recover()
    await asyncio.sleep(0.2)
    record = store.load(task_id)
    assert record.retry_count == 2

    # 第 3 次：retry_count=3，达到 max_retries
    task = runner._running_tasks.pop(task_id, None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await runner.recover()
    await asyncio.sleep(0.2)

    record = store.load(task_id)
    assert record.status == TaskStatus.FAILED
    assert "UNKNOWN after 3 retries" in record.error_message

    await runner.shutdown()


@pytest.mark.asyncio
async def test_unknown_crash_recovery_then_retry(temp_task_dir):
    """
    Case 7: UNKNOWN → execute → RUNNING → crash → 接管 RUNNING → COMPLETED
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    # 注册本地 Calculator
    from masgent.models.calculator import CalculationResult

    class UnknownThenRunningThenCompletedCalculator(MockCalculator):
        TYPE = "unknown_then_running_then_completed"

        async def detect_status(self, work_dir, job=None):
            counter_file = work_dir / ".detect_count"
            count = 0
            if counter_file.exists():
                count = int(counter_file.read_text())
            count += 1
            counter_file.write_text(str(count))
            if count == 1:
                return TaskStatus.UNKNOWN
            if count == 2:
                return TaskStatus.RUNNING
            return TaskStatus.COMPLETED

        async def collect(self, work_dir, workflow_type):
            return CalculationResult(
                success=True,
                workflow_type=workflow_type,
                data={"energy": -10.5},
                metadata={"calculator": "unknown_then_running_then_completed"},
            )

    if not registry._factories.get("unknown_then_running_then_completed"):
        registry.register("unknown_then_running_then_completed", UnknownThenRunningThenCompletedCalculator)

    task_id = "unknown_crash_e2e"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.UNKNOWN,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="unknown_then_running_then_completed",
        calculator_params={},
        workflow_params={},
        retry_count=0,
    )
    store.save(record)

    # ---- Process A: UNKNOWN → retry → execute → RUNNING ----
    runner_a = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.AUTO)
    await runner_a.recover()

    # 等待进入 RUNNING 状态，retry_count=1
    for _ in range(30):
        record = store.load(task_id)
        if record.status == TaskStatus.RUNNING and record.retry_count == 1:
            break
        await asyncio.sleep(0.1)

    assert record.status == TaskStatus.RUNNING
    assert record.retry_count == 1
    assert task_id in runner_a._running_tasks

    # ---- 模拟 crash ----
    for task in list(runner_a._running_tasks.values()):
        if not task.done():
            task.cancel()
    runner_a._running_tasks.clear()
    runner_a._executors.clear()
    runner_a._calculators.clear()
    runner_a._recovery_started_at.clear()
    runner_a._recovery_lock.clear()
    del runner_a

    # ---- Process B: 接管 RUNNING 任务 ----
    runner_b = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.AUTO)
    await runner_b.recover()

    # 等待任务完成（detect_status 第三次返回 COMPLETED）
    for _ in range(50):
        record = store.load(task_id)
        if record.status == TaskStatus.COMPLETED:
            break
        await asyncio.sleep(0.1)

    record = store.load(task_id)
    assert record.status == TaskStatus.COMPLETED
    # retry_count 保持 1（Process B 接管的是 RUNNING，不是 UNKNOWN）
    assert record.retry_count == 1

    # 验证事件链：retry → probe → restart_execute → collect
    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()
    with open(events_file, "r") as f:
        events = [json.loads(line) for line in f.readlines()]
    task_events = [e for e in events if e["task_id"] == task_id]
    actions = [e["action"] for e in task_events]
    # Process A 触发 retry, probe, restart_execute
    # Process B 触发 collect（因为检测到 RUNNING 后最终完成）
    assert "retry" in actions
    assert "probe" in actions
    assert "restart_execute" in actions
    assert "collect" in actions

    await runner_b.shutdown()

@pytest.mark.asyncio
async def test_unknown_crash_before_recovery(temp_task_dir):
    """
    Case 8: UNKNOWN 记录 + crash before recovery

    场景：
        Process A: 只保存 UNKNOWN 记录，不执行 recover
        Process A: crash
        Process B: recover → UNKNOWN → retry → execute → RUNNING

    验证：retry_count==1，事件链止于 restart_execute，任务进入 RUNNING
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    from masgent.models.calculator import CalculationResult

    class UnknownThenRunningCalculator(MockCalculator):
        TYPE = "unknown_then_running"

        async def detect_status(self, work_dir, job=None):
            counter_file = work_dir / ".detect_count"
            count = 0
            if counter_file.exists():
                count = int(counter_file.read_text())
            count += 1
            counter_file.write_text(str(count))
            # 前2次返回 UNKNOWN（recover 检测 + execute 内 detect_status 各一次）
            # 之后返回 RUNNING
            if count <= 2:
                return TaskStatus.UNKNOWN
            return TaskStatus.RUNNING

        async def collect(self, work_dir, workflow_type):
            return CalculationResult(
                success=True,
                workflow_type=workflow_type,
                data={"energy": -10.5},
                metadata={"calculator": "unknown_then_running"},
            )

    if not registry._factories.get("unknown_then_running"):
        registry.register("unknown_then_running", UnknownThenRunningCalculator)

    task_id = "unknown_crash_before_recovery"
    work_dir = temp_task_dir / task_id
    work_dir.mkdir(parents=True, exist_ok=True)

    record = TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.UNKNOWN,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=str(work_dir),
        calculator_type="unknown_then_running",
        calculator_params={},
        workflow_params={},
        retry_count=0,
    )
    store.save(record)

    # ---- Process A: 只有磁盘记录，没有 TaskRunner ----
    # 直接模拟 crash

    # ---- Process B: 完整 recovery ----
    runner_b = TaskRunner(store, registry, unknown_strategy=UnknownStrategy.AUTO)
    await runner_b.recover()

    # 等待任务进入 RUNNING
    for _ in range(30):
        record = store.load(task_id)
        if record.status == TaskStatus.RUNNING:
            break
        await asyncio.sleep(0.1)

    assert record.status == TaskStatus.RUNNING
    assert record.retry_count == 1

    # 验证事件链：只有 retry → probe → restart_execute（没有 collect）
    events_file = temp_task_dir / "recovery_events.jsonl"
    assert events_file.exists()
    with open(events_file, "r") as f:
        events = [json.loads(line) for line in f.readlines()]
    task_events = [e for e in events if e["task_id"] == task_id]
    actions = [e["action"] for e in task_events]

    assert actions == ["retry", "probe", "restart_execute"]

    await runner_b.shutdown()