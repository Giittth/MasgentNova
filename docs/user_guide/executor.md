# Executor 执行器

## 支持的后端

| 执行器 | 标识 | 适用场景 |
|---|---|---|
| LocalExecutor | `local` | 本地开发 / 单机 |
| SlurmExecutor | `slurm` | HPC 集群 |
| SSHExecutor | `ssh`（规划中） | 远程服务器 |

## 创建执行器

### 方式一：直接实例化

from masgent.executors import SlurmExecutor

executor = SlurmExecutor(
    partition="cpu",
    ntasks=32,
    walltime="24:00:00",
    jobname="masgent_job",
    modules=["vasp/6.4.2"],
)
方式二：通过工厂
from masgent.executors import ExecutorFactory

executor = ExecutorFactory.create("slurm", partition="cpu", ntasks=32)
JobHandle
每个 spawn() 返回一个 JobHandle，包含：

job_id: 全局唯一标识

backend: 后端类型

pid: 本地进程 PID（本地）

scheduler_id: 调度器作业号（Slurm）

metadata: 额外信息（partition、nodes等）

配置 Slurm
executor = SlurmExecutor(
    partition="gpu",
    account="project_123",
    qos="high",
    nodes=2,
    ntasks=64,
    cpus_per_task=2,
    walltime="48:00:00",
    jobname="my_job",
    modules=["vasp/6.4.2", "intel/2023.0"],
    extra_sbatch_args={"gres": "gpu:4", "mem": "128G"},
)