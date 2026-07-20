## Machine Learning Potentials

### Supported ML Approaches in MASgent
1. **Feature-based ML pipeline**
   - analyze_features (compute descriptors)
   - reduce_dimensions (PCA, t-SNE)
   - augment_data (VAE-based generation for small datasets)
   - design_model (Optuna hyperparameter search)
   - train_model / retrain_model (PyTorch neural network)
   - model_prediction (pre-trained for specific alloys)

2. **ML Potentials as ASE calculators** (via `run_simulation_using_mlps`)
   - MACE (mace-mp-0, mace-omat-0)
   - CHGNet (chgnet-0.3.0)
   - M3GNet (m3gnet)
   - These can perform: single-point energy, geometry relaxation, MD

### Data Pipeline Details
- **Feature analysis**: computes composition and structure-based features from existing data
- **Dimension reduction**: visualizes high-dimensional feature space, identifies clusters/outliers
- **Data augmentation**: uses Conditional VAE to generate synthetic samples
  - Required when dataset size < ~100 samples
  - Preserves input-output relationships
- **Model design**: Optuna searches over hidden layers, learning rate, activation, regularization
- **Training**: early stopping (patience), learning rate scheduling, train/val/test split

### Pre-trained Models
- `Al-Mg-Si-Sc`: predicts tensile properties from composition
  - Input: Mg (wt.%), Si (wt.%)
  - Output: UTS (MPa), YS (MPa), Elongation (%)
  - Uses CALPHAD phase fractions internally
- `Al-Co-Cr-Fe-Ni`: predicts phase stability + elastic constants
  - Input: Al, Co, Cr, Fe (at.%)
  - Output: FCC and BCC formation energy, C11, C12, C44
  - Derived: B_VRH, G_VRH, E, ν

### Data Formats
- Input CSV: columns = feature dimensions (e.g., composition, phase fractions, descriptors)
- Output CSV: columns = target properties (e.g., energy, elastic moduli)
- File paths should be relative to the current session runs directory
