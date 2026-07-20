# MasgentNova

**Materials Simulation Agent** -- An AI-powered, crash-safe orchestration framework for computational materials science. Masgent unifies DFT calculations, machine learning potentials, and custom simulation workflows under a single, extensible architecture with natural language interaction.

[![DOI](https://img.shields.io/badge/DOI-10.1039/D6DD00043F-blue)](https://doi.org/10.1039/D6DD00043F)
[![arXiv](https://img.shields.io/badge/DOI-10.48550/arXiv.2512.23010-blue)](https://doi.org/10.48550/arXiv.2512.23010)
[![Zenodo](https://img.shields.io/badge/DOI-10.5281/zenodo.19456831-blue)](https://doi.org/10.5281/zenodo.19456831)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Overview

Masgent is a three-tier asynchronous framework for running materials simulations at scale. You can interact with it through a natural-language AI agent or a structured CLI. The core engine provides process-level crash recovery, persistent task storage, configurable retry policies, and DAG-based workflow scheduling.

**At a glance:**

- Talk to your simulation stack in natural language
- Multi-LLM support -- OpenAI, Anthropic, Google, DeepSeek, xAI, Alibaba
- Crash-safe task engine with process-level recovery
- DAG workflow scheduling (relax, static, DOS, band)
- Cross-platform execution -- Local, Slurm, WSL
- 60+ tools covering DFT, MLP, ML training, analysis
- Pre-trained ML models for Al-Mg-Si-Sc and Al-Co-Cr-Fe-Ni


---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [AI Agent Mode](#ai-agent-mode)
- [CLI Mode](#cli-mode)
- [Project Structure](#project-structure)
- [Core Components](#core-components)
- [Configuration](#configuration)
- [Development](#development)
- [Testing](#testing)
- [Citation](#citation)
- [License](#license)

---

## Features

### DFT Simulation
- Structure generation from Materials Project database (POSCAR, CIF) and chemical formula
- Structure modification: supercells, defects (vacancy/substitution/interstitial), surface slabs, interfaces, SQS
- VASP input generation (INCAR, KPOINTS, POTCAR, POSCAR) with all standard input sets
- HPC submission script generation (Slurm)
- Standard workflows: Convergence Test, EOS, Elastic Constants, AIMD, NEB
- Built-in analysis for all workflow results

### Machine Learning Potentials
- Single-point energy calculations, geometry relaxation, and molecular dynamics
- Backends: SevenNet, CHGNet, Orb-v3 (ORB), MatterSim (MatSim) via ASE interface
- Asynchronous wrapper for synchronous MLP codes

### ML Utilities
- Composition and structure-based feature analysis
- Dimensionality reduction (PCA, t-SNE)
- Data augmentation via Variational Autoencoders (VAE) for small datasets
- Hyperparameter optimization with Optuna
- Neural network training and retraining (PyTorch)
- Pre-trained models for Al-Mg-Si-Sc and Al-Co-Cr-Fe-Ni (UTS, yield strength, elongation)

### Reliability
- Process-level crash recovery with file-based locks (fcntl)
- In-process recovery locks (threading) for multi-runner safety
- Structured error taxonomy (transient, permanent, infrastructure)
- Configurable retry policy with max retry limits
- Recovery event audit trail

---

## Architecture

Masgent follows a strict layered architecture:

```
User / Client (AI Agent / CLI)
        |
        v
   Workflow Layer        (WorkflowBuilder DSL, WorkflowScheduler, DAG)
        |
        v
   Execution Layer       (TaskRunner, RecoveryManager, TaskStateManager)
        |
        v
   Calculator Layer      (VaspCalculator, MLPCalculator, Mock, Cached)
        |
        v
   Executor Layer        (Local, Slurm, WSL, Custom)
        |
        v
   HPC / Local Backend
```

### Core Design Principles

| Principle | Description |
|-----------|-------------|
| Three-layer separation | Execution, Recovery, State layers are fully independent |
| Single state source | All task state changes go through TaskStateManager |
| Lock lifecycle binding | FileLock lifetime matches TaskRunner lifetime |
| Crash safe | Kernel auto-releases locks on crash; tasks recoverable |
| Process safe | FileLock prevents multi-process duplicate recovery |
| Structured audit | RecoveryEvent uses typed error codes |

### Task State Machine

```
PENDING  --->  RUNNING  --->  COMPLETED
  |               |              |
  |               +--->  FAILED  |
  |               |              |
  |               +--->  CANCELLED
  |               |
  |               +--->  UNKNOWN  --->  RUNNING / PENDING / COMPLETED / FAILED
  |
  +--->  FAILED / CANCELLED / UNKNOWN / COMPLETED
```

UNKNOWN resolution strategies: AUTO (probe then decide), POLL (force re-poll), EXECUTE (force re-execute).

---

## Quick Start

**Requirements:** Python >= 3.11, < 3.15

```bash
pip install masgent
masgent
```

Then type your request in natural language:

```
Generate a POSCAR file for NaCl.
Prepare VASP input files for a graphene structure.
Run an EOS calculation for this structure.
Predict mechanical properties of Al-Mg-Si-Sc with 0.8 wt.% Mg, 0.6 wt.% Si.
```

### Two Modes

- **AI Agent Mode** (masgent): Natural language interface with multi-LLM support, prompt assembly, and tool orchestration
- **CLI Mode** (masgent --cli): Structured command-line interface for DFT, ML, and MLP operations

---

## AI Agent Mode

The AI agent (src/masgent/ai_mode/) provides a conversational interface to all Masgent capabilities.

### Multi-LLM Support

| Provider | Models | API Key Required |
|----------|--------|------------------|
| Masgent (built-in) | Pydantic AI models | No |
| OpenAI | GPT-5, GPT-4o, etc. | Yes (openai_api_key) |
| Anthropic | Claude Sonnet, Opus | Yes (anthropic_api_key) |
| Google | Gemini 2.5 Flash, Pro | Yes (google_api_key) |
| xAI | Grok | Yes (grok_api_key) |
| DeepSeek | DeepSeek Chat | Yes (deepseek_api_key) |
| Alibaba | Qwen Flash | Yes (dashscope_api_key) |

### Prompt Assembly

The agent uses a modular prompt assembly framework (src/masgent/ai_mode/prompts/):

- **Domain prompts**: Crystallography, defects, DFT/VASP, elastic properties, Materials Project, ML potentials, pymatgen/ASE, surface/interface
- **Dynamic context**: Model profiles, session state (current files, runs directory, recent tools)
- **Few-shot examples**: Convergence test, elastic constants, ML prediction
- **Execution protocols**: Error recovery, parameter validation, Plan -> Execute -> Analyze
- **Orchestration recipes**: Batch mode, tool chaining, tool selection, workflow recipes
- **Output formatting**: Comparison tables, next-step suggestions, result formatting standards

### Tool Inventory (60+ Tools)

Structure generation, VASP input/output, workflow orchestration, ML potentials, ML model training/retraining/prediction, analysis, and visualization.

---

## CLI Mode

```bash
masgent --cli
```

| Command | Subcommands |
|---------|-------------|
| masgent dft | poscar, inputs, relax, eos, elastic, aimd, neb, convergence |
| masgent ml | features, reduce, augment, design, train, predict |
| masgent mlp | single-point, relax, eos, elastic, md |

---

## Project Structure

```
src/masgent/
  app.py                    Application lifecycle (start, shutdown, signals)
  cli.py                    CLI entry point
  _config.py                Global settings (API keys, paths, HPC)

  ai_mode/                  AI Agent backend
    ai_backend.py              Agent orchestration, tool execution loop
    memory_manager.py          Layered conversation memory
    provider_factory.py        Multi-LLM provider factory
    system_prompt.txt          Base agent system prompt
    prompts/                   Prompt Assembly framework
      assembler.py               Dynamic prompt composition
      registry.py                 PromptModule metadata and routing
      domain/                     Domain knowledge (crystallography, DFT, defects, elastic, etc.)
      dynamic/                    Dynamic context (model profiles, session state, few-shot examples)
      execution/                  Execution protocols (error recovery, parameter validation)
      orchestration/              Orchestration recipes (batch mode, tool chaining, workflow recipes)
      output/                     Output formatting (comparison, next-steps, formatting)

  calculators/               Scientific computation layer
    base.py                    Abstract Calculator
    vasp.py                    VASP calculator
    mlp.py                     ML potential calculator
    cached.py                  TaskStore-based caching decorator
    mock.py                    Mock calculator for testing
    registry.py                Factory-based dynamic creation
    helpers.py                 Shared async utilities

  cli_mode/                  CLI implementation
    cli_entries.py, cli_run.py, dft.py, ml.py, mlp.py

  executors/                 Process/job execution layer
    base.py                    Abstract Executor
    local.py                   Local subprocess executor
    slurm.py                   Slurm HPC executor
    wsl.py                     Windows WSL executor
    factory.py                 Dynamic executor creation

  ml/                        ML internals
    ml_cvae.py                 CVAE data augmentation
    ml_nn_design.py            Optuna neural architecture search
    ml_nn_train.py             PyTorch training loop

  models/                    Shared data models
    enums.py                   TaskStatus, WorkflowType, UnknownStrategy
    task.py                    TaskRecord (serialization with pymatgen/numpy support)
    calculator.py              CalculationResult, CalculationFingerprint, ConfidenceLevel
    executor.py                CommandResult
    job.py                     JobHandle
    events.py                  RecoveryEvent for audit trail
    error_codes.py             ErrorCode, ErrorCategory, ErrorSource
    cancel.py                  CancelSource, CancelInfo
    schemas.py                 Pydantic validation schemas for all tool inputs

  tasks/                     Task engine
    task_runner.py             TaskRunner (submit, execute, poll, collect, cancel, shutdown)
    task_store.py              TaskStore + JSONTaskStore (persistence, fingerprint index)
    task_state.py              TaskStateManager (state transitions, persistence)
    recovery.py                UNKNOWN task classification helpers
    recovery_manager.py        RecoveryManager (lock mgmt, retry, timeout)
    recovery_lock.py           In-process threading-based recovery lock
    file_lock.py               Cross-process fcntl-based file lock
    retry.py                   RetryPolicy (max retries, retryable statuses)

  tools/                     Tool definitions for AI agent
    core.py, structure.py, vasp.py, workflow.py, ml.py, mlp.py

  utils/                     Shared utilities
    banner.py, fingerprint.py, interface_maker.py, io_helpers.py
    keychain.py, logger.py, session.py, utils.py, visualize.py, workdir_manager.py

  workflows/                 Workflow definitions and scheduling
    base.py                    Abstract Workflow
    eos.py                     EOS workflow (Birch-Murnaghan fitting)
    builder.py                 Fluent chain-style DSL
    graph.py                   DAG graph (topological sort, cycle detection)
    node.py                    WorkflowNode with NodeStatus lifecycle
    scheduler.py               Concurrent DAG scheduler
    handle.py                  WorkflowHandle (async result handle)
    checkpoint.py              Checkpoint save/restore
    status.py                  WorkflowStatus enum
```

---

## Core Components

### Calculator Layer

| Method | Purpose |
|--------|---------|
| prepare(work_dir, structure, workflow_type) | Write input files |
| launch(work_dir, executor) | Start calculation |
| detect_status(work_dir, job_handle) | Check job status |
| collect(work_dir) | Parse output |
| cancel(work_dir, job_handle) | Kill job |

**Implementations:** VaspCalculator, MLPCalculator, MockEOSCalculator, CachedCalculator

### Executor Layer

| Method | Purpose |
|--------|---------|
| spawn(work_dir, command, env) | Start process / submit job |
| is_running(job_id, pid) | Check if alive |
| wait(job_id, timeout) | Wait for completion |
| kill(job_id) | Terminate job |
| run(work_dir, command, env, timeout) | Synchronous run (WSL) |

**Implementations:** LocalExecutor, SlurmExecutor, WSLExecutor

### Task Engine

| Component | Responsibility |
|-----------|---------------|
| TaskRunner | Submit, execute, poll, cancel, graceful shutdown |
| TaskStateManager | Single authority for task state transitions |
| RecoveryManager | UNKNOWN task recovery, lock mgmt, retry policy, timeout |
| RecoveryLock | In-process (threading) mutual exclusion |
| FileLock | Cross-process (fcntl) mutual exclusion with stale detection |
| RetryPolicy | Max retries (default 3), retryable statuses |
| TaskStore | JSON-based persistence with fingerprint indexing |

### Workflow Layer

| Component | Purpose |
|-----------|---------|
| Workflow | Abstract base for sequential workflows |
| EOSWorkflow | Equation of State with Birch-Murnaghan fitting |
| WorkflowBuilder | Fluent chain-style DSL (.relax().static().dos().build()) |
| WorkflowGraph | DAG graph with CRUD, cycle detection, topological sort |
| WorkflowNode | Individual computation node with NodeStatus lifecycle |
| WorkflowScheduler | Concurrent DAG executor with dependency resolution |
| WorkflowHandle | Async result handle |
| WorkflowCheckpointManager | Persistent checkpoint save/restore for long-running DAGs |

---

## Configuration

Set in a .env file at the project root or as environment variables:

```env
# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
GROK_API_KEY=...
DEEPSEEK_API_KEY=...
DASHSCOPE_API_KEY=...
MP_API_KEY=...                  # Materials Project

# HPC / Remote
REMOTE_HOST=hpc.cluster.edu
REMOTE_USER=username
REMOTE_KEY=/path/to/ssh/key

# VASP / Pymatgen
POTCAR_DIR=/path/to/potcars

# Session
RUNS_DIR=~/masgent_runs
```

The configuration system (pydantic-settings):
- Loads from .env file at project root automatically
- Creates ~/masgent_runs as default session directory
- Returns empty string gracefully for missing keys
- Supports runtime reload via reload_config()

---

## Development

```bash
git clone https://github.com/syndra/masgent.git
cd masgent
pip install -e ".[dev,test]"
```

### Adding a Calculator
1. Subclass Calculator in src/masgent/calculators/
2. Implement prepare(), launch(), detect_status(), collect(), cancel()
3. Register via CalculatorRegistry.register("my_calc", MyCalculator)

### Adding an Executor
1. Subclass Executor in src/masgent/executors/
2. Implement spawn(), is_running(), wait(), kill()
3. Register via ExecutorFactory.register("my_backend", MyExecutor)

### Dependencies

**Core:** Python 3.11+, ASE, NumPy, Pandas, SciPy, scikit-learn, Matplotlib, Seaborn, Pydantic AI, Pymatgen, pymatgen-analysis-defects, mp-api, dotenv, colorama, bullet, yaspin

**ML:** icet, sevenn, chgnet, orb-models, mattersim, optuna

**Dev:** pytest, pytest-asyncio, pytest-cov, build, twine

---

## Testing

```bash
pytest                           # All tests
pytest --cov=masgent             # With coverage
pytest tests/unit/               # Unit tests
pytest tests/integration/        # Integration tests
pytest tests/workflows/          # Workflow tests
pytest tests/tasks/              # Task engine tests
pytest tests/task_runner/        # Task runner tests
pytest tests/calculators/        # Calculator tests
pytest tests/executors/          # Executor tests
pytest tests/models/             # Data model tests
```

### Test Infrastructure

- tests/conftest.py: Shared fixtures (mock executors, calculators, task stores, application instances)
- tests/mock_calculator.py: MockEOSCalculator with parabolic energy for workflow verification
- tests/mock_executors.py: Mock executors for recovery, timeout, and Slurm scenarios

---

## Citation

```bibtex
@misc{liu2025masgentaiassistedmaterialssimulation,
  title={Masgent: An AI-assisted Materials Simulation Agent},
  author={Guanghen Liu and Songge Yang and Yu Zhong},
  year={2025},
  eprint={2512.23010},
  archivePrefix={arXiv},
  primaryClass={physics.comp-ph},
  url={https://arxiv.org/abs/2512.23010},
}
```

Additional DOIs:
- Digital Discovery: 10.1039/D6DD00043F
- Zenodo: 10.5281/zenodo.19456831

---

## License

MIT License. Copyright (c) 2025 Guangchen Liu, 2026 syndra.

Masgent builds on the open-source materials ecosystem including ASE, Pymatgen, Icet, and modern Machine Learning Potentials.

---

## Acknowledgements

Masgent is built upon the foundational work by Guangchen Liu (original Masgent, https://github.com/aguang5241/masgent). The AI Agent backend, prompt assembly framework, crash recovery system, and workflow orchestration were developed by syndra (https://github.com/syndra/masgent).

We thank the developers of ASE, Pymatgen, Icet, SevenNet, CHGNet, ORB, MatterSim, Optuna, and the broader computational materials science community.
