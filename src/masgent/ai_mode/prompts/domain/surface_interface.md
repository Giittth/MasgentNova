## Surface & Interface Construction

### Surface Slab Generation
Uses `generate_surface_slab_from_poscar` with:
- **Miller indices** (hkl): determines the exposed surface plane
- **Slab layers**: number of atomic layers in the slab (minimum 2, recommended ≥ 4)
- **Vacuum thickness**: vacuum gap above the slab in Angstrom (recommended ≥ 10 Å)

### Miller Index Conventions
- For FCC (111): close-packed surface, most stable for many metals
- For FCC (100): square symmetry, good for adsorption studies
- For BCC (110): most stable for BCC metals
- Validation: indices are normalized to the smallest integers

### Slab Construction Notes
- Uses ASE's `surface()` function with `periodic=True`
- Slab retains the original lattice symmetry in-plane
- Vacuum is added along the surface normal direction
- The resulting POSCAR is a non-periodic slab in the vacuum direction

### After Slab Generation
Suggest: visualize the slab, prepare VASP inputs with appropriate dipole correction.
For asymmetric slabs: recommend `LDIPOL=.TRUE.` and `IDIPOL=3` in INCAR.

### Interface Construction
Uses `generate_interface_from_poscars` with two separate bulk POSCAR files:

| Parameter | Description | Typical value |
|-----------|-------------|---------------|
| lower_hkl, upper_hkl | Miller indices for each material | [1,1,1] for FCC metals |
| slab_layers | Layers for each material | 4-6 each |
| slab_vacuum | Vacuum above the interface | 15.0 Å |
| min_area, max_area | Interface area range (Å²) | 50-500 |
| interface_gap | Initial gap between slabs | 2.0 Å |
| uv_tolerance | Lattice vector matching tolerance | 5.0% |
| angle_tolerance | Angle matching tolerance | 5.0° |
| shape_filter | Filter non-rectangular matches | False |

### Interface Matching Algorithm
1. Construct slabs for both materials at the specified Miller indices
2. Search for lattice matches where in-plane vectors are within tolerance
3. Rank candidates by: lattice mismatch, interface area, number of atoms
4. Save all viable candidates as individual POSCAR files

### Common Pitfalls
- If no candidates found: increase tolerance or try different Miller indices
- Large supercells may become computationally expensive
- Interface always saves the lower slab below the upper slab
- After construction: geometry relaxation is required to find the optimal interface separation
