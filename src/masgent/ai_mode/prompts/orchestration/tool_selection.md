## Tool Selection Decision Tree

Use this guide to decide which tools to use based on the user's stated goal.

### "Generate a crystal structure" / "Get POSCAR"
```
Does the user provide a formula?
  Yes -> generate_vasp_poscar(formula)
         (fetches from Materials Project)
  No -> Does the user provide a file (CIF, XYZ)?
    Yes -> convert_structure_format(input_path, input_format, "POSCAR")
    No -> Ask for formula or file path
```

### "Modify an existing structure"
"""
Does the user want to:
  Change size?         -> generate_supercell_from_poscar(scaling_matrix)
  Add surface?         -> generate_surface_slab_from_poscar(miller_indices)
  Create interface?    -> generate_interface_from_poscars(...)
  Remove atoms?        -> generate_vasp_poscar_with_vacancy_defects(...)
  Swap atoms?          -> generate_vasp_poscar_with_substitution_defects(...)
  Add atoms?           -> generate_vasp_poscar_with_interstitial_defects(...)
  Build random alloy?  -> generate_sqs_from_poscar(target_configurations)
  Change file format?  -> convert_structure_format(...)
"""

### "Set up VASP calculation"
```
What type of calculation?
  Standard relaxation / static -> generate_vasp_inputs_from_poscar
    (choose MPRelaxSet, MPMetalRelaxSet, or MPStaticSet)
  DOS / band structure -> generate_vasp_inputs_from_poscar
    (choose MPNonSCFDOSSet or MPNonSCFBandSet)
  Molecular dynamics -> generate_vasp_inputs_from_poscar
    (choose MPMDSet)
  Just the INCAR -> generate_vasp_inputs_from_poscar(only_incar=True)
  Add Slurm script -> generate_vasp_inputs_hpc_slurm_script(...)
  Adjust k-points -> customize_vasp_kpoints_with_accuracy(...)
```

### "Run an automated workflow"
```
What property?
  Convergence (k-points + ENCUT) -> generate_vasp_workflow_of_convergence_tests
  Equation of state              -> generate_vasp_workflow_of_eos
  Elastic constants              -> generate_vasp_workflow_of_elastic_constants
  Ab initio MD                   -> generate_vasp_workflow_of_aimd
  NEB / transition state         -> generate_vasp_workflow_of_neb
```

### "Analyze results"
```
Of which workflow?
  Convergence -> analyze_vasp_workflow_of_convergence_tests
  EOS         -> analyze_vasp_workflow_of_eos
  Elastic     -> analyze_vasp_workflow_of_elastic_constants
  AIMD        -> analyze_vasp_workflow_of_aimd
```

### "Run machine learning"
```
Does the user want pre-trained model predictions?
  Alloy is Al-Mg-Si-Sc?       -> model_prediction_for_AlMgSiSc
  Alloy is Al-Co-Cr-Fe-Ni?    -> model_prediction_for_AlCoCrFeNi
  Other system or custom?     -> analyze_features -> design_model -> train_model

Does the user want to train a new model from data?
  Steps: analyze_features -> reduce_dimensions(optional)
         -> augment_data(if data is small)
         -> design_model -> train_model

Does the user want to retrain an existing model?
  -> retrain_model_for_machine_learning(old_model_path, ...)
```

### "List / read / rename files"
"""
- List session files: list_files()
- Read a file: read_file(name)
- Rename a file: rename_file(name, new_name)
"""

### "Visualize"
"""
- Visualize POSCAR as 3D HTML: visualize_structure_from_poscar(poscar_path)
"""

### Combined intent patterns
- "Generate LaCoO3 and calculate elastic constants"
  -> generate_vasp_poscar → generate_vasp_inputs → generate_workflow_of_elastic → analyze
- "Get POSCAR for MgO, add a surface, and set up VASP"
  -> generate_vasp_poscar → generate_surface_slab → generate_vasp_inputs
- "Train a model for my new alloy data"
  -> analyze_features → design_model → train_model
