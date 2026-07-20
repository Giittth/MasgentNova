## Defect Physics & Generation

### Defect Types Supported in MASgent
| Type | Tool | Description | Concentration |
|------|------|-------------|---------------|
| Vacancy | `generate_vasp_poscar_with_vacancy_defects` | Remove atoms of element X | Fraction (0-1) or absolute count |
| Substitution | `generate_vasp_poscar_with_substitution_defects` | Replace A atoms with B atoms | Same as above |
| Interstitial | `generate_vasp_poscar_with_interstitial_defects` | Add atoms at Voronoi sites | One per site (algorithm chooses sites) |

### Prerequisite
- A valid POSCAR file must exist in the session (or specify one via `poscar_path`)
- For meaningful defect formation energies: use a **supercell** (4-8× the primitive cell) to minimize defect-defect interaction

### Vacancy Defects
- Randomly removes atoms of the specified element
- Fraction example: `defect_amount=0.25` means 25% of target element atoms removed
- Integer example: `defect_amount=3` means exactly 3 atoms removed
- Atoms are selected uniformly at random (no site preference)

### Substitution Defects
- Replaces atoms of `original_element` with `defect_element`
- Random selection, same concentration semantics as vacancies
- The substituted structure may require geometry relaxation before property calculation

### Interstitial Defects
- Uses pymatgen's VoronoiInterstitialGenerator to find candidate sites
- Only one defect element at a time
- Multiple candidate sites may be generated; each is saved as `POSCAR_{N}`
- Not all sites are physically accessible — check distances manually

### Defect Formation Energy (not automated)
To compute formation energy, you need:
1. Total energy of defect supercell (E_def)
2. Total energy of pristine supercell (E_pris)
3. Chemical potential of the added/removed element (u_X)
4. For vacancies: E_f = E_def - E_pris + n * u_X
5. For substitutions: E_f = E_def - E_pris - u_B + u_A
6. For interstitials: E_f = E_def - E_pris - u_X

### Charged Defects
- Requires compensating background charge in VASP (not handled by MASgent)
- User must manually set NELECT in INCAR for charged cells
- Use `only_incar=True` in `generate_vasp_inputs_from_poscar` to generate a custom INCAR

### After Defect Generation
Suggest: generate VASP inputs for each defect structure and run relaxation calculations.
For multiple defect configurations, recommend comparing total energies to find the most favorable.
