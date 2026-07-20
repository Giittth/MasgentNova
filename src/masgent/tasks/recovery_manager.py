"""
任务恢复管理 —— 恢复逻辑、锁、重试、超时
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Union, List

from masgent.models.task import TaskRecord
from masgent.models.enums import TaskStatus, UnknownStrategy
from masgent.models.job import JobHandle
from masgent.models.events import RecoveryEvent
from masgent.models.error_codes import RecoveryError, ErrorCode, ErrorCategory, ErrorSource
from masgent.tasks.task_state import TaskStateManager
from masgent.tasks.recovery_lock import RecoveryLock
from masgent.tasks.file_lock import FileLock
from masgent.tasks.retry import RetryPolicy
from masgent.calculators.base import Calculator
from masgent.calculators.registry import CalculatorRegistry
from masgent.executors.base import Executor
from masgent.executors.factory import ExecutorFactory
from masgent.utils.logger import logger


class RecoveryManager:
    """任务恢复管理：唯一负责恢复逻辑、锁、重试、超时"""
    def __init__(
        self,
        state_manager: TaskStateManager,
        calculator_registry: CalculatorRegistry,
        poll_interval: float = 10.0,
        retry_policy: Optional[RetryPolicy] = None,
        unknown_strategy: Union[str, UnknownStrategy] = UnknownStrategy.AUTO,
        recovery_timeout: float = 3600.0,
        lock_dir: Optional[Path] = None,
        task_runner=None,
    ):
        self._state = state_manager
        self._registry = calculator_registry
        self._poll_interval = poll_interval
        self._retry_policy = retry_policy or RetryPolicy()
        self._unknown_strategy = UnknownStrategy(unknown_strategy) if isinstance(unknown_strategy, str) else unknown_strategy
        self._recovery_timeout = recovery_timeout
        self._task_runner = task_runner  # 保存引用

        # 恢复层专属状态
        self._file_locks: Dict[str, FileLock] = {}
        self._recovery_lock = RecoveryLock()
        self._recovery_started_at: Dict[str, datetime] = {}
        self._lock_dir = lock_dir or Path(".") / ".locks"
        self._lock_dir.mkdir(parents=True, exist_ok=True)

        # 不再需要外部 callback，直接使用自身的方法
        self._shutting_down = False

        # 直接绑定 TaskRunner 的方法（不再使用回调）
        if task_runner is not None:
            self._restart_poll_impl = task_runner._restart_poll
            self._restart_execute_impl = task_runner._restart_execute
        else:
            self._restart_poll_impl = None
            self._restart_execute_impl = None

        # 保留 running_tasks_getter 用于锁状态检查
        self._running_tasks_getter = None


    def set_running_tasks_getter(self, getter):
        """设置获取 _running_tasks 的 getter（用于锁判断）"""
        self._running_tasks_getter = getter

    def set_shutting_down(self, value: bool):
        self._shutting_down = value

    def log_recovery_event(
        self,
        record: TaskRecord,
        action: str,
        error: Optional[RecoveryError] = None,
    ) -> None:
        """记录恢复事件到日志和持久化存储（仅结构化错误）"""
        event = RecoveryEvent(
            task_id=record.task_id,
            old_status=record.status,
            action=action,
            retry_count=record.retry_count,
            error=error,
        )
        event_dict = event.to_dict()
        logger.info("[RECOVERY] %s", event_dict)
        try:
            self._state._task_store.append_recovery_event(event_dict)
        except Exception as e:
            logger.warning("Failed to persist recovery event: %s", e)


    async def recover(self) -> None:
        """恢复所有活跃任务"""
        if self._shutting_down:
            return

        active = self._state.get_active_tasks()
        for record in active:
            if self._shutting_down:
                break
            await self._recover_single(record)

    async def _recover_single(self, record: TaskRecord) -> None:
        """恢复单个任务，包含锁管理"""
        if self._shutting_down:
            return

        task_id = record.task_id
        if record.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            return

        running_tasks = self._running_tasks_getter() if self._running_tasks_getter else {}
        if task_id in running_tasks:
            return

        # 内存锁失败
        if not await self._recovery_lock.acquire(task_id, timeout=0.0):
            self.log_recovery_event(
                record,
                "skipped",
                error=RecoveryError.lock_acquire_failed(),
            )
            return

        # 文件锁
        file_lock = FileLock(task_id, self._lock_dir)
        if not file_lock.acquire(timeout=0.0):
            if file_lock.is_stale():
                # 持有进程已死亡，强制夺取陈旧锁
                if not file_lock.force_acquire():
                    self.log_recovery_event(
                        record,
                        "skipped",
                        error=RecoveryError.file_lock_failed("Stale lock force acquire failed"),
                    )
                    self._recovery_lock.release(task_id)
                    return
            else:
                # 同进程内有其他 TaskRunner 正在恢复此任务，跳过
                self.log_recovery_event(
                    record,
                    "skipped",
                    error=RecoveryError.file_lock_failed(),
                )
                self._recovery_lock.release(task_id)
                return

        self._file_locks[task_id] = file_lock

        handed_over = False
        try:
            handed_over = await self._recover_task(record, file_lock)
            if handed_over:
                return
        finally:
            if not handed_over:
                # 释放所有锁
                lock = self._file_locks.pop(task_id, None)
                if lock:
                    lock.release()
                self._recovery_lock.release(task_id)


    async def _recover_task(self, record: TaskRecord, file_lock: FileLock) -> bool:
        """
        执行实际恢复逻辑

        Returns:
            True: 任务已成功交给执行层（_running_tasks 中已有对应的后台任务）
            False: 任务未交给执行层（已完成、失败、或被跳过）
        """
        if self._shutting_down:
            return False

        task_id = record.task_id
        # 提前设置 recovery 开始时间，供超时检查使用
        self._recovery_started_at.setdefault(task_id, datetime.now())
        # 检查是否已是终态
        current = self._state.load(task_id)
        if current and current.status.is_terminal:
            return False

        # 1. 重建 Executor
        executor = None
        if record.executor_config:
            try:
                executor = ExecutorFactory.create(record.executor_config)
                if not executor.validate():
                    raise ValueError(f"Invalid executor config: {record.executor_config}")
            except Exception as e:
                self.log_recovery_event(
                    record,
                    "failed",
                    error=RecoveryError.executor_rebuild_failed(str(e)),
                )
                self._state.set_status(task_id, TaskStatus.FAILED, f"Executor rebuild failed: {e}")
                return False

        # 2. 重建 Calculator
        calc_params = record.calculator_params.copy()
        if executor is not None:
            calc_params["executor"] = executor

        try:
            calc = self._registry.create(record.calculator_type, **calc_params)
        except Exception as e:
            self.log_recovery_event(
                record,
                "failed",
                error=RecoveryError.calculator_rebuild_failed(str(e)),
            )
            self._state.set_status(task_id, TaskStatus.FAILED, f"Registry create failed: {e}")
            return False

        # 3. 恢复 JobHandle
        job_handle = None
        if record.job_handle:
            try:
                job_handle = JobHandle.from_dict(record.job_handle)
            except Exception:
                pass

        # 4. 检测状态
        work_dir = Path(record.work_dir)
        try:
            status = await calc.detect_status(work_dir, job_handle)
        except Exception as e:
            self.log_recovery_event(
                record,
                "failed",
                error=RecoveryError.detect_status_failed(str(e)),
            )
            self._state.set_status(task_id, TaskStatus.FAILED, f"detect_status failed: {e}")
            return False

        # 5. 根据状态恢复
        if status == TaskStatus.COMPLETED:
            try:
                result = await calc.collect(work_dir, record.workflow_type)
                self._state.set_completed(task_id, {"data": result.data, "metadata": result.metadata})
                self.log_recovery_event(record, "collect")
            except Exception as e:
                self.log_recovery_event(
                    record,
                    "failed",
                    error=RecoveryError.collect_failed(str(e)),
                )
                self._state.set_status(task_id, TaskStatus.FAILED, f"collect failed: {e}")
            return False  # 已完成，不需要后台任务

        elif status == TaskStatus.RUNNING:
            self.log_recovery_event(record, "restart_poll")
            # 直接调用自身方法，不再通过回调
            return await self._restart_poll(record, calc, work_dir, job_handle, file_lock)

        elif status == TaskStatus.PENDING:
            if record.job_handle:
                self.log_recovery_event(record, "restart_poll")
                return await self._restart_poll(record, calc, work_dir, job_handle, file_lock)
            else:
                self.log_recovery_event(record, "restart_execute")
                return await self._restart_execute(record, calc, work_dir, file_lock)

        elif status == TaskStatus.UNKNOWN:
            # 获取最新记录并增加重试计数（原子操作）
            record = self._state.load(task_id)
            record.retry_count += 1
            record.updated_at = datetime.now()
            self._state.save(record)

            if self._retry_policy.is_exhausted(record):
                self.log_recovery_event(
                    record,
                    "failed",
                    error=RecoveryError.unknown_retry_exhausted(
                        f"UNKNOWN after {record.retry_count} retries"
                    ),
                )
                self._state.set_status(
                    task_id,
                    TaskStatus.FAILED,
                    f"UNKNOWN after {record.retry_count} retries"
                )
                return False

            self.log_recovery_event(record, "retry")
            should_poll = False
            if self._unknown_strategy == UnknownStrategy.POLL:
                should_poll = bool(job_handle)
            elif self._unknown_strategy == UnknownStrategy.EXECUTE:
                should_poll = False
            elif self._unknown_strategy == UnknownStrategy.AUTO:
                from masgent.tasks.recovery import classify_unknown_task
                # executor 可能为 None，做保护
                if executor is not None:
                    result = await classify_unknown_task(executor, job_handle)
                else:
                    result = "execute"  # 无 executor，保守执行
                should_poll = (result == "poll")
                self.log_recovery_event(
                    record,
                    "probe",
                    error=RecoveryError(
                        code=ErrorCode.UNKNOWN_ERROR,
                        category=ErrorCategory.INFRA,
                        source=ErrorSource.RECOVERY,
                        detail=f"classified: {result}",
                    ),
                )

            if should_poll:
                self.log_recovery_event(record, "restart_poll")
                return await self._restart_poll(record, calc, work_dir, job_handle, file_lock)
            else:
                self.log_recovery_event(record, "restart_execute")
                return await self._restart_execute(record, calc, work_dir, file_lock)

        elif status == TaskStatus.FAILED:
            self.log_recovery_event(
                record,
                "failed",
                error=RecoveryError.job_reported_failed(),
            )
            self._state.set_status(task_id, TaskStatus.FAILED, "Recovered job reported FAILED")
            return False

        elif status == TaskStatus.CANCELLED:
            self.log_recovery_event(record, "failed", error=RecoveryError.job_reported_cancelled())
            self._state.set_status(task_id, TaskStatus.CANCELLED, "Recovered job reported CANCELLED")
            return False
        # 兜底
        return False


    async def _restart_poll(
        self,
        record: TaskRecord,
        calc: Calculator,
        work_dir: Path,
        job_handle: Optional[JobHandle],
        file_lock: Optional[FileLock] = None,
    ) -> bool:
        """委托给 TaskRunner"""
        if self._task_runner is None:
            return False
        result = await self._task_runner._restart_poll(record, calc, work_dir, job_handle, file_lock)
        if not result:
            logger.error(f"[RECOVERY] restart_poll failed for task {record.task_id}")
        return result

    async def _restart_execute(
        self,
        record: TaskRecord,
        calc: Calculator,
        work_dir: Path,
        file_lock: Optional[FileLock] = None,
    ) -> bool:
        """委托给 TaskRunner"""
        if self._task_runner is None:
            return False
        result = await self._task_runner._restart_execute(record, calc, work_dir, file_lock)
        if not result:
            logger.error(f"[RECOVERY] restart_execute failed for task {record.task_id}")
        return result


    def _check_recovery_timeout(self, task_id: str) -> bool:
        """检查任务是否超时，超时则标记 FAILED"""
        if self._recovery_timeout <= 0:
            return False

        started = self._recovery_started_at.get(task_id)
        if not started:
            return False

        elapsed = (datetime.now() - started).total_seconds()
        if elapsed > self._recovery_timeout:
            record = self._state.load(task_id)
            if record:
                self._state.set_status(
                    task_id,
                    TaskStatus.FAILED,
                    f"Recovery timeout: {elapsed:.1f}s > {self._recovery_timeout}s"
                )
            return True
        return False


    def release_recovery_lock(self, task_id: str) -> None:
        """释放恢复锁（供 _poll_loop 完成时调用）"""
        self._recovery_lock.release(task_id)

    def release_file_lock(self, task_id: str) -> None:
        """释放文件锁（供 _poll_loop 完成时调用）"""
        lock = self._file_locks.pop(task_id, None)
        if lock:
            lock.release()

    def get_file_lock(self, task_id: str) -> Optional[FileLock]:
        return self._file_locks.get(task_id)

    def cleanup_file_locks(self) -> None:
        """清理所有文件锁（shutdown 时调用）"""
        for lock in self._file_locks.values():
            lock.release()
        self._file_locks.clear()