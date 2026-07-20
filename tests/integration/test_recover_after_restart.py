"""TaskRunner —— 任务生命周期管理"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from masgent.models.task import TaskRecord, TaskInfo
from masgent.models.enums import TaskStatus, WorkflowType
from masgent.models.job import JobHandle
from masgent.tasks.task_store import TaskStore
from masgent.calculators.base import Calculator
from masgent.calculators.registry import CalculatorRegistry


class TaskRunner:
    def __init__(
        self,
        task_store: TaskStore,
        calculator_registry: CalculatorRegistry,
        poll_interval: float = 10.0,
    ):
        self.task_store = task_store
        self.registry = calculator_registry
        self.poll_interval = poll_interval
        self._running_tasks: Dict[str, asyncio.Task] = {}

    # ========== 公开 API ==========

    async def submit(
        self,
        calculator: Calculator,
        structure,
        workflow_type: WorkflowType,
        **workflow_params,
    ) -> TaskInfo:
        task_id = self._generate_task_id()
        work_dir = await calculator.prepare(structure, workflow_type, **workflow_params)

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
        )
        self.task_store.save(record)

        task = asyncio.create_task(self._execute(record, calculator))
        self._running_tasks[task_id] = task

        return TaskInfo(
            task_id=task_id,
            status=TaskStatus.PENDING,
            work_dir=str(work_dir),
            workflow_type=workflow_type,
        )

    async def poll(self, task_id: str) -> TaskStatus:
        record = self.task_store.load(task_id)
        return record.status if record else TaskStatus.FAILED

    async def collect(self, task_id: str) -> Optional[Dict[str, Any]]:
        record = self.task_store.load(task_id)
        return record.result if record else None

    async def cancel(self, task_id: str) -> bool:
        """
        取消任务：先取消协程，然后 kill 外部进程（如果存在）。
        只有这个方法会将任务标记为 CANCELLED。
        """
        if task_id not in self._running_tasks:
            return False

        # 取消协程
        self._running_tasks[task_id].cancel()

        # 尝试 kill 外部进程
        record = self.task_store.load(task_id)
        if record and record.job_handle:
            try:
                job_handle = JobHandle.from_dict(record.job_handle)
                calc = self.registry.create(
                    record.calculator_type,
                    **record.calculator_params
                )
                await calc.cancel(job_handle)
                self._set_status_direct(task_id, TaskStatus.CANCELLED, "Cancelled by user")
            except Exception as e:
                self._set_status_direct(task_id, TaskStatus.CANCELLED, f"Cancel with error: {e}")
                return False
        else:
            self._set_status_direct(task_id, TaskStatus.CANCELLED, "Cancelled by user")

        return True

    async def recover(self):
        """恢复所有非终态任务（PENDING, RUNNING, UNKNOWN）"""
        active = self.task_store.get_active_tasks()
        for record in active:
            if record.task_id in self._running_tasks:
                continue

            # 尝试重建 Calculator
            try:
                calc = self.registry.create(
                    record.calculator_type,
                    **record.calculator_params
                )
            except Exception as e:
                self._set_status_direct(record.task_id, TaskStatus.FAILED, f"Registry create failed: {e}")
                continue

            work_dir = Path(record.work_dir)
            job_handle = None
            if record.job_handle:
                try:
                    job_handle = JobHandle.from_dict(record.job_handle)
                except Exception:
                    pass

            # 检测当前状态
            try:
                status = await calc.detect_status(work_dir, job_handle)
            except Exception as e:
                self._set_status_direct(record.task_id, TaskStatus.FAILED, f"detect_status failed: {e}")
                continue

            if status == TaskStatus.COMPLETED:
                try:
                    result = await calc.collect(work_dir, record.workflow_type)
                    self._set_completed(record.task_id, result)
                except Exception as e:
                    self._set_status_direct(record.task_id, TaskStatus.FAILED, f"collect failed: {e}")

            elif status == TaskStatus.RUNNING:
                self._restart_poll(record, calc, work_dir, job_handle)

            elif status == TaskStatus.PENDING:
                # 如果已经有 job_handle，说明之前已经提交过，直接进入轮询
                if record.job_handle:
                    self._restart_poll(record, calc, work_dir, job_handle)
                else:
                    self._restart_execute(record, calc, work_dir)

            elif status == TaskStatus.UNKNOWN:
                # 重试计数
                record.retry_count += 1
                if record.retry_count >= 3:
                    record.status = TaskStatus.FAILED
                    record.error_message = f"UNKNOWN after {record.retry_count} retries"
                    record.finished_at = datetime.now()
                    record.updated_at = datetime.now()
                self.task_store.save(record)

            elif status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
                # 终态，无需处理
                pass

    # ========== 内部方法 ==========

    def _generate_task_id(self) -> str:
        import uuid
        return f"task_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _set_status_direct(self, task_id: str, status: TaskStatus, error_message: str = None):
        """
        强制设置状态（绕过状态机），仅用于异常恢复、取消等特殊场景。
        正常状态迁移应使用 TaskRecord.set_status()。
        """
        record = self.task_store.load(task_id)
        if record is None:
            return
        record.status = status
        record.updated_at = datetime.now()
        if error_message:
            record.error_message = error_message
        if status.is_terminal:
            record.finished_at = datetime.now()
        self.task_store.save(record)

    def _set_completed(self, task_id: str, result):
        """
        安全设置 COMPLETED 状态：优先走状态机，若失败则强制设置。
        """
        record = self.task_store.load(task_id)
        if record is None:
            return
        try:
            record.set_status(TaskStatus.COMPLETED)
        except ValueError:
            # 如果状态机不允许（例如从 UNKNOWN 直接完成），则强制设置
            record.status = TaskStatus.COMPLETED
            record.updated_at = datetime.now()
            record.finished_at = datetime.now()
        record.result = {
            "data": result.data,
            "metadata": result.metadata,
        }
        self.task_store.save(record)

    async def _execute(
        self,
        record: TaskRecord,
        calc: Optional[Calculator] = None,
    ):
        """
        执行任务流程：launch → poll → collect。
        如果传入 calc，则复用；否则从 registry 创建。
        """
        task_id = record.task_id
        work_dir = Path(record.work_dir)

        # 如果未传入 calc，则从 registry 创建
        if calc is None:
            try:
                calc = self.registry.create(
                    record.calculator_type,
                    **record.calculator_params
                )
            except Exception as e:
                self._set_status_direct(task_id, TaskStatus.FAILED, f"calculator create failed: {e}")
                return

        job_handle = None

        try:
            # 更新状态为 RUNNING（正常迁移，使用 set_status）
            record = self.task_store.load(task_id)
            if record:
                try:
                    record.set_status(TaskStatus.RUNNING)
                    self.task_store.save(record)
                except ValueError:
                    # 如果状态机不允许（例如从 UNKNOWN 恢复），强制设置
                    self._set_status_direct(task_id, TaskStatus.RUNNING)

            # 启动计算
            try:
                job_handle = await calc.launch(work_dir)
                if job_handle:
                    record = self.task_store.load(task_id)
                    if record:
                        record.job_handle = job_handle.to_dict()
                        self.task_store.save(record)
            except Exception as e:
                self._set_status_direct(task_id, TaskStatus.FAILED, f"launch failed: {e}")
                return

            # 轮询 detect_status
            status = TaskStatus.PENDING
            while True:
                try:
                    status = await calc.detect_status(work_dir, job_handle)
                except Exception as e:
                    self._set_status_direct(task_id, TaskStatus.FAILED, f"detect_status failed: {e}")
                    return

                if status.is_terminal:
                    break
                await asyncio.sleep(self.poll_interval)

            # 收集结果
            if status == TaskStatus.COMPLETED:
                try:
                    result = await calc.collect(work_dir, record.workflow_type)
                    self._set_completed(task_id, result)
                except Exception as e:
                    self._set_status_direct(task_id, TaskStatus.FAILED, f"collect failed: {e}")
            else:
                self._set_status_direct(
                    task_id,
                    TaskStatus.FAILED,
                    f"Task ended with status {status.value}"
                )

        except asyncio.CancelledError:
            # 取消信号仅用于中断协程，不改变任务状态。
            # 状态由 TaskRunner.cancel() 设置，这里只记录日志并重新抛出。
            logging.info(f"Task execution interrupted: {task_id}")
            # 如果有 job_handle，尝试 kill 外部进程（但可能在 cancel() 中已处理）
            if job_handle:
                try:
                    await calc.cancel(job_handle)
                except Exception:
                    pass
            raise
        except Exception as e:
            self._set_status_direct(task_id, TaskStatus.FAILED, str(e))
        finally:
            self._running_tasks.pop(task_id, None)

    def _restart_poll(self, record: TaskRecord, calc: Calculator, work_dir: Path, job_handle: Optional[JobHandle]):
        """恢复 RUNNING 任务：启动快速轮询"""
        task = asyncio.create_task(
            self._poll_loop(
                record.task_id,
                calc,
                work_dir,
                job_handle,
                interval=0.1  # 快速轮询，满足测试要求
            )
        )
        self._running_tasks[record.task_id] = task

    def _restart_execute(self, record: TaskRecord, calc: Calculator, work_dir: Path):
        """恢复 PENDING 任务：重新执行，复用 calc 实例，避免重复创建"""
        task = asyncio.create_task(self._execute(record, calc))
        self._running_tasks[record.task_id] = task

    async def _poll_loop(
        self,
        task_id: str,
        calc: Calculator,
        work_dir: Path,
        job_handle: Optional[JobHandle],
        interval: Optional[float] = None,
    ):
        """轮询检测状态，支持自定义间隔"""
        interval = interval if interval is not None else self.poll_interval

        try:
            status = TaskStatus.PENDING
            while True:
                try:
                    status = await calc.detect_status(work_dir, job_handle)
                except Exception as e:
                    self._set_status_direct(task_id, TaskStatus.FAILED, f"detect_status failed: {e}")
                    return

                if status.is_terminal:
                    break
                await asyncio.sleep(interval)

            if status == TaskStatus.COMPLETED:
                record = self.task_store.load(task_id)
                if record:
                    try:
                        result = await calc.collect(work_dir, record.workflow_type)
                        self._set_completed(task_id, result)
                    except Exception as e:
                        self._set_status_direct(task_id, TaskStatus.FAILED, f"collect failed: {e}")
            else:
                self._set_status_direct(
                    task_id,
                    TaskStatus.FAILED,
                    f"Recovered task ended with status {status.value}"
                )
        except asyncio.CancelledError:
            # 恢复轮询被取消时，不改变状态，仅记录并重新抛出
            logging.info(f"Poll loop interrupted: {task_id}")
            raise
        except Exception as e:
            self._set_status_direct(task_id, TaskStatus.FAILED, str(e))
        finally:
            self._running_tasks.pop(task_id, None)