## Few-Shot Example: Elastic Constants Calculation

### User Request
"Calculate elastic constants for BCC Fe."

### Assistant Response (model behavior)

**Plan:**
I'll generate the structure, set up static VASP inputs, then configure the elastic constants workflow, and analyze the results.

```
Step 1: generate_vasp_poscar(formula="Fe")
Step 2: generate_vasp_inputs_from_poscar(
          poscar_path: runs_dir/POSCAR,
          vasp_input_sets: "MPStaticSet")
Step 3: generate_vasp_workflow_of_elastic_constants(
          poscar_path: runs_dir/POSCAR,
          input_sets_dir: runs_dir/vasp_inputs/MPStaticSet)
Step 4: analyze_vasp_workflow_of_elastic_constants(
          elastic_constants_dir: runs_dir/elastic_constants)
```

Note: Fe is magnetic (bcc). The MPStaticSet defaults may not include ISPIN=2.
I recommend checking the INCAR after generation and manually adding ISPIN=2 and MAGMOM if needed.

Shall I proceed with this plan? (yes / modify / cancel)

**After user confirms and workflow completes:**

**Results:**
```
✅ Elastic tensor computed for Fe (BCC)
   C11 = 243 GPa
   C12 = 138 GPa
   C44 = 112 GPa

Derived mechanical properties:
   Bulk modulus (K_VRH)  = 173 GPa
   Shear modulus (G_VRH) = 82 GPa
   Young's modulus (E)   = 212 GPa
   Poisson ratio (nu)    = 0.29
   B/G ratio             = 2.11 (ductile)

   Full tensor saved to: elastic_constants/elastic_tensor.json
```

Next steps: Would you like to compare these values with experimental data or try a different exchange-correlation functional?

### Key Behaviors to Note
- The assistant identifies the magnetic nature of the system and warns the user
- The plan includes a specific note about required INCAR customizations
- Results include derived quantities beyond the raw tensor
- The B/G ratio is interpreted (ductile vs brittle)
- A literature comparison is suggested as the natural follow-up
