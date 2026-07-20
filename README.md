# Masgent

**Materials Simulation Agent** -- AI-powered, crash-safe materials simulation orchestration. Unifies DFT, ML potentials, and ML model training with natural language interaction.

[![arXiv](https://img.shields.io/badge/DOI-10.48550/arXiv.2512.23010-blue)](https://arxiv.org/abs/2512.23010)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Download and Setup

Requirements: Python >= 3.11, < 3.15

### One-liner (Linux/WSL)

```bash
bash <(curl -s https://raw.githubusercontent.com/syndra/masgent/main/scripts/setup.sh)
```

### Manual install

```bash
git clone https://github.com/syndra/masgent.git
cd masgent
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
masgent
```

### PyPI install

```bash
pip install masgent
masgent
```

### Configuration

Edit `.env` (copy from `.env.example`):

```env
OPENAI_API_KEY=sk-...  # at least one LLM API key required
MP_API_KEY=...         # Materials Project (optional)
POTCAR_DIR=/path/...   # VASP pseudopotentials (optional)
```

Includes: `.env.example`, `requirements.txt`, `scripts/setup.sh`

---

## Overview

Masgent is a three-tier asynchronous framework for DFT, ML potentials, and ML model training. Supports AI agent and CLI modes with crash recovery and DAG workflow scheduling.

**Key capabilities:** Multi-LLM, crash-safe task engine, DAG workflows, local/Slurm/WSL executors, 60+ tools, pre-trained alloy models.
 
---
 
## Features
 
### DFT Simulation
- Structure from MP, supercells, defects, slabs, interfaces, SQS
- VASP inputs (INCAR, KPOINTS, POTCAR, POSCAR), Slurm scripts
- Workflows: Convergence, EOS, Elastic, AIMD, NEB
 
### Machine Learning Potentials
- SevenNet, CHGNet, Orb-v3, MatterSim
- Single-point, relaxation, MD
 
### ML Utilities
- VAE augmentation, Optuna, PyTorch training
- Pre-trained Al-Mg-Si-Sc and Al-Co-Cr-Fe-Ni models
 
---
 
## AI Agent Mode
 
Multi-LLM support. Modular prompt assembly.
 
---
 
## CLI Mode
 
masgent --cli
Commands: dft, ml, mlp
 
---
 
## Architecture
 
Layered: WorkflowScheduler -> TaskRunner -> Calculator -> Executor
 
---
 
## Development
 
pip install -e ".[dev,test]"
 
---
 
## License
 
MIT License. (c) 2025 Guangchen Liu, 2026 syndra.
