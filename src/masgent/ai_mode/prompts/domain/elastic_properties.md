## Elastic Properties Workflow

### Required Steps (in order)
1. Fully relax the conventional cell (EDIFFG < 0.01 eV/A)
2. Generate deformation matrices via `create_deformation_matrices`
3. Apply each deformation to create a supercell for each strain mode
4. Run static SCF for each deformed structure
5. Parse output (Vasprun) to extract stress or energy
6. Fit elastic tensor Cij from stress-strain or energy-strain curve

### Deformation Patterns
For cubic symmetry (standard in MASgent):
- 6 independent strain modes (ε₁, ε₂, ε₃, ε₄, ε₅, ε₆)
- Strain magnitude: typically ±1%, ±2%, ±3% in each direction
- Energy-volume polynomial fit of order 2-4

### Derived Mechanical Quantities
| Symbol | Quantity | Formula |
|--------|----------|---------|
| K_VRH | Bulk modulus (Voigt-Reuss-Hill) | (K_V + K_R) / 2 |
| G_VRH | Shear modulus (Voigt-Reuss-Hill) | (G_V + G_R) / 2 |
| E | Young's modulus | 9KG / (3K + G) |
| ν | Poisson ratio | (3K - 2G) / (2(3K + G)) |
| B/G | Ductility criterion | B/G > 1.75 = ductile |

### Workflow Tool
Use `generate_vasp_workflow_of_elastic_constants` to automate steps 2-4.
Use `analyze_vasp_workflow_of_elastic_constants` to perform steps 5-6.
The analysis tool writes the full elastic tensor and derived moduli to a result file.

### Pre-trained ML Predictions
For alloys without DFT data, use pre-trained models:
- `model_prediction_for_AlMgSiSc`: predicts UTS, YS, elongation from composition
- `model_prediction_for_AlCoCrFeNi`: predicts formation energy + elastic constants for FCC and BCC phases
