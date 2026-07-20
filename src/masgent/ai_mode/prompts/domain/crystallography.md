## Crystal Structure Basics

### Lattice Systems
Material structures fall into 7 crystal systems. For VASP POSCAR generation and workflow setup:
- **Cubic**: a=b=c, alpha=beta=gamma=90 (e.g., NaCl, Si, FCC metals)
- **Tetragonal**: a=b≠c, alpha=beta=gamma=90 (e.g., TiO2 rutile)
- **Orthorhombic**: a≠b≠c, alpha=beta=gamma=90 (e.g., MgSiO3 perovskite)
- **Hexagonal**: a=b≠c, alpha=beta=90, gamma=120 (e.g., graphite, hcp metals)
- **Rhombohedral (Trigonal)**: a=b=c, alpha=beta=gamma≠90 (e.g., LaCoO3, calcite)
- **Monoclinic**: a≠b≠c, alpha=gamma=90, beta≠90 (e.g., ZrO2)
- **Triclinic**: a≠b≠c, alpha≠beta≠gamma≠90

### Miller Indices
- Planes: (hkl) — used for surface slab generation
- Directions: [hkl]
- Families: {hkl} for planes, <hkl> for directions
- Negative indices: written as (hkl) with bar notation, in POSCAR just use negative numbers
- In cubic systems, (100), (010), (001) are equivalent; for lower symmetry they are distinct

### Common POSCAR Coordinate Systems
- **Direct (fractional)**: coordinates relative to lattice vectors, range [0,1)
- **Cartesian**: coordinates in Angstrom (Å), absolute positions
- Use `convert_poscar_coordinates` to toggle between them

### Supercell Convention
- Scaling matrix: 3×3 integer matrix [[a,b,c],[d,e,f],[g,h,i]]
- Diagonal shorthand: [n1, n2, n3] means [[n1,0,0],[0,n2,0],[0,0,n3]]
- All values must be positive integers
- Total atoms scale factor = det(scaling_matrix)

### Defect Types
- **Vacancy**: remove atoms of a specified element
- **Substitution**: replace atoms of element A with element B
- **Interstitial**: add atoms at Voronoi interstitial sites (pymatgen algorithm)
- Defect concentration: fraction (0-1) or absolute count (integer)
- For charged defects, VASP requires compensating background charge (not handled automatically)
