"""
测试 UNKNOWN 分类纯函数（classify_unknown_task）
"""

import pytest
from datetime import datetime
from pathlib import Path

from masgent.models.job import JobHandle
from masgent.tasks.recovery import classify_unknown_task
from tests.mock_executors import FakeSlurmExecutor


@pytest.mark.asyncio
async def test_classify_unknown_no_job_handle():
    """无 job_handle → execute"""
    executor = FakeSlurmExecutor(partition="cpu")
    result = await classify_unknown_task(executor, None)
    assert result == "execute"


@pytest.mark.asyncio
async def test_classify_unknown_no_executor():
    """有 job_handle 但无 executor → execute"""
    job_handle = JobHandle(
        job_id="slurm_12345",
        backend="slurm",
        scheduler_id="12345",
        submitted_at=datetime.now().isoformat(),
    )
    result = await classify_unknown_task(None, job_handle)
    assert result == "execute"


@pytest.mark.asyncio
async def test_classify_unknown_job_alive():
    """job_handle 存在且 is_running()=True → poll"""
    executor = FakeSlurmExecutor(partition="cpu")
    
    # 直接伪造 RUNNING 作业
    FakeSlurmExecutor.GLOBAL_JOBS["1234"] = {
        "status": "RUNNING",
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": "/tmp",
    }
    
    job_handle = JobHandle(
        job_id="slurm_1234",
        backend="slurm",
        scheduler_id="1234",
        submitted_at=datetime.now().isoformat(),
    )
    
    result = await classify_unknown_task(executor, job_handle)
    assert result == "poll"


@pytest.mark.asyncio
async def test_classify_unknown_job_dead():
    """job_handle 存在但 is_running()=False → execute"""
    executor = FakeSlurmExecutor(partition="cpu")
    
    # 直接伪造 COMPLETED 作业
    FakeSlurmExecutor.GLOBAL_JOBS["5678"] = {
        "status": "COMPLETED",
        "exit_code": 0,
        "command": "echo done",
        "work_dir": "/tmp",
    }
    
    job_handle = JobHandle(
        job_id="slurm_5678",
        backend="slurm",
        scheduler_id="5678",
        submitted_at=datetime.now().isoformat(),
    )
    
    result = await classify_unknown_task(executor, job_handle)
    assert result == "execute"


@pytest.mark.asyncio
async def test_classify_unknown_is_running_exception():
    """is_running() 抛出异常 → execute（保守处理）"""
    
    class FailingExecutor(FakeSlurmExecutor):
        async def is_running(self, job_id, pid=None):
            raise RuntimeError("Slurm API timeout")
    
    executor = FailingExecutor(partition="cpu")
    job_handle = JobHandle(
        job_id="slurm_12345",
        backend="slurm",
        scheduler_id="12345",
        submitted_at=datetime.now().isoformat(),
    )
    
    result = await classify_unknown_task(executor, job_handle)
    assert result == "execute"


@pytest.mark.asyncio
async def test_classify_unknown_fallback_job_id():
    """
    scheduler_id 为 None 时，fallback 到 job_id
    验证此分支正常工作
    """
    executor = FakeSlurmExecutor(partition="cpu")
    
    # 伪造 RUNNING 作业，使用 job_id 作为键
    FakeSlurmExecutor.GLOBAL_JOBS["1234"] = {
        "status": "RUNNING",
        "exit_code": None,
        "command": "sleep 10",
        "work_dir": "/tmp",
    }
    
    # scheduler_id 为 None，应使用 job_id
    job_handle = JobHandle(
        job_id="slurm_1234",
        backend="slurm",
        scheduler_id=None,  # ← 关键：scheduler_id 为空
        submitted_at=datetime.now().isoformat(),
    )
    
    result = await classify_unknown_task(executor, job_handle)
    assert result == "poll"


@pytest.mark.asyncio
async def test_classify_unknown_cleanup():
    """测试完成后清理 GLOBAL_JOBS（隔离性）"""
    FakeSlurmExecutor.clear_jobs()