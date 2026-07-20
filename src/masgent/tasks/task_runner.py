"""TaskRunner —— 任务执行层"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Union

from masgent.models.task import TaskRecord, TaskInfo
from masgent.models.enums import TaskStatus, WorkflowType, UnknownStrategy
from masgent.models.job import JobHandle
from masgent.models.cancel import CancelInfo, CancelSource
from masgent.tasks.task_state import TaskStateManager
from masgent.tasks.recovery_manager import RecoveryManager
from masgent.tasks.recovery_lock import RecoveryLock
from masgent.tasks.retry import RetryPolicy
from masgent.tasks.file_lock import FileLock
from masgent.calculators.base import Calculator
from masgent.calculators.registry import CalculatorRegistry
from masgent.executors.base import Executor
from masgent.utils.logger import logger


class TaskRunner:
    """任务执行层：submit、execute、poll、cancel、shutdown"""
    def __init__(
        self,
        task_store,
        calculator_registry: CalculatorRegistry,
        poll_interval: float = 10.0,
        retry_policy: Optional[RetryPolicy] = None,
        unknown_strategy: Union[str, UnknownStrategy] = UnknownStrategy.AUTO,
        recovery_timeout: float = 3600.0,
        lock_dir: Optional[Path] = None,
    ):
        # 状态管理层
        self._state = TaskStateManager(task_store)

        # 执行层专属状态
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._executors: Dict[str, Executor] = {}
        self._calculators: Dict[str, Calculator] = {}

        # Phase 3 准备：cancel 来源跟踪
        self._cancel_info: Dict[str, CancelInfo] = {}

        # 恢复管理层（传入 self 供内部委托）
        self._recovery = RecoveryManager(
            state_manager=self._state,
            calculator_registry=calculator_registry,
            poll_interval=poll_interval,
            retry_policy=retry_policy,
            unknown_strategy=unknown_strategy,
            recovery_timeout=recovery_timeout,
            lock_dir=lock_dir,
            task_runner=self,  # 传入自身，RecoveryManager 将直接调用 TaskRunner 的方法
        )

        # 向 RecoveryManager 注入 running_tasks getter（仅用于锁状态判断，不用于创建任务）
        self._recovery.set_running_tasks_getter(lambda: self._running_tasks)
        self._poll_interval = poll_interval
        self._shutting_down = False
        self._allow_recovery = False  # 恢复模式标志


    # ========== 公开 API ==========
    async def submit(
        self,
        calculator: Calculator,
        structure,
        workflow_type: WorkflowType,
        **workflow_params,
    ) -> TaskInfo:
        """提交任务"""
        task_id = self._generate_task_id()
        work_dir = await calculator.prepare(structure, workflow_type, **workflow_params)

        executor_config = None
        if hasattr(calculator, "executor") and hasattr(calculator.executor, "get_config"):
            try:
                executor_config = calculator.executor.get_config()
            except Exception:
                pass

        record = TaskRecord(
            task_id=task_id,
            workflow_type=workflow_type,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            work_dir=str(work_dir),
            calculator_type=calculator.TYPE,
            calculator_params=calculator.get_init_params(),
            workflow_params=workflow_params,
            retry_count=0,
            executor_config=executor_config,
        )
        self._state.save(record)

        executor = getattr(calculator, "executor", None)
        if executor is not None:
            self._executors[task_id] = executor
        self._calculators[task_id] = calculator

        task = asyncio.create_task(self._execute(record, calculator))
        self._running_tasks[task_id] = task

        return TaskInfo(
            task_id=task_id,
            status=TaskStatus.PENDING,
            work_dir=str(work_dir),
            workflow_type=workflow_type,
        )

    async def poll(self, task_id: str) -> TaskStatus:
        record = self._state.load(task_id)
        return record.status if record else TaskStatus.FAILED

    async def collect(self, task_id: str) -> Optional[Dict[str, Any]]:
        record = self._state.load(task_id)
        return record.result if record else None

    async def cancel(self, task_id: str) -> bool:
        """
        用户主动取消任务（立即写状态 + 打标记）
        
        与 shutdown 取消的区别：
            - cancel(): 立即写 CANCELLED 状态 + USER 标记
            - shutdown(): 不写状态，只打 SHUTDOWN 标记
        """
        if task_id not in self._running_tasks:
            return False

        # 立即写 CANCELLED 状态（用户可见）
        self._state.set_status(task_id, TaskStatus.CANCELLED, "Cancelled by user")

        # 记录取消来源（审计用）
        from masgent.models.cancel import CancelInfo, CancelSource
        self._cancel_info[task_id] = CancelInfo(
            source=CancelSource.USER,
            timestamp=datetime.now(),
            reason="Cancelled by user",
        )
        # 取消后台任务
        self._running_tasks[task_id].cancel()
        # Kill 外部作业
        record = self._state.load(task_id)
        if record and record.job_handle:
            try:
                job_handle = JobHandle.from_dict(record.job_handle)
                executor = self._executors.get(task_id)
                if executor:
                    await executor.kill(job_handle.job_id)
                else:
                    calc = self._registry.create(record.calculator_type, **record.calculator_params)
                    await calc.executor.kill(job_handle.job_id)
            except Exception:
                pass
        return True


    async def recover(self):
        """恢复所有任务（委托给 RecoveryManager）"""
        self._allow_recovery = True  # 进入恢复模式
        try:
            self._recovery.set_shutting_down(self._shutting_down)
            await self._recovery.recover()
        finally:
            self._allow_recovery = False  # 退出恢复模式


    async def shutdown(self, timeout: float = 5.0) -> None:
        """优雅关闭（不写 CANCELLED 状态）"""
        if self._shutting_down:
            return
        self._shutting_down = True
        self._allow_recovery = False  # 确保退出恢复模式
        self._recovery.set_shutting_down(True)

        try:
            if not self._running_tasks:
                self._executors.clear()
                self._calculators.clear()
                self._recovery.cleanup_file_locks()
                return

            for tid, task in list(self._running_tasks.items()):
                if not task.done():
                    self._cancel_info[tid] = CancelInfo(
                        source=CancelSource.SHUTDOWN,
                        timestamp=datetime.now(),
                        reason="Runner shutting down",
                    )
                    task.cancel()

            tasks = list(self._running_tasks.values())
            if tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*tasks, return_exceptions=True),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.sleep(0.1)

            self._running_tasks.clear()
            self._executors.clear()
            self._calculators.clear()
            self._recovery.cleanup_file_locks()

        finally:
            pass


    # 内部执行方法
    async def _execute(self, record: TaskRecord, calc: Optional[Calculator] = None):
        """执行任务主循环"""
        task_id = record.task_id
        current_task = asyncio.current_task()
        work_dir = Path(record.work_dir)

        if calc is None:
            try:
                calc = self._registry.create(record.calculator_type, **record.calculator_params)
            except Exception as e:
                self._state.set_status(task_id, TaskStatus.FAILED, f"calculator create failed: {e}")
                return
        job_handle = None
        try:
            self._state.set_status(task_id, TaskStatus.RUNNING)

            try:
                job_handle = await calc.launch(work_dir)
            except Exception as e:
                self._state.set_status(task_id, TaskStatus.FAILED, f"launch failed: {e}")
                return

            if job_handle:
                record = self._state.load(task_id)
                if record:
                    record.job_handle = job_handle.to_dict()
                    record.status = TaskStatus.RUNNING
                    record.updated_at = datetime.now()
                    self._state.save(record)

            record = self._state.load(task_id)
            job_handle_obj = None
            if record and record.job_handle:
                try:
                    job_handle_obj = JobHandle.from_dict(record.job_handle)
                except Exception:
                    pass

            status = TaskStatus.PENDING
            while True:
                try:
                    status = await calc.detect_status(work_dir, job_handle_obj)
                except Exception as e:
                    self._state.set_status(task_id, TaskStatus.FAILED, f"detect_status failed: {e}")
                    return

                if status.is_terminal:
                    break
                await asyncio.sleep(self._poll_interval)

            if status == TaskStatus.COMPLETED:
                try:
                    result = await calc.collect(work_dir, record.workflow_type)
                    self._state.set_completed(task_id, {"data": result.data, "metadata": result.metadata})
                except Exception as e:
                    self._state.set_status(task_id, TaskStatus.FAILED, f"collect failed: {e}")
            else:
                self._state.set_status(task_id, TaskStatus.FAILED, f"Task ended with status {status.value}")

        except asyncio.CancelledError:
            # 从 _cancel_info 读取来源（不删除）
            from masgent.models.cancel import CancelSource
            cancel_info = self._cancel_info.get(task_id)
            source = cancel_info.source if cancel_info else CancelSource.INTERNAL

            # 只有 USER 来源才写 CANCELLED 状态（幂等保护）
            if source == CancelSource.USER:
                record = self._state.load(task_id)
                if record and record.status != TaskStatus.CANCELLED:
                    self._state.set_status(task_id, TaskStatus.CANCELLED)
            # SHUTDOWN 和 INTERNAL 不写状态
            if job_handle:
                try:
                    await calc.cancel(job_handle)
                except Exception:
                    pass
            raise

        except Exception as e:
            self._state.set_status(task_id, TaskStatus.FAILED, str(e))
        finally:
            # 只 pop 自己
            if self._running_tasks.get(task_id) is current_task:
                self._running_tasks.pop(task_id, None)
            # 释放恢复层持有的锁
            self._recovery.release_file_lock(task_id)
            self._recovery.release_recovery_lock(task_id)


    async def _poll_loop(
        self,
        task_id: str,
        calc: Calculator,
        work_dir: Path,
        job_handle: Optional[JobHandle],
        interval: Optional[float] = None,
    ):
        """轮询任务状态"""
        interval = interval if interval is not None else self._poll_interval
        error_count = 0
        current_task = asyncio.current_task()

        # 确保 recovery_started_at 已设置（通过 RecoveryManager）
        if task_id not in self._recovery._recovery_started_at:
            self._recovery._recovery_started_at[task_id] = datetime.now()

        try:
            while True:
                try:
                    status = await calc.detect_status(work_dir, job_handle)
                    error_count = 0
                except Exception as e:
                    error_count += 1
                    max_poll_errors = self._recovery._retry_policy.max_retries
                    if error_count > max_poll_errors:
                        self._state.set_status(task_id, TaskStatus.FAILED, f"poll failed: {e}")
                        return
                    await asyncio.sleep(interval)
                    continue

                # 超时检查
                if status == TaskStatus.RUNNING:
                    if self._recovery._check_recovery_timeout(task_id):
                        return

                # UNKNOWN 视为非终态，继续轮询（不退出，不移除任务）
                if status == TaskStatus.UNKNOWN:
                    print(f"[RECOVER POLL] {task_id}: UNKNOWN, continuing poll")
                    await asyncio.sleep(interval)
                    continue

                # 终端状态：退出循环
                if status.is_terminal:
                    break
                await asyncio.sleep(interval)

            # 循环结束后处理终端状态
            if status == TaskStatus.COMPLETED:
                record = self._state.load(task_id)
                if record:
                    try:
                        result = await calc.collect(work_dir, record.workflow_type)
                        self._state.set_completed(task_id, {"data": result.data, "metadata": result.metadata})
                    except Exception as e:
                        self._state.set_status(task_id, TaskStatus.FAILED, f"collect failed: {e}")
            else:
                self._state.set_status(task_id, TaskStatus.FAILED, f"Recovered task ended with status {status.value}")

        except asyncio.CancelledError:
            # _poll_loop 的取消由 _execute 或 shutdown 触发
            # 不在这里写状态，由 _execute 处理
            raise
        except Exception as e:
            self._state.set_status(task_id, TaskStatus.FAILED, str(e))
        finally:
            # 只 pop 自己，避免把后来注册的新任务误删
            if self._running_tasks.get(task_id) is current_task:
                self._running_tasks.pop(task_id, None)
            # 释放锁
            self._recovery.release_file_lock(task_id)
            self._recovery.release_recovery_lock(task_id)


    async def _restart_poll(
        self,
        record: TaskRecord,
        calc: Calculator,
        work_dir: Path,
        job_handle: Optional[JobHandle],
        file_lock: Optional[FileLock] = None,
    ) -> bool:
        """
        启动轮询任务（由 RecoveryManager 调用，负责创建后台任务并注册到 _running_tasks）

        Args:
            record: 任务记录
            calc: 已重建的 Calculator 实例
            work_dir: 工作目录
            job_handle: 作业句柄（可能为 None）
            file_lock: 恢复层持有的文件锁（由调用方管理，本方法不获取也不释放）

        Returns:
            True: 任务已成功创建并交给执行层
            False: 任务未创建（关闭中或已在运行）
        """
        # 只有真正关闭且不在恢复模式时才拒绝
        if self._shutting_down and not self._allow_recovery:
            return False

        task_id = record.task_id
        # 防御：如果任务已在运行，记录警告并跳过
        if task_id in self._running_tasks:
            logger.warning(f"[RESTART_POLL] task {task_id} already in _running_tasks")
            return False

        # 存储 executor 和 calculator（唯一 state owner）
        executor = getattr(calc, "executor", None)
        if executor is not None:
            self._executors[task_id] = executor
        self._calculators[task_id] = calc

        # 核心：创建后台轮询任务并注册
        task = asyncio.create_task(
            self._poll_loop(
                task_id,
                calc,
                work_dir,
                job_handle,
                interval=0.1,
            )
        )
        self._running_tasks[task_id] = task
        await asyncio.sleep(0)  # 让事件循环有机会调度任务
        return True


    async def _restart_execute(
        self,
        record: TaskRecord,
        calc: Calculator,
        work_dir: Path,
        file_lock: Optional[FileLock] = None,
    ) -> bool:
        """
        重新执行任务（由 RecoveryManager 调用，负责创建后台任务并注册到 _running_tasks）

        Args:
            record: 任务记录
            calc: 已重建的 Calculator 实例
            work_dir: 工作目录
            file_lock: 恢复层持有的文件锁（由调用方管理，本方法不获取也不释放）

        Returns:
            True: 任务已成功创建并交给执行层
            False: 任务未创建（关闭中或已在运行）
        """
        # 只有真正关闭且不在恢复模式时才拒绝
        if self._shutting_down and not self._allow_recovery:
            return False

        task_id = record.task_id
        # 防御：如果任务已在运行，记录警告并跳过（与 _restart_poll 保持一致）
        if task_id in self._running_tasks:
            logger.warning(f"[RESTART_EXECUTE] task {task_id} already in _running_tasks")
            return False

        # 存储 executor 和 calculator
        executor = getattr(calc, "executor", None)
        if executor is not None:
            self._executors[task_id] = executor
        self._calculators[task_id] = calc

        # 恢复开始时间（供超时检查使用）
        self._recovery_started_at.setdefault(task_id, datetime.now())
        # 核心：创建后台执行任务并注册
        task = asyncio.create_task(self._execute(record, calc))
        self._running_tasks[task_id] = task
        await asyncio.sleep(0)  # 让事件循环有机会调度任务
        return True


    def _generate_task_id(self) -> str:
        import uuid
        return f"task_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


    # ========== 兼容层属性（只读，委托给 RecoveryManager） ==========
    @property
    def task_store(self):
        """兼容旧测试：直接访问 task_store"""
        return self._recovery._state._task_store

    @property
    def retry_policy(self):
        """兼容旧测试：直接访问 retry_policy"""
        return self._recovery._retry_policy

    @property
    def unknown_strategy(self):
        """兼容旧测试：直接访问 unknown_strategy"""
        return self._recovery._unknown_strategy

    @property
    def _recovery_lock(self):
        """兼容旧测试：直接访问 recovery_lock"""
        return self._recovery._recovery_lock

    @property
    def _recovery_started_at(self):
        """兼容旧测试：直接访问 recovery_started_at"""
        return self._recovery._recovery_started_at

    @property
    def _file_locks(self):
        """兼容旧测试：直接访问 file_locks"""
        return self._recovery._file_locks

    @property
    def _lock_dir(self):
        return self._recovery._lock_dir

    # 如果测试需要访问 _recover_task（如 test_race_case_3）
    @staticmethod
    def _recover_task():
        """兼容旧测试：使用静态占位，实际功能已迁移"""
        raise NotImplementedError("_recover_task moved to RecoveryManager")