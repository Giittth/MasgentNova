"""Calculator 层数据模型：统一返回格式 + 状态 + 配置"""

from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum

from masgent.models.enums import TaskStatus, WorkflowType


class WorkflowStatus(str, Enum):
    """工作流状态——用于 TaskManager 跟踪 Workflow 执行"""
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ConfidenceLevel(str, Enum):
    """结果置信度标签（修复缺陷 3）"""
    EXACT = "exact"              # 直接来自参考数据库/自算
    INTERPOLATED = "interpolated" # 插值/外推
    MLP_ESTIMATED = "mlp_estimated" # MLP 估算
    DFT_CONVERGED = "dft_converged" # 已收敛的 DFT
    SIMULATED = "simulated"       # 教学模拟


@dataclass
class CalculationFingerprint:
    """计算指纹：保证可复现性（补充 13）"""
    calculator_type: str
    executor_type: str
    executable_hash: Optional[str] = None
    mlp_model_version: Optional[str] = None
    pseudopotential_set: Optional[str] = None
    xc_functional: Optional[str] = None
    gamma_centered: bool = True
    kppa: Optional[int] = None
    encut: Optional[int] = None
    random_seed: int = 42
    masgent_version: str = "0.3.0"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    git_commit: Optional[str] = None


@dataclass
class CalculationResult:
    """
    统一结果容器——所有 Calculator 返回这个格式
    
    不同 workflow 使用 data 字段存放特定数据:
    - SINGLE_POINT: {"energy": -10.2, "energy_per_atom": -1.275}
    - EOS: {"volumes": [...], "energies": [...], "equilibrium_volume": 100.0}
    - RELAX: {"structure": Structure, "energy": -10.2}
    """
    success: bool
    workflow_type: WorkflowType
    data: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    fingerprint: Optional[dict] = None
    error_message: Optional[str] = None

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


@dataclass
class TaskInfo:
    """任务信息——submit 返回"""
    task_id: str
    status: TaskStatus
    work_dir: str
    workflow_type: WorkflowType
    created_at: str = field(default_factory=lambda: __import__("datetime").datetime.now().isoformat())
    

@dataclass
class EOSResult:
    """EOS 工作流的专门返回结果"""
    equilibrium_volume: float
    bulk_modulus: float
    bulk_modulus_pressure_derivative: float
    volumes: np.ndarray
    energies: np.ndarray
    fit_parameters: tuple
    fit_function: str = "birch_murnaghan"


@dataclass
class HealthStatus:
    """计算后端健康状态（补充 19）"""
    healthy: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def ok(cls, details: Dict[str, Any] = None) -> "HealthStatus":
        return cls(healthy=True, message="OK", details=details or {})
    
    @classmethod
    def failed(cls, message: str, details: Dict[str, Any] = None) -> "HealthStatus":
        return cls(healthy=False, message=message, details=details or {})