## Multi-Structure Comparison

When the user requests comparison between structures or results, format them consistently.

### Comparing Crystal Structures
| Property | Structure A | Structure B |
|----------|-------------|-------------|
| Formula | LaCoO₃ | LaCoO₃ |
| Space group | R-3c | Pm-3m |
| a (Å) | 5.43 | 3.85 |
| b (Å) | 5.43 | 3.85 |
| c (Å) | 13.38 | 3.85 |
| Volume (Å³) | 341.7 | 57.1 |
| Atoms/cell | 30 | 5 |
| Energy above hull | 0 eV | 0.12 eV |

### Comparing Convergence Results
| ENCUT (eV) | Energy/atom (eV) | ΔE (meV/atom) |
|-------------|------------------|----------------|
| 400 | -12.3456 | — |
| 500 | -12.3489 | 3.3 |
| 520 | -12.3493 | 0.4 |
| 600 | -12.3497 | 0.4 |

### Comparing Defect Configurations
| Structure | Total Energy (eV) | Relative Stability |
|-----------|-------------------|-------------------|
| Pristine supercell | -245.32 | Reference |
| 1 La vacancy | -238.15 | +7.17 eV |
| 2 La vacancies | -231.02 | +14.30 eV |
| 1 O vacancy (site A) | -242.89 | +2.43 eV |
| 1 O vacancy (site B) | -242.76 | +2.56 eV |

### Comparing ML Model Performance
| Metric | Model v1 | Model v2 (retrained) |
|--------|----------|---------------------|
| Architecture | [64,32,16] | [128,64,32] |
| Training loss | 0.023 | 0.015 |
| Validation loss | 0.028 | 0.019 |
| Test R² | 0.92 | 0.95 |
| Test MAE | 12.5 MPa | 9.8 MPa |

### When to Compare
- User asks "which structure is more stable" → compare energy above hull or total energy
- User asks "which one should I use" → compare stability + computational cost + property relevance
- User asks "how do these differ" → highlight key differences in symmetry, volume, composition
- User generates multiple defect configurations → rank by total energy
- User trains multiple ML models → rank by validation loss and test R²

### Visualization Linking
When comparison involves structural differences, offer to visualize:
"Would you like to view these structures in the browser to compare them visually?"
