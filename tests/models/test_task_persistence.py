"""TaskRecord 持久化测试（锁死序列化行为）"""

import pytest
from pathlib import Path
from datetime import datetime
from pymatgen.core import Structure, Lattice

from masgent.models.task import TaskRecord
from masgent.models.enums import TaskStatus, WorkflowType
from masgent.tasks.task_store import JSONTaskStore


class TestTaskPersistence:
    def test_structure_roundtrip(self, temp_task_dir):
        """验证 Structure 存入 TaskRecord 后能完整恢复"""
        store = JSONTaskStore(temp_task_dir)

        original_structure = Structure(
            Lattice.cubic(5.43),
            ["Si"],
            [[0.0, 0.0, 0.0]]
        )

        record = TaskRecord(
            task_id="struct_test",
            workflow_type=WorkflowType.RELAX,
            status=TaskStatus.COMPLETED,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            work_dir="/tmp/test",
            calculator_type="vasp",
            result={"energy": -10.5, "structure": original_structure},
        )

        store.save(record)
        loaded = store.load("struct_test")

        assert loaded is not None
        assert loaded.result is not None
        assert "structure" in loaded.result

        struct = loaded.result["structure"]
        assert isinstance(struct, Structure)
        assert struct.composition.reduced_formula == "Si"
        assert struct.lattice.a == 5.43

    def test_result_without_structure(self, temp_task_dir):
        """验证不含 Structure 的 result 也能正常 roundtrip"""
        store = JSONTaskStore(temp_task_dir)

        record = TaskRecord(
            task_id="simple_result",
            workflow_type=WorkflowType.SINGLE_POINT,
            status=TaskStatus.COMPLETED,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            work_dir="/tmp/test",
            calculator_type="vasp",
            result={"energy": -10.5, "volume": 160.0},
        )

        store.save(record)
        loaded = store.load("simple_result")

        assert loaded is not None
        assert loaded.result is not None
        assert loaded.result["energy"] == -10.5
        assert loaded.result["volume"] == 160.0

    def test_empty_result(self, temp_task_dir):
        """验证 result=None 的情况"""
        store = JSONTaskStore(temp_task_dir)

        record = TaskRecord(
            task_id="empty_result",
            workflow_type=WorkflowType.SINGLE_POINT,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            work_dir="/tmp/test",
            calculator_type="vasp",
            result=None,
        )

        store.save(record)
        loaded = store.load("empty_result")

        assert loaded is not None
        assert loaded.result is None