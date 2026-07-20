## Standard Workflow Recipes

Each recipe lists tools in order with parameter hints. Follow these when the user describes a task that matches.

### 1. Structure Preparation from Database
Goal: Generate a crystal structure from a formula.
```
1. generate_vasp_poscar           formula: (user-input formula, e.g., "LaCoO3")
```
Then offer: supercell, defects, surface, or VASP inputs.

### 2. Full POSCAR + VASP Input Setup
Goal: Structure from MP + ready-to-run VASP inputs.
```
1. generate_vasp_poscar           formula: (user input)
2. generate_vasp_inputs_from_poscar  vasp_input_sets: "MPStaticSet" | "MPRelaxSet" | "MPMetalRelaxSet"
```

### 3. Convergence Test (K-points & ENCUT)
Goal: Determine converged computational parameters.
```
1. generate_vasp_poscar           formula: (user input)
2. generate_vasp_workflow_of_convergence_tests
       poscar_path: runs_dir/POSCAR
       encut_range: "300,800,50" typical
       kpoint_range: "2,10,2" typical
3. analyze_vasp_workflow_of_convergence_tests
       convergence_tests_dir: runs_dir/convergence_tests
```
After analysis, suggest setting ENCUT and KPOINTS for production run.

### 4. Equation of State (EOS)
```
1. generate_vasp_poscar           formula: (user input)
2. generate_vasp_inputs_from_poscar  vasp_input_sets: "MPStaticSet"
3. generate_vasp_workflow_of_eos
       poscar_path: runs_dir/POSCAR
       input_sets_dir: runs_dir/vasp_inputs/MPStaticSet
       volumetric_strain: ±5%, step 1%
4. analyze_vasp_workflow_of_eos
       eos_dir: runs_dir/eos
```

### 5. Elastic Constants
```
1. generate_vasp_poscar           formula: (user input)
2. generate_vasp_inputs_from_poscar  vasp_input_sets: "MPStaticSet"
3. generate_vasp_workflow_of_elastic_constants
       poscar_path: runs_dir/POSCAR
       input_sets_dir: runs_dir/vasp_inputs/MPStaticSet
4. analyze_vasp_workflow_of_elastic_constants
       elastic_constants_dir: runs_dir/elastic_constants
```

### 6. Surface Slab Construction
```
1. generate_vasp_poscar           formula: (user input)
2. generate_surface_slab_from_poscar
       miller_indices: (user input, e.g., [1,0,0] or [1,1,1])
       vacuum_thickness: 15.0 (default)
       slab_layers: 4 (default, adjust for convergence)
3. generate_vasp_inputs_from_poscar  poscar_path: runs_dir/surface_slab/POSCAR
```

### 7. Defect Structure
```
1. generate_vasp_poscar           formula: (user input)
2. generate_supercell_from_poscar
       scaling_matrix: (e.g., "2;0;0;0;2;0;0;0;2" or "[2,2,2]")
3. generate_vasp_poscar_with_*_defects  (vacancy/substitution/interstitial)
       original_element / defect_element / defect_amount: (user input)
4. generate_vasp_inputs_from_poscar  poscar_path: runs_dir/defects/*/POSCAR
```

### 8. Interface Construction
```
1. generate_vasp_poscar           formula: (lower material, e.g., "Al")
2. generate_vasp_poscar           formula: (upper material, e.g., "MgO")
3. generate_interface_from_poscars
       lower_poscar_path: runs_dir/POSCAR_Al
       upper_poscar_path: runs_dir/POSCAR_MgO
       lower_hkl: (e.g., [1,1,1])
       upper_hkl: (e.g., [1,1,1])
```

### 9. ML Data Pipeline
```
1. analyze_features_for_machine_learning
       input_data_path: (CSV)
2. reduce_dimensions_for_machine_learning   (optional)
3. augment_data_for_machine_learning         (if small dataset)
4. design_model_for_machine_learning         (starts Optuna)
5. train_model_for_machine_learning
6. model_prediction_for_AlMgSiSc / AlCoCrFeNi  (if applicable)
```

### 10. Pre-trained ML Prediction (quick)
```
- model_prediction_for_AlMgSiSc      Mg: (wt.%), Si: (wt.%)
- model_prediction_for_AlCoCrFeNi    Al: (at.%), Co: (at.%), Cr: (at.%), Fe: (at.%)
```

### 11. AIMD (Ab Initio Molecular Dynamics)
```
1. generate_vasp_poscar           formula: (user input)
2. generate_vasp_inputs_from_poscar  vasp_input_sets: "MPMDSet"
3. generate_vasp_workflow_of_aimd
4. analyze_vasp_workflow_of_aimd
```

### 12. NEB (Transition State)
```
1. generate_vasp_poscar           formula: (initial state)
2. generate_vasp_poscar           formula: (final state, same cell size)
3. generate_vasp_workflow_of_neb
4. analyze_vasp_workflow_of_neb
```

### 13. SQS (Alloy Modeling)
```
1. generate_vasp_poscar           formula: (primitive cell, e.g., "Co3Pt")
2. generate_sqs_from_poscar
       target_configurations: (e.g., {"Co": {"Co": 0.75, "Pt": 0.25}})
       cutoffs: [8.0, 4.0]  (pair + triplet)
       mc_steps: 10000
```

When the user's request matches one of these, use the recipe as a starting plan and customize parameters based on the user's specific input.
