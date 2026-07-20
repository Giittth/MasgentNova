## pymatgen / ASE Data Models

### Core Object Hierarchy
```
POSCAR file
  -> pymatgen.io.vasp.Poscar (format-specific IO)
  -> pymatgen.core.Structure (lattice + sites + species)
  -> ase.io.read / write (format-agnostic IO)
  -> ase.Atoms (positions + symbols + cell)
```

### File Format Mapping
| Input | MASgent function | Output |
|-------|-----------------|--------|
| POSCAR | generate_vasp_poscar | POSCAR |
| CIF | convert_structure_format | POSCAR / CIF / XYZ |
| XYZ | convert_structure_format | POSCAR / CIF / XYZ |
| POSCAR | convert_poscar_coordinates | POSCAR (different coord system) |
| POSCAR | visualize_structure_from_poscar | HTML (3Dmol.js) |
| CSVs | analyze_features / train_model | ML models + plots |

### Coordinate Conventions
- **Direct (fractional)**: coordinates in [0,1) relative to lattice vectors
  - Preferred for VASP input, pymatgen internal representation
  - Easier for symmetry analysis and defect placement
- **Cartesian**: coordinates in Angstrom
  - Used by ASE for geometry operations
  - Required for some structure analysis tools

### Path Conventions
- All file paths in tool parameters are relative to the current session runs directory
- Exception: `poscar_path` defaults to `{runs_dir}/POSCAR` when left unspecified
- Generated files are always written into subdirectories under the runs dir
  - `defects/vacancies/`, `defects/substitutions/`, `defects/interstitials/`
  - `supercell/`, `sqs/`, `surface_slab/`, `interface_maker/`
  - `vasp_inputs/{input_set}/`, `convert/`, `visualization/`
  - `machine_learning/` (with subdirs per step)

### Error Handling
- If a file does not exist at the given path, check if the preceding generation step was completed
- File creation tools write into auto-created subdirectories; verify using `list_files`
- Rename operations are copy-based and confined to the runs directory
