"""Calculator 注册表 —— 用于动态创建计算器实例"""

from typing import Dict, Callable, Any
from masgent.calculators.base import Calculator


class CalculatorRegistry:
    """工厂注册表，使用稳定标识符（如 "vasp"）而非类名"""

    _factories: Dict[str, Callable[..., Calculator]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[..., Calculator]) -> None:
        """注册计算器工厂"""
        cls._factories[name] = factory

    @classmethod
    def create(cls, name: str, **kwargs) -> Calculator:
        """根据标识符创建实例"""
        if name not in cls._factories:
            raise ValueError(f"Unknown calculator type: {name}")
        return cls._factories[name](**kwargs)

    @classmethod
    def list(cls) -> list:
        return list(cls._factories.keys())