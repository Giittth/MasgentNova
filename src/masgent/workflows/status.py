from enum import Enum


class WorkflowStatus(str, Enum):
    """工作流整体状态"""
    CREATED = "created"          # 已创建，未开始
    RUNNING = "running"          # 执行中
    COMPLETED = "completed"      # 全部成功完成
    FAILED = "failed"            # 有节点失败
    CANCELLED = "cancelled"      # 用户取消
    PARTIAL = "partial"          # 部分完成（有失败但有结果）