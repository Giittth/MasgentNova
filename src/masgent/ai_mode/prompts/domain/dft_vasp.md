## DFT / VASP Calculation Conventions

### VASP Input Set Guide
Available via `generate_vasp_inputs_from_poscar`:
| Input Set | Purpose | Key INCAR settings |
|-----------|---------|-------------------|
| MPMetalRelaxSet | Metal relaxation | ISMEAR=1, SIGMA~0.2 |
| MPRelaxSet | Non-metal relaxation | ISMEAR=0, SIGMA~1.0 |
| MPStaticSet | High-precision SCF | EDIFF=1e-6, NSW=0 |
| MPNonSCFBandSet | Band structure | Non-SCF along k-path |
| MPNonSCFDOSSet | DOS / PDOS | Uniform k-mesh, NEDOS=5000 |
| MPMDSet | AIMD | NVT ensemble, timestep, TEBEG |

### Convergence Thresholds (Standard Practice)
- **ENCUT**: typically 1.3× ENMAX from POTCAR. Always test (Low=1000, Medium=3000, High=5000 kppa in KPOINTS)
- **K-points**: convergence criterion is < 1 meV/atom energy difference
- **EDIFF (energy)**: 1e-5 eV for relaxation, 1e-6 for static/properties
- **EDIFFG (forces)**: -0.02 eV/A for standard relaxation, -0.01 eV/A for precise
- **Slab vacuum**: > 10 Å recommended to avoid inter-slab interaction

### Magnetic Systems
- ISPIN=2 for spin-polarized calculations
- MAGMOM initialization: use known magnetic moments for each element
- For non-collinear magnetism: LNONCOLLINEAR=.TRUE., LSORBIT=.TRUE.
- Default VASP input sets do NOT set MAGMOM; user must customize INCAR

### POTCAR Considerations
- POTCAR ordering must match the species order in POSCAR exactly
- Use PBE pseudopotentials by default (Materials Project standard)
- For transition metals: check whether semi-core states are included (e.g., _pv, _d variants)

### Common Pitfalls
- **Symmetry issues**: defects break symmetry; turn off ISYM for defective cells
- **K-point scaling**: k-mesh density must scale with inverse cell dimensions (larger cell = fewer k-points)
- **Convergence**: always verify both ENCUT and k-point convergence before production runs
- **Slab dipole correction**: use LDIPOL=.TRUE. for asymmetric slabs
- **NEB**: use at least 3 images between endpoints; climb=TRUE for saddle point
### AIMD settings
- Use MPMDSet for Nose-Hoover thermostat (NVT)
- Timestep: 1-2 fs (set in INCAR as POTIM)
- Total simulation time: at least 1-2 ps for equilibration
- For NPT ensemble: Langevin thermostat, PMASS
### NEB (Nudged Elastic Band)
- Requires initial and final POSCAR in the same cell
- Use `generate_vasp_workflow_of_neb` with image count 3-7
- Climbing image method for accurate barrier
### EOS (Equation of State)
- Fit with Birch-Murnaghan, Vinet, or Murnaghan equation
- Output: V0 (equilibrium volume), E0 (cohesive energy), B0 (bulk modulus), B1 (pressure derivative)
