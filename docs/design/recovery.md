# Recovery System Design

本文档描述 Masgent 的任务恢复系统设计，涵盖 UNKNOWN 状态处理、RecoveryManager、TaskRunner 回调、Crash Recovery 和 Shutdown 等核心机制。

## 1. Architecture
┌─────────────────────────────────────────────────────────────────┐
│ Task Store │
│ (JSONTaskStore) │
│ (SQLite 未来计划) │
└─────────────────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────┐
│ TaskRunner │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Execution Layer │ │
│ │ submit() poll() collect() cancel() shutdown() │ │
│ │ _execute() _poll_loop() │ │
│ └─────────────────────────────────────────────────────────┘ │
│ │ │
│ ▼ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Recovery Layer │ │
│ │ recover() _recover_single() _recover_task() │ │
│ │ _restart_poll() _restart_execute() │ │
│ └─────────────────────────────────────────────────────────┘ │
│ │ │
│ ▼ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ State Layer │ │
│ │ set_status() set_completed() set_failed() │ │
│ │ load() save() │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────┐
│ Recovery Lock (FileLock) │
│ ┌──────────────┐ ┌──────────────┐ │
│ │ RecoveryLock │ │ FileLock │ │
│ │ (threading) │ │ (fcntl) │ │
│ └──────────────┘ └──────────────┘ │
└─────────────────────────────────────────────────────────────────┘


**三层职责**：

| 层 | 职责 | 关键方法 |
|----|------|----------|
| **Execution Layer** | 任务执行与生命周期管理 | `submit()`, `_execute()`, `_poll_loop()`, `shutdown()` |
| **Recovery Layer** | 任务恢复逻辑与锁管理 | `recover()`, `_recover_single()`, `_recover_task()` |
| **State Layer** | 状态持久化与迁移 | `set_status()`, `set_completed()`, `load()`, `save()` |

## 2. UNKNOWN State

### 2.1 Definition

`UNKNOWN` 是任务状态的一种，表示系统无法确定任务的真实执行状态。它不是业务失败，而是：

> **"我们不知道它到底成功还是失败。"**

### 2.2 When Does UNKNOWN Occur?

| 场景 | 说明 |
|------|------|
| `Calculator.detect_status()` 返回 UNKNOWN | 后端无法确定任务状态（如 Slurm 作业状态丢失） |
| 进程崩溃后恢复 | TaskRecord 状态为 RUNNING，但无活跃的 TaskRunner |
| Executor 重建失败 | 无法重建 Executor，任务状态变为 UNKNOWN |
| 文件锁检测失败 | stale lock 状态导致无法确定任务归属 |

### 2.3 UNKNOWN Strategy

`UNKNOWN` 状态有三种恢复策略，由 `unknown_strategy` 参数控制：

| 策略 | 行为 | 适用场景 |
|------|------|----------|
| `AUTO` | 通过 `executor.is_running()` 探测作业状态后决定 poll 或 execute | **默认推荐**，适应大部分场景 |
| `POLL` | 强制轮询（假设作业仍在运行） | 确认作业仍在远程调度器中运行 |
| `EXECUTE` | 强制重新执行（假设作业已丢失） | 确认作业已不存在或无需恢复 |


# 使用示例
runner = TaskRunner(
    store,
    registry,
    unknown_strategy=UnknownStrategy.AUTO  # 默认
)
3. RecoveryManager Lifecycle
text
discover UNKNOWN task (from TaskStore.get_active_tasks())
        │
        ▼
┌───────────────────────────────────────────────┐
│  _recover_single(record)                     │
│                                               │
│  if task in _running_tasks: return           │
│  if not RecoveryLock.acquire(): return       │
│  if not FileLock.acquire(): return           │
│                                               │
│  ⭐ FileLock acquired, stored in _file_locks │
└───────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────┐
│  _recover_task(record, file_lock)            │
│                                               │
│  1. rebuild Executor (from executor_config)  │
│  2. rebuild Calculator (from calculator_params)│
│  3. recover JobHandle                         │
│  4. detect_status()                          │
└───────────────────────────────────────────────┘
        │
        ├── COMPLETED ──► collect() ──► COMPLETED (lock released)
        │
        ├── RUNNING ────► _restart_poll() ──► lock → TaskRunner
        │
        ├── PENDING ────► _restart_execute() ──► lock → TaskRunner
        │
        └── UNKNOWN ────► retry ──► classify ──► restart_poll/execute
        │
        ▼
┌───────────────────────────────────────────────┐
│  handed_over = True                          │
│  ⭐ FileLock transferred to TaskRunner       │
│  _recover_single returns (lock NOT released) │
└───────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────┐
│  TaskRunner._poll_loop / _execute            │
│  ... running ...                             │
│                                               │
│  finally:                                     │
│    release_file_lock(task_id)                │
│    release_recovery_lock(task_id)            │
└───────────────────────────────────────────────┘
关键设计原则：

FileLock 生命周期与 TaskRunner 生命周期一致，而不是 RecoveryManager 函数生命周期。

RecoveryManager 负责获取锁（_recover_single 中获取）

TaskRunner 负责释放锁（_poll_loop 或 _execute 的 finally 中释放）

通过 handed_over 标志控制锁的转移：任务进入 _running_tasks 后锁不释放，否则锁在 _recover_single 的 finally 中释放

这确保锁在整个任务执行期间被持有，防止多进程重复恢复

3.1 handed_over 机制详解
python
async def _recover_single(self, record: TaskRecord) -> None:
    handed_over = False
    try:
        await self._recover_task(record, file_lock)
        if task_id in self._running_tasks_getter():
            handed_over = True  # ★ 锁由 TaskRunner 释放
            return
    finally:
        if not handed_over:
            # 任务未进入运行状态，释放所有锁
            lock = self._file_locks.pop(task_id, None)
            if lock:
                lock.release()
            self._recovery_lock.release(task_id)
4. TaskRunner Callback 机制
text
RecoveryManager                    TaskRunner
      │                                │
      │  _recover_task()               │
      │                                │
      │  status == RUNNING             │
      │  or status == UNKNOWN          │
      │                                │
      │  ┌─────────────────────────────┘
      │  │
      ▼  ▼
await self._restart_poll(record, calc, work_dir, job_handle, file_lock)
      │                                │
      │                                ▼
      │                         ┌─────────────────────┐
      │                         │ _restart_poll()     │
      │                         │                     │
      │                         │ create_task(        │
      │                         │   _poll_loop(...)   │
      │                         │ )                   │
      │                         │                     │
      │                         │ _running_tasks[     │
      │                         │   task_id] = task   │
      │                         └─────────────────────┘
      │                                │
      │  ◄─────────────────────────────┘
      │  return True
      │
      ▼
handed_over = True
lock transferred to TaskRunner
对应地，_restart_execute 也是同样的回调模式：


await self._restart_execute(record, calc, work_dir, file_lock)
      │
      ▼
  _restart_execute()
      │
      ▼
  create_task(_execute(record, calc))
      │
      ▼
  _running_tasks[task_id] = task
      │
      ▼
  return True
5. FileLock Integration
┌─────────────────────────────────────────────────────────────────────┐
│                    FileLock 生命周期                               │
│                                                                   │
│  RecoveryManager._recover_single()                                │
│         │                                                        │
│         ▼                                                        │
│  FileLock(task_id, lock_dir)                                     │
│         │                                                        │
│         ▼                                                        │
│  file_lock.acquire()  ◄─── 获取锁                               │
│         │                                                        │
│         ▼                                                        │
│  hand over to TaskRunner                                         │
│         │                                                        │
│         ▼                                                        │
│  _poll_loop / _execute 运行中                                    │
│         │                                                        │
│         ▼                                                        │
│  finally:                                                        │
│    self._recovery.release_file_lock(task_id)  ◄─── 释放锁       │
│    self._recovery.release_recovery_lock(task_id)                 │
│                                                                   │
└─────────────────────────────────────────────────────────────────────┘
锁释放的三条路径：

路径	释放位置	条件
Poll 路径	_poll_loop finally	轮询正常结束或被取消
Execute 路径	_execute finally	执行正常结束或被取消
直接终态	_set_status_direct / _set_completed	任务变为终态
6. Crash Recovery Flow
Process A                           Process B (after restart)
─────────────────                   ──────────────────────────

                                      Application.start()
                                           │
                                           ▼
                                      TaskRunner.recover()
                                           │
                                           ▼
                                      load UNKNOWN task
                                           │
                                           ▼
                                      _recover_single()
                                           │
                                           ▼
                                      FileLock.acquire()
                                           │
                                           ▼
                                    ┌──────────────┐
                                    │ is_stale()?  │
                                    └──────────────┘
                                         │    │
                                        Yes   No
                                         │    │
                                         ▼    ▼
                                  ┌─────────┐ ┌─────────┐
                                  │ force_  │ │ acquire │
                                  │ acquire │ │ blocked │
                                  └─────────┘ └─────────┘
                                         │       │
                                         ▼       ▼
                                  ┌─────────────────────┐
                                  │ TaskRunner running  │
                                  └─────────────────────┘
                                           │
                                           ▼
                                  ┌─────────────────────┐
                                  │  finally:           │
                                  │  release lock       │
                                  └─────────────────────┘
6.1 is_stale() + force_acquire() 完整流程
def is_stale(self) -> bool:
    # 1. 文件不存在 → 没有锁
    if not lock_path.exists():
        return False
    
    # 2. 读取 PID
    pid = read_owner_pid()
    if pid is None:
        return True  # 文件内容无效
    
    # 3. PID 进程死亡 → stale
    if not is_pid_alive(pid):
        return True
    
    # 4. 尝试获取 flock
    try:
        flock(fd, LOCK_EX | LOCK_NB)
        return True  # 能获取 → 没有其它进程持有锁
    except BlockingIOError:
        return False  # 锁被其它进程持有 → 有效锁

def force_acquire(self) -> bool:
    if not self.is_stale():
        return False  # 非 stale 不强制获取
    unlink(lock_path)   # 删除旧锁文件
    return self.acquire(timeout=0)  # 重新创建并获取
7. Shutdown Race Handling
shutdown()
      │
      ▼
set _shutting_down = True
      │
      ▼
set _allow_recovery = False
      │
      ▼
cancel all _running_tasks
      │
      ▼
await asyncio.gather(*tasks, return_exceptions=True)
      │  (等待所有任务真正完成)
      ▼
cleanup:
  - _running_tasks.clear()
  - _executors.clear()
  - _calculators.clear()
  - _recovery_started_at.clear()
  - cleanup_file_locks()
关键点：

Shutdown 不直接释放锁，而是等待任务自然完成

如果在任务运行时释放锁，会导致另一个进程接手，造成重复执行

_shutting_down 标志阻止新恢复任务启动

_allow_recovery 标志阻止恢复操作绕过 shutdown 检查

7.1 _allow_recovery 标志
async def recover(self):
    self._allow_recovery = True  # 进入恢复模式
    try:
        await self._recovery.recover()
    finally:
        self._allow_recovery = False

async def _restart_poll(...):
    if self._shutting_down and not self._allow_recovery:
        return False  # ★ 只有恢复模式才允许在 shutdown 后创建任务
8. Design Principles
Principle	Description
Single Recovery	同一任务任意时刻最多只有一个恢复实例
Lock Ownership	锁生命周期绑定 TaskRunner，而非 RecoveryManager
Crash Safe	进程崩溃后可重新恢复（内核自动释放 flock）
Process Safe	多进程不会重复恢复（FileLock 互斥）
Idempotent Recovery	恢复可重复扫描，但任务只会执行一次
Graceful Shutdown	shutdown 不会提前释放锁
Stale Lock Detection	可检测并清理孤儿锁（is_stale + force_acquire）
Callback-based Release	锁统一在 TaskRunner callback 中释放
9. Design Invariants
Invariant 1: Single Recovery
同一 UNKNOWN 任务，最多被恢复一次。

UNKNOWN
    │
    ▼
lock acquire (FileLock)
    │
    ▼
只有一个进程成功获取锁
    │
    ▼
唯一 TaskRunner
    │
    ▼
唯一 callback
    │
    ▼
唯一 release
Invariant 2: Lock-Execution Coupling
锁的生命周期 ≥ 任务执行周期。

锁在任务进入 _running_tasks 之前获取，在任务完成后释放。中间任何时刻锁都被持有。

Invariant 3: Crash Safety
进程崩溃后，锁状态由内核自动清理，不影响后续恢复。

SIGKILL 后，内核自动释放 fcntl.flock，锁文件保留但不再被持有，新进程可通过 force_acquire 接管。

Invariant 4: Process Safety
多个进程同时恢复同一任务时，只有一个成功。

FileLock 基于 fcntl.flock 实现跨进程互斥，确保互斥性。

10. Key Data Structures
10.1 RecoveryManager State
class RecoveryManager:
    # 锁管理
    _file_locks: Dict[str, FileLock]      # task_id → FileLock
    _recovery_lock: RecoveryLock           # threading.Lock，同进程防重入
    
    # 超时管理
    _recovery_started_at: Dict[str, datetime]
    _recovery_timeout: float
    
    # 状态控制
    _shutting_down: bool
    _running_tasks_getter: Callable       # 获取 TaskRunner._running_tasks
10.2 TaskRunner State (Execution Layer)
class TaskRunner:
    # 执行状态
    _running_tasks: Dict[str, asyncio.Task]
    _executors: Dict[str, Executor]
    _calculators: Dict[str, Calculator]
    
    # 取消管理
    _cancel_info: Dict[str, CancelInfo]   # task_id → CancelInfo
    
    # 控制标志
    _shutting_down: bool
    _allow_recovery: bool

11. RecoveryEvent Audit
每次恢复操作都会记录结构化事件：
@dataclass
class RecoveryEvent:
    task_id: str
    old_status: TaskStatus
    action: str          # restart_poll, restart_execute, retry, probe, collect, failed, skipped
    retry_count: int
    error: Optional[RecoveryError]  # 结构化错误
    timestamp: datetime
11.1 Event Actions
Action	Description
restart_poll	启动轮询任务
restart_execute	重新执行任务
retry	UNKNOWN 重试计数增加
probe	AUTO 策略探测作业状态
collect	收集已完成任务的结果
failed	恢复失败
skipped	锁获取失败，跳过恢复
11.2 事件示例
{
  "task_id": "task_abc123",
  "old_status": "unknown",
  "action": "probe",
  "retry_count": 1,
  "error": {
    "code": "unknown_error",
    "category": "infra",
    "source": "recovery",
    "detail": "classified: poll"
  },
  "timestamp": "2026-06-28T10:30:15.123456"
}

相关文档：

Task Lifecycle — 任务状态转换与执行生命周期

FileLock Design — 跨进程锁实现与边界场景

Architecture — 系统总体架构

---

## 主要优化点

| 优化项 | 说明 |
|--------|------|
| 架构图标注 | 明确 JSONTaskStore 当前实现，SQLite 为未来计划 |
| 添加 `handed_over` 机制详解 | 解释锁如何从 RecoveryManager 转移给 TaskRunner |
| 补充 `_restart_execute` 回调 | 与 `_restart_poll` 对称展示 |
| 完善 `is_stale()` + `force_acquire()` 流程 | 展示完整算法 |
| 添加 `_allow_recovery` 标志说明 | 解释 shutdown 与 recovery 的交互 |
| 补充 Key Data Structures | 展示 RecoveryManager 和 TaskRunner 的关键状态 |
| 补充 RecoveryEvent Audit | 展示结构化事件模型 |
| 标注事件示例 | JSON 格式便于理解 |
| 优化表格格式 | 更清晰易读 |