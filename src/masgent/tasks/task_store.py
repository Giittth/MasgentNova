"""
任务存储层 —— TaskStore 抽象 + JSON 实现

职责：
    - 持久化 TaskRecord
    - 按状态查询任务（用于恢复）
    - 构建 fingerprint 索引以支持缓存查询（CachedCalculator）
    - 提供缓存专用的 save_cache() 方法

设计原则：
    - 文件系统存储，每个任务一个 JSON 文件
    - fingerprint 索引构建在内存中，加速缓存命中查询
    - 支持删除任务（清理缓存）

路径：
    原位置：src/masgent/utils/task_store.py
    新位置：src/masgent/tasks/task_store.py（与 TaskRunner 同级）
"""

import json
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from masgent.models.task import TaskRecord
from masgent.models.enums import TaskStatus, WorkflowType


class TaskStore(ABC):
    """
    TaskStore 抽象基类

    定义任务存储的统一接口，支持：
        - 增删改查
        - 状态更新
        - 结果保存
        - 缓存指纹索引
        - 活动任务查询（用于恢复）
    """

    @abstractmethod
    def save(self, task: TaskRecord) -> None:
        """保存任务记录（新增或更新）"""
        pass

    @abstractmethod
    def load(self, task_id: str) -> Optional[TaskRecord]:
        """根据 task_id 加载任务记录"""
        pass

    @abstractmethod
    def update_status(self, task_id: str, status: TaskStatus) -> None:
        """更新任务状态（便捷方法）"""
        pass

    @abstractmethod
    def save_result(self, task_id: str, result: Dict[str, Any]) -> None:
        """保存任务结果"""
        pass

    @abstractmethod
    def delete(self, task_id: str) -> None:
        """删除任务记录（用于清理缓存）"""
        pass

    @abstractmethod
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 20
    ) -> List[TaskRecord]:
        """列出任务（按创建时间降序）"""
        pass

    @abstractmethod
    def get_active_tasks(self) -> List[TaskRecord]:
        """获取所有活跃任务（PENDING, RUNNING, UNKNOWN）"""
        pass

    @abstractmethod
    def find_by_fingerprint(self, fingerprint: str) -> Optional[TaskRecord]:
        """通过 fingerprint 查找已完成的任务（用于缓存命中）"""
        pass

    @abstractmethod
    def append_recovery_event(self, event: dict) -> None:
        """追加恢复事件到持久化存储（用于审计追踪）"""
        pass

    @abstractmethod
    def save_cache(
        self,
        fingerprint: str,
        workflow_type: WorkflowType,
        result: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> None:
        """保存缓存结果（CachedCalculator 专用）"""
        pass

    @abstractmethod
    def build_fingerprint_index(self) -> None:
        """构建 fingerprint → task_id 索引（加速查询）"""
        pass

    def get_stats(self) -> dict:
        """获取存储统计信息（可选）"""
        return {}


class JSONTaskStore(TaskStore):
    """
    JSON 文件存储实现

    每个任务保存在单独的文件中：
        {tasks_dir}/{task_id}.json

    索引文件（可选）：
        {tasks_dir}/_index.json  （可弃用，改为内存索引）

    内存索引：
        _fingerprint_index: Dict[str, str]  # fingerprint -> task_id
        _index_built: bool
    """

    def __init__(self, tasks_dir: Path):
        """
        初始化 JSON 任务存储

        Args:
            tasks_dir: 存储目录路径（会自动创建）
        """
        self.tasks_dir = Path(tasks_dir)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

        # 指纹索引（内存）
        self._fingerprint_index: Dict[str, str] = {}
        self._index_built = False

    # ========== 内部辅助 ==========
    def _task_path(self, task_id: str) -> Path:
        """返回任务文件路径"""
        return self.tasks_dir / f"{task_id}.json"

    # ========== 核心 CRUD ==========
    def save(self, task: TaskRecord) -> None:
        """
        保存任务记录

        如果任务有 fingerprint，且在索引已构建的情况下，更新索引。
        """
        path = self._task_path(task.task_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(task.to_dict(), f, indent=2, ensure_ascii=False)

        # 如果有 fingerprint 且索引已构建，更新索引
        if self._index_built and task.fingerprint:
            # 检查是否已有旧映射
            old_id = self._fingerprint_index.get(task.fingerprint)
            if old_id is None or old_id == task.task_id:
                self._fingerprint_index[task.fingerprint] = task.task_id
            else:
                # 如果 fingerprint 已存在，保留较新的记录
                old_task = self.load(old_id)
                if old_task and task.created_at > old_task.created_at:
                    self._fingerprint_index[task.fingerprint] = task.task_id

    def load(self, task_id: str) -> Optional[TaskRecord]:
        """加载任务记录"""
        path = self._task_path(task_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return TaskRecord.from_dict(data)
        except Exception:
            return None

    def update_status(self, task_id: str, status: TaskStatus) -> None:
        """更新任务状态（仅状态，不修改其他字段）"""
        task = self.load(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        task.set_status(status)  # 内部更新 updated_at 和 finished_at
        self.save(task)

    def append_recovery_event(self, event: dict) -> None:
        """追加恢复事件到 recovery_events.jsonl 文件"""
        events_file = self.tasks_dir / "recovery_events.jsonl"
        with open(events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def save_result(self, task_id: str, result: Dict[str, Any]) -> None:
        """保存结果（不改变状态）"""
        task = self.load(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        task.result = result
        task.updated_at = datetime.now()
        self.save(task)

    def delete(self, task_id: str) -> None:
        """
        删除任务记录，同时清理索引

        注意：如果任务被删除，其对应的索引条目也会被清理。
        """
        task = self.load(task_id)
        path = self._task_path(task_id)
        if path.exists():
            path.unlink()

        # 清理索引
        if self._index_built and task and task.fingerprint:
            if self._fingerprint_index.get(task.fingerprint) == task_id:
                del self._fingerprint_index[task.fingerprint]

    # ========== 查询 ==========

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 20,
    ) -> List[TaskRecord]:
        """
        列出任务（按创建时间降序）

        Args:
            status: 过滤状态（可选）
            limit: 最大返回数量

        Returns:
            List[TaskRecord]: 任务列表
        """
        tasks = []
        for path in self.tasks_dir.glob("*.json"):
            if path.name == "_index.json":   # 忽略旧索引文件（如果有）
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                task = TaskRecord.from_dict(data)
                if status is None or task.status == status:
                    tasks.append(task)
            except Exception:
                continue

        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    def get_active_tasks(self) -> List[TaskRecord]:
        """
        获取所有活跃任务（需要恢复的任务）

        活跃状态包括：
            - PENDING
            - RUNNING
            - UNKNOWN

        Returns:
            List[TaskRecord]: 活跃任务列表
        """
        tasks = []
        for path in self.tasks_dir.glob("*.json"):
            if path.name == "_index.json":
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                task = TaskRecord.from_dict(data)
                if task.status.is_active:   # PENDING, RUNNING, UNKNOWN
                    tasks.append(task)
            except Exception:
                continue
        return tasks

    # ========== 缓存索引 ==========

    def build_fingerprint_index(self) -> None:
        """
        构建 fingerprint → task_id 索引

        遍历所有 JSON 文件，只索引已完成（COMPLETED）且带有 fingerprint 的任务。
        如果同一 fingerprint 有多个任务，保留创建时间最新的。
        """
        self._fingerprint_index = {}
        for path in self.tasks_dir.glob("*.json"):
            if path.name == "_index.json":
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                fingerprint = data.get("fingerprint")
                status_str = data.get("status")
                if fingerprint and status_str == TaskStatus.COMPLETED.value:
                    task_id = data["task_id"]
                    created_at = datetime.fromisoformat(data["created_at"])
                    # 检查是否已有
                    old_id = self._fingerprint_index.get(fingerprint)
                    if old_id is None:
                        self._fingerprint_index[fingerprint] = task_id
                    else:
                        # 如果已有，比较创建时间，保留较新的
                        old_task = self.load(old_id)
                        if old_task and created_at > old_task.created_at:
                            self._fingerprint_index[fingerprint] = task_id
            except Exception:
                continue
        self._index_built = True

    def find_by_fingerprint(self, fingerprint: str) -> Optional[TaskRecord]:
        """
        通过 fingerprint 查找已完成的任务（用于缓存命中）

        如果索引未构建，则先构建索引。
        如果索引中没有，则返回 None。
        """
        if not self._index_built:
            self.build_fingerprint_index()

        task_id = self._fingerprint_index.get(fingerprint)
        if task_id:
            return self.load(task_id)
        return None

    def save_cache(
        self,
        fingerprint: str,
        workflow_type: WorkflowType,
        result: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> None:
        """
        保存缓存结果（CachedCalculator 专用）

        创建一个标记为 COMPLETED 的任务，不关联实际工作目录，
        但保存 fingerprint 以便后续查找。
        """
        now = datetime.now()
        task = TaskRecord(
            task_id=f"cache_{uuid.uuid4().hex[:8]}",
            workflow_type=workflow_type,
            status=TaskStatus.COMPLETED,
            created_at=now,
            updated_at=now,
            finished_at=now,
            work_dir="",   # 缓存任务无实际工作目录
            calculator_type="cache",
            calculator_params={},
            workflow_params={},
            result=result,
            metadata=metadata,
            fingerprint=fingerprint,
        )
        self.save(task)

        # 如果索引已构建，直接更新索引
        if self._index_built and fingerprint:
            # 如果已有相同 fingerprint，保留较新的
            existing_id = self._fingerprint_index.get(fingerprint)
            if existing_id is None:
                self._fingerprint_index[fingerprint] = task.task_id
            else:
                existing_task = self.load(existing_id)
                if existing_task and task.created_at > existing_task.created_at:
                    self._fingerprint_index[fingerprint] = task.task_id

    # ========== 统计信息 ==========

    def get_stats(self) -> dict:
        """
        获取存储统计信息

        Returns:
            dict: 包含 total, completed, failed, active
        """
        total = 0
        completed = 0
        failed = 0
        active = 0
        for path in self.tasks_dir.glob("*.json"):
            if path.name == "_index.json":
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                status_str = data.get("status")
                total += 1
                if status_str == TaskStatus.COMPLETED.value:
                    completed += 1
                elif status_str == TaskStatus.FAILED.value:
                    failed += 1
                elif status_str in (
                    TaskStatus.PENDING.value,
                    TaskStatus.RUNNING.value,
                    TaskStatus.UNKNOWN.value,
                ):
                    active += 1
            except Exception:
                continue
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "active": active,
        }