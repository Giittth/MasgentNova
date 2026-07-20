# FileLock Design

本文档描述 FileLock 的设计原理、使用方式、状态机、边界场景和测试覆盖。

## 1. Why FileLock?

### 1.1 Problem Statement

在多进程环境中，多个 TaskRunner 实例可能同时尝试恢复同一个 `UNKNOWN` 任务，导致：

- 任务重复执行
- 状态冲突（两个进程同时修改 TaskRecord）
- 资源浪费（重复的 Calculator / Executor 实例）
- 数据不一致（collect 结果被覆盖）

### 1.2 Solution

FileLock 基于 POSIX `fcntl.flock` 实现**跨进程互斥锁**，确保：

- 同一任务同一时刻只有一个进程进行恢复
- 进程崩溃后锁由内核自动释放（Crash Safe）
- 陈旧锁可被检测和清理（Stale Detection）

## 2. flock 原理
┌─────────────────────────────────────────────────────────────────────┐
│ Linux Kernel │
│ ┌─────────────────────────┐ │
│ │ inode │ │
│ │ ┌─────────────────┐ │ │
│ │ │ lock state │ │ │
│ │ │ (flock) │ │ │
│ │ └─────────────────┘ │ │
│ └─────────────────────────┘ │
│ ▲ │
│ │ │
│ ┌───────────────┼───────────────┐ │
│ │ │ │ │
│ ▼ ▼ ▼ │
│ Process A Process B Process C │
│ (locked) (blocked) (blocked) │
└─────────────────────────────────────────────────────────────────────┘


### 2.1 Key Properties

| Property | Description |
|----------|-------------|
| **Kernel-managed** | 锁状态由内核维护，进程退出（包括 SIGKILL）时自动释放 |
| **Inode-based** | 锁绑定到文件 inode，而非文件名（删除文件不影响现有 fd 上的锁） |
| **Advisory** | 不强制，但约定使用（flock 需要所有进程协作） |
| **Cross-process** | 不同进程可以共享同一个锁 |

### 2.2 flock vs threading.Lock

| 对比项 | `threading.Lock` | `fcntl.flock` |
|--------|------------------|---------------|
| 作用域 | 同一进程 | 跨进程 |
| 持久性 | 进程内 | 内核级 |
| 崩溃恢复 | 丢失 | 自动释放 |
| 速度 | 快（内存） | 慢（文件系统操作） |

## 3. Design

### 3.1 File Format

FileLock 使用一个简单的文本文件作为锁文件，内容为持有锁的进程 PID：
文件路径：{lock_dir}/{task_id}.lock
文件内容：12345 # 持有者的 PID


### 3.2 Core Operations

class FileLock:
    def __init__(self, task_id: str, lock_dir: Path):
        """创建 FileLock 实例，自动创建锁目录"""
        self.lock_dir = Path(lock_dir).resolve()
        self.lock_dir.mkdir(parents=True, exist_ok=True)

    def acquire(self, timeout: float = 0.0) -> bool:
        """
        1. os.open(O_CREAT | O_RDWR) 创建或打开锁文件
        2. fcntl.flock(LOCK_EX | LOCK_NB) 获取互斥锁
        3. ftruncate(0) 清空文件
        4. write(PID) 写入当前进程 PID
        """

    def release(self) -> None:
        """
        1. fcntl.flock(LOCK_UN) 释放锁
        2. os.close(fd)
        3. unlink(lock_file) 删除锁文件（彻底清理状态）
        """

    def is_stale(self) -> bool:
        """
        检测锁是否陈旧：
        1. 文件不存在 → False（无锁）
        2. PID 无效（空或非数字）→ True（stale）
        3. PID 进程已死亡 → True（stale）
        4. flock 可获取（能获取 LOCK_NB）→ True（stale）
        5. flock 被阻塞（BlockingIOError）→ False（有效锁）
        """

    def force_acquire(self) -> bool:
        """
        强制获取陈旧锁：
        1. if not is_stale(): return False
        2. unlink(lock_file) 删除旧文件
        3. acquire(timeout=0) 重新获取
        """
4. State Machine
┌─────────────────────────────────────────────────────────────────────┐
│                     FileLock 状态机                                │
│                                                                   │
│                    ┌─────────────────────────────┐                │
│                    │          UNLOCKED            │                │
│                    │  (锁文件不存在)               │                │
│                    └─────────────────────────────┘                │
│                              │                                     │
│                              │ acquire()                           │
│                              ▼                                     │
│                    ┌─────────────────────────────┐                │
│                    │           LOCKED             │                │
│                    │  (锁文件存在 + flock 持有)    │                │
│                    └─────────────────────────────┘                │
│                     /            │            \                    │
│                    /             │             \                   │
│                   ▼              ▼              ▼                  │
│            ┌──────────┐  ┌─────────────┐  ┌──────────┐            │
│            │ release  │  │  进程崩溃    │  │ is_stale │            │
│            │          │  │  (SIGKILL)  │  │  检测    │            │
│            └──────────┘  └─────────────┘  └──────────┘            │
│                │               │                │                 │
│                ▼               ▼                ▼                 │
│         ┌──────────┐  ┌─────────────┐  ┌─────────────┐           │
│         │UNLOCKED  │  │   STALE     │  │  有效锁判断 │           │
│         │(文件删除)│  │ (文件残留)   │  │             │           │
│         └──────────┘  └─────────────┘  └─────────────┘           │
│                              │                │                   │
│                              ▼                ▼                   │
│                    ┌─────────────────────┐   ┌─────────┐          │
│                    │ force_acquire()     │   │ LOCKED  │          │
│                    │ (删除文件 + acquire)│   │ (flock  │          │
│                    └─────────────────────┘   │ 存在)   │          │
│                              │               └─────────┘          │
│                              ▼                                    │
│                    ┌─────────────────────┐                        │
│                    │       LOCKED        │                        │
│                    └─────────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
4.1 State Descriptions
State	Description	Condition
UNLOCKED	无锁状态	锁文件不存在
LOCKED	有效锁	锁文件存在 + flock 被持有
STALE	陈旧锁	锁文件存在 + flock 已释放（进程死亡）
5. Stale Detection
5.1 Why Stale Detection is Needed
场景	问题
进程被 SIGKILL	flock 由内核释放，但锁文件残留 → 其他进程无法区分
进程正常退出但未清理文件	同左
PID 复用	旧进程的 PID 被新进程使用，仅检查 PID 会误判为有效锁
锁文件损坏	文件内容为空或非数字，无法判断状态
5.2 is_stale() Algorithm
python
def is_stale(self) -> bool:
    lock_path = self._get_lock_path()
    
    # 1. 文件不存在 → 无锁，不是 stale
    if not lock_path.exists():
        return False
    
    # 2. 读取 PID
    pid = self._read_owner_pid()
    if pid is None:
        return True  # 文件存在但内容无效 → stale
    
    # 3. PID 进程已死亡 → stale
    if not self._is_pid_alive(pid):
        return True
    
    # 4. 核心：尝试获取 flock
    #    如果 flock 能获取（LOCK_NB 成功），说明没有其它进程持有锁 → stale
    #    如果 flock 被阻塞（BlockingIOError），说明锁被有效持有 → 不是 stale
    try:
        fd = os.open(str(lock_path), os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # 能获取 → 没有其它进程持有
            return True
        except BlockingIOError:
            # 被阻塞 → 有其它进程持有
            return False
        finally:
            os.close(fd)
    except OSError:
        return True
5.3 Why Flock Check is Essential
情况	PID 存活	flock 存在	仅检查 PID	flock 检查	正确状态
正常持锁	✅	✅	有效锁	有效锁	有效锁 ✅
PID 复用（新进程接手）	✅	❌	有效锁 ❌	stale	stale ✅
同进程遗留	✅	❌	有效锁 ❌	stale	stale ✅
进程死亡	❌	❌	stale	stale	stale ✅
锁文件损坏	❌	❌	stale	stale	stale ✅
6. force_acquire
6.1 When to Use
仅在 is_stale() 返回 True 时调用。 调用前必须检查，否则可能破坏有效锁。

6.2 Algorithm
def force_acquire(self) -> bool:
    # 1. 必须先检查 stale
    if not self.is_stale():
        return False
    
    # 2. 关闭当前文件描述符（释放本地引用）
    self._close_fd()
    
    # 3. 删除旧锁文件
    lock_path = self._get_lock_path()
    try:
        lock_path.unlink(missing_ok=True)
    except OSError:
        pass
    
    # 4. 重新获取锁
    return self.acquire(timeout=0.0)
6.3 Safety Guarantee
✅ 不会破坏有效锁（先检查 is_stale()）

✅ 删除旧锁文件后重新创建，绕过旧 fd 上的残留 flock

✅ unlink(missing_ok=True) 避免竞争条件（文件可能已被删除）

7. Multi-Process Scenarios
7.1 Concurrent Acquire
Process A          Process B          Process C
    │                  │                  │
    ├── open(O_CREAT)  │                  │
    │                  │                  │
    ├── flock(LOCK_EX) │                  │
    │                  │                  │
    │   success        ├── open(O_RDWR)   │
    │                  │                  │
    │                  ├── flock(LOCK_NB) │
    │                  │      │           │
    │                  │  BlockingIOError │
    │                  │      │           │
    │                  │   return False   │
    │                  │                  │
    └── release()      │                  │
                       │                  │
                       ├── open(O_RDWR)   │
                       │                  │
                       ├── flock(LOCK_NB) │
                       │                  │
                       │   success        │
                       │                  │
                       └── release()      │
7.2 Crash Recovery (SIGKILL)
Process A                    Process B
    │                            │
    │  acquire lock              │
    │                            │
    │  Task running              │
    │                            │
    │  SIGKILL ──────────────────│
    │  X                         │
    │                            │
    │  kernel releases flock     │
    │                            │
    │                            ├── is_stale() = True
    │                            │
    │                            ├── force_acquire()
    │                            │
    │                            ├── running...
8. Edge Cases
8.1 Orphan Lock File
场景：进程死亡后锁文件残留。

处理：is_stale() 检测到 PID 无效或 PID 死亡（_is_pid_alive() == False），返回 True，后续 force_acquire() 清理并重新获取。

8.2 PID Reuse
场景：旧进程 PID 被新进程复用。

处理：is_stale() 检测到 flock 已释放（flock(LOCK_NB) 成功），返回 True，不会误判为有效锁。

8.3 Lock File Corruption
场景：锁文件内容为空或包含非数字字符。

处理：_read_owner_pid() 返回 None → is_stale() 返回 True → force_acquire() 清理。

8.4 Permission Denied
场景：锁目录不可写。

处理：acquire() 中 os.open() 抛出 OSError，捕获后返回 False，调用方决定后续处理（记录错误、重试或跳过）。

8.5 Lock File Deleted During Acquire
场景：两个进程同时操作同一锁文件。

处理：force_acquire() 使用 unlink(missing_ok=True)，如果文件已被其他进程删除，则继续重新创建，不会抛异常。

9. Test Coverage
9.1 Test Layers
Layer	Tests	Validation
Layer 1	Basic Correctness	acquire/release, sequential, timeout
Layer 2	Concurrency	20/50 worker 互斥, subprocess 并发
Layer 3	Crash Safety	SIGKILL recovery, multi-race
Layer 4	Filesystem Chaos	readonly, permission denied, missing dir, deleted file
Layer 5	Stale Correctness	active lock, fake PID, empty file, corrupted PID, SIGKILL, PID reuse, no file
Layer 6	Stress	high frequency, CPU burn, context switch
9.2 Key Assertions
Scenario	Expected
Active lock + force_acquire()	False（不破坏有效锁）
Orphan lock file	is_stale() == True
Empty lock file	is_stale() == True, force_acquire() == True
Fake PID（不存在的 PID）	is_stale() == True, force_acquire() == True
SIGKILL crash	lock recoverable after crash
Multi-process concurrent	only 1 success per execution
50 workers stress	at least 40 workers acquire sequentially

10. Design Principles
Principle	Description
Single Source of Truth	锁文件是唯一状态源，不依赖内存缓存
Kernel-managed	依赖内核管理 flock 状态
Stale-first	force_acquire 先检查 is_stale()
Atomic Operations	文件操作（open、flock、unlink）保证原子性
Graceful Degradation	权限错误时返回失败，不 crash
Test-driven	所有边界情况有对应测试
No Assumptions	不假设文件系统行为（如 flock 是否跨 NFS）

11. Design Invariants
Invariant 1: Single Writer
任意时刻，同一任务只有一个进程持有锁。

由 fcntl.flock 保证（内核级互斥）。

Invariant 2: Crash Safety
进程崩溃后，锁状态自动恢复为 Unlocked（不干扰后续恢复）。

SIGKILL 后，内核自动释放 flock，新进程可通过 force_acquire 接管。

Invariant 3: Stale Detection Correctness
is_stale() 在以下情况返回 True：

锁文件存在但内容无效

PID 进程已死亡

flock 未被持有

is_stale() 在以下情况返回 False：

锁文件不存在（无锁）

flock 被有效持有（有效锁）

Invariant 4: force_acquire Safety
force_acquire() 只在 is_stale() == True 时执行，不会破坏有效锁。

12. Configuration & Integration
12.1 Lock Directory
# 默认锁目录
lock_dir = Path(task_store.tasks_dir) / ".locks"

# 可自定义
runner = TaskRunner(
    store,
    registry,
    lock_dir=Path("/var/masgent/locks")
)
12.2 Integration with RecoveryManager
RecoveryManager
    │
    ├── _recover_single()
    │      │
    │      ├── FileLock(task_id, lock_dir)
    │      │
    │      ├── file_lock.acquire()
    │      │      │
    │      │      ├── success → store in _file_locks[task_id]
    │      │      │
    │      │      └── failure → log event + return
    │      │
    │      ├── _recover_task()
    │      │      │
    │      │      └── await _restart_poll(record, ..., file_lock)
    │      │
    │      └── handed_over = True
    │
    └── TaskRunner._poll_loop / _execute
           │
           └── finally:
                  self._recovery.release_file_lock(task_id)
12.3 file_lock.py API Reference
# 获取锁
lock = FileLock("task_abc", Path("/tmp/locks"))
if lock.acquire(timeout=0.5):
    try:
        # 临界区
        pass
    finally:
        lock.release()

# 检测 stale
if lock.is_stale():
    if lock.force_acquire():
        try:
            # 临界区
            pass
        finally:
            lock.release()

# 上下文管理器
with FileLock("task_abc", Path("/tmp/locks")) as lock:
    # 临界区
    pass

    
相关文档：

Recovery System Design — 恢复系统架构与设计原则

Task Lifecycle — 任务状态转换与执行生命周期

Architecture — 系统总体架构