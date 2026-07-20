# Masgent 架构设计

## 系统分层
┌─────────────────────────────────────────────────────────────────┐
│ User / Client │
│ (WorkflowBuilder DSL / API) │
└─────────────────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────┐
│ WorkflowScheduler │
│ (DAG 调度 / 任务编排) │
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
│ │ RecoveryManager │ │
│ │ recover() _recover_single() _recover_task() │ │
│ │ _restart_poll() _restart_execute() │ │
│ └─────────────────────────────────────────────────────────┘ │
│ │ │
│ ▼ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ TaskStateManager │ │
│ │ set_status() set_completed() set_failed() │ │
│ │ load() save() │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────┐
│ Calculator │
│ prepare() launch() detect_status() │
│ collect() cancel() │
└─────────────────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────┐
│ Executor │
│ spawn() is_running() kill() run() │
└─────────────────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────┐
│ HPC / Local Backend │
│ Slurm Local PBS LSF WSL │
└─────────────────────────────────────────────────────────────────┘


## 核心组件

### 1. TaskRunner — 任务执行层
- **职责**：任务提交、执行、轮询、取消、优雅关闭
- **关键方法**：`submit()`、`_execute()`、`_poll_loop()`、`cancel()`、`shutdown()`
- **状态**：维护 `_running_tasks`（运行中的 asyncio Task）、`_executors`、`_calculators`
- **取消语义**：区分 USER / SHUTDOWN / INTERNAL 三种取消来源

### 2. RecoveryManager — 任务恢复层
- **职责**：UNKNOWN 状态任务恢复、锁管理、重试策略、超时检查
- **关键方法**：`recover()`、`_recover_single()`、`_recover_task()`、`_restart_poll()`、`_restart_execute()`
- **状态**：维护 `_file_locks`、`_recovery_lock`、`_recovery_started_at`
- **策略**：支持 AUTO / POLL / EXECUTE 三种 UNKNOWN 处理策略

### 3. TaskStateManager — 状态管理层
- **职责**：任务状态持久化与迁移
- **关键方法**：`set_status()`、`set_completed()`、`set_failed()`、`load()`、`save()`
- **设计原则**：状态变更的唯一入口，确保 `updated_at`、`finished_at` 等元数据一致

### 4. JSONTaskStore — 任务存储
- **职责**：任务记录的持久化存储（JSON 文件）
- **功能**：CRUD、状态查询、fingerprint 索引、恢复事件持久化
- **关键方法**：`save()`、`load()`、`get_active_tasks()`、`append_recovery_event()`

### 5. Calculator — 计算抽象
- **职责**：输入准备、计算启动、状态检测、结果收集、任务取消
- **关键方法**：`prepare()`、`launch()`、`detect_status()`、`collect()`、`cancel()`
- **实现**：`VaspCalculator`、`MLPCalculator`、`MockCalculator` 等
- **注册机制**：通过 `CalculatorRegistry` 实现动态创建

### 6. Executor — 执行后端
- **职责**：进程/作业的提交、状态查询、等待、终止
- **关键方法**：`spawn()`、`is_running()`、`wait()`、`kill()`、`run()`
- **实现**：`LocalExecutor`、`SlurmExecutor`、`FakeSlurmExecutor` 等
- **注册机制**：通过 `ExecutorFactory` 实现动态创建

### 7. Recovery Lock — 跨进程互斥锁
- **RecoveryLock (threading)**：同进程防重入，短生命周期
- **FileLock (fcntl)**：跨进程互斥，长生命周期（绑定 TaskRunner 生命周期）
- **功能**：`acquire()`、`release()`、`is_stale()`、`force_acquire()`
- **设计原则**：锁文件是唯一状态源，`release()` 删除锁文件

### 8. WorkflowScheduler — 工作流调度（v0.7+ 计划）
- **职责**：DAG 图结构管理、并发调度、失败传播、检查点保存/恢复
- **状态**：维护节点状态图、执行上下文

## 架构原则

| 原则 | 说明 |
|------|------|
| **三层职责分离** | 执行层（TaskRunner）、恢复层（RecoveryManager）、状态层（TaskStateManager）各自独立 |
| **单状态源** | 所有任务状态变更通过 `TaskStateManager`，不绕过 |
| **锁生命周期绑定** | FileLock 生命周期与 TaskRunner 生命周期一致，而非 RecoveryManager 函数生命周期 |
| **Crash Safe** | 进程崩溃后锁由内核自动释放，任务可恢复 |
| **Process Safe** | 多进程不会重复恢复同一任务（FileLock 互斥） |
| **结构化审计** | 恢复事件（RecoveryEvent）使用结构化错误码，不依赖自由字符串 |

## 数据流

### 正常提交路径
User
│
▼
TaskRunner.submit()
│
▼
TaskStateManager.save(PENDING)
│
▼
TaskRunner._execute()
│
▼
Calculator.launch()
│
▼
Executor.spawn()
│
▼
Job running
│
▼
Calculator.detect_status()
│
▼
COMPLETED → TaskStateManager.set_completed()


### 恢复路径
UNKNOWN task detected
│
▼
TaskRunner.recover()
│
▼
RecoveryManager.recover()
│
▼
RecoveryManager._recover_single()
│
├── acquire RecoveryLock
├── acquire FileLock
├── rebuild Executor + Calculator
├── detect_status()
├── _restart_poll() / _restart_execute()
└── hand over lock to TaskRunner
│
▼
TaskRunner._poll_loop() / _execute()
│
▼
finally: release lock + cleanup


## 相关文档

- [Task Lifecycle](design/task_lifecycle.md) — 任务状态转换与执行生命周期
- [Recovery System Design](design/recovery.md) — 恢复系统架构与设计原则
- [FileLock Design](design/file_lock.md) — 跨进程锁实现与边界场景
- [Adding a Calculator](adding_calculator.md) — 如何添加新的 Calculator