# Task Lifecycle & State Machine

本文档描述任务从提交到完成的完整生命周期，包括状态转换、锁持有关系和执行流程。

## 1. Task Lifecycle (Full)
            submit()
                │
                ▼
            ┌─────────┐
            │ PENDING │
            └─────────┘
                │
            _execute() 启动
                │
                ▼
            ┌─────────┐
            │ RUNNING │
            └─────────┘
                │
                │
▼               ▼           ▼
┌──────────┐ ┌──────┐ ┌──────────┐
│COMPLETED │ │FAILED│ │ UNKNOWN  │
└──────────┘ └──────┘ └──────────┘
            │
            │ recover()
            ▼
    ┌─────────────────┐
    │ RecoveryManager │
    └─────────────────┘
            │
            acquire FileLock
            │
┌───────────┴───────────┐
│                       │
▼                       ▼
retry allowed retry exhausted
│                       │
▼                       ▼
┌─────────┐     ┌──────────┐
│ RUNNING │     │  FAILED  │
└─────────┘     └──────────┘
            │
            ▼
        ┌──────────┐
        │COMPLETED │
        └──────────┘


### 1.1 State Descriptions

|    State    |                          Description                         | Terminal |
|-------------|--------------------------------------------------- ----------|----------|
| `PENDING`   | 任务已提交，等待 `_execute()` 调度执行                         |   No     |
| `RUNNING`   | 任务正在执行（`_execute`）或轮询中（`_poll_loop`）             |    No    | 
| `COMPLETED` | 任务成功完成，结果已收集                                       |   Yes    |
| `FAILED`    | 任务执行失败（launch 失败、detect_status 失败、collect 失败等） |   Yes    |
| `CANCELLED` | 用户主动取消（`cancel()` 调用）                                |   Yes    |
| `UNKNOWN`   | 状态未知，等待 `RecoveryManager.recover()` 处理                |   No     |

### 1.2 State Transitions

|    From   |      To     |                               Trigger                           |
|-----------|-------------|-----------------------------------------------------------------|
| `PENDING` | `RUNNING`   | `TaskRunner._execute()` 开始执行                                 |
| `PENDING` | `FAILED`    | `_execute()` 中 Calculator 创建失败或 launch 失败                 |
| `PENDING` | `CANCELLED` | 用户调用 `TaskRunner.cancel()`                                   |
| `RUNNING` | `COMPLETED` | `detect_status()` 返回 `COMPLETED`，`collect()` 成功             |
| `RUNNING` | `FAILED`    | `detect_status()` 返回 `FAILED`，或超时，或 collect 失败          |
| `RUNNING` | `CANCELLED` | 用户调用 `TaskRunner.cancel()`                                   |
| `RUNNING` | `UNKNOWN`   | `detect_status()` 返回 `UNKNOWN`（无法确定任务状态）               |
| `UNKNOWN` | `RUNNING`   | `RecoveryManager` 恢复成功，`_restart_poll` 或 `_restart_execute` |
| `UNKNOWN` | `FAILED`    | `RetryPolicy.is_exhausted()` 返回 True，重试耗尽                  |
| `UNKNOWN` | `COMPLETED` | `RecoveryManager` 检测到任务已完成，`collect()` 成功               |

## 2. Lock Lifecycle (Full)
┌─────────────────────────────────────────────────────────────────────┐
│ Task 生命周期与锁持有 │
│ │
│ PENDING │
│ │ │
│ ▼ │
│ RUNNING │
│ │ │
│ ├── RecoveryLock acquired (threading) ──┐ │
│ │ │ │
│ ├── FileLock acquired (fcntl) ──────────┤ │
│ │ │ │
│ ├── TaskRunner._running_tasks[task_id] │ 锁持有期间 │
│ │ │ │
│ ├── _poll_loop / _execute 运行 │ │
│ │ │ │
│ ├── RecoveryLock released (finally) ───┘ │
│ │ │
│ ├── FileLock released (finally) │
│ │ │
│ ▼ │
│ COMPLETED / FAILED / UNKNOWN │
│ │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Recovery 路径锁生命周期 │
│ │
│ UNKNOWN │
│ │ │
│ ▼ │
│ RecoveryManager.recover() │
│ │ │
│ ├── RecoveryLock.acquire() (threading) │
│ │ │
│ ├── FileLock.acquire() (fcntl) │
│ │ │
│ ├── rebuild Executor (ExecutorFactory.create) │
│ │ │
│ ├── rebuild Calculator (CalculatorRegistry.create) │
│ │ │
│ ├── detect_status() │
│ │ │
│ ├── handed_over = True (任务进入 _running_tasks) │
│ │ │
│ ├── lock transferred to TaskRunner │
│ │ │
│ ▼ │
│ RUNNING (TaskRunner 运行中) │
│ │ │
│ ▼ │
│ _poll_loop / _execute │
│ │ │
│ ▼ │
│ finally: │
│ ├── self._recovery.release_file_lock(task_id) │
│ └── self._recovery.release_recovery_lock(task_id) │
│ │
└─────────────────────────────────────────────────────────────────────┘


### 2.1 Lock Ownership Table

| Lock Type | Acquired By | Released By | Purpose |
|-----------|-------------|-------------|---------|
| **RecoveryLock** (threading) | `RecoveryManager._recover_single()` | `_poll_loop` / `_execute` finally | 同进程防重入 |
| **FileLock** (fcntl) | `RecoveryManager._recover_single()` | `_poll_loop` / `_execute` finally | 跨进程互斥 |

### 2.2 Lock Release Paths

| Path | Release Location | When |
|------|------------------|------|
| Poll 路径 | `TaskRunner._poll_loop` finally | 轮询正常结束或被取消 |
| Execute 路径 | `TaskRunner._execute` finally | 执行正常结束或被取消 |
| 直接终态 | `TaskStateManager.set_status()` / `set_completed()` | 任务变为终态 |

## 3. _poll_loop Lifecycle
┌─────────────────────────────────────────────────────┐
│ TaskRunner._poll_loop 启动 │
│ (由 RecoveryManager._restart_poll 创建) │
└─────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────┐
│ 确保 _recovery_started_at 已设置 │
│ self._recovery._recovery_started_at[task_id] = │
│ datetime.now() │
└─────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────┐
│ while True: │
└─────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────┐
│ status = await calc.detect_status( │
│ work_dir, job_handle │
│ ) │
└─────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────┐
│ 状态判断 │
└─────────────────────────────────────────────────────┘
/ │ \ \
/ │ \ \
▼ ▼ ▼ ▼ ▼
┌──────────┐┌──────┐┌──────┐┌──────┐┌──────────┐
│ RUNNING ││UNKNOWN││COMPL. ││FAILED││CANCELLED │
└──────────┘└──────┘└──────┘└──────┘└──────────┘
│ │ │ │ │
▼ ▼ │ │ │
超时检查 继续轮询 │ │ │
/ \ │ ▼ ▼ ▼
▼ ▼ │ ┌─────────────────────────────┐
超时 未超时 │ │ status.is_terminal │
│ │ │ │ == True │
▼ ▼ │ └─────────────────────────────┘
标记FAILED │ │ │
│ │ ▼
▼ │ break (退出循环)
继续轮询 │
│
▼
┌─────────────────────────────────────────────────────┐
│ 处理终端状态 │
│ │
│ if status == COMPLETED: │
│ result = await calc.collect(...) │
│ TaskStateManager.set_completed(...) │
│ else: │
│ TaskStateManager.set_status(FAILED, ...) │
└─────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────┐
│ finally: │
│ │
│ 1. 只清理自己的 task (identity 检查) │
│ if _running_tasks.get(task_id) is current: │
│ _running_tasks.pop(task_id) │
│ │
│ 2. self._recovery.release_file_lock(task_id) │
│ │
│ 3. self._recovery.release_recovery_lock(task_id) │
└─────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────┐
│ _poll_loop 结束 │
└─────────────────────────────────────────────────────┘


> **注意**：
> - `_poll_loop` 对 `UNKNOWN` 状态**继续轮询**，不主动触发恢复（恢复由 `RecoveryManager.recover()` 统一调度）
> - 使用 `current_task` identity 确保只清理自己，避免误删后来注册的新任务
> - 锁在 `finally` 中**始终释放**，无论任务成功、失败还是被取消

## 4. _execute Lifecycle
┌─────────────────────────────────────────────────────┐
│ TaskRunner._execute 启动 │
│ (由 submit() 或 RecoveryManager._restart_execute) │
└─────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────┐
│ TaskStateManager.set_status(RUNNING) │
└─────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────┐
│ job_handle = await calc.launch(work_dir) │
│ (提交作业到 Executor) │
└─────────────────────────────────────────────────────┘
│
┌─────────┴─────────┐
│ │
▼ ▼
success failure
│ │
▼ ▼
save job_handle TaskStateManager.
to TaskStore set_status(FAILED)
│ │
│ │
▼ │
┌─────────────────────────────────────────────────────┐
│ while True: │
└─────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────┐
│ status = await calc.detect_status( │
│ work_dir, job_handle_obj │
│ ) │
└─────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────┐
│ status.is_terminal? │
└─────────────────────────────────────────────────────┘
/
/
▼ ▼
Yes No
│ │
▼ ▼
退出循环 继续轮询 (sleep)
│
▼
┌─────────────────────────────────────────────────────┐
│ 处理终端状态 │
│ │
│ if status == COMPLETED: │
│ result = await calc.collect(...) │
│ TaskStateManager.set_completed(...) │
│ else: │
│ TaskStateManager.set_status(FAILED, ...) │
└─────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────┐
│ except asyncio.CancelledError: │
│ if not self._shutting_down: │
│ TaskStateManager.set_status(CANCELLED) │
└─────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────┐
│ finally: │
│ │
│ 1. 只清理自己的 task (identity 检查) │
│ if _running_tasks.get(task_id) is current: │
│ _running_tasks.pop(task_id) │
│ │
│ 2. self._recovery.release_file_lock(task_id) │
│ │
│ 3. self._recovery.release_recovery_lock(task_id) │
│ │
│ 4. self._executors.pop(task_id) │
└─────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────┐
│ _execute 结束 │
└─────────────────────────────────────────────────────┘


## 5. _poll_loop vs _execute 对比

| 阶段 | `_poll_loop` | `_execute` |
|------|--------------|------------|
| **触发场景** | `RecoveryManager._restart_poll`（RUNNING 恢复） | `submit()` 或 `RecoveryManager._restart_execute`（新提交/PENDING 恢复） |
| **初始状态** | 任务已在 `RUNNING` | 先 `set_status(RUNNING)` |
| **launch 调用** | ❌ 不调用 | ✅ 调用 `calc.launch()` |
| **状态检测** | 轮询 `detect_status()` | 轮询 `detect_status()` |
| **超时检查** | ✅ 支持（`_check_recovery_timeout`） | ✅ 支持 |
| **UNKNOWN 处理** | 继续轮询（不退出） | 不适用（_execute 不处理 UNKNOWN） |
| **锁释放** | `finally` 中释放 | `finally` 中释放 |
| **`_running_tasks` 清理** | `finally` 中清理 | `finally` 中清理 |
| **执行者** | `TaskRunner` | `TaskRunner` |

## 6. Key Constraints

| Rule | Description |
|------|-------------|
| **锁不交叉** | `RecoveryLock` 和 `FileLock` 互不依赖，各自独立管理 |
| **单释放** | 每个锁只在 `_poll_loop` / `_execute` 的 `finally` 中释放一次 |
| **幂等清理** | `_running_tasks.pop(task_id, None)` 是幂等的，多次调用安全 |
| **状态原子性** | 状态变更由 `TaskStateManager` 统一管理，不绕过 |
| **Task Identity** | `finally` 中通过 `current_task` 检查，只清理自己创建的任务 |
| **Cancel 语义分离** | `USER` cancel 写 `CANCELLED`；`SHUTDOWN`/`INTERNAL` cancel 不写状态 |

## 7. Design Invariants

### Invariant 1: Lock-Execution Coupling

> **锁的生命周期 ≥ 任务执行周期。**

锁在任务进入 `_running_tasks` 之前获取，在任务完成后释放。中间任何时刻锁都被持有。

### Invariant 2: Task Identity

> **`_running_tasks[task_id]` 中的任务一定与当前执行的任务是同一个对象。**

`finally` 中使用 `self._running_tasks.get(task_id) is current_task` 确保只清理自己创建的任务，避免误删后来注册的新任务。

### Invariant 3: Single Release

> **每个锁在其生命周期内只被释放一次。**

锁由 `RecoveryManager` 获取，由 `TaskRunner` 在 `finally` 中释放，中间没有任何其他释放路径。

### Invariant 4: State Consistency

> **状态变更总是通过 `TaskStateManager`，不绕过。**

所有状态修改（包括 `COMPLETED`、`FAILED`、`CANCELLED`）都通过 `TaskStateManager` 的方法，确保 `updated_at`、`finished_at` 等元数据一致更新。

---

**相关文档**：
- [Recovery System Design](recovery.md) — 恢复系统架构与设计原则
- [FileLock Design](file_lock.md) — 跨进程锁实现与边界场景
- [Architecture](../architecture.md) — 系统总体架构