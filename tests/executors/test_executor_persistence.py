"""Executor 配置持久化测试"""

import pytest
from datetime import datetime

from masgent.models.task import TaskRecord
from masgent.models.enums import TaskStatus, WorkflowType
from masgent.executors import LocalExecutor, SlurmExecutor, ExecutorFactory


class TestExecutorPersistence:
    def test_task_record_saves_executor_config(self):
        config = {"type": "slurm", "partition": "cpu", "ntasks": 32}
        record = TaskRecord(
            task_id="test",
            workflow_type=WorkflowType.SINGLE_POINT,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            work_dir="/tmp",
            calculator_type="vasp",
            executor_config=config,
        )
        data = record.to_dict()
        restored = TaskRecord.from_dict(data)
        assert restored.executor_config == config

    def test_local_executor_get_config(self):
        executor = LocalExecutor(aliases={"vasp_std": "/fake/vasp"})
        config = executor.get_config()
        assert config["type"] == "local"
        assert config["aliases"] == {"vasp_std": "/fake/vasp"}

    def test_slurm_executor_get_config(self):
        executor = SlurmExecutor(
            partition="gpu",
            ntasks=4,
            walltime="02:00:00",
            jobname="test_job",
            modules=["vasp/6.4.2"],
        )
        config = executor.get_config()
        assert config["type"] == "slurm"
        assert config["partition"] == "gpu"
        assert config["ntasks"] == 4
        assert config["walltime"] == "02:00:00"
        assert config["jobname"] == "test_job"
        assert config["modules"] == ["vasp/6.4.2"]

    def test_executor_factory_create_from_config(self):
        config = {"type": "local", "aliases": {"vasp_std": "/fake/vasp"}}
        executor = ExecutorFactory.create(config)
        assert isinstance(executor, LocalExecutor)
        assert executor.aliases["vasp_std"] == "/fake/vasp"

        config = {"type": "slurm", "partition": "cpu", "ntasks": 32}
        executor = ExecutorFactory.create(config)
        assert isinstance(executor, SlurmExecutor)
        assert executor.partition == "cpu"
        assert executor.ntasks == 32


def test_local_executor_round_trip():
    """验证 LocalExecutor 配置可以完整恢复"""
    original = LocalExecutor(aliases={"vasp_std": "/opt/vasp/bin/vasp_std"})
    config = original.get_config()
    restored = ExecutorFactory.create(config)
    assert isinstance(restored, LocalExecutor)
    assert restored.aliases["vasp_std"] == "/opt/vasp/bin/vasp_std"

def test_slurm_executor_round_trip():
    """验证 SlurmExecutor 配置可以完整恢复"""
    original = SlurmExecutor(
        partition="gpu",
        ntasks=8,
        walltime="04:00:00",
        jobname="test_job",
        modules=["vasp/6.4.2"],
        extra_sbatch_args={"gres": "gpu:4"},
    )
    config = original.get_config()
    restored = ExecutorFactory.create(config)
    assert isinstance(restored, SlurmExecutor)
    assert restored.partition == "gpu"
    assert restored.ntasks == 8
    assert restored.walltime == "04:00:00"
    assert restored.jobname == "test_job"
    assert restored.modules == ["vasp/6.4.2"]
    assert restored.extra_sbatch_args == {"gres": "gpu:4"}