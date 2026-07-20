"""
JSONTaskStore 持久化测试

验证：
    - save/load 基本功能
    - list_tasks 过滤
    - 跨实例持久化
    - 损坏 JSON 文件的跳过
    - delete 清理文件和索引
    - fingerprint 索引构建与查找
"""

import pytest
import json
from pathlib import Path
from datetime import datetime

from masgent.tasks.task_store import JSONTaskStore
from masgent.models.task import TaskRecord
from masgent.models.enums import TaskStatus, WorkflowType


class TestJSONTaskStore:
    def test_save_and_load(self, temp_task_dir):
        """保存和加载基本功能"""
        store = JSONTaskStore(temp_task_dir)
        record = TaskRecord(
            task_id="test_001",
            workflow_type=WorkflowType.SINGLE_POINT,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            work_dir="/tmp/work",
            calculator_type="mock",
        )
        store.save(record)
        loaded = store.load("test_001")
        assert loaded is not None
        assert loaded.task_id == "test_001"
        assert loaded.status == TaskStatus.PENDING

    def test_load_nonexistent_returns_none(self, temp_task_dir):
        store = JSONTaskStore(temp_task_dir)
        assert store.load("nonexistent") is None

    def test_list_tasks(self, temp_task_dir):
        store = JSONTaskStore(temp_task_dir)
        for i in range(3):
            record = TaskRecord(
                task_id=f"task_{i:03d}",
                workflow_type=WorkflowType.SINGLE_POINT,
                status=TaskStatus.PENDING if i % 2 == 0 else TaskStatus.COMPLETED,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                work_dir="/tmp/work",
                calculator_type="mock",
            )
            store.save(record)
        all_tasks = store.list_tasks(limit=10)
        assert len(all_tasks) == 3
        pending = store.list_tasks(status=TaskStatus.PENDING)
        assert len(pending) == 2

    def test_persistence_across_instances(self, temp_task_dir):
        """同一目录，不同实例读取数据一致"""
        store1 = JSONTaskStore(temp_task_dir)
        record = TaskRecord(
            task_id="persist_test",
            workflow_type=WorkflowType.SINGLE_POINT,
            status=TaskStatus.RUNNING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            work_dir="/tmp/work",
            calculator_type="mock",
        )
        store1.save(record)

        # 新实例读取同一目录
        store2 = JSONTaskStore(temp_task_dir)
        loaded = store2.load("persist_test")
        assert loaded is not None
        assert loaded.task_id == "persist_test"
        assert loaded.status == TaskStatus.RUNNING

    def test_corrupted_json_skipped(self, temp_task_dir):
        """损坏的 JSON 文件在 list_tasks 时被跳过"""
        store = JSONTaskStore(temp_task_dir)
        # 写入一个合法任务
        record = TaskRecord(
            task_id="good",
            workflow_type=WorkflowType.SINGLE_POINT,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            work_dir="/tmp/work",
            calculator_type="mock",
        )
        store.save(record)

        # 手动写入一个损坏的 JSON 文件
        bad_path = temp_task_dir / "bad.json"
        bad_path.write_text("{ not json }")

        tasks = store.list_tasks()
        assert len(tasks) == 1
        assert tasks[0].task_id == "good"

    def test_delete_removes_file_and_index(self, temp_task_dir):
        store = JSONTaskStore(temp_task_dir)
        record = TaskRecord(
            task_id="to_delete",
            workflow_type=WorkflowType.SINGLE_POINT,
            status=TaskStatus.COMPLETED,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            work_dir="/tmp/work",
            calculator_type="mock",
            fingerprint="abc123",
        )
        store.save(record)
        # 构建索引
        store.build_fingerprint_index()
        # 确认索引存在
        assert store.find_by_fingerprint("abc123") is not None

        # 删除
        store.delete("to_delete")
        assert store.load("to_delete") is None
        # 索引应该被清理
        store.build_fingerprint_index()
        assert store.find_by_fingerprint("abc123") is None

    def test_fingerprint_index_build_and_find(self, temp_task_dir):
        store = JSONTaskStore(temp_task_dir)
        # 创建几个任务，其中一个带有 fingerprint
        record1 = TaskRecord(
            task_id="no_fp",
            workflow_type=WorkflowType.SINGLE_POINT,
            status=TaskStatus.COMPLETED,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            work_dir="/tmp/work",
            calculator_type="mock",
            fingerprint=None,
        )
        store.save(record1)

        record2 = TaskRecord(
            task_id="has_fp",
            workflow_type=WorkflowType.SINGLE_POINT,
            status=TaskStatus.COMPLETED,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            work_dir="/tmp/work",
            calculator_type="mock",
            fingerprint="fp_xyz",
        )
        store.save(record2)

        store.build_fingerprint_index()
        found = store.find_by_fingerprint("fp_xyz")
        assert found is not None
        assert found.task_id == "has_fp"

        # 不存在的 fingerprint
        found = store.find_by_fingerprint("nonexistent")
        assert found is None

    def test_get_stats(self, temp_task_dir):
        store = JSONTaskStore(temp_task_dir)
        # 创建各种状态的任务
        statuses = [
            TaskStatus.PENDING,
            TaskStatus.RUNNING,
            TaskStatus.COMPLETED,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.UNKNOWN,
        ]
        for i, status in enumerate(statuses):
            record = TaskRecord(
                task_id=f"task_{i}",
                workflow_type=WorkflowType.SINGLE_POINT,
                status=status,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                work_dir="/tmp/work",
                calculator_type="mock",
            )
            store.save(record)

        stats = store.get_stats()
        assert stats["total"] == 6
        assert stats["completed"] == 2
        assert stats["failed"] == 1
        assert stats["active"] == 3  # PENDING, RUNNING, UNKNOWN