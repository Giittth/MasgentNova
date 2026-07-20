"""
Executor + Calculator 完整配置恢复测试

验证 recover 时能从 executor_config 和 calculator_params 完整重建
Executor 和 Calculator 的所有关键属性。
"""

import pytest
from pathlib import Path

from masgent.models.enums import TaskStatus
from masgent.tasks.task_runner import TaskRunner
from masgent.tasks.task_store import JSONTaskStore
from masgent.calculators.registry import CalculatorRegistry
from masgent.executors import ExecutorFactory
from tests.conftest import create_task_record
from tests.mock_executors import FakeSlurmExecutor


@pytest.fixture(autouse=True)
def register_fake_slurm():
    if "fake_slurm" not in ExecutorFactory.list_available():
        ExecutorFactory.register("fake_slurm", FakeSlurmExecutor)
    yield


@pytest.mark.asyncio
async def test_recover_full_executor_and_calculator_config(temp_task_dir):
    """
    验证 recover 后：
        - Executor 的所有配置字段（partition, ntasks, account, qos, walltime）正确恢复
        - Calculator 的初始化参数（encut, vasp_command, incar 等）正确恢复
    """
    store = JSONTaskStore(temp_task_dir)
    registry = CalculatorRegistry()

    # 构造完整的执行器配置（模拟 Slurm）
    executor_config = {
        "type": "fake_slurm",
        "partition": "gpu",
        "ntasks": 8,
        "account": "project_123",
        "qos": "high",
        "walltime": "04:00:00",
    }

    # 构造计算器参数
    # 注意：MockCalculator 的额外参数应放在 init_params 键下，
    # 这样它们会被 get_init_params() 返回并持久化。
    calculator_params = {
        "detect_status_return": TaskStatus.RUNNING,   # MockCalculator 自己的参数
        "init_params": {                               # 额外参数
            "encut": 520,
            "vasp_command": "vasp_gpu",
            "incar": {"ISMEAR": 0, "SIGMA": 0.05},
            "some_other_param": 123,
        }
    }

    # 预先保存一个 RUNNING 任务（模拟崩溃前的状态）
    record = create_task_record(
        task_id="full_restore_test",
        status=TaskStatus.RUNNING,
        work_dir="/tmp/full_restore",
        calculator_type="mock",
        calculator_params=calculator_params,
    )
    record.executor_config = executor_config
    store.save(record)

    # 恢复
    runner = TaskRunner(store, registry)
    await runner.recover()

    # --- 验证 Executor 重建 ---
    executor = runner._executors["full_restore_test"]
    assert isinstance(executor, FakeSlurmExecutor)
    assert executor.partition == "gpu"
    assert executor.ntasks == 8
    assert executor.account == "project_123"
    assert executor.qos == "high"
    assert executor.walltime == "04:00:00"

    # --- 验证 Calculator 重建 ---
    calc = runner._calculators["full_restore_test"]
    # 通过 init_params 验证额外参数
    assert calc.init_params.get("encut") == 520
    assert calc.init_params.get("vasp_command") == "vasp_gpu"
    assert calc.init_params.get("incar") == {"ISMEAR": 0, "SIGMA": 0.05}
    assert calc.init_params.get("some_other_param") == 123

    # 清理
    await runner.shutdown()