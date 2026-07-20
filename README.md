# Masgent

**Materials Simulation Agent** -- An AI-powered, crash-safe framework that unifies DFT calculations, machine learning potentials, and ML model training under a single architecture. Interact through natural language (AI Agent) or structured menus (CLI).

[![arXiv](https://img.shields.io/badge/DOI-10.48550/arXiv.2512.23010-blue)](https://arxiv.org/abs/2512.23010)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [AI Agent Mode](#ai-agent-mode)
5. [CLI Mode](#cli-mode)
6. [Project Structure](#project-structure)
7. [Core Components](#core-components)
8. [Configuration](#configuration)
9. [Development](#development)
10. [Testing](#testing)
11. [Citation](#citation)
12. [License](#license)

---

## Features

### DFT Simulation

- **Structure generation** from Materials Project (POSCAR, CIF) and chemical formula
- **Structure manipulation**: supercells, defects (vacancy/substitution/interstitial), surface slabs, interfaces, SQS
- **VASP input preparation** (INCAR, KPOINTS, POTCAR, POSCAR) using pymatgen standard input sets
- **HPC submission scripts** (Slurm sbatch generation)
- **Standard workflows**: convergence tests, equation of state (EOS), elastic constants, AIMD, NEB
- **Built-in analysis** for all workflow results

### Machine Learning Potentials

- Single-point energy, geometry relaxation, and molecular dynamics
- Backends: [SevenNet](https://github.com/MDIL-SNU/SevenNet), [CHGNet](https://github.com/CederGroupHub/chgnet), [Orb-v3 (ORB)](https://github.com/orbital-materials/orb-models), [MatterSim (MatSim)](https://github.com/microsoft/mattersim) via ASE interface

### ML Utilities

- Composition- and structure-based feature analysis with dimensionality reduction (PCA, t-SNE)
- VAE-based data augmentation for small datasets
- Hyperparameter optimization with [Optuna](https://optuna.org/)
- Neural network training and retraining (PyTorch)
- Pre-trained models for Al-Mg-Si-Sc and Al-Co-Cr-Fe-Ni (UTS, yield strength, elongation) alloy systems

### Reliability

- Process-level crash recovery with file locks and in-process threading locks
- Structured error taxonomy (transient, permanent, infrastructure)
- Configurable retry policy with max retry limits and recovery event audit trail
- Graceful shutdown with signal handling (SIGTERM/SIGINT)

---

## Architecture

Masgent is a five-layer asynchronous framework designed for crash-safe materials simulation.

```
                    User Interface
    AI Agent (natural language)    |    CLI (menus)

                   Tool Layer (60+ tools)
  structure | vasp | mlp | ml  | workflow | core

                Workflow Scheduler Layer
  DAG graph | checkpoint | resume | status

              Task Engine Layer
  TaskRunner | TaskStore | Recovery | Retry | Lock

         Calculator Layer (stateless, async)
   VASP | MLP (CHGNet/SevenNet/ORB/MatterSim) | Mock

         Executor Layer (cross-platform)
   LocalExecutor | SlurmExecutor | WSLExecutor
```

### Design Principles

| Principle | Implementation |
|---|---|
| Crash safety | File locks (fcntl.flock) + recovery lock for multi-process protection |
| Stateless calculators | Calculator methods take only work_dir and JobHandle, no task_id |
| Persistent task store | Each task is a JSON file; fingerprint index for cache queries |
| Deterministic work dirs | Path derived from structure hash + workflow type |
| Graceful degradation | UNKNOWN state probe + configurable retry policy + timeout |

### Task State Machine

```
                PENDING
                   | submit
                   v
                RUNNING <---- UNKNOWN (poll recover)
                 |      |
                 v      v
              FAILED  CANCELLED ---> (terminal)
                 |
                 v
              UNKNOWN -- restart_poll or restart_execute
              retry_count < max_retries ---|
              retry_count >= max_retries -> FAILED (terminal)

             COMPLETED (terminal)
```

### Data Flow

**Normal submission path:** User -> TaskRunner.submit() -> Calculator.prepare() -> Calculator.launch() -> poll -> Calculator.collect() -> TaskStore

**Recovery path:** Application.start() -> TaskRunner.recover() -> RecoveryManager._recover_single() -> Calculator.detect_status() -> restart_poll or restart_execute

---

## Quick Start

### Requirements

- Python >= 3.11, < 3.15
- At least one LLM API key (OpenAI, Anthropic, Google, etc.)

### PyPI install

```
pip install masgent
masgent
```

### Manual install

```
git clone https://github.com/syndra/masgent.git
cd masgent
python3 -m venv .venv
source .venv/bin/activate    (Windows: .venv\Scripts\activate)
pip install -e .
cp .env.example .env          (configure API keys)
masgent
```

### One-liner (Linux/WSL)

```
bash <(curl -s https://raw.githubusercontent.com/syndra/masgent/main/scripts/setup.sh)
```

### Quick example

```python
import asyncio
from masgent.calculators.mlp import MLPCalculator
from masgent.calculators.cached import CachedCalculator
from masgent.tasks.task_store import JSONTaskStore
from pathlib import Path, Lattice, Structure

calc = MLPCalculator(backend="chgnet", device="cpu")
store = JSONTaskStore(Path("./tasks"))
cached = CachedCalculator(calc, store)

async def run():
    si = Structure(Lattice.cubic(5.43), ["Si", "Si"],
                   [[0,0,0], [0.25,0.25,0.25]])
    result = await cached.compute_energy(si)
    print(f"Energy: {result.data['energy']:.4f} eV")

asyncio.run(run())
```

---

## AI Agent Mode

Start the interactive AI agent from the main menu by typing `AI`, or run directly:

```
masgent     (then select AI)
```

### Supported LLM Providers

| Provider | Menu Selection | API Key Required | Notes |
|---|---|---|---|
| Masgent AI | Masgent | No | Managed inference; cold start may be slow |
| OpenAI | OpenAI | OPENAI_API_KEY | GPT-5 Nano |
| Anthropic | Anthropic | ANTHROPIC_API_KEY | Claude Sonnet 4.5 |
| Google | Google | GOOGLE_API_KEY | Gemini 2.5 Flash |
| xAI | xAI | GROK_API_KEY | Grok 4.1 Fast |
| DeepSeek | Deepseek | DEEPSEEK_API_KEY | DeepSeek Chat |
| Alibaba | Alibaba | DASHSCOPE_API_KEY | Qwen Flash |

### 60+ Tools Available

- Structure generation, format conversion, defect creation
- VASP input preparation and HPC script generation
- Standard workflow orchestration (convergence, EOS, elastic, AIMD, NEB)
- MLP simulation (single-point, relax, molecular dynamics)
- ML feature analysis, dimensionality reduction, data augmentation
- Neural network design, training, retraining, and prediction

### Prompt Assembly

The AI Agent uses a modular prompt assembly system that adapts to the user's intent:

- **Base prompt** (`system_prompt.txt`): core system instructions
- **Domain modules** (P0): crystallography, DFT/VASP, elastic properties, ML potentials, pymatgen
- **Orchestration modules** (P0-P2): workflow recipes, tool chaining, batch mode
- **Execution modules** (P0-P1): execution protocol, error recovery, parameter validation
- **Output modules** (P1-P2): result formatting, follow-up suggestions, comparison
- **Dynamic modules** (P1-P2): session context injection, model capability profiles, few-shot examples

Prompt depth is tiered by model capability (`strong`/`medium`/`light`) to optimize token usage.

---

## CLI Mode

Three main modules accessible from the main menu:

**Module 1: Density Functional Theory (DFT) Simulations**
- 1.1 Structure Preparation & Manipulation (POSCAR generation, defects, supercells, SQS, surfaces, interfaces, visualization)
- 1.2 VASP Input File Preparation (full inputs, INCAR templates, KPOINTS, HPC scripts)
- 1.3 Standard VASP Workflows (convergence testing, EOS, elastic constants, AIMD, NEB)
- 1.4 VASP Output Analysis (analysis for all workflows above)

**Module 2: Fast Simulations Using Machine Learning Potentials (MLPs)**
- 2.1 SevenNet
- 2.2 CHGNet
- 2.3 Orb-v3
- 2.4 MatterSim

**Module 3: Simple Machine Learning for Materials Science**
- 3.1 Dataset Preparation & Feature Analysis (feature analysis, dimensionality reduction, data augmentation)
- 3.2 Model Design & Hyperparameter Tuning
- 3.3 Model Training & Evaluation
- 3.4 Model Retraining
- 3.5 Pre-trained Model Applications (Al-Mg-Si-Sc and Al-Co-Cr-Fe-Ni)

Global commands: `AI`, `New`, `Back`, `Main`, `Help`, `Exit`

---

## Project Structure

```
masgent/
  src/masgent/
    app.py                Application lifecycle, recovery, signal handling
    cli.py                CLI entry point
    _config.py            Pydantic-settings config (MasgentSettings)

    ai_mode/              AI Agent backend
      ai_backend.py       Interactive AI loop, provider selection
      provider_factory.py LLM provider creation
      memory_manager.py   Conversation memory
      system_prompt.txt   Base system prompt
      prompts/            Modular prompt assembly system
        assembler.py      PromptAssembler: tiered, intent-driven assembly
        registry.py       PromptModule registry (26 modules, 3 tiers)
        tool_docs.md      Documentation tool instructions
        domain/           Domain knowledge modules
        dynamic/          Dynamic content (session context, model profiles, few-shot)
        execution/        Execution protocol and error recovery
        orchestration/    Workflow recipes and tool chaining
        output/           Result formatting and follow-up suggestions

    cli_mode/             CLI menu system
      cli_entries.py      Menu hierarchy (commands 0 to 3.5)
      cli_run.py          Command registration and dispatch
      base.py             bullet_menu() helper
      dft.py              DFT subcommands
      mlp.py              MLP subcommands
      ml.py               ML subcommands

    calculators/          Stateless scientific computation layer
      base.py             Calculator ABC
      vasp.py             VASP calculator (MP input sets, OUTCAR parsing)
      mlp.py              MLP calculator (CHGNet/SevenNet/ORB/MatterSim)
      mock.py             Mock calculator for testing
      cached.py           CachedCalculator (fingerprint-based caching)
      helpers.py          run_blocking(), to_ase(), to_pmg()
      registry.py         CalculatorRegistry (stable type identifiers)

    executors/            Cross-platform execution layer
      base.py             Executor ABC
      local.py            Local process execution with log persistence
      slurm.py            Slurm HPC (sbatch/squeue/scancel/sacct)
      wsl.py              WSL execution
      factory.py          ExecutorFactory (create from config dict)

    models/               Data models
      task.py             TaskRecord (Monty serialization for pymatgen objects)
      calculator.py       CalculationResult, CalculationFingerprint
      enums.py            TaskStatus, WorkflowType, UnknownStrategy
      job.py              JobHandle
      cancel.py           CancelInfo, CancelSource
      executor.py         CommandResult
      error_codes.py      RecoveryError taxonomy
      events.py           RecoveryEvent audit trail
      schemas.py          Input validation schemas

    tasks/                Task engine layer
      task_runner.py      TaskRunner: submit, execute, poll, cancel, shutdown
      task_store.py       JSONTaskStore with fingerprint index
      task_state.py       TaskStateManager: status transitions
      recovery.py         classify_unknown_task() helper
      recovery_manager.py RecoveryManager: lock, retry, timeout
      recovery_lock.py    In-process threading lock
      file_lock.py        Cross-process fcntl.flock with stale detection
      retry.py            RetryPolicy

    tools/                AI Agent tools (60+)
      core.py             File operations, documentation reader
      structure.py        Structure generation and manipulation
      vasp.py             VASP input preparation and workflows
      mlp.py              MLP simulation tools
      ml.py               ML feature analysis and model tools
      workflow.py         Workflow orchestration tools

    workflows/            DAG workflow scheduling
      base.py             Workflow ABC
      node.py             WorkflowNode with status machine
      graph.py            WorkflowGraph: DAG, topology, resume
      scheduler.py        WorkflowScheduler: concurrent DAG execution
      eos.py              EOSWorkflow (Birch-Murnaghan fitting)
      builder.py          Workflow builder
      checkpoint.py       WorkflowCheckpointManager
      handle.py           WorkflowHandle
      status.py           WorkflowStatus enum

    ml/                   Machine learning utilities
      ml_nn_design.py     Neural network architecture design
      ml_nn_train.py      Training loop with early stopping
      ml_cvae.py          Conditional VAE for data augmentation

    res/                  Pre-trained model files (.pkl)
    utils/                Shared utilities (logger, session, fingerprint, etc.)

  tests/                  Test suites (unit, integration, calculators, etc.)
  docs/                   Documentation
  examples/               Example scripts
  scripts/                Setup scripts
  pyproject.toml          Project metadata and dependencies
  .env.example            Configuration template
  LICENSE                 MIT License
```

---

## Core Components

### Calculator Layer

| Method | Responsibility | Example (VASP) |
|---|---|---|
| `prepare()` | Create input files, return work_dir | Writes INCAR, KPOINTS, POTCAR, POSCAR |
| `launch()` | Submit computation, return JobHandle | Runs vasp_std via executor |
| `detect_status()` | Check running/completed/failed | Parses OUTCAR, checks process |
| `collect()` | Parse output, return CalculationResult | Reads vasprun.xml energy |
| `cancel()` | Kill running job | `executor.kill(job_id)` |
| `get_init_params()` | Serializable config for recovery | `{vasp_command, nprocs, incar_template}` |

### Executor Layer

| Method | LocalExecutor | SlurmExecutor |
|---|---|---|
| `spawn()` | subprocess.Popen + log files | sbatch job.sbatch + parse job ID |
| `is_running()` | proc.poll() is None | squeue -j id |
| `wait()` | proc.wait(timeout) | poll squeue then sacct |
| `kill()` | psutil process tree kill | scancel id |
| `run()` | subprocess.run | sbatch --wait |

### Task Engine Layer

| Component | Responsibility |
|---|---|
| TaskRunner | Submit, execute, poll, cancel, graceful shutdown |
| TaskStore | Persistent JSON storage with fingerprint index |
| TaskStateManager | Status transitions with validation and timestamps |
| RecoveryManager | Lock acquisition, retry policy, timeout, event audit |
| FileLock | Cross-process fcntl.flock with stale detection |
| RecoveryLock | In-process threading lock for multi-runner safety |
| RetryPolicy | Max retries (default 3) for UNKNOWN tasks |

### Workflow Layer

| Component | Responsibility |
|---|---|
| WorkflowGraph | DAG management, topology sort, resume-only-PENDING |
| WorkflowNode | Single task node with status machine |
| WorkflowScheduler | Concurrent DAG execution with checkpointing |
| WorkflowCheckpointManager | Persist/recover graph + nodes from JSON |
| EOSWorkflow | EOS fitting (Birch-Murnaghan) across scaled volumes |

---

## Configuration

Copy `.env.example` to `.env` and configure:

```env
# ===== API Keys (at least one LLM key required) =====
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
GROK_API_KEY=...
DEEPSEEK_API_KEY=...
DASHSCOPE_API_KEY=sk-...

# ===== Materials Project (for structure generation) =====
MP_API_KEY=...

# ===== VASP Pseudopotentials =====
POTCAR_DIR=/path/to/potcars

# ===== Remote HPC (for SlurmExecutor via SSH) =====
REMOTE_HOST=hpc.example.com
REMOTE_USER=username
REMOTE_KEY=/path/to/ssh_key
```

Configuration is managed by `MasgentSettings` (pydantic-settings), which reads from `.env` at project root. The `runs_dir` defaults to `$HOME/masgent_runs` unless set via the `MASGENT_SESSION_RUNS_DIR` environment variable.

---

## Development

### Adding a Calculator

1. Create a new file in `src/masgent/calculators/` subclassing `Calculator`:

```python
from masgent.calculators.base import Calculator
from masgent.models.enums import WorkflowType, TaskStatus

class MyCalculator(Calculator):
    TYPE = "my_calc"  # stable identifier for recovery

    async def prepare(self, structure, workflow_type, **kwargs): ...
    async def launch(self, work_dir): ...
    async def detect_status(self, work_dir, job=None): ...
    async def collect(self, work_dir, workflow_type): ...
    async def cancel(self, job): ...
    def get_init_params(self): return {...}
```

2. Register: `CalculatorRegistry.register("my_calc", MyCalculator)`
3. If needed, implement a `Workflow` subclass in `src/masgent/workflows/`.

### Adding an Executor

1. Create a new file in `src/masgent/executors/` subclassing `Executor`.
2. Register: `ExecutorFactory.register("my_backend", MyExecutor)`
3. Implement: `spawn`, `is_running`, `wait`, `kill`, `run`, `get_config`, `validate`

### Dependency Groups

| Group | Command | Purpose |
|---|---|---|
| core | `pip install masgent` | Runtime dependencies |
| dev | `pip install -e ".[dev]"` | Build and packaging tools |
| test | `pip install -e ".[test]"` | Testing framework |

---

## Testing

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run with coverage
pytest --cov=src/masgent

# Run specific test file
pytest tests/tasks/test_task_runner.py -v --tb=long
```

Test configuration is in `pyproject.toml`:
- `asyncio_mode = "auto"` (async tests work out of the box)
- `testpaths = ["tests"]`
- Patterns: `test_*.py`, `Test*` classes, `test_*` functions

### Test Infrastructure

- `tests/mock_calculator.py`: MockCalculator with configurable behavior
- `tests/mock_executors.py`: MockExecutor for testing without real execution
- `tests/conftest.py`: Shared fixtures (task_store, calculator_registry, etc.)

---

## Citation

If you use Masgent in your research:

```bibtex
@software{liu2024masgent,
  author = {Liu, Guangchen and syndra},
  title = {Masgent: Materials Simulation Agent},
  year = {2024},
  doi = {10.48550/arXiv.2512.23010},
  url = {https://github.com/syndra/masgent}
}
```

Additional DOI: [10.48550/arXiv.2512.23010](https://arxiv.org/abs/2512.23010)

---

## License

MIT License. See [LICENSE](LICENSE) for details.

### Acknowledgements

- Original DFT/ML structure inspired by [ASE](https://wiki.fysik.dtu.dk/ase/) and [pymatgen](https://pymatgen.org/) communities.
- MLP backends: CHGNet (Ceder Group), SevenNet (MDIL-SNU), Orb (Orbital Materials), MatterSim (Microsoft Research).
- Pre-trained models trained on Materials Project and literature data.
