## Multi-Parameter Batch Execution

### When to Use Batch Mode
- User asks to "try multiple values" or "sweep" parameters
- User asks to "compare" different settings
- User asks "what happens if I change X"
- User provides a list or range of values for a parameter

### Batch Planning Pattern
```
User: "Try convergence with both MPRelaxSet and MPStaticSet"

Plan:
1. generate_vasp_poscar(formula=...)
2. generate_vasp_inputs_from_poscar(vasp_input_sets="MPRelaxSet")
3. generate_vasp_inputs_from_poscar(vasp_input_sets="MPStaticSet")
4. run convergence workflow on each set...

Present as parallel branches and ask user to confirm.
```

### Parameter Sweep Pattern
```
User: "Check convergence from 2x2x2 to 8x8x8 k-points"

Plan:
1. generate_vasp_poscar(formula=...)
2. generate_vasp_workflow_of_convergence_tests(
       kpoint_range="2,8,2")
```

### Handling Lists in Parameters
- When the user provides a range like "300 to 800 eV", map it to workflow parameters:
  `encut_range: "300,800,50"`
- When the user provides multiple options for a single parameter (e.g., two accuracy levels):
  Propose running the workflow once per option and comparing results

### Post-Batch Comparison
After executing a batch, use the comparison format (see comparison module) to present results.
Highlight:
- Which option gives the best accuracy
- Which option gives the best performance/speed
- Recommended compromise value
If the user ran multiple workflows (e.g., EOS with and without relaxation), compare the key outputs side by side.

### Limitations
- Each tool runs sequentially; there is no parallel tool execution in this system
- Large sweeps (20+ values) are time-consuming; warn the user and suggest a sparse grid first
- For ML training, multiple Optuna trials are handled automatically (n_trials parameter)
