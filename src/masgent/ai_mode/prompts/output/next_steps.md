## Follow-Up Suggestions

After completing a task, always offer the most relevant next step.

### After Structure Generation
```
Next steps: Would you like to?
  - Generate a supercell?
  - Create defects (vacancy/substitution/interstitial)?
  - Prepare VASP input files for this structure?
  - Generate a surface slab from this bulk?
  - Visualize the structure in your browser?
```

### After VASP Input Set Generation
```
Next steps: Would you like to?
  - Generate a Slurm submission script for HPC?
  - Customize KPOINTS with specific accuracy?
  - Set up a convergence test workflow?
  - Run an EOS / elastic constants / AIMD / NEB workflow?
```

### After Convergence Test Analysis
```
Next steps: The converged parameters are ENCUT=520 eV and KPOINTS=6×6×6.
Would you like to:
  - Set up a production calculation with these values?
  - Run elastic constants with converged settings?
  - Run EOS with converged settings?
```

### After Defect Generation
```
Next steps: Would you like to:
  - Generate VASP inputs for each defect structure?
  - Generate other defect types on the same structure?
  - Visualize the defect structures?
```

### After EOS / Elastic Constants Analysis
```
Next steps: Would you like to?
  - Check the fitted plot (saved in the results directory)?
  - Run elastic constants with a different input set?
  - Compare results with experimental or literature values?
```

### After ML Model Training
```
Next steps: Would you like to?
  - Make predictions with the trained model?
  - Retrain with more data or different parameters?
  - Check the training loss curves?
```

### After ML Prediction
```
Next steps: Would you like to?
  - Save the prediction results?
  - Try a different composition?
  - Compare with DFT calculations or experiments?
```

### After SQS Generation
```
Next steps: Would you like to?
  - Generate VASP inputs for the SQS structure?
  - Check the SQS correlation functions?
  - Visualize the SQS structure?
```

### General Fallback (if none of the above apply)
```
Next steps: Is there anything else you would like to do?
  - List files in the current session
  - Read a generated file
  - Start a new workflow
```
