"""
应用主入口 —— 集成 TaskRunner 和生命周期管理
"""

import asyncio
import signal
from typing import Optional, Union

from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import TaskStore
from masgent.calculators.registry import CalculatorRegistry
from masgent.models.enums import UnknownStrategy
from masgent.utils.logger import logger


class Application:
    """
    材料模拟应用主类

    职责：
        - 启动时自动恢复未完成任务
        - 管理 TaskRunner 生命周期
        - 优雅关闭
    """

    def __init__(
        self,
        task_store: TaskStore,
        calculator_registry: CalculatorRegistry,
        poll_interval: float = 10.0,
        unknown_strategy: Union[str, UnknownStrategy] = UnknownStrategy.AUTO,
        auto_recover: bool = True,
    ):
        self.task_store = task_store
        self.calculator_registry = calculator_registry
        self.poll_interval = poll_interval
        self.auto_recover = auto_recover

        self.task_runner = TaskRunner(
            task_store=task_store,
            calculator_registry=calculator_registry,
            poll_interval=poll_interval,
            unknown_strategy=unknown_strategy,
        )

        self._running = False
        self._shutdown_requested = False
        self._started = False  # 幂等保护

    async def start(self) -> None:
        """启动应用，自动恢复未完成任务"""
        # 幂等保护
        if self._started:
            logger.warning("Application already started, skipping")
            return
        self._started = True

        logger.info("Application starting...")

        # 1. 自动恢复
        if self.auto_recover:
            logger.info("Running auto-recovery...")
            await self.task_runner.recover()
            logger.info("Auto-recovery completed")

        # 2. 标记运行状态
        self._running = True

        # 3. 注册信号处理（优雅关闭）
        self._setup_signal_handlers()

        logger.info("Application started successfully")

    def _setup_signal_handlers(self):
        """注册 SIGTERM/SIGINT 信号处理"""
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig,
                    lambda: asyncio.create_task(self.shutdown())
                )
        except RuntimeError:
            # 没有运行中的事件循环，跳过信号注册
            logger.debug("No running event loop, skipping signal handlers")

    async def shutdown(self, timeout: float = 5.0) -> None:
        """优雅关闭应用"""
        if self._shutdown_requested:
            return
        self._shutdown_requested = True

        logger.info("Application shutting down...")
        await self.task_runner.shutdown(timeout=timeout)
        self._running = False
        logger.info("Application shutdown complete")

    def is_running(self) -> bool:
        return self._running