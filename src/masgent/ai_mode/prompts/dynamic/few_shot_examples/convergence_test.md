## Few-Shot Example: Convergence Test

### User Request
"Run a convergence test for SrTiO3 to find optimal ENCUT and k-points."

### Assistant Response (model behavior)

**Plan:**
I'll generate the structure from Materials Project, then set up a convergence test workflow, and finally analyze the results.

```
Step 1: generate_vasp_poscar(formula="SrTiO3")
Step 2: generate_vasp_workflow_of_convergence_tests(
          poscar_path: runs_dir/POSCAR,
          encut_range: "300,800,50",
          kpoint_range: "2,10,2")
Step 3: analyze_vasp_workflow_of_convergence_tests(
          convergence_tests_dir: runs_dir/convergence_tests)
```

Shall I proceed with this plan? (yes / modify / cancel)

**After user confirms:**

Step 1: ✅ Structure generated for SrTiO3 (cubic, Pm-3m, 5 atoms/cell)

Step 2: ✅ Convergence workflow generated and executed

Step 3: 🔍 Analyzing convergence data...

**Results:**
```
✅ ENCUT converged at 500 eV
   Energy difference from 600 eV: 0.6 meV/atom
   Recommended: 500 eV (or 520 eV for safety margin)

✅ K-points converged at 8x8x8
   Energy difference from 10x10x10: 0.3 meV/atom
   Recommended: 8x8x8
```

Next step: Shall I set up a production calculation with ENCUT=520 eV and KPOINTS=8x8x8?

### Key Behaviors to Note
- The assistant presents a complete plan upfront before executing anything
- Parameters use defaults where the user didn't specify
- After each tool, a status line with icon is shown
- Analysis results are interpreted with specific numbers and units
- A concrete next step is suggested based on the outcome
