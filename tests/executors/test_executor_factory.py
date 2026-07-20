"""ExecutorFactory 单元测试"""

import pytest

from masgent.executors import ExecutorFactory, LocalExecutor, SlurmExecutor, Executor


class TestExecutorFactory:
    def test_create_local(self):
        """创建本地执行器"""
        executor = ExecutorFactory.create("local")
        assert isinstance(executor, LocalExecutor)

    def test_create_local_with_aliases(self):
        """创建带别名的本地执行器"""
        executor = ExecutorFactory.create(
            "local",
            aliases={"vasp_std": "/path/to/fake_vasp.sh"}
        )
        assert isinstance(executor, LocalExecutor)
        assert executor.aliases["vasp_std"] == "/path/to/fake_vasp.sh"

    def test_create_slurm(self):
        """创建 Slurm 执行器"""
        executor = ExecutorFactory.create(
            "slurm",
            partition="gpu",
            ntasks=4,
            walltime="02:00:00",
            jobname="test_job"
        )
        assert isinstance(executor, SlurmExecutor)
        assert executor.partition == "gpu"
        assert executor.ntasks == 4
        assert executor.walltime == "02:00:00"
        assert executor.jobname == "test_job"

    def test_create_unknown_backend(self):
        """未知 backend 应抛出 ValueError"""
        with pytest.raises(ValueError, match="Unknown executor backend: unknown"):
            ExecutorFactory.create("unknown")

    def test_list_available(self):
        """列出所有可用的执行器"""
        available = ExecutorFactory.list_available()
        assert "local" in available
        assert "slurm" in available

    def test_register_custom_executor(self):
        """注册自定义执行器"""
        # 创建一个简单的 mock 执行器类
        class MockExecutor(Executor):
            async def spawn(self, *args, **kwargs):
                pass
            async def is_running(self, *args, **kwargs):
                return False
            async def wait(self, *args, **kwargs):
                return 0
            async def kill(self, *args, **kwargs):
                return True
            async def run(self, *args, **kwargs):
                return None

        ExecutorFactory.register("mock", MockExecutor)
        assert "mock" in ExecutorFactory.list_available()

        executor = ExecutorFactory.create("mock")
        assert isinstance(executor, MockExecutor)

    def test_register_invalid_type(self):
        """注册非 Executor 子类应抛出 TypeError"""

        class NotExecutor:
            pass

        with pytest.raises(TypeError, match="must be a subclass of Executor"):
            ExecutorFactory.register("invalid", NotExecutor)