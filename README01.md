1. README.md（项目根目录）
# Masgent — Materials Simulation Agent

**Masgent** 是一个面向材料科学计算的自动化任务编排框架，支持：
- 多步骤工作流（DAG）调度
- 任务持久化与崩溃恢复
- 本地 / Slurm / 远程执行后端
- 可扩展的 Calculator（VASP、QE、LAMMPS...）

## 快速开始

pip install masgent
from masgent.calculators.vasp import VaspCalculator
from masgent.executors import LocalExecutor
from masgent.tasks import TaskRunner, JSONTaskStore
from masgent.calculators import CalculatorRegistry
from masgent.models.enums import WorkflowType
from pymatgen.core import Structure, Lattice

# 1. 准备组件
executor = LocalExecutor()
calc = VaspCalculator(executor=executor)
store = JSONTaskStore("./tasks")
registry = CalculatorRegistry()
runner = TaskRunner(store, registry)

# 2. 提交任务
structure = Structure(Lattice.cubic(5.43), ["Si"], [[0.0, 0.0, 0.0]])
info = await runner.submit(calc, structure, WorkflowType.RELAX)

# 3. 等待结果
status = await runner.poll(info.task_id)
result = await runner.collect(info.task_id)

核心特性
任务生命周期管理（submit/poll/collect/cancel/recover）
DAG 工作流编排（relax → static → dos → band）
崩溃恢复（进程退出后自动恢复）
多后端执行（Local / Slurm / SSH）
可配置重试策略（RetryPolicy）
科学对象持久化（Structure / Dos / BandStructure）

文档
用户指南

API 参考

开发指南

许可证
MIT