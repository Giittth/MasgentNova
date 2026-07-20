"""pytest 全局配置和 fixture"""

import sys
import os
import time
import asyncio
import pytest
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Any
from pymatgen.core import Structure, Lattice
from datetime import datetime

from masgent.models.enums import TaskStatus


# 将 src/ 目录添加到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# 获取项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ========== 工具函数 ==========
async def wait_until(condition, timeout=10.0, interval=0.1):
    """等待 condition() 返回 True，超时抛出 TimeoutError"""
    start = asyncio.get_event_loop().time()
    while True:
        if condition():
            return
        if asyncio.get_event_loop().time() - start > timeout:
            raise TimeoutError("Condition not met within timeout")
        await asyncio.sleep(interval)


# ========== 原有的 fixtures ==========
@pytest.fixture
def tmp_project_dir(tmp_path):
    """为每个测试提供独立的临时工作目录（含子目录结构）"""
    runs_dir = tmp_path / "masgent_runs"
    runs_dir.mkdir()
    return runs_dir


@pytest.fixture
def poscar_nacl():
    """NaCl 结构（岩盐，Fm-3m）"""
    lattice = Lattice.cubic(5.64)
    species = ["Na", "Na", "Na", "Na", "Cl", "Cl", "Cl", "Cl"]
    coords = [
        [0.0, 0.0, 0.0],
        [0.5, 0.5, 0.0],
        [0.5, 0.0, 0.5],
        [0.0, 0.5, 0.5],
        [0.0, 0.0, 0.5],
        [0.5, 0.5, 0.5],
        [0.5, 0.0, 0.0],
        [0.0, 0.5, 0.0],
    ]
    return Structure(lattice, species, coords)


@pytest.fixture
def poscar_si():
    """Si 结构（金刚石）"""
    lattice = Lattice.cubic(5.43)
    species = ["Si", "Si"]
    coords = [
        [0.0, 0.0, 0.0],
        [0.25, 0.25, 0.25],
    ]
    return Structure(lattice, species, coords)


@pytest.fixture
def poscar_nacl_path(tmp_project_dir, poscar_nacl):
    """POSCAR 文件路径（NaCl）"""
    poscar_path = tmp_project_dir / "POSCAR"
    poscar_nacl.to_file(str(poscar_path), "poscar")
    return poscar_path


@pytest.fixture
def poscar_si_path(tmp_project_dir, poscar_si):
    """POSCAR 文件路径（Si）"""
    poscar_path = tmp_project_dir / "POSCAR_Si"
    poscar_si.to_file(str(poscar_path), "poscar")
    return poscar_path


# ========== Phase 4.3 新增 fixtures ==========
@pytest.fixture
def temp_task_dir():
    """临时任务存储目录（用于 TaskStore）"""
    path = Path(tempfile.mkdtemp(prefix="masgent_test_"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def task_store(temp_task_dir):
    """JSONTaskStore 实例"""
    from masgent.tasks.task_store import JSONTaskStore
    return JSONTaskStore(temp_task_dir)


@pytest.fixture
def calculator_registry():
    """CalculatorRegistry 实例（已注册 mock）"""
    from masgent.calculators.registry import CalculatorRegistry
    return CalculatorRegistry


@pytest.fixture(autouse=True)
def ensure_mock_registered():
    """
    自动注册 MockCalculator，避免重复注册冲突。
    使用 autouse=True 确保每个测试前都执行。
    """
    from masgent.calculators.registry import CalculatorRegistry
    from tests.mock_calculator import MockCalculator
    if not CalculatorRegistry._factories.get("mock"):
        CalculatorRegistry.register("mock", MockCalculator)
    yield


@pytest.fixture
def task_runner(task_store, calculator_registry):
    """TaskRunner 实例"""
    from masgent.tasks.task_runner import TaskRunner
    return TaskRunner(task_store, calculator_registry)


@pytest.fixture
def mock_calculator():
    """返回一个默认行为的 MockCalculator（默认 detect_status_return=COMPLETED）"""
    from tests.mock_calculator import MockCalculator
    return MockCalculator()


@pytest.fixture
def mock_calc(mock_calculator):
    """别名：保持向后兼容，供旧测试使用"""
    return mock_calculator


@pytest.fixture
def sample_task_record():
    """创建一个示例 TaskRecord（用于状态机测试）"""
    from masgent.models.task import TaskRecord
    from masgent.models.enums import WorkflowType, TaskStatus
    return TaskRecord(
        task_id="test_task_001",
        workflow_type=WorkflowType.SINGLE_POINT,
        status=TaskStatus.PENDING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir="/tmp/test_workdir",
        calculator_type="mock",
        calculator_params={},
        workflow_params={"fmax": 0.1},
        retry_count=0,
    )


def create_task_record(
    task_id: str,
    status: "TaskStatus",
    work_dir: str = "/tmp/test_workdir",
    calculator_type: str = "mock",
    calculator_params: dict = None,
    job_handle: dict = None,
    retry_count: int = 0,
) -> "TaskRecord":
    """便捷工厂函数，用于在测试中快速创建 TaskRecord"""
    from masgent.models.task import TaskRecord
    from masgent.models.enums import WorkflowType
    from datetime import datetime
    return TaskRecord(
        task_id=task_id,
        workflow_type=WorkflowType.SINGLE_POINT,
        status=status,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        work_dir=work_dir,
        calculator_type=calculator_type,
        calculator_params=calculator_params or {},
        workflow_params={},
        job_handle=job_handle,
        retry_count=retry_count,
    )


# ========== 为恢复测试准备的 BlockingCalculator 注册 ==========
@pytest.fixture(autouse=True)
def register_blocking_calculator():
    """注册 BlockingCalculator（用于恢复测试）"""
    from masgent.calculators.registry import CalculatorRegistry
    try:
        from tests.mock_calculator import BlockingCalculator
        if not CalculatorRegistry._factories.get("blocking"):
            CalculatorRegistry.register("blocking", BlockingCalculator)
    except ImportError:
        pass
    yield


# ========== 为 UNKNOWN 测试注册 UnknownCalculator（非自动） ==========
@pytest.fixture
def register_unknown_calculator():
    """
    注册 UnknownCalculator（用于 UNKNOWN 状态测试）
    注意：此 fixture 不是 autouse，测试需要显式注入才生效。
    """
    from masgent.calculators.registry import CalculatorRegistry
    try:
        from tests.mock_calculator import UnknownCalculator
        if not CalculatorRegistry._factories.get("unknown"):
            CalculatorRegistry.register("unknown", UnknownCalculator)
    except ImportError:
        pass
    yield


@pytest.fixture
def vasp_calc(tmp_path):
    """返回一个使用 fake_vasp 的 VaspCalculator 实例"""
    from masgent.calculators.vasp import VaspCalculator
    from masgent.executors.local import LocalExecutor
    from masgent.utils.workdir_manager import WorkDirManager
    fake_vasp = Path(__file__).parent.parent / "src/masgent/scripts/fake_vasp.sh"
    executor = LocalExecutor(aliases={"vasp_std": str(fake_vasp)})
    return VaspCalculator(
        executor=executor,
        workdir_manager=WorkDirManager(base_dir=tmp_path / "runs"),
        vasp_command="vasp_std",
    )


@pytest.fixture
def fake_slurm_factory():
    """注册 FakeSlurmExecutor 到 Factory（仅测试环境）"""
    from tests.mock_executors import FakeSlurmExecutor
    from masgent.executors import ExecutorFactory

    if "fake_slurm" not in ExecutorFactory.list_available():
        ExecutorFactory.register("fake_slurm", FakeSlurmExecutor)
    yield


@pytest.fixture(autouse=True)
def ensure_fake_slurm_registered():
    """确保 FakeSlurmExecutor 已注册到 ExecutorFactory（仅测试环境）"""
    from tests.mock_executors import FakeSlurmExecutor
    from masgent.executors.factory import ExecutorFactory
    if "fake_slurm" not in ExecutorFactory._registry:
        ExecutorFactory.register("fake_slurm", FakeSlurmExecutor)
    yield


@pytest.fixture
async def task_runner_with_cleanup(temp_task_dir, calculator_registry):
    """返回一个 TaskRunner 实例，测试结束后自动清理"""
    from masgent.tasks.task_runner import TaskRunner
    from masgent.tasks.task_store import JSONTaskStore

    store = JSONTaskStore(temp_task_dir / "tasks")
    runner = TaskRunner(store, calculator_registry)
    yield runner
    # 测试结束后清理
    await runner.shutdown()
    # 清理全局 FakeSlurm 状态
    from tests.mock_executors import FakeSlurmExecutor
    FakeSlurmExecutor.clear_jobs()