#!/usr/bin/env python3
"""验证 JSONTaskStore"""

import asyncio
from pathlib import Path
import uuid
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from masgent.models.task import TaskRecord, TaskStatus
from masgent.models.enums import WorkflowType  # ← 新增导入
from masgent.utils.task_store import JSONTaskStore


def main():
    print("=" * 60)
    print("JSONTaskStore 验证")
    print("=" * 60)

    # 1. 创建存储目录
    store = JSONTaskStore(Path("./test_tasks"))

    # 2. 创建任务记录（使用 WorkflowType 枚举）
    task = TaskRecord(
        task_id=f"task_{uuid.uuid4().hex[:8]}",
        workflow_type=WorkflowType.EOS,  # ← 改为枚举
        status=TaskStatus.CREATED,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir="/home/user/masgent_runs/Si/eos/abc123",
        metadata={"calculator": "VaspCalculator", "scale_factors": [0.94, 1.0, 1.06]},
    )

    # 3. 保存任务
    print(f"\n 创建任务: {task.task_id}")
    store.save(task)

    # 4. 加载任务
    loaded = store.load(task.task_id)
    print(f" 加载任务: {loaded.task_id}")
    print(f"   workflow_type: {loaded.workflow_type.value}")
    print(f"   status: {loaded.status.value}")

    # 5. 更新状态
    store.update_status(task.task_id, TaskStatus.RUNNING)
    loaded = store.load(task.task_id)
    print(f" 更新状态后: {loaded.status.value}")

    # 6. 保存结果
    store.save_result(task.task_id, {"energy": -10.5, "volume": 160.2})
    loaded = store.load(task.task_id)
    print(f" 保存结果后: status={loaded.status.value}, result={loaded.result}")

    # 7. 列出所有任务
    print("\n 所有任务:")
    for t in store.list_tasks(limit=10):
        print(f"   {t.task_id}: {t.status.value}")

    print("\n" + "=" * 60)
    print("✅ JSONTaskStore 验证通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()