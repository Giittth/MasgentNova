## Tool Chaining Rules

### Built-in Prerequisites
Some tools have `prereqs` in their metadata. Enforce them during planning:

| Tool | Prereqs | Why |
|------|---------|-----|
| generate_vasp_inputs_from_poscar | (none, but requires POSCAR file) | Input sets need a crystal structure |
| generate_vasp_poscar_with_*_defects | (none, expects POSCAR file) | Defects modify an existing structure |
| generate_sqs_from_poscar | (none, expects POSCAR file) | SQS needs a primitive cell |
| train_model_for_machine_learning | design_model_for_machine_learning | Needs best model structure from Optuna |
| analyze_vasp_workflow_of_* | corresponding generate_vasp_workflow_of_* | Needs workflow results to analyze |

### State Tracking
Track which files were created by previous tools so you can reference them in subsequent steps:
- **Default POSCAR**: `{runs_dir}/POSCAR` (always updated by generate_vasp_poscar)
- **Generated POSCAR variants**: stored in subdirectories (defects/, supercell/, surface_slab/, etc.)
- **VASP inputs**: `{runs_dir}/vasp_inputs/{input_set}/`
- **Workflow results**: `{runs_dir}/convergence_tests/`, `{runs_dir}/eos/`, etc.
- **ML artifacts**: `{runs_dir}/machine_learning/`

### Offer Chaining Naturally
After running a tool, suggest what logically comes next:
- After structure → "Shall I generate VASP inputs for this structure?"
- After supercell → "Shall I create defects in this supercell?"
- After convergence analysis → "Shall I set up a production run with ENCUT=X and KPOINTS=Y?"
- After ML training → "Shall I make predictions with the trained model?"

### Avoid Breaking Sequences
- If the user asks for elastic constants, do not start from convergence tests unless they also ask
- If the user provides a POSCAR file path, do not regenerate from MP unless needed
- For complex workflows, propose the full sequence upfront and let the user accept or modify
### Pre-conditions to Verify Before Planning
- Check if `{runs_dir}/POSCAR` exists before calling defect/supercell/surface tools
- Check if the Materials Project API key is configured before calling generate_vasp_poscar
- Check if icet is installed before calling generate_sqs (fallback: tell user to `pip install icet`)
- Check if the output directory from a previous step exists before calling analysis tools
