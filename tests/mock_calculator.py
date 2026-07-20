"""
Mock Calculator —— 用于 TaskRunner 单元测试

可以精确控制每个方法的行为，并追踪调用次数。
同时自动注册到 CalculatorRegistry（使用 "mock" 标识符）。
提供 BlockingCalculator 用于控制任务停留在 RUNNING 状态。
"""

from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

import asyncio

from pymatgen.core import Structure

from masgent.models.calculator import CalculationResult
from masgent.models.enums import TaskStatus, WorkflowType
from masgent.models.job import JobHandle
from masgent.calculators.base import Calculator
from masgent.calculators.registry import CalculatorRegistry
from masgent.executors.factory import ExecutorFactory


@dataclass
class MockCalculator(Calculator):
    """完全可控的模拟计算器，默认 detect_status 返回 COMPLETED"""

    TYPE: str = "mock"

    # ---- 行为控制 ----
    prepare_return: Path = Path("/tmp/mock_workdir")
    prepare_raises: Optional[Exception] = None

    launch_return: JobHandle = field(
        default_factory=lambda: JobHandle(
            job_id="mock_123",
            backend="mock",
            pid=9999,
            submitted_at=JobHandle.now(),
        )
    )
    launch_raises: Optional[Exception] = None

    detect_status_return: TaskStatus = TaskStatus.COMPLETED
    detect_status_raises: Optional[Exception] = None

    collect_return: Optional[CalculationResult] = None
    collect_raises: Optional[Exception] = None

    cancel_return: bool = True
    cancel_raises: Optional[Exception] = None

    init_params: Dict[str, Any] = field(default_factory=dict)

    # 接受 executor 参数（用于恢复链路测试）
    executor: Optional[Any] = None

    # ---- 调用追踪 ----
    prepare_called: bool = False
    launch_called: bool = False
    detect_status_called: bool = False
    collect_called: bool = False
    cancel_called: bool = False

    detect_status_call_count: int = 0

    # ---- Calculator 接口实现 ----
    def get_init_params(self) -> dict:
        return self.init_params

    async def prepare(self, structure: Structure, workflow_type: WorkflowType, **kwargs) -> Path:
        self.prepare_called = True
        if self.prepare_raises:
            raise self.prepare_raises
        return self.prepare_return

    async def launch(self, work_dir: Path) -> JobHandle:
        self.launch_called = True
        if self.launch_raises:
            raise self.launch_raises

        # 如果有 executor，直接调用 spawn（不吞异常）
        if self.executor is not None:
            return await self.executor.spawn(work_dir, "mock calculation")

        # 兜底
        if self.launch_return is not None:
            return self.launch_return

        import uuid
        from datetime import datetime
        scheduler_id = str(uuid.uuid4())[:8]
        return JobHandle(
            job_id=f"mock_{scheduler_id}",
            backend="mock",
            scheduler_id=scheduler_id,
            submitted_at=datetime.now().isoformat(),
            metadata={},
        )

    async def detect_status(self, work_dir: Path, job: Optional[JobHandle] = None) -> TaskStatus:
        self.detect_status_called = True
        self.detect_status_call_count += 1

        print(f"[MOCK DETECT] job={job}, executor={self.executor}")
        # 如果配置了 executor，委托给 executor 判断状态
        if self.executor is not None and job is not None:
            scheduler_id = job.scheduler_id if job.scheduler_id else job.job_id
            running = await self.executor.is_running(scheduler_id)
            print(f"[MOCK DETECT] is_running({scheduler_id}) = {running}")
            if running:
                return TaskStatus.RUNNING
            # 检查退出码
            if hasattr(self.executor, "_get_exit_code"):
                exit_code = await self.executor._get_exit_code(scheduler_id)
                if exit_code == 0:
                    return TaskStatus.COMPLETED
                elif exit_code == 1:
                    return TaskStatus.FAILED
            return TaskStatus.UNKNOWN

        if self.detect_status_raises:
            raise self.detect_status_raises
        # 防御性转换：确保返回 TaskStatus 枚举
        status = self.detect_status_return
        if isinstance(status, str):
            try:
                status = TaskStatus(status)
            except ValueError:
                status = TaskStatus.UNKNOWN
        return status

    async def collect(self, work_dir: Path, workflow_type: WorkflowType) -> CalculationResult:
        self.collect_called = True
        if self.collect_raises:
            # 支持字符串或 Exception 对象
            if isinstance(self.collect_raises, Exception):
                raise self.collect_raises
            raise RuntimeError(self.collect_raises)
        if self.collect_return is not None:
            return self.collect_return
        return CalculationResult(
            success=True,
            workflow_type=workflow_type,
            data={"energy": -10.5},
            metadata={"calculator": "mock"},
        )

    async def cancel(self, job: JobHandle) -> bool:
        self.cancel_called = True
        if self.cancel_raises:
            raise self.cancel_raises
        return self.cancel_return


# 扩展：始终返回 UNKNOWN 的 Calculator
class UnknownCalculator(MockCalculator):
    """专门用于测试 UNKNOWN 状态恢复"""

    TYPE = "unknown"

    async def detect_status(self, work_dir: Path, job: Optional[JobHandle] = None) -> TaskStatus:
        self.detect_status_called = True
        self.detect_status_call_count += 1
        return TaskStatus.UNKNOWN


# 扩展：可通过 Event 控制阻塞的 Calculator（用于崩溃恢复测试）
class BlockingCalculator(MockCalculator):
    """
    用于恢复测试：通过 asyncio.Event 控制 detect_status 的行为。
    
    默认 detect_status 会等待 event 被 set，期间返回 blocking_status（默认 RUNNING）。
    调用 release() 后，后续 detect_status 返回正常状态。
    """
    TYPE = "blocking"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = asyncio.Event()
        self.blocking_status = TaskStatus.RUNNING  # 阻塞时返回的状态
        self._call_count = 0
        # 可以设置释放前的调用次数，默认为 1（即第一次调用阻塞，之后释放）
        self.continue_after = 1

    async def detect_status(self, work_dir: Path, job: Optional[JobHandle] = None) -> TaskStatus:
        self.detect_status_called = True
        self.detect_status_call_count += 1
        # 如果还没达到释放次数，且事件未设置，则等待
        if self._call_count <= self.continue_after:
            await self.event.wait()
        # 如果事件已设置，返回正常状态
        return self.detect_status_return

    def release(self):
        """释放阻塞，让 detect_status 可以返回正常状态"""
        self.event.set()

    def reset(self):
        """重置事件和计数器，用于多次测试"""
        self.event.clear()
        self._call_count = 0


class CompletedCalculator(MockCalculator):
    """始终返回 COMPLETED"""
    TYPE = "completed"
    async def detect_status(self, work_dir, job=None):
        return TaskStatus.COMPLETED


class RunningCalculator(MockCalculator):
    """始终返回 RUNNING，用于测试轮询启动"""
    TYPE = "running_mock"
    async def detect_status(self, work_dir, job=None):
        # 如果 job_handle 存在，查询 FakeSlurmExecutor 的状态
        if job and hasattr(job, "scheduler_id"):
            from tests.mock_executors import FakeSlurmExecutor
            scheduler_id = job.scheduler_id or job.job_id
            job_info = FakeSlurmExecutor.GLOBAL_JOBS.get(scheduler_id)
            if job_info:
                status = job_info.get("status")
                if status == "RUNNING":
                    return TaskStatus.RUNNING
                elif status == "COMPLETED":
                    return TaskStatus.COMPLETED
                elif status == "FAILED":
                    return TaskStatus.FAILED
                else:
                    return TaskStatus.UNKNOWN
        # 兜底：返回 RUNNING
        return TaskStatus.RUNNING


class PendingCalculator(MockCalculator):
    """始终返回 PENDING，用于测试执行启动"""
    TYPE = "pending_mock"
    async def detect_status(self, work_dir, job=None):
        return TaskStatus.PENDING


# 安全注册到 CalculatorRegistry
# 使用前检查是否已注册，避免重复注册冲突
_calculator_classes = [
    ("mock", MockCalculator),
    ("unknown", UnknownCalculator),
    ("blocking", BlockingCalculator),
    ("completed", CompletedCalculator),
    ("running_mock", RunningCalculator),
    ("pending_mock", PendingCalculator),
]

for name, cls in _calculator_classes:
    if not CalculatorRegistry._factories.get(name):
        CalculatorRegistry.register(name, cls)