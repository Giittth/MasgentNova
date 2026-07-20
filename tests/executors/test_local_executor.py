"""LocalExecutor 单元测试"""

import pytest
import asyncio
from pathlib import Path

from masgent.executors.local import LocalExecutor


@pytest.mark.asyncio
async def test_local_executor_spawn_and_wait(tmp_path):
    executor = LocalExecutor()
    handle = await executor.spawn(
        work_dir=tmp_path,
        command="echo 'Hello'",
    )
    assert handle.job_id is not None
    assert handle.backend == "local"
    assert handle.pid is not None

    exit_code = await executor.wait(handle.job_id, timeout=10)
    assert exit_code == 0


@pytest.mark.asyncio
async def test_local_executor_kill(tmp_path):
    executor = LocalExecutor()
    handle = await executor.spawn(
        work_dir=tmp_path,
        command="sleep 30",
    )
    assert await executor.is_running(handle.job_id) is True

    result = await executor.kill(handle.job_id)
    assert result is True

    await asyncio.sleep(0.5)
    assert await executor.is_running(handle.job_id) is False


@pytest.mark.asyncio
async def test_local_executor_writes_logs(tmp_path):
    """验证 stdout/stderr 日志文件是否正确写入"""
    executor = LocalExecutor()
    handle = await executor.spawn(
        work_dir=tmp_path,
        command="echo 'Hello stdout' && echo 'Hello stderr' >&2",
    )
    await executor.wait(handle.job_id, timeout=10)

    stdout_path = tmp_path / "stdout.log"
    stderr_path = tmp_path / "stderr.log"

    assert stdout_path.exists(), "stdout.log not created"
    assert stderr_path.exists(), "stderr.log not created"

    stdout_content = stdout_path.read_text()
    stderr_content = stderr_path.read_text()

    assert "Hello stdout" in stdout_content
    assert "Hello stderr" in stderr_content


@pytest.mark.asyncio
async def test_local_executor_logs_closed_after_wait(tmp_path):
    """验证 wait 后日志文件句柄被正确关闭"""
    executor = LocalExecutor()
    handle = await executor.spawn(
        work_dir=tmp_path,
        command="echo test",
    )
    # 检查日志文件是否在 _log_files 中
    assert handle.job_id in executor._log_files

    await executor.wait(handle.job_id, timeout=10)
    # 等待完成后应被移除
    assert handle.job_id not in executor._log_files


@pytest.mark.asyncio
async def test_local_executor_logs_closed_after_kill(tmp_path):
    """验证 kill 后日志文件句柄被正确关闭"""
    executor = LocalExecutor()
    handle = await executor.spawn(
        work_dir=tmp_path,
        command="sleep 30",
    )
    assert handle.job_id in executor._log_files

    await executor.kill(handle.job_id)
    assert handle.job_id not in executor._log_files