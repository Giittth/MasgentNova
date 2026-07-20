"""Calculator 抽象基类 —— 纯无状态科学计算组件"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from pymatgen.core import Structure

from masgent.models.enums import TaskStatus, WorkflowType
from masgent.models.job import JobHandle
from masgent.models.calculator import CalculationResult


class Calculator(ABC):
    """
    Calculator 抽象基类

    职责：
        - 准备输入文件
        - 启动计算（通过 Executor）
        - 检测状态
        - 收集结果
        - 取消作业

    不关心：
        - task_id
        - 持久化
        - 调度逻辑
    """

    # 稳定标识符，子类必须覆盖（如 "vasp", "qe"）
    TYPE: str = "unknown"

    @abstractmethod
    async def prepare(
        self,
        structure: Structure,
        workflow_type: WorkflowType,
        **kwargs,
    ) -> Path:
        """准备输入文件，返回工作目录路径"""
        pass

    @abstractmethod
    async def launch(
        self,
        work_dir: Path,
    ) -> JobHandle:
        """启动计算，返回作业句柄"""
        pass

    @abstractmethod
    async def detect_status(
        self,
        work_dir: Path,
        job: Optional[JobHandle] = None,
    ) -> TaskStatus:
        """检测任务状态（若提供 JobHandle，可结合调度系统状态）"""
        pass

    @abstractmethod
    async def collect(
        self,
        work_dir: Path,
        workflow_type: WorkflowType,
    ) -> CalculationResult:
        """收集计算结果"""
        pass

    @abstractmethod
    async def cancel(self, job: JobHandle) -> bool:
        """取消正在运行的计算作业"""
        pass

    @abstractmethod
    def get_init_params(self) -> dict:
        """返回实例化参数，用于恢复重建"""
        pass