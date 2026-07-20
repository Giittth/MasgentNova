"""
真实 Slurm 环境集成测试

运行条件：
    - 必须在有 Slurm 集群的 HPC 节点上运行
    - 需要 sbatch/squeue/scancel/sacct 命令可用
    - 必须设置环境变量 MASGENT_RUN_SLURM_TESTS=1

运行命令：
    MASGENT_RUN_SLURM_TESTS=1 pytest tests/integration/test_slurm_real.py -m slurm -v
"""

import asyncio
import os
import shutil
import pytest
from pathlib import Path

from masgent.executors import SlurmExecutor


# ========== 环境检测 ==========
def slurm_available() -> bool:
    """检查 Slurm 命令是否可用"""
    return all(shutil.which(cmd) for cmd in ["sbatch", "squeue", "scancel", "sacct"])


# ========== 辅助函数 ==========
async def wait_until_active(executor, job_id, timeout: int = 60) -> None:
    """
    等待作业进入活跃状态（PENDING/RUNNING/CONFIGURING 等）

    注意：is_running() 返回 True 表示作业仍在 Slurm 队列中活跃，
    包括 PENDING（排队）、RUNNING（运行中）等状态。
    不要与"作业正在运行（RUNNING）"混淆。
    """
    start = asyncio.get_event_loop().time()
    while True:
        if await executor.is_running(job_id):
            return
        if asyncio.get_event_loop().time() - start > timeout:
            raise TimeoutError(f"Job {job_id} never entered active state within {timeout}s")
        await asyncio.sleep(1)

async def wait_until_not_active(executor, job_id, timeout: int = 30) -> None:
    """等待作业不再活跃（用于取消/停止后确认）"""
    start = asyncio.get_event_loop().time()
    while True:
        if not await executor.is_running(job_id):
            return
        if asyncio.get_event_loop().time() - start > timeout:
            raise TimeoutError(f"Job {job_id} still active after {timeout}s")
        await asyncio.sleep(1)

async def wait_for_exit_code(executor, job_id, timeout: int = 15) -> int:
    """
    等待 sacct 记录可用并获取退出码
    sacct 可能需要几秒才能写入记录
    """
    start = asyncio.get_event_loop().time()
    while True:
        code = await executor._get_exit_code(job_id)
        if code != -1:
            return code
        if asyncio.get_event_loop().time() - start > timeout:
            return -1
        await asyncio.sleep(1)

async def wait_for_file(path: Path, timeout: int = 10) -> bool:
    """等待文件出现（处理 NFS 延迟）"""
    start = asyncio.get_event_loop().time()
    while True:
        if path.exists():
            return True
        if asyncio.get_event_loop().time() - start > timeout:
            return False
        await asyncio.sleep(0.5)


# ========== 测试控制 ==========
# 环境变量保护：防止误提交到生产集群
RUN_REAL_SLURM = os.getenv("MASGENT_RUN_SLURM_TESTS") == "1"
SKIP_REASON = "Real Slurm tests disabled. Set MASGENT_RUN_SLURM_TESTS=1 to run."


@pytest.fixture(scope="function")
def slurm_executor():
    partition = os.getenv("MASGENT_SLURM_PARTITION", "cpu")
    return SlurmExecutor(
        partition=partition,
        ntasks=1,
        walltime="00:10:00",
        jobname="masgent_test",
        modules=[],
    )

@pytest.fixture(scope="function")
def work_dir(tmp_path):
    return tmp_path


# ========== P0.1：最小验证 ==========
@pytest.mark.skipif(not slurm_available(), reason="Slurm commands not found")
@pytest.mark.skipif(not RUN_REAL_SLURM, reason=SKIP_REASON)
@pytest.mark.slurm
@pytest.mark.integration
@pytest.mark.asyncio
async def test_slurm_spawn_and_wait(slurm_executor, work_dir):
    """
    P0.1.1: 核心链路验证
    提交作业 → 等待完成 → 验证退出码
    """
    handle = await slurm_executor.spawn(
        work_dir,
        "echo 'Hello Slurm' && /bin/true"
    )

    assert handle.backend == "slurm"
    assert handle.scheduler_id is not None
    assert handle.job_id.startswith("slurm_")

    # 等待完成（不必检查 running，直接 wait）
    exit_code = await slurm_executor.wait(handle.scheduler_id, timeout=60)
    assert exit_code == 0

    # 验证输出文件（处理 NFS 延迟）
    out_file = work_dir / "slurm.out"
    assert await wait_for_file(out_file), f"slurm.out not found: {out_file}"
    content = out_file.read_text()
    assert "Hello Slurm" in content

@pytest.mark.skipif(not slurm_available(), reason="Slurm commands not found")
@pytest.mark.skipif(not RUN_REAL_SLURM, reason=SKIP_REASON)
@pytest.mark.slurm
@pytest.mark.integration
@pytest.mark.asyncio
async def test_slurm_failed_exit_code(slurm_executor, work_dir):
    """
    P0.1.2: 失败作业的 sacct 解析
    使用 /bin/false 确保退出码为 1
    """
    handle = await slurm_executor.spawn(
        work_dir,
        "/bin/false"
    )

    exit_code = await slurm_executor.wait(handle.scheduler_id, timeout=60)
    # /bin/false 的退出码为 1
    assert exit_code == 1

@pytest.mark.skipif(not slurm_available(), reason="Slurm commands not found")
@pytest.mark.skipif(not RUN_REAL_SLURM, reason=SKIP_REASON)
@pytest.mark.slurm
@pytest.mark.integration
def test_slurm_health_check(slurm_executor):
    """
    P0.1.3: 健康检查
    """
    ok, msg = slurm_executor.health_check()
    assert ok is True
    assert "All Slurm commands available" in msg


# ========== P0.2：生命周期验证 ==========
@pytest.mark.skipif(not slurm_available(), reason="Slurm commands not found")
@pytest.mark.skipif(not RUN_REAL_SLURM, reason=SKIP_REASON)
@pytest.mark.slurm
@pytest.mark.integration
@pytest.mark.asyncio
async def test_slurm_is_active(slurm_executor, work_dir):
    """
    P0.2.1: 验证 squeue 状态查询（活跃性）

    注意：作业可能因排队而处于 PENDING，仍算 active。
    此测试验证 is_running() 在作业处于 PENDING/RUNNING 时返回 True。
    """
    handle = await slurm_executor.spawn(
        work_dir,
        "sleep 30"
    )

    # 等待作业进入活跃状态（PENDING 或 RUNNING 都算）
    await wait_until_active(slurm_executor, handle.scheduler_id, timeout=30)

    # 确认作业处于活跃状态
    active = await slurm_executor.is_running(handle.scheduler_id)
    assert active is True

    # 取消作业，避免残留
    await slurm_executor.kill(handle.scheduler_id)

    # 等待取消生效（轮询，固定 sleep）
    await wait_until_not_active(slurm_executor, handle.scheduler_id, timeout=30)

    # 验证作业已不再活跃
    active_after = await slurm_executor.is_running(handle.scheduler_id)
    assert active_after is False


@pytest.mark.skipif(not slurm_available(), reason="Slurm commands not found")
@pytest.mark.skipif(not RUN_REAL_SLURM, reason=SKIP_REASON)
@pytest.mark.slurm
@pytest.mark.integration
@pytest.mark.asyncio
async def test_slurm_kill(slurm_executor, work_dir):
    """
    P0.2.2: 验证 scancel 取消作业 + sacct 退出码
    """
    handle = await slurm_executor.spawn(
        work_dir,
        "sleep 60"
    )

    # 等待作业进入活跃状态
    await wait_until_active(slurm_executor, handle.scheduler_id, timeout=30)

    # 取消作业
    result = await slurm_executor.kill(handle.scheduler_id)
    assert result is True

    # 等待取消生效
    await wait_until_not_active(slurm_executor, handle.scheduler_id, timeout=30)

    # 验证 sacct 返回非零退出码（CANCELLED 视为失败）
    exit_code = await wait_for_exit_code(slurm_executor, handle.scheduler_id, timeout=15)
    # 非 COMPLETED 一律返回 1
    assert exit_code == 1


# ========== P0.3：同步执行模式 ==========
@pytest.mark.skipif(not slurm_available(), reason="Slurm commands not found")
@pytest.mark.skipif(not RUN_REAL_SLURM, reason=SKIP_REASON)
@pytest.mark.slurm
@pytest.mark.integration
@pytest.mark.asyncio
async def test_slurm_run_sync(slurm_executor, work_dir):
    """
    P0.3: 同步执行模式验证
    """
    result = await slurm_executor.run(
        work_dir,
        "echo 'Sync test'"
    )

    # sbatch --wait 的 stdout 可能只是提交信息，真正输出在 slurm.out
    out_file = work_dir / "slurm.out"
    assert await wait_for_file(out_file), f"slurm.out not found: {out_file}"
    content = out_file.read_text()
    assert "Sync test" in content


# ========== P0.4：sacct 精准解析 ==========
@pytest.mark.skipif(not slurm_available(), reason="Slurm commands not found")
@pytest.mark.skipif(not RUN_REAL_SLURM, reason=SKIP_REASON)
@pytest.mark.slurm
@pytest.mark.integration
@pytest.mark.asyncio
async def test_slurm_sacct_parse_completed(slurm_executor, work_dir):
    """
    P0.4.1: 验证 sacct 对 COMPLETED 的解析
    """
    handle = await slurm_executor.spawn(
        work_dir,
        "echo 'done' && /bin/true"
    )
    await slurm_executor.wait(handle.scheduler_id, timeout=60)

    code = await wait_for_exit_code(slurm_executor, handle.scheduler_id, timeout=15)
    assert code == 0


@pytest.mark.skipif(not slurm_available(), reason="Slurm commands not found")
@pytest.mark.skipif(not RUN_REAL_SLURM, reason=SKIP_REASON)
@pytest.mark.slurm
@pytest.mark.integration
@pytest.mark.asyncio
async def test_slurm_sacct_parse_failed(slurm_executor, work_dir):
    """
    P0.4.2: 验证 sacct 对 FAILED 的解析
    """
    handle = await slurm_executor.spawn(
        work_dir,
        "/bin/false"
    )
    await slurm_executor.wait(handle.scheduler_id, timeout=60)

    code = await wait_for_exit_code(slurm_executor, handle.scheduler_id, timeout=15)
    # 非 COMPLETED 一律返回 1
    assert code == 1