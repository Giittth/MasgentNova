# TaskRunner 任务管理

## 核心概念
- **Task**：一个独立的计算任务（如单点能计算）
- **TaskRecord**：任务的持久化记录（状态、结果、元数据）
- **TaskStore**：存储 TaskRecord（JSON 或数据库）

## 提交任务

info = await runner.submit(
    calculator=calc,
    structure=structure,
    workflow_type=WorkflowType.RELAX,
    fmax=0.05,          # 额外参数
    steps=200,
)
查询状态
status = await runner.poll(info.task_id)
# TaskStatus.PENDING / RUNNING / COMPLETED / FAILED / CANCELLED / UNKNOWN
收集结果
result = await runner.collect(info.task_id)
# {"data": {...}, "metadata": {...}}
取消任务
await runner.cancel(info.task_id)
崩溃恢复
# 程序重启后
await runner.recover()   # 自动恢复所有未完成任务
重试策略
from masgent.tasks import RetryPolicy

policy = RetryPolicy(max_retries=5)
runner = TaskRunner(store, registry, retry_policy=policy)
