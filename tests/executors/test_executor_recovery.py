"""Executor 配置持久化与恢复链路测试

验证：
    TaskRecord.executor_config → JSON → load → ExecutorFactory → Executor
    整条恢复链路是否正确。
不需要真实 Slurm 环境。
"""

import pytest
from datetime import datetime
from pathlib import Path

from masgent.models.task import TaskRecord
from masgent.models.enums import TaskStatus, WorkflowType
from masgent.executors import LocalExecutor, SlurmExecutor, ExecutorFactory
from masgent.tasks.task_store import JSONTaskStore


class TestExecutorRecovery:
    def test_executor_config_roundtrip(self, temp_task_dir):
        """验证：executor_config → JSON → load → ExecutorFactory"""
        store = JSONTaskStore(temp_task_dir)

        config = {
            "type": "slurm",
            "partition": "gpu",
            "ntasks": 8,
            "walltime": "04:00:00",
            "jobname": "test",
        }

        record = TaskRecord(
            task_id="exec_test",
            workflow_type=WorkflowType.SINGLE_POINT,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            work_dir="/tmp/test",
            calculator_type="vasp",
            executor_config=config,
        )

        store.save(record)
        loaded = store.load("exec_test")

        assert loaded is not None
        assert loaded.executor_config == config

        restored = ExecutorFactory.create(loaded.executor_config)
        assert isinstance(restored, SlurmExecutor)
        assert restored.partition == "gpu"
        assert restored.ntasks == 8

    def test_legacy_record_no_executor_config(self, temp_task_dir):
        """验证：旧格式记录（无 executor_config）兼容性"""
        store = JSONTaskStore(temp_task_dir)

        record = TaskRecord(
            task_id="legacy",
            workflow_type=WorkflowType.SINGLE_POINT,
            status=TaskStatus.COMPLETED,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            work_dir="/tmp/legacy",
            calculator_type="vasp",
        )

        store.save(record)
        loaded = store.load("legacy")
        assert loaded is not None
        assert loaded.executor_config is None