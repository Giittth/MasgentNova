## Materials Project Integration

### First-time Setup
- `generate_vasp_poscar` requires a Materials Project API key
- If key is not found, the tool will interactively ask for it
- Key is stored in .env and reused across sessions
- MASgent validates the key before using it

### Search Behavior
- Searches by exact chemical formula (case-sensitive formula, e.g., "LaCoO3")
- Returns ALL polymorphs/phases of that formula
- Results sorted by energy above hull (most stable first)
- The most stable structure is saved as both `POSCAR` (default) and `POSCAR_{formula}`
- All structures are saved in `POSCARs/{formula}/` with naming:
  `POSCAR_{crystal_system}_{space_group}_{material_id}`

### Output Structure Format
- **Conventional unit cell** is downloaded by default
- Coordinate format: Direct (fractional) by default
- Symmetry information is embedded in the POSCAR comment line

### Important Limitations
- MP data is DFT (GGA-PBE), not experimental
- Band gaps are systematically underestimated (DFT limitation)
- Some structures may be high-energy metastable phases
- Surface / defect properties are not available from MP directly
- The database covers mostly inorganic crystalline solids
- For amorphous or disordered materials, use alternative approaches
### When to Use Alternatives
- If MP returns no results: verify the formula, try alternative stoichiometry
- If the desired phase is not in MP: use experimental CIF from literature
- For 2D materials: specify the corresponding space group if known
- For alloys: use SQS generation from existing POSCAR
