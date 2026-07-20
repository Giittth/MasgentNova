## Parameter Validation Hints

Before passing parameters to a tool, check for physical reasonableness.

### Structure Parameters
| Parameter | Rule | Why |
|-----------|------|-----|
| `defect_amount` (float 0-1) | Must be between 0.0 and 1.0 | Fraction of atoms to modify |
| `defect_amount` (int) | Must be ≤ total atoms of the target element | Can't remove more than exist |
| `vacuum_thickness` | Must be ≥ 5 Å (recommend ≥ 10 Å) | Below 5 Å risks inter-slab interaction |
| `slab_layers` | Must be ≥ 2 | A slab needs at least 2 layers for bulk-like interior |
| `scaling_matrix` | All values must be positive integers | Can't have negative or zero cell scaling |
| `interface_gap` | Should be between 1.0 and 5.0 Å | Too small = overlap, too large = not bonded |

### VASP Calculation Parameters
| Parameter | Rule | Why |
|-----------|------|-----|
| `vasp_input_sets` | Must be one of the 6 supported sets | Other values will fail validation |
| `accuracy_level` | One of: Low, Medium, High, Custom | Maps to kppa values 1000, 3000, 5000 |
| `custom_kppa` | Required when accuracy=Custom, must be > 0 | K-points per reciprocal atom |

### ML Pipeline Parameters
| Parameter | Rule | Why |
|-----------|------|-----|
| `n_trials` (Optuna) | Should be ≥ 10, recommend 50-200 | Too few = unreliable optimization |
| `max_epochs` | Should be ≥ 100, recommend 500-1000 | Too few = underfitting |
| `patience` | Should be 10-100, must be < max_epochs | Early stopping window |
| `num_augmentations` | Must be ≥ 1 | At least one augmented sample needed |

### Workflow Parameters
| Parameter | Rule | Why |
|-----------|------|-----|
| `target_configurations` (SQS) | Values per species must sum to 1.0 | Mass conservation |
| Composition (at.%) | Sum of all elements must be ≤ 100 at.% | Physical constraint |
| Composition (wt.%) | Sum of all elements must be ≤ 100 wt.% | Physical constraint |

### When to Ask
- If the user specifies a value outside these ranges: politely flag it and ask for confirmation
- If the user omits a required parameter: ask explicitly, don't guess
- If a value is at the physical boundary (vacuum=5.0): note it as borderline and let user decide
- For `scaling_matrix` format: accept both semicolon-separated rows "2;0;0;0;2;0;0;0;2" and bracket notation "[2,2,2]"
