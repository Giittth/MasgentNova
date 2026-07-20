"""数据模型层：共享枚举、Pydantic 校验模式、错误协议、事件模型、任务记录"""

# 枚举
from .enums import (
    TaskStatus,
    WorkflowType,
    UnknownStrategy,
)

# 错误协议
from .error_codes import (
    ErrorCode,
    ErrorCategory,
    ErrorSource,
    RecoveryError,
)

# 事件模型
from .events import RecoveryEvent

# 任务模型
from .task import (
    TaskRecord,
    TaskInfo,
    _serialize_result,
    _deserialize_result,
    VALID_TRANSITIONS,
)

# Calculator 层模型
from .calculator import (
    CalculationResult,
    CalculationFingerprint,
    TaskInfo as CalculatorTaskInfo,
    EOSResult,
    HealthStatus,
    WorkflowStatus,
    ConfidenceLevel,
)

# Executor 层模型
from .executor import CommandResult

# cancel 模型
from .cancel import CancelSource, CancelInfo

# Job 模型
from .job import JobHandle

# Schemas（Pydantic 校验）
from .schemas import (
    ToolMetadata,
    CheckPklFile,
    CheckLogFile,
    CheckCSVFile,
    CheckPoscar,
    CheckElement,
    CheckElementExistence,
    GenerateVaspPoscarSchema,
    ConvertStructureFormatSchema,
    ConvertPoscarCoordinatesSchema,
    GenerateVaspInputsFromPoscar,
    GenerateVaspInputsHpcSlurmScript,
    CustomizeVaspKpointsWithAccuracy,
    GenerateVaspPoscarWithVacancyDefects,
    GenerateVaspPoscarWithSubstitutionDefects,
    GenerateVaspPoscarWithInterstitialDefects,
    GenerateSupercellFromPoscar,
    GenerateSqsFromPoscar,
    GenerateSurfaceSlabFromPoscar,
    GenerateInterfaceFromPoscars,
    GenerateVaspWorkflowOfConvergenceTests,
    GenerateVaspWorkflowOfEos,
    GenerateVaspWorkflowOfElasticConstants,
    GenerateVaspWorkflowOfAimd,
    GenerateVaspWorkflowOfNeb,
    RunSimulationUsingMlps,
    AnalyzeFeaturesForMachineLearning,
    ReduceDimensionsForMachineLearning,
    AugmentDataForMachineLearning,
    DesignModelForMachineLearning,
    TrainModelForMachineLearning,
    ModelPredictionForAlMgSiSc,
    ModelPredictionForAlCoCrFeNi,
)


# 版本信息
__version__ = "0.6.6-dev"


# 模块导出
__all__ = [
    # 枚举
    "TaskStatus",
    "WorkflowType",
    "UnknownStrategy",
    # 错误协议
    "ErrorCode",
    "ErrorCategory",
    "ErrorSource",
    "RecoveryError",
    # 事件模型
    "RecoveryEvent",
    # 任务模型
    "TaskRecord",
    "TaskInfo",
    "_serialize_result",
    "_deserialize_result",
    "VALID_TRANSITIONS",
    # Calculator 模型
    "CalculationResult",
    "CalculationFingerprint",
    "CalculatorTaskInfo",
    "EOSResult",
    "HealthStatus",
    "WorkflowStatus",
    "ConfidenceLevel",
    # Executor 模型
    "CommandResult",
    # Job 模型
    "JobHandle",
    # Schemas（Pydantic）
    "ToolMetadata",
    "CheckPklFile",
    "CheckLogFile",
    "CheckCSVFile",
    "CheckPoscar",
    "CheckElement",
    "CheckElementExistence",
    "GenerateVaspPoscarSchema",
    "ConvertStructureFormatSchema",
    "ConvertPoscarCoordinatesSchema",
    "GenerateVaspInputsFromPoscar",
    "GenerateVaspInputsHpcSlurmScript",
    "CustomizeVaspKpointsWithAccuracy",
    "GenerateVaspPoscarWithVacancyDefects",
    "GenerateVaspPoscarWithSubstitutionDefects",
    "GenerateVaspPoscarWithInterstitialDefects",
    "GenerateSupercellFromPoscar",
    "GenerateSqsFromPoscar",
    "GenerateSurfaceSlabFromPoscar",
    "GenerateInterfaceFromPoscars",
    "GenerateVaspWorkflowOfConvergenceTests",
    "GenerateVaspWorkflowOfEos",
    "GenerateVaspWorkflowOfElasticConstants",
    "GenerateVaspWorkflowOfAimd",
    "GenerateVaspWorkflowOfNeb",
    "RunSimulationUsingMlps",
    "AnalyzeFeaturesForMachineLearning",
    "ReduceDimensionsForMachineLearning",
    "AugmentDataForMachineLearning",
    "DesignModelForMachineLearning",
    "TrainModelForMachineLearning",
    "ModelPredictionForAlMgSiSc",
    "ModelPredictionForAlCoCrFeNi",
]