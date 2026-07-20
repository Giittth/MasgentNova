## Result Formatting Standards

After each tool execution, always format the result consistently.

### Status Indicator
- ✅ **Success**: tool completed as expected
- ❌ **Error**: tool failed; describe what happened
- ⚠️ **Partial**: tool completed but with caveats

### Required Elements in Every Result
1. **Status** with icon
2. **Key output paths** (relative to runs directory)
3. **Physical quantities** if the tool computes them (with units)
4. **One-line interpretation** of what the result means

### Examples

**Structure generation:**
```
✅ Structure generated from Materials Project
   Crystal: LaCoO3, rhombohedral, R-3c
   Lattice: a=5.43 Å, c=13.38 Å
   Saved as: POSCAR and POSCAR_LaCoO3
   All polymorphs saved in: POSCARs/LaCoO3/
```

**Convergence analysis:**
```
✅ ENCUT converged at 520 eV
   Energy difference from 600 eV: 0.4 meV/atom (threshold: 1 meV/atom)
   Recommended ENCUT for production: 520 eV

✅ K-points converged at 6×6×6
   Energy difference from 8×8×8: 0.3 meV/atom
   Recommended K-points: 6×6×6
```

**EOS analysis:**
```
✅ EOS fitting completed
   Equation: Birch-Murnaghan (3rd order)
   V0 = 58.23 Å³/atom
   E0 = -12.45 eV/atom
   B0 = 185 GPa
   B1 = 4.2
   Plot saved: eos/eos_fit.png
```

**Elastic constants:**
```
✅ Elastic tensor computed
   C11 = 248 GPa, C12 = 145 GPa, C44 = 115 GPa
   Bulk modulus (K_VRH) = 179 GPa
   Shear modulus (G_VRH) = 78 GPa
   Young's modulus (E) = 205 GPa
   Poisson ratio (ν) = 0.32
```

**ML prediction:**
```
✅ Al-Mg-Si-Sc prediction complete
   Input: Mg=0.8 wt.%, Si=0.6 wt.%
   Predicted UTS: 385 MPa
   Predicted YS: 320 MPa
   Predicted Elongation: 12.5%
   Full report: machine_learning/ml_model_prediction/AlMgSiSc_prediction.txt
```

**Error:**
```
❌ POSCAR generation failed
   Cause: No materials found for formula "LaCo3"
   Suggestion: Check the formula spelling. Did you mean LaCoO₃ or La₂CoO₄?
```

**SQS generation:**
```
✅ SQS generated with icet
   Target: Co₀.₇₅Pt₀.₂₅ on sublattice A
   Supercell: 3×3×3 (108 atoms)
   Saved: sqs/POSCAR
   Log: sqs/masgent_sqs.log
```

### After Full Workflow Completion
Provide a **summary card** that includes:
- All tools that were executed (checklist style)
- Key findings per tool
- Total output files generated
- Suggested next step
