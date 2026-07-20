## Error Response Patterns

When a tool returns an error, follow this sequence:

### Step 1: Classify the Error
- **Validation error**: tool returns before execution due to param check
- **Runtime error**: tool ran but something failed
- **Dependency error**: prerequisite not met

### Step 2: Try the Appropriate Response
**Invalid input parameters** (Schema validation failed)
- Re-read the tool's parameter requirements and ask user for corrected values
- Restate each invalid field with the acceptable range

**File not found at path** (Missing prerequisite file)
- Check if the generation step was completed
- Ask user if they want to create it first
- Use `list_files` to see what exists in the session

**Materials Project API key** (MP key not configured)
- Tell the user they need an MP API key
- The system will interactively ask for it on next tool call

**icet package is not installed** (Missing third-party dependency)
- Recommend `pip install icet`
- Offer alternative: random structure generation without SQS

**No materials found** (Formula not in MP database)
- Verify formula spelling
- Suggest alternative stoichiometries
- Or use CIF from other source

**No interstitial sites found** (Voronoi algorithm failed)
- Try a supercell with more atoms
- Choose a different defect element

**No candidates found** (interface lattice mismatch too large)
- Suggest increasing uv_tolerance or angle_tolerance
- Or try different Miller indices

**POSCAR defect generation failed** (Random selection failed)
- Check if enough atoms of the target element exist
- Reduce defect_amount

### Step 3: Retry or Escalate
- **Auto-retry once**: if the error might be transient (file system race, API timeout)
- If the same error persists, present to the user with:
  1. What went wrong in plain language
  2. The specific file or parameter involved
  3. One or two actionable options
  4. Ask: "Shall I try this approach instead?"

### Partial Success
- SQS generates no valid structures: suggest relaxing constraints (cutoffs, max_size)
- ML training diverges: suggest adjusting max_epochs, patience, or learning rate
- Interface finds only 1 candidate: tell the user and proceed, but note the limitation

### Fallback Suggestions
If a tool is completely blocked, offer alternatives:
- Can't query MP: suggest loading a CIF file from the user's local files
- Can't run VASP: suggest generating inputs for later manual submission
- Can't train ML: suggest using pre-trained models instead
