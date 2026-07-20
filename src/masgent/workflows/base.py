"""Workflow 基类——定义工作流的标准接口"""

from abc import ABC, abstractmethod
from pymatgen.core import Structure

from masgent.calculators.base import Calculator
from masgent.models.calculator import CalculationResult


class Workflow(ABC):
    """
    工作流基类

    所有 Workflow 都遵循统一的模式：
    1. 初始化时传入 Calculator
    2. run() 方法执行完整工作流
    3. 返回 CalculationResult
    """

    def __init__(self, calculator: Calculator):
        self.calculator = calculator

    @abstractmethod
    async def run(self, structure: Structure) -> CalculationResult:
        """执行工作流，返回计算结果"""
        pass

    # 去掉 @abstractmethod，让子类可继承默认实现
    def get_info(self) -> dict:
        """返回工作流信息"""
        return {
            "name": self.__class__.__name__,
            "calculator": self.calculator.__class__.__name__,
        }

    def health_check(self) -> dict:
        """检查工作流及其 Calculator 的健康状态"""
        return {
            "workflow": self.__class__.__name__,
            "calculator": self.calculator.health_check(),
        }