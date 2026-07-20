"""横幅、帮助信息、清屏与显示"""

import os
from importlib.metadata import version, PackageNotFoundError
from masgent.utils.utils import color_print, color_input
from masgent._config import config


def get_pkg_version():
    try:
        return version('masgent')
    except PackageNotFoundError:
        return 'dev'


def print_banner():
    pkg_version = get_pkg_version()
    ascii_banner = rf'''
╔═════════════════════════════════════════════════════════════════════════╗
║                                                                         ║
║  ███╗   ███╗  █████╗  ███████╗  ██████╗  ███████╗ ███╗   ██╗ ████████╗  ║
║  ████╗ ████║ ██╔══██╗ ██╔════╝ ██╔════╝  ██╔════╝ ████╗  ██║ ╚══██╔══╝  ║
║  ██╔████╔██║ ███████║ ███████╗ ██║  ███╗ █████╗   ██╔██╗ ██║    ██║     ║
║  ██║╚██╔╝██║ ██╔══██║ ╚════██║ ██║   ██║ ██╔══╝   ██║╚██╗██║    ██║     ║
║  ██║ ╚═╝ ██║ ██║  ██║ ███████║ ╚██████╔╝ ███████╗ ██║ ╚████║    ██║     ║
║  ╚═╝     ╚═╝ ╚═╝  ╚═╝ ╚══════╝  ╚═════╝  ╚══════╝ ╚═╝  ╚═══╝    ╚═╝     ║
║                                                                         ║
║                                   Masgent: Materials Simulation Agent   ║
║                                      Copyright (c) 2025 Guangchen Liu   ║
║                                                                         ║
║  Version:       {pkg_version:<54}  ║
║  License:       MIT License                                             ║
║  Citation:      Liu, G. et al. (2025). arXiv: 2512.23010                ║
║  DOI:           https://doi.org/10.48550/arXiv.2512.23010               ║
║  Repository:    https://github.com/aguang5241/Masgent                   ║
║  Contact:       gliu4@wpi.edu                                           ║
║                                                                         ║
╚═════════════════════════════════════════════════════════════════════════╝
    '''
    color_print(ascii_banner, 'yellow')


def clear_and_print_entry_message():
    os.system('cls' if os.name == 'nt' else 'clear')
    runs_dir = str(config.get_runs_dir())
    msg = f'''
Welcome to Masgent — Your Materials Simulations Agent.
---------------------------------------------------------
Current Session Runs Directory: {runs_dir}

Please select from the following options:
'''
    color_print(msg, 'white')


def clear_and_print_banner_and_entry_message():
    os.system('cls' if os.name == 'nt' else 'clear')
    print_banner()
    runs_dir = str(config.get_runs_dir())
    msg = f'''
Welcome to Masgent — Your Materials Simulation Agent.
---------------------------------------------------------
Current Session Runs Directory: {runs_dir}

Please select from the following options:
'''
    color_print(msg, 'white')


def print_help():
    os.system('cls' if os.name == 'nt' else 'clear')
    content = '''
Masgent - Available Commands and Functions: 
-------------------------------------------
1. Density Functional Theory (DFT) Simulations
  - 1.1 Structure Preparation & Manipulation
    - 1.1.1 Generate POSCAR from chemical formula
    - 1.1.2 Convert POSCAR coordinates (Direct <-> Cartesian)
    - 1.1.3 Convert structure file formats (CIF, POSCAR, XYZ)
    - 1.1.4 Generate structures with defects (Vacancies, Substitutions, Interstitials)
    - 1.1.5 Generate supercells
    - 1.1.6 Generate Special Quasirandom Structures (SQS)
    - 1.1.7 Generate surface slabs
    - 1.1.8 Generate interface structures
    - 1.1.9 Visualize structures
  
  - 1.2 VASP Input File Preparation
    - 1.2.1 Prepare full VASP input files (INCAR, KPOINTS, POTCAR, POSCAR)
    - 1.2.2 Generate INCAR templates
      - MPMetalRelaxSet: suggested for metallic structure relaxation
      - MPRelaxSet: suggested for structure relaxation
      - MPStaticSet: suggested for static calculations
      - MPNonSCFBandSet: suggested for non-self-consistent field calculations (Band structure)
      - MPNonSCFDOSSet: suggested for non-self-consistent field calculations (Density of States)
      - MPMDSet: suggested for molecular dynamics simulations
    - 1.2.3 Generate KPOINTS with specified accuracy
    - 1.2.4 Generate HPC job submission script
  
  - 1.3 Standard VASP Workflow Preparation
    - 1.3.1 Convergence test (ENCUT, KPOINTS)
    - 1.3.2 Equation of State (EOS)
    - 1.3.3 Elastic constants calculations
    - 1.3.4 Ab-initio Molecular Dynamics (AIMD)
    - 1.3.5 Nudged Elastic Band (NEB) calculations
  
  - 1.4 Standard VASP Workflow Output Analysis
    - 1.4.1 Convergence test analysis
    - 1.4.2 Equation of State (EOS) analysis
    - 1.4.3 Elastic constants analysis 
    - 1.4.4 Ab-initio Molecular Dynamics (AIMD) analysis
    - 1.4.5 Nudged Elastic Band (NEB) analysis

2. Fast Simulations Using Machine Learning Potentials (MLPs)
  - Supported MLPs:
    - 2.1 SevenNet
    - 2.2 CHGNet
    - 2.3 Orb-v3
    - 2.4 MatterSim
  - Implemented Simulations for all MLPs:
    - Single Point Energy Calculation
    - Equation of State (EOS) Calculation
    - Elastic Constants Calculation
    - Molecular Dynamics Simulation (NVT)

3. Simple Machine Learning for Materials Science
  - 3.1 Data Preparation & Feature Analysis
    - 3.1.1 Feature analysis and visualization
    - 3.1.2 Dimensionality reduction (if too many features)
    - 3.1.3 Data augmentation (if limited data)
  - 3.2 Model Design & Hyperparameter Tuning
  - 3.3 Model Training & Evaluation
  - 3.4 Pre-trained Model Applications
    - 3.4.1 Mechanical Properties Prediction in Sc-modified Al-Mg-Si Alloys
    - 3.4.2 Phase Stability & Elastic Properties Prediction in Al-Co-Cr-Fe-Ni High-Entropy Alloys
'''
    color_print(content, 'green')
    try:
        while True:
            inp = color_input('Type "back" to return: ', 'yellow').strip().lower()
            if inp == 'back':
                return
    except KeyboardInterrupt:
        return