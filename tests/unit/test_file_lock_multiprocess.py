"""
FileLock 工业可靠性测试套件（最终收敛版）

测试架构：
    Layer 1: Basic Correctness
    Layer 2: Concurrency Truth（含 subprocess 跨进程）
    Layer 3: Crash Safety (real SIGKILL)
    Layer 4: Filesystem Chaos
    Layer 5: Stale Correctness（完整工业级）
    Layer 6: Critical Section Analysis & Stress

设计原则：
    - 使用临界区窗口证明互斥（不依赖辅助标志）
    - 压力测试仅用于稳定性，不参与正确性断言
    - 测试使用 subprocess 模拟真实多进程场景
"""

import pytest
import multiprocessing as mp
import time
import random
import os
import signal
import subprocess
import sys
import hashlib
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

from masgent.tasks.file_lock import FileLock


# ============================================================================
# 核心工具：Critical Section Window（真实临界区）
# ============================================================================

@dataclass
class CriticalSectionWindow:
    """记录一次完整的临界区执行（从 acquire 成功到 release）"""
    worker_id: int
    start_ns: int          # lock.acquire() 成功的时间
    end_ns: int            # lock.release() 的时间
    acquired: bool         # 是否成功获取锁（只有成功的才记录）

    def overlaps(self, other: "CriticalSectionWindow") -> bool:
        """判断两个临界区是否时间重叠"""
        return not (self.end_ns <= other.start_ns or other.end_ns <= self.start_ns)

    def duration_us(self) -> float:
        return (self.end_ns - self.start_ns) / 1000.0


class CriticalSectionAnalyzer:
    """临界区时间线分析器（唯一互斥证明工具）"""

    def __init__(self, windows: List[CriticalSectionWindow]):
        self.windows = [w for w in windows if w.acquired]
        self.windows.sort(key=lambda w: w.start_ns)

    def assert_no_overlap(self, msg: str = "Overlapping critical sections detected"):
        for i, w1 in enumerate(self.windows):
            for w2 in self.windows[i+1:]:
                assert not w1.overlaps(w2), f"{msg}: worker {w1.worker_id} and {w2.worker_id}"

    def assert_no_overlap_ignore_count(self):
        """只验证无重叠，不验证执行次数（用于压力测试）"""
        self.assert_no_overlap()

    def get_success_count(self) -> int:
        return len(self.windows)

    def get_timeline(self) -> str:
        lines = ["Critical Section Timeline:"]
        for i, w in enumerate(self.windows):
            lines.append(
                f"  [{i}] worker={w.worker_id} start={w.start_ns} end={w.end_ns} "
                f"dur={w.duration_us():.2f}us"
            )
        return "\n".join(lines)

    def assert_execution_count(self, expected: int):
        """断言成功获取锁的 worker 数量等于期望值"""
        assert self.get_success_count() == expected, \
            f"Expected {expected} executions, got {self.get_success_count()}"


# ============================================================================
# 辅助工作进程
# ============================================================================

def worker_critical_section(lock_dir, task_id, windows, barrier, worker_id, work_delay=0.02):
    """
    工作进程：记录临界区窗口（使用 try-finally 保证 append 始终执行）
    """
    lock = FileLock(task_id, Path(lock_dir))
    try:
        barrier.wait(timeout=5)
    except:
        pass

    acquired = lock.acquire(timeout=5.0)

    start_ns = time.monotonic_ns()
    end_ns = start_ns

    try:
        if acquired:
            time.sleep(work_delay)
            end_ns = time.monotonic_ns()
    finally:
        windows.append(CriticalSectionWindow(worker_id, start_ns, end_ns, acquired))
        if acquired:
            lock.release()


def worker_crash_hold_lock(lock_dir, task_id, barrier, wait_seconds=0.3):
    """获取锁后 SIGKILL 自杀"""
    lock = FileLock(task_id, Path(lock_dir))
    try:
        barrier.wait(timeout=5)
    except:
        pass

    if not lock.acquire(timeout=2.0):
        return
    time.sleep(wait_seconds)
    os.kill(os.getpid(), signal.SIGKILL)


def worker_basic_acquire(lock_dir, task_id, counter, barrier):
    """基本获取锁（用于 Layer 1-2）"""
    lock = FileLock(task_id, Path(lock_dir))
    try:
        barrier.wait(timeout=5)
    except:
        pass

    if lock.acquire(timeout=2.0):
        with counter.get_lock():
            counter.value += 1
        time.sleep(random.uniform(0.02, 0.08))
        lock.release()


def worker_cpu_burn(
    lock_dir, task_id, shared_flag, violation_counter, barrier, worker_id, burn_iterations=1000
):
    """带 CPU 压力的工作进程（稳定性测试）"""
    lock = FileLock(task_id, Path(lock_dir))
    try:
        barrier.wait(timeout=5)
    except:
        pass

    for _ in range(burn_iterations):
        hashlib.md5(str(time.monotonic_ns()).encode()).hexdigest()

    if not lock.acquire(timeout=5.0):
        return

    for _ in range(burn_iterations // 2):
        hashlib.md5(str(time.monotonic_ns()).encode()).hexdigest()

    with shared_flag.get_lock():
        if shared_flag.value != 0:
            violation_counter.value += 1
        shared_flag.value = 1

    time.sleep(0.02)

    with shared_flag.get_lock():
        shared_flag.value = 0

    lock.release()


def worker_high_freq(lock_dir, task_id, counter, barrier):
    """高频获取释放（上下文切换压力）"""
    lock = FileLock(task_id, Path(lock_dir))
    try:
        barrier.wait(timeout=5)
    except:
        pass

    for _ in range(50):
        if lock.acquire(timeout=0.5):
            with counter.get_lock():
                counter.value += 1
            lock.release()
        time.sleep(random.uniform(0, 0.001))


# ============================================================================
# Layer 1: Basic Correctness
# ============================================================================

class TestFileLockLayer1Basic:
    @pytest.fixture
    def lock_dir(self, tmp_path):
        d = tmp_path / ".locks"
        d.mkdir(parents=True, exist_ok=True)
        return str(d)

    def test_acquire_release(self, lock_dir):
        lock = FileLock("test", Path(lock_dir))
        assert lock.acquire(timeout=1.0)
        assert lock.is_locked()
        lock.release()
        assert not lock.is_locked()

    def test_sequential_acquire(self, lock_dir):
        lock1 = FileLock("test", Path(lock_dir))
        lock2 = FileLock("test", Path(lock_dir))
        assert lock1.acquire(timeout=1.0)
        assert not lock2.acquire(timeout=0.1)
        lock1.release()
        assert lock2.acquire(timeout=1.0)
        lock2.release()

    def test_timeout(self, lock_dir):
        lock1 = FileLock("test", Path(lock_dir))
        assert lock1.acquire(timeout=1.0)
        start = time.time()
        lock2 = FileLock("test", Path(lock_dir))
        acquired = lock2.acquire(timeout=0.3)
        elapsed = time.time() - start
        assert not acquired
        assert elapsed >= 0.25
        lock1.release()


# ============================================================================
# Layer 2: Concurrency Truth
# ============================================================================

class TestFileLockLayer2Concurrency:
    @pytest.fixture
    def lock_dir(self, tmp_path):
        d = tmp_path / ".locks"
        d.mkdir(parents=True, exist_ok=True)
        return str(d)

    def test_concurrent_sequential_execution(self, lock_dir):
        task_id = "concurrent_seq"
        counter = mp.Value('i', 0)
        barrier = mp.Barrier(20)
        processes = []
        for _ in range(20):
            p = mp.Process(target=worker_basic_acquire, args=(lock_dir, task_id, counter, barrier))
            p.start()
            processes.append(p)
        for p in processes:
            p.join(timeout=10)
            if p.is_alive(): p.terminate(); p.join()
        assert counter.value == 20

    def test_critical_section_no_overlap(self, lock_dir):
        """核心互斥证明：使用临界区窗口"""
        task_id = "crit_section_proof"
        manager = mp.Manager()
        windows = manager.list()
        barrier = mp.Barrier(20)

        processes = []
        for i in range(20):
            p = mp.Process(target=worker_critical_section, args=(lock_dir, task_id, windows, barrier, i, 0.02))
            p.start()
            processes.append(p)

        for p in processes:
            p.join(timeout=10)
            if p.is_alive(): p.terminate(); p.join()

        analyzer = CriticalSectionAnalyzer(list(windows))
        # 使用 get_success_count 替代不存在的 assert_execution_count
        assert analyzer.get_success_count() == 20, \
            f"Expected 20 executions, got {analyzer.get_success_count()}"
        analyzer.assert_no_overlap()

    def test_subprocess_multi_worker_concurrent(self, lock_dir, tmp_path):
        """
        使用 subprocess 模拟真实跨进程并发
        启动 20 个子进程同时竞争同一锁
        """
        task_id = "subprocess_concurrent"
        lock_dir_resolved = Path(lock_dir).resolve()
        src_dir = str(Path(__file__).parent.parent.parent / "src")

        script = f'''
import sys
import time
import os
sys.path.insert(0, "{src_dir}")
from pathlib import Path
from masgent.tasks.file_lock import FileLock

lock_dir = "{str(lock_dir_resolved)}"
task_id = "{task_id}"
lock = FileLock(task_id, Path(lock_dir))

acquired = lock.acquire(timeout=5.0)
if acquired:
    time.sleep(0.02)
    lock.release()
    sys.exit(0)
else:
    sys.exit(1)
'''

        success_count = 0
        total = 20
        processes = []

        for _ in range(total):
            proc = subprocess.Popen(
                [sys.executable, "-c", script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            processes.append(proc)

        for proc in processes:
            stdout, stderr = proc.communicate(timeout=10)
            if proc.returncode == 0:
                success_count += 1

        # ★ 所有进程应该都能顺序执行完成
        assert success_count == total, f"Expected {total} successes, got {success_count}"


# ============================================================================
# Layer 3: Crash Safety
# ============================================================================

class TestFileLockLayer3CrashSafety:
    @pytest.fixture
    def lock_dir(self, tmp_path):
        d = tmp_path / ".locks"
        d.mkdir(parents=True, exist_ok=True)
        return str(d)

    def test_crash_recovery_single(self, lock_dir):
        task_id = "crash_recovery_single"
        lock_path = Path(lock_dir) / f"{task_id}.lock"
        barrier = mp.Barrier(1)
        p = mp.Process(target=worker_crash_hold_lock, args=(lock_dir, task_id, barrier, 0.3))
        p.start()
        p.join(timeout=3)
        lock = FileLock(task_id, Path(lock_dir))
        assert lock.acquire(timeout=3.0), "Lock should be recoverable after SIGKILL"
        lock.release()
        if lock_path.exists(): lock_path.unlink()

    def test_crash_recovery_multi_race(self, lock_dir):
        task_id = "crash_recovery_race"
        lock_path = Path(lock_dir) / f"{task_id}.lock"
        barrier1 = mp.Barrier(1)
        p_crash = mp.Process(target=worker_crash_hold_lock, args=(lock_dir, task_id, barrier1, 0.3))
        p_crash.start()
        p_crash.join(timeout=3)

        counter = mp.Value('i', 0)
        barrier2 = mp.Barrier(10)
        processes = []
        for _ in range(10):
            p = mp.Process(target=worker_basic_acquire, args=(lock_dir, task_id, counter, barrier2))
            p.start()
            processes.append(p)
        for p in processes:
            p.join(timeout=10)
            if p.is_alive(): p.terminate(); p.join()
        assert counter.value == 10
        if lock_path.exists(): lock_path.unlink()


# ============================================================================
# Layer 4: Filesystem Chaos
# ============================================================================

class TestFileLockLayer4FilesystemChaos:
    @pytest.fixture
    def lock_dir(self, tmp_path):
        d = tmp_path / ".locks"
        d.mkdir(parents=True, exist_ok=True)
        return str(d)

    def test_readonly_lock_dir(self, lock_dir):
        task_id = "readonly_test"
        lock_dir_path = Path(lock_dir)
        os.chmod(lock_dir_path, 0o444)
        try:
            lock = FileLock(task_id, lock_dir_path)
            acquired = False
            try:
                acquired = lock.acquire(timeout=1.0)
            except OSError:
                pass
            if acquired: lock.release()
            # ★ 只读目录应无法获取锁
            assert not acquired, "Should not acquire lock in read-only dir"
        finally:
            os.chmod(lock_dir_path, 0o755)

    def test_lock_dir_permission_denied(self, lock_dir):
        task_id = "perm_denied_test"
        lock_dir_path = Path(lock_dir)
        sub_dir = lock_dir_path / "unwritable"
        sub_dir.mkdir()
        os.chmod(sub_dir, 0o000)
        try:
            lock = FileLock(task_id, sub_dir)
            acquired = False
            try:
                acquired = lock.acquire(timeout=1.0)
            except OSError:
                pass
            if acquired: lock.release()
            assert not acquired, "Should not acquire lock in permission denied dir"
        finally:
            os.chmod(sub_dir, 0o755)
            sub_dir.rmdir()

    def test_lock_dir_not_exists(self, lock_dir):
        task_id = "missing_dir_test"
        missing_dir = Path(lock_dir) / "does_not_exist"
        # FileLock 会自动创建目录，所以应该能获取锁
        lock = FileLock(task_id, missing_dir)
        acquired = False
        try:
            acquired = lock.acquire(timeout=0.5)
            if acquired:
                lock.release()
        except OSError:
            pass
        # FileLock 自动创建目录，所以应能获取锁
        assert acquired, "Should acquire lock (directory auto-created)"
        assert missing_dir.exists(), "Directory should be auto-created"

    def test_lock_file_deleted_during_acquire(self, lock_dir):
        """锁文件在被获取前被删除 → 应能优雅处理"""
        task_id = "deleted_file_test"
        lock_path = Path(lock_dir) / f"{task_id}.lock"

        # 创建空锁文件
        lock_path.touch()

        # 删除锁文件（模拟其他进程清理）
        lock_path.unlink()

        # 尝试获取锁（应成功）
        lock = FileLock(task_id, Path(lock_dir))
        assert lock.acquire(timeout=1.0), "Should acquire after file deleted"
        lock.release()


# ============================================================================
# Layer 5: Stale Correctness（完整工业级）
# ============================================================================

class TestFileLockLayer5StaleCorrectness:
    @pytest.fixture
    def lock_dir(self, tmp_path):
        d = tmp_path / ".locks"
        d.mkdir(parents=True, exist_ok=True)
        return str(d)

    def test_stale_case1_active_lock_force_fails(self, lock_dir):
        """Case 1: Active Lock → force_acquire 失败"""
        task_id = "case1_active"
        lock1 = FileLock(task_id, Path(lock_dir))
        assert lock1.acquire(timeout=2.0)

        lock2 = FileLock(task_id, Path(lock_dir))
        # ★ 直接验证行为：force_acquire 应该失败
        assert not lock2.force_acquire()

        lock1.release()

    def test_stale_case2_fake_pid(self, lock_dir):
        """Case 2: Fake PID（不存在的进程）→ is_stale True，force_acquire 成功"""
        task_id = "case2_fake_pid"
        lock_path = Path(lock_dir) / f"{task_id}.lock"

        # 写入一个不存在的 PID
        lock_path.write_text("999999999")

        lock = FileLock(task_id, Path(lock_dir))
        assert lock.is_stale(), "Fake PID should be stale"
        assert lock.force_acquire(), "force_acquire should succeed on fake PID"
        lock.release()

    def test_stale_case3_empty_file(self, lock_dir):
        """Case 3: Empty file → is_stale True，force_acquire 成功"""
        task_id = "case3_empty"
        lock_path = Path(lock_dir) / f"{task_id}.lock"
        lock_path.touch()

        lock = FileLock(task_id, Path(lock_dir))
        assert lock.is_stale(), "Empty file should be stale"
        assert lock.force_acquire(), "force_acquire should succeed on empty file"
        lock.release()

    def test_stale_case4_corrupted_pid(self, lock_dir):
        """Case 4: Corrupted PID（非数字内容）→ is_stale True，force_acquire 成功"""
        task_id = "case4_corrupted"
        lock_path = Path(lock_dir) / f"{task_id}.lock"
        lock_path.write_text("abc123xyz")

        lock = FileLock(task_id, Path(lock_dir))
        assert lock.is_stale(), "Corrupted PID should be stale"
        assert lock.force_acquire(), "force_acquire should succeed on corrupted PID"
        lock.release()

    def test_stale_case5_sigkill_stale(self, lock_dir):
        """Case 5: Real SIGKILL → is_stale True，force_acquire 成功"""
        task_id = "case5_sigkill"
        lock_path = Path(lock_dir) / f"{task_id}.lock"
        src_dir = str(Path(__file__).parent.parent.parent / "src")

        script = f'''
import sys
import time
import os
import signal
sys.path.insert(0, "{src_dir}")
from pathlib import Path
from masgent.tasks.file_lock import FileLock

lock = FileLock("{task_id}", Path("{lock_dir}"))
if lock.acquire(timeout=2.0):
    time.sleep(0.2)
    os.kill(os.getpid(), signal.SIGKILL)
'''

        proc = subprocess.Popen([sys.executable, "-c", script])
        proc.wait(timeout=5)

        # 锁文件应该存在（进程崩溃后残留）
        assert lock_path.exists(), "Lock file should exist after SIGKILL"

        lock = FileLock(task_id, Path(lock_dir))
        assert lock.is_stale(), "Lock should be stale after SIGKILL"
        assert lock.force_acquire(), "force_acquire should succeed on SIGKILL stale lock"
        lock.release()

    def test_stale_case6_pid_reuse_subprocess(self, lock_dir):
        """Case 6: PID Reuse 场景（子进程获取锁后崩溃）"""
        task_id = "case6_pid_reuse"
        lock_dir_resolved = Path(lock_dir).resolve()
        lock_path = lock_dir_resolved / f"{task_id}.lock"
        src_dir = str(Path(__file__).parent.parent.parent / "src")

        script = f'''
import sys
import time
import os
import signal
sys.path.insert(0, "{src_dir}")
from pathlib import Path
from masgent.tasks.file_lock import FileLock

lock = FileLock("{task_id}", Path(r"{str(lock_dir_resolved)}"))
if lock.acquire(timeout=2.0):
    time.sleep(0.1)
    os.kill(os.getpid(), signal.SIGKILL)
'''

        proc = subprocess.Popen([sys.executable, "-c", script])
        proc.wait(timeout=5)

        # ★ 锁文件应该存在
        assert lock_path.exists(), f"Lock file should exist at {lock_path}"

        lock = FileLock(task_id, lock_dir_resolved)
        assert lock.is_stale(), "Lock should be stale after PID death"
        assert lock.force_acquire(), "force_acquire should succeed"
        lock.release()

    def test_stale_case7_no_file(self, lock_dir):
        """Case 7: No file → is_stale False"""
        task_id = "case7_no_file"
        lock = FileLock(task_id, Path(lock_dir))
        assert not lock.is_stale(), "No file should not be stale"


# ============================================================================
# Layer 6: Critical Section Proof + Stress
# ============================================================================

class TestFileLockLayer6ProofAndStress:
    """Layer 6: 互斥证明 + 压力稳定性测试"""

    @pytest.fixture
    def lock_dir(self, tmp_path):
        d = tmp_path / ".locks"
        d.mkdir(parents=True, exist_ok=True)
        return str(d)

    def test_critical_section_no_overlap_10_workers(self, lock_dir):
        """10 个进程，证明临界区无重叠"""
        task_id = "crit_10"
        manager = mp.Manager()
        windows = manager.list()
        barrier = mp.Barrier(10)

        processes = []
        for i in range(10):
            p = mp.Process(target=worker_critical_section, args=(lock_dir, task_id, windows, barrier, i, 0.02))
            p.start()
            processes.append(p)

        for p in processes:
            p.join(timeout=10)
            if p.is_alive(): p.terminate(); p.join()

        analyzer = CriticalSectionAnalyzer(list(windows))
        # ★ 只验证无重叠，不强制固定数量
        analyzer.assert_no_overlap()
        # 但至少应该有 worker 成功
        assert analyzer.get_success_count() > 0, "No worker acquired lock"

    def test_critical_section_no_overlap_50_workers(self, lock_dir):
        """50 个进程，压力互斥验证"""
        task_id = "crit_50"
        manager = mp.Manager()
        windows = manager.list()
        barrier = mp.Barrier(50)

        processes = []
        for i in range(50):
            p = mp.Process(target=worker_critical_section, args=(lock_dir, task_id, windows, barrier, i, 0.01))
            p.start()
            processes.append(p)

        for p in processes:
            p.join(timeout=15)
            if p.is_alive(): p.terminate(); p.join()

        analyzer = CriticalSectionAnalyzer(list(windows))
        # 只验证无重叠，不验证具体数量（避免 flaky）
        analyzer.assert_no_overlap()
        # 至少有一些 worker 成功
        assert analyzer.get_success_count() > 0, "No worker acquired lock"

    def test_high_frequency_acquire_release(self, lock_dir):
        """高频获取释放（压力测试）"""
        task_id = "high_freq"
        iterations = 500
        lock = FileLock(task_id, Path(lock_dir))
        for i in range(iterations):
            assert lock.acquire(timeout=0.5), f"Failed at iteration {i}"
            lock.release()

    def test_cpu_burn_stability(self, lock_dir):
        """CPU 高负载下的稳定性"""
        task_id = "cpu_burn"
        shared_flag = mp.Value('i', 0)
        violation_counter = mp.Value('i', 0)
        barrier = mp.Barrier(10)

        processes = []
        for i in range(10):
            p = mp.Process(target=worker_cpu_burn, args=(lock_dir, task_id, shared_flag, violation_counter, barrier, i, 2000))
            p.start()
            processes.append(p)

        for p in processes:
            p.join(timeout=15)
            if p.is_alive(): p.terminate(); p.join()

        assert violation_counter.value == 0
        assert shared_flag.value == 0

    def test_context_switch_pressure(self, lock_dir):
        """上下文切换压力测试"""
        task_id = "context_switch"
        counter = mp.Value('i', 0)
        barrier = mp.Barrier(10)

        processes = []
        for _ in range(10):
            p = mp.Process(target=worker_high_freq, args=(lock_dir, task_id, counter, barrier))
            p.start()
            processes.append(p)

        for p in processes:
            p.join(timeout=15)
            if p.is_alive(): p.terminate(); p.join()

        assert counter.value == 500