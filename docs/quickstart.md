# 快速开始

#1. 运行第一个 VASP 单点计算（本地）

from masgent.calculators.vasp import VaspCalculator
from masgent.executors import LocalExecutor
from masgent.tasks import TaskRunner, JSONTaskStore
from masgent.calculators import CalculatorRegistry
from pymatgen.core import Structure, Lattice

executor = LocalExecutor()
calc = VaspCalculator(executor=executor)
store = JSONTaskStore("./tasks")
registry = CalculatorRegistry()
runner = TaskRunner(store, registry)

structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])
info = await runner.submit(calc, structure, WorkflowType.SINGLE_POINT)

# 轮询直到完成
import asyncio
while True:
    status = await runner.poll(info.task_id)
    if status.is_terminal:
        break
    await asyncio.sleep(5)

result = await runner.collect(info.task_id)
print(f"Energy: {result['data']['energy']:.4f} eV")

2. 运行工作流（relax → static → dos）
from masgent.workflows import WorkflowBuilder, WorkflowScheduler

workflow = (WorkflowBuilder("Si_band")
    .set_calculator(calc)
    .relax(structure, fmax=0.05, steps=100)
    .static()
    .dos(nedos=5000)
    .build()
)

scheduler = WorkflowScheduler(runner)
results = await scheduler.run(workflow, structure)

3. 提交到 Slurm 集群
from masgent.executors import SlurmExecutor

executor = SlurmExecutor(
    partition="cpu",
    ntasks=32,
    walltime="24:00:00",
    modules=["vasp/6.4.2"],
)
calc = VaspCalculator(executor=executor, vasp_command="srun vasp_std")

# 其余代码与本地相同