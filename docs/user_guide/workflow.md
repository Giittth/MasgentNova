# Workflow DAG 工作流

## 构建工作流

from masgent.workflows import WorkflowBuilder

workflow = (WorkflowBuilder("my_workflow")
    .set_calculator(calc)
    .relax(structure, fmax=0.05)
    .static()
    .dos(nedos=5000)
    .build()
)
并行 DAG
workflow = (WorkflowBuilder("parallel")
    .set_calculator(calc)
    .add("relax", WorkflowType.RELAX)
    .add("static", WorkflowType.SINGLE_POINT, depends_on=["relax"])
    .add("dos", WorkflowType.DOS, depends_on=["static"])
    .add("band", WorkflowType.BAND_STRUCTURE, depends_on=["static"])
    .build()
)
执行工作流
scheduler = WorkflowScheduler(runner)
results = await scheduler.run(workflow, structure)
检查点恢复
from masgent.workflows import WorkflowCheckpointManager

checkpoint_manager = WorkflowCheckpointManager("./checkpoints")
scheduler = WorkflowScheduler(runner, checkpoint_manager=checkpoint_manager)

# 自动保存检查点

# 崩溃后恢复
scheduler2 = WorkflowScheduler(runner, checkpoint_manager=checkpoint_manager)
await scheduler2.resume(graph_id, calculators={"vasp": calc})