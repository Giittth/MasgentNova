"""Executor 工厂 —— 支持直接创建和从配置恢复"""

from typing import Dict, Any, Union
from pathlib import Path

from masgent.executors.base import Executor
from masgent.executors.local import LocalExecutor
from masgent.executors.slurm import SlurmExecutor


class ExecutorFactory:
    """
    Executor 工厂

    支持两种创建方式：
        1. 直接创建：ExecutorFactory.create("slurm", partition="cpu", ntasks=32)
        2. 从配置恢复：ExecutorFactory.create({"type": "slurm", "partition": "cpu"})

    也支持注册自定义执行器：ExecutorFactory.register("custom", CustomExecutor)
    """

    _registry: Dict[str, type] = {
        "local": LocalExecutor,
        "slurm": SlurmExecutor,
    }

    @classmethod
    def register(cls, name: str, executor_class: type) -> None:
        """注册新的 Executor 类型"""
        if not issubclass(executor_class, Executor):
            raise TypeError(f"{executor_class} must be a subclass of Executor")
        cls._registry[name] = executor_class

    @classmethod
    def create(cls, backend_or_config: Union[str, Dict[str, Any]], **kwargs) -> Executor:
        """
        创建 Executor 实例

        支持两种输入方式：

        1. 直接创建：
            executor = ExecutorFactory.create("slurm", partition="cpu", ntasks=32)

        2. 从配置恢复：
            executor = ExecutorFactory.create({"type": "local", "aliases": {...}})

        Args:
            backend_or_config: 执行器类型名（str）或配置字典
            **kwargs: 当第一个参数为 str 时，作为构造参数传递

        Returns:
            Executor: 执行器实例

        Raises:
            ValueError: 未知的执行器类型
        """
        # 方式2：从配置字典创建
        if isinstance(backend_or_config, dict):
            config = backend_or_config
            executor_type = config.get("type")
            if executor_type is None:
                raise ValueError("Executor config missing 'type' field")
            params = {k: v for k, v in config.items() if k != "type"}
            executor_class = cls._registry.get(executor_type)
            if executor_class is None:
                raise ValueError(f"Unknown executor type: {executor_type}")
            return executor_class(**params)

        # 方式1：直接创建
        backend = backend_or_config
        executor_class = cls._registry.get(backend)
        if executor_class is None:
            available = ", ".join(cls._registry.keys())
            raise ValueError(
                f"Unknown executor backend: {backend}. "
                f"Available: {available}"
            )
        return executor_class(**kwargs)

    @classmethod
    def list_available(cls) -> list[str]:
        """列出所有已注册的执行器类型"""
        return list(cls._registry.keys())

    @classmethod
    def get_class(cls, backend: str) -> type:
        """获取执行器类（不实例化）"""
        executor_class = cls._registry.get(backend)
        if executor_class is None:
            raise ValueError(f"Unknown executor type: {backend}")
        return executor_class