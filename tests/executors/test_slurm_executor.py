"""SlurmExecutor 单元测试（mock 子进程）"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock

from masgent.executors.slurm import SlurmExecutor


@pytest.mark.asyncio
async def test_slurm_spawn(tmp_path):
    executor = SlurmExecutor()

    with patch.object(executor, "_run_cmd") as mock_run:
        mock_run.return_value = (0, "Submitted batch job 12345", "")

        handle = await executor.spawn(tmp_path, "echo hello")

        assert handle.backend == "slurm"
        assert handle.scheduler_id == "12345"
        assert handle.job_id == "slurm_12345"
        mock_run.assert_called_once_with("sbatch", str(tmp_path / "job.sbatch"))


@pytest.mark.asyncio
async def test_slurm_is_running(tmp_path):
    executor = SlurmExecutor()

    with patch.object(executor, "_run_cmd") as mock_run:
        mock_run.return_value = (0, "RUNNING", "")
        running = await executor.is_running("slurm_12345")
        assert running is True

        mock_run.return_value = (0, "", "")
        running = await executor.is_running("slurm_12345")
        assert running is False


@pytest.mark.asyncio
async def test_slurm_kill(tmp_path):
    executor = SlurmExecutor()

    with patch.object(executor, "_run_cmd") as mock_run:
        mock_run.return_value = (0, "", "")
        result = await executor.kill("slurm_12345")
        assert result is True
        mock_run.assert_called_once_with("scancel", "12345")


@pytest.mark.asyncio
async def test_slurm_wait(tmp_path):
    """wait 测试：只测轮询逻辑，不触发真实 sacct"""
    executor = SlurmExecutor(poll_interval=0.1)

    with patch.object(executor, "is_running", side_effect=[True, False]), \
         patch.object(executor, "_get_exit_code", return_value=0):
        exit_code = await executor.wait("slurm_12345")
        assert exit_code == 0


@pytest.mark.asyncio
async def test_slurm_spawn_failure(tmp_path):
    executor = SlurmExecutor()

    with patch.object(executor, "_run_cmd") as mock_run:
        mock_run.return_value = (1, "", "invalid partition")
        with pytest.raises(RuntimeError, match="sbatch failed"):
            await executor.spawn(tmp_path, "echo hello")


@pytest.mark.asyncio
async def test_slurm_health_check_no_sbatch():
    """health_check 应返回批量检测结果"""
    executor = SlurmExecutor()

    with patch("shutil.which", return_value=None):
        ok, msg = executor.health_check()
        assert ok is False
        # 批量检测信息应包含所有缺失命令
        assert "Missing Slurm commands" in msg
        assert "sbatch" in msg


@pytest.mark.asyncio
async def test_slurm_failed_exit_code():
    executor = SlurmExecutor()

    with patch.object(executor, "_run_cmd") as mock_run:
        mock_run.return_value = (0, "FAILED|1:0", "")
        code = await executor._get_exit_code("slurm_123")
        assert code == 1


@pytest.mark.asyncio
async def test_slurm_exit_code_variants():
    executor = SlurmExecutor()

    with patch.object(executor, "_run_cmd") as mock_run:
        # COMPLETED
        mock_run.return_value = (0, "COMPLETED|0:0", "")
        code = await executor._get_exit_code("123")
        assert code == 0

        # COMPLETED+
        mock_run.return_value = (0, "COMPLETED+|0:0", "")
        code = await executor._get_exit_code("123")
        assert code == 0

        # FAILED
        mock_run.return_value = (0, "FAILED|1:0", "")
        code = await executor._get_exit_code("123")
        assert code == 1