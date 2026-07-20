"""VASP 工作流分析工具"""

import os
import pandas as pd
import numpy as np
from pymatgen.core import Structure 
from pymatgen.io.vasp import Vasprun
from pymatgen.analysis.transition_state import NEBAnalysis
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from ase.io import read
from masgent.models import schemas
from masgent.utils import write_comments, list_files_in_dir, fit_eos, create_deformation_matrices
from .core import with_metadata


@with_metadata(schemas.ToolMetadata(
    name='Analyze VASP workflow of convergence tests for k-points and energy cutoff',
    description='Analyze VASP workflow of convergence tests for k-points and energy cutoff',
    requires=['convergence_tests_dir'],
    optional=[],
    defaults={},
    prereqs=[],
))
def analyze_vasp_workflow_of_convergence_tests(
    convergence_tests_dir: str,
) -> dict:
    '''
    Analyze VASP workflow of convergence tests for k-points and energy cutoff
    '''
    try:
        os.path.exists(convergence_tests_dir)
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Invalid input parameters: {str(e)}'
        }
    
    try:
        runs_dir = convergence_tests_dir

        # Get all vasprun.xml files in the encut_tests subdirectory
        encut_tests_dir = os.path.join(runs_dir, 'encut_tests')
        if os.path.exists(encut_tests_dir):
            encut_tests_dict = {}
            for root, dirs, files in os.walk(encut_tests_dir):
                for file in files:
                    if file == 'vasprun.xml':
                        vasprun_path = os.path.join(root, file)
                        vasprun = Vasprun(vasprun_path)
                        final_energy = vasprun.final_energy
                        natoms = len(vasprun.atomic_symbols)
                        final_energy_per_atom = final_energy / natoms
                        encut_value = int(os.path.basename(root).split('_')[-1])
                        encut_tests_dict[encut_value] = final_energy_per_atom

        # Get all vasprun.xml files in the kpoint_tests subdirectory
        kpoint_tests_dir = os.path.join(runs_dir, 'kpoint_tests')
        if os.path.exists(kpoint_tests_dir):
            kpoint_tests_dict = {}
            for root, dirs, files in os.walk(kpoint_tests_dir):
                for file in files:
                    if file == 'vasprun.xml':
                        vasprun_path = os.path.join(root, file)
                        vasprun = Vasprun(vasprun_path)
                        final_energy = vasprun.final_energy
                        natoms = len(vasprun.atomic_symbols)
                        final_energy_per_atom = final_energy / natoms
                        kpoints_value = int(os.path.basename(root).split('_')[-1])
                        kpoint_tests_dict[kpoints_value] = final_energy_per_atom

        # Plot the results: Final Energy per Atom vs Encut and Kpoints
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend for plotting
        import matplotlib.pyplot as plt
        import seaborn as sns

        sns.set_theme(font_scale=1.2, style='whitegrid')
        matplotlib.rcParams['xtick.direction'] = 'in'
        matplotlib.rcParams['ytick.direction'] = 'in'

        # Plot Encut tests
        if encut_tests_dict:
            fig = plt.figure(figsize=(8, 6), constrained_layout=True)
            ax = plt.subplot()
            encut_values = sorted(encut_tests_dict.keys())
            encut_energies = [encut_tests_dict[encut] * 1000 for encut in encut_values]
            encut_energy_diffs = [encut_energies[i - 1] - encut_energies[i] for i in range(1, len(encut_energies))]
            sns.lineplot(x=encut_values[1:], y=encut_energy_diffs, marker='o', ax=ax, linestyle='-', linewidth=3.0, markersize=12, color='C0', markerfacecolor='C2')
            ax.axhline(y=1, color='r', linestyle='-', linewidth=1.0)
            ax.text(encut_values[-1], 1, 'Threshold < 1 meV/atom', color='r', ha='right', va='center', fontdict={'fontweight': 'bold'}, fontsize='small', bbox=dict(facecolor='white', edgecolor='none', pad=0.5))
            ax.set_xlabel('ENCUT (eV)')
            ax.set_ylabel('Energy Difference (meV/atom)')
            ax.set_title('Masgent ENCUT Convergence Test')
            plt.savefig(f'{runs_dir}/encut_tests.png', dpi=330)
            plt.close()

        # Plot Kpoint tests
        if kpoint_tests_dict:
            fig = plt.figure(figsize=(8, 6), constrained_layout=True)
            ax = plt.subplot()
            kpoint_values = sorted(kpoint_tests_dict.keys())
            kpoint_energies = [kpoint_tests_dict[kp] * 1000 for kp in kpoint_values]
            kpoint_energy_diffs = [kpoint_energies[i - 1] - kpoint_energies[i] for i in range(1, len(kpoint_energies))]
            sns.lineplot(x=kpoint_values[1:], y=kpoint_energy_diffs, marker='o', ax=ax, linestyle='-', linewidth=3.0, markersize=12, color='C0', markerfacecolor='C2')
            ax.axhline(y=1, color='r', linestyle='-', linewidth=1.0)
            ax.text(kpoint_values[-1], 1, 'Threshold < 1 meV/atom', color='r', ha='right', va='center', fontdict={'fontweight': 'bold'}, fontsize='small', bbox=dict(facecolor='white', edgecolor='none', pad=0.5))
            ax.set_xlabel('Kpoints Per Atom (kppa)')
            ax.set_ylabel('Energy Difference (meV/atom)')
            ax.set_title('Masgent Kpoint Convergence Test')
            plt.savefig(f'{runs_dir}/kpoint_tests.png', dpi=330)
            plt.close()

        return {
            'status': 'success',
            'message': f'Analyzed VASP workflow of convergence tests in {runs_dir}.',
            'encut_tests_plot': f'{runs_dir}/encut_tests.png' if encut_tests_dict else None,
            'kpoint_tests_plot': f'{runs_dir}/kpoint_tests.png' if kpoint_tests_dict else None,
        }

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error analyzing VASP convergence tests workflow: {str(e)}'
        }


@with_metadata(schemas.ToolMetadata(
    name='Analyze VASP workflow of equation of state (EOS) calculations',
    description='Analyze VASP workflow of equation of state (EOS) calculations',
    requires=['eos_dir'],
    optional=[],
    defaults={},
    prereqs=[],
))
def analyze_vasp_workflow_of_eos(
    eos_dir: str,
) -> dict:
    '''
    Analyze VASP workflow of equation of state (EOS) calculations
    '''
    try:
        os.path.exists(eos_dir)
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Invalid input parameters: {str(e)}'
        }
    
    try:
        runs_dir = eos_dir

        scales = []
        structures = []
        volumes = []
        energies = []

        for root, dirs, files in os.walk(runs_dir):
            for dir_name in dirs:
                if dir_name.startswith('scale_'):
                    scale_value = float(dir_name.split('_')[-1])
                    scales.append(scale_value)
                    structure_path = os.path.join(root, dir_name, 'POSCAR')
                    structure = Structure.from_file(structure_path)
                    structures.append(structure)
                    vasprun_path = os.path.join(root, dir_name, 'vasprun.xml')
                    vasprun = Vasprun(vasprun_path)
                    final_energy = vasprun.final_energy
                    natoms = len(vasprun.atomic_symbols)
                    final_energy_per_atom = final_energy / natoms
                    structure = vasprun.final_structure
                    volume = structure.volume / natoms
                    volumes.append(volume)
                    energies.append(final_energy_per_atom)
        eos_df = pd.DataFrame({'Scale': scales, 'Volume[Å³/atom]': volumes, 'Energy[eV/atom]': energies}).sort_values(by='Volume[Å³/atom]')
        eos_df.to_csv(f'{runs_dir}/eos_cal.csv', index=False, float_format='%.8f')

        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend for plotting
        import matplotlib.pyplot as plt
        import seaborn as sns

        volumes_fit, energies_fit = fit_eos(volumes, energies)
        eos_fit_df = pd.DataFrame({'Volume[Å³/atom]': volumes_fit, 'Energy[eV/atom]': energies_fit})
        eos_fit_df.to_csv(f'{runs_dir}/eos_fit.csv', index=False, float_format='%.8f')
        equilibrium_volume = volumes_fit[energies_fit.argmin()]
        scale_temp = scales[0]
        volume_temp = volumes[0]
        structure_temp = structures[0]
        volume_at_scale_1 = volume_temp / scale_temp
        structure_at_scale_1 = structure_temp.copy()
        structure_at_scale_1.scale_lattice(structure_temp.volume / scale_temp)
        equilibrium_scale = equilibrium_volume / volume_at_scale_1
        structure_equilibrium = structure_at_scale_1.copy()
        structure_equilibrium.scale_lattice(equilibrium_volume * len(structure_equilibrium))
        structure_equilibrium.to(filename=f'{runs_dir}/POSCAR_equilibrium')
        poscar_comments = f'# Generated by Masgent for EOS calculation with scale factor = {equilibrium_scale:.6f}, equilibrium volume = {equilibrium_volume:.6f} Å³/atom.'
        write_comments(f'{runs_dir}/POSCAR_equilibrium', 'poscar', poscar_comments)
        
        # Plot the EOS curve
        sns.set_theme(font_scale=1.2, style='whitegrid')
        matplotlib.rcParams['xtick.direction'] = 'in'
        matplotlib.rcParams['ytick.direction'] = 'in'
        fig = plt.figure(figsize=(8, 6), constrained_layout=True)
        ax = plt.subplot()
        ax.scatter(volumes, energies, color='C2', label='Calculated', s=150, edgecolors='white', linewidths=1, zorder=5)
        ax.scatter(equilibrium_volume, energies_fit.min(), color='C3', marker='*', s=300, label='Equilibrium', edgecolors='white', linewidths=1, zorder=5)
        ax.plot(volumes_fit, energies_fit, color='C0', linestyle='-', linewidth=3.0, label='Fitted')
        ax.set_xlabel('Volume (Å³/atom)')
        ax.set_ylabel('Energy (eV/atom)')
        ax.set_title('Masgent EOS')
        ax.legend(frameon=True, loc='upper right')
        plt.savefig(f'{runs_dir}/eos_curve.png', dpi=330)
        plt.close()

        return {
            'status': 'success',
            'message': f'Analyzed VASP workflow of EOS calculations in {runs_dir}.',
            'eos_fit_csv': f'{runs_dir}/eos_fit.csv',
            'eos_curve_plot': f'{runs_dir}/eos_curve.png',
            'poscar_equilibrium': f'{runs_dir}/POSCAR_equilibrium',
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error analyzing VASP EOS workflow: {str(e)}'
        }


@with_metadata(schemas.ToolMetadata(
    name='Analyze VASP workflow of elastic constants calculations',
    description='Analyze VASP workflow of elastic constants calculations',
    requires=['elastic_constants_dir'],
    optional=[],
    defaults={},
    prereqs=[],
))
def analyze_vasp_workflow_of_elastic_constants(
    elastic_constants_dir: str,
) -> dict:
    '''
    Analyze VASP workflow of elastic constants calculations
    '''
    try:
        os.path.exists(elastic_constants_dir)
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Invalid input parameters: {str(e)}'
        }
    
    try:
        runs_dir = elastic_constants_dir

        D_all = create_deformation_matrices()
        strains, stresses = [], []
        
        for D_dict in D_all:
            folder_name = list(D_dict.keys())[0]
            D = D_dict[folder_name]
            strains.append(D)

            deform_dir = os.path.join(runs_dir, folder_name)
            vasprun_path = os.path.join(deform_dir, 'vasprun.xml')
            if os.path.exists(vasprun_path):
                vasprun = Vasprun(vasprun_path)
                stress = vasprun.ionic_steps[-1]['stress'] # in kBar
                stresses.append(stress)

        # Substract the stress of the undeformed structure
        eq_stress = stresses[0]
        strains = strains[1:]
        stresses = stresses[1:]

        from pymatgen.analysis.elasticity.strain import Strain
        from pymatgen.analysis.elasticity.stress import Stress
        from pymatgen.analysis.elasticity.elastic import ElasticTensor
        
        pmg_strains = [Strain(eps) for eps in strains]
        pmg_stresses = [Stress(sig) for sig in stresses]
        C = ElasticTensor.from_independent_strains(strains=pmg_strains, stresses=pmg_stresses, eq_stress=eq_stress, vasp=True)
        elastic_constants = C.voigt
        K_V = C.k_voigt
        K_R = C.k_reuss
        K_H = C.k_vrh
        G_V = C.g_voigt
        G_R = C.g_reuss
        G_H = C.g_vrh
        # Save elastic constants and properties to txt
        with open(f'{runs_dir}/elastic_constants.txt', 'w') as f:
            f.write(f'# Elastic constants and moduli calculated by Masgent\n')
            f.write(f'\nElastic Constants (GPa):\n')
            for row in elastic_constants:
                f.write('\t'.join([f'{val:.2f}' for val in row]) + '\n')
            f.write('\nMechanical Properties (GPa):')
            f.write(f'\nBulk Modulus (Voigt):\t\t{K_V:.2f}')
            f.write(f'\nBulk Modulus (Reuss):\t\t{K_R:.2f}')
            f.write(f'\nBulk Modulus (Hill):\t\t{K_H:.2f}')
            f.write(f'\nShear Modulus (Voigt):\t\t{G_V:.2f}')
            f.write(f'\nShear Modulus (Reuss):\t\t{G_R:.2f}')
            f.write(f'\nShear Modulus (Hill):\t\t{G_H:.2f}')

        return {
            'status': 'success',
            'message': f'Analyzed VASP workflow of elastic constants calculations in {runs_dir}.',
            'elastic_constants_txt': f'{runs_dir}/elastic_constants.txt',
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error analyzing VASP elastic constants workflow: {str(e)}'
        }


@with_metadata(schemas.ToolMetadata(
    name='Analyze VASP workflow of ab initio molecular dynamics (AIMD) simulations',
    description='Analyze VASP workflow of ab initio molecular dynamics (AIMD) simulations',
    requires=['aimd_dir', 'specie'],
    optional=[],
    defaults={},
    prereqs=[],
))
def analyze_vasp_workflow_of_aimd(
    aimd_dir: str,
    specie: str,
) -> dict:
    '''
    Analyze VASP workflow of ab initio molecular dynamics (AIMD) simulations
    '''
    try:
        os.path.exists(aimd_dir)
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Invalid input parameters: {str(e)}'
        }
    
    try:
        schemas.CheckElement(element_symbol=specie)
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Invalid input parameters: {str(e)}'
        }

    try: 
        runs_dir = aimd_dir

        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend for plotting
        import matplotlib.pyplot as plt
        import seaborn as sns

        sns.set_theme(font_scale=1.2, style='whitegrid')
        matplotlib.rcParams['xtick.direction'] = 'in'
        matplotlib.rcParams['ytick.direction'] = 'in'

        D_data= []
        for root, dirs, files in os.walk(runs_dir):
            for dir_name in dirs:
                if dir_name.startswith('T_') and dir_name.endswith('K'):
                    temperature = int(dir_name[2:-1])
                    folder_path = os.path.join(root, dir_name)
                    
                    # Parse the time step from INCAR
                    incar_path = os.path.join(folder_path, 'INCAR')
                    with open(incar_path, 'r') as f:
                        lines = f.readlines()
                        POTIM = 1.0
                        for line in lines:
                            if line.strip().startswith('POTIM'):
                                POTIM = float(line.strip().split('=')[1])
                    
                    # Parse the temperature and energy from OSZICAR
                    oszicar_path = os.path.join(folder_path, 'OSZICAR')
                    with open(oszicar_path, 'r') as f:
                        lines = f.readlines()
                        T_E_data = []
                        for line in lines:
                            if 'T=' in line:
                                T = float(line.split()[2])
                                E = float(line.split()[4])
                                T_E_data.append((T, E))
                    T_E_df = pd.DataFrame(T_E_data, columns=['Temperature (K)', 'Energy (eV)'])
                    T_E_df.to_csv(f'{folder_path}/aimd_temperature_energy.csv', index=False, float_format='%.6f')
                    
                    # Plot Time vs Temperature and Energy
                    time = np.arange(len(T_E_df)) * POTIM / 1000  # Convert to ps
                    fig, ax = plt.subplots(2, 1, figsize=(8, 6), constrained_layout=True, sharex=True)
                    ax[0].plot(time, T_E_df['Temperature (K)'], color='C0', label='Temperature', linewidth=1.0)
                    ax[0].hlines(temperature, 0, time[-1], colors='C3', linestyles='dashed', label='Target Temperature')
                    ax[0].set_ylabel('Temperature (K)')
                    ax[0].set_title(f'Masgent AIMD Temperature & Energy at {temperature} K')
                    ax[0].legend(frameon=True, loc='upper right')
                    ax[1].plot(time, T_E_df['Energy (eV)'], color='C1', label='Energy', linewidth=1.0)
                    ax[1].set_ylabel('Energy (eV)')
                    ax[1].set_xlabel('Time (ps)')
                    ax[1].legend(frameon=True, loc='upper right')
                    plt.savefig(f'{folder_path}/aimd_temperature_energy.png', dpi=330)
                    plt.close()

                    # Parse MSD, diffusion coefficient, and conductivity from XDATCAR
                    xdatcar_path = os.path.join(folder_path, 'XDATCAR')
                    traj = read(xdatcar_path, index=':')
                    indices = [i for i, a in enumerate(traj[0]) if a.symbol == specie]
                    positions_all = np.array([traj[i].get_positions() for i in range(len(traj))])
                    cell = traj[0].cell.array
                    unwrapped = positions_all.copy()
                    for i in range(1, len(positions_all)):
                        delta = positions_all[i] - positions_all[i-1]
                        delta -= np.round(delta @ np.linalg.inv(cell)) @ cell
                        unwrapped[i] = unwrapped[i-1] + delta
                    positions = unwrapped[:, indices]
                    positions_x = positions[:, :, 0]
                    positions_y = positions[:, :, 1]
                    positions_z = positions[:, :, 2]
                    msd_x = np.mean((positions_x - positions_x[0])**2, axis=1)
                    msd_y = np.mean((positions_y - positions_y[0])**2, axis=1)
                    msd_z = np.mean((positions_z - positions_z[0])**2, axis=1)
                    msd_total = np.mean(np.sum((positions - positions[0])**2, axis=2), axis=1)
                    time_ps = np.arange(len(msd_total)) * POTIM / 1000  # Convert to ps
                    msd_df = pd.DataFrame({
                        'Time (ps)': time_ps,
                        'MSD_x (Å²)': msd_x,
                        'MSD_y (Å²)': msd_y,
                        'MSD_z (Å²)': msd_z,
                        'MSD_total (Å²)': msd_total
                    })
                    msd_df.to_csv(f'{folder_path}/aimd_msd.csv', index=False, float_format='%.6f')
                    
                    # Plot time vs MSD
                    fig = plt.figure(figsize=(8, 6), constrained_layout=True)
                    ax = plt.subplot()
                    ax.plot(time_ps, msd_x, label='MSD_x', color='C0', linewidth=1.0)
                    ax.plot(time_ps, msd_y, label='MSD_y', color='C1', linewidth=1.0)
                    ax.plot(time_ps, msd_z, label='MSD_z', color='C2', linewidth=1.0)
                    ax.plot(time_ps, msd_total, label='MSD_total', color='C3', linewidth=1.0)
                    ax.set_xlabel('Time (ps)')
                    ax.set_ylabel('Mean Squared Displacement (Å²)')
                    ax.set_title(f'Masgent AIMD Mean Squared Displacement at {temperature} K')
                    ax.legend(frameon=True, loc='upper left')
                    plt.savefig(f'{folder_path}/aimd_msd.png', dpi=330)
                    plt.close()
                    
                    # Calculate diffusion coefficient from linear fit of MSD_total
                    slope, intercept = np.polyfit(time_ps, msd_total, 1)
                    diffusivity = slope / 6 / 1e4  # cm^2/s
                    D_data.append((temperature, diffusivity))

        D_df = pd.DataFrame(D_data, columns=['Temperature (K)', 'Diffusion Coefficient (cm²/s)']).sort_values(by='Temperature (K)')
        D_df.to_csv(f'{runs_dir}/aimd_diffusion_coefficients.csv', index=False, float_format='%.6e')

        # Fit Arrhenius plot
        D_df['Diffusion Coefficient (cm²/s)'] = D_df['Diffusion Coefficient (cm²/s)'].apply(lambda x: x if x > 0 else 1e-20)
        logD = np.log10(D_df['Diffusion Coefficient (cm²/s)'])
        inv_T = 1000 / D_df['Temperature (K)']
        slope, intercept = np.polyfit(inv_T, logD, 1)
        
        # Calculate activation energy from slope
        from ase.units import J, mol
        R = 8.31446261815324  # J/(mol·K)
        activation_energy = -slope * R * np.log(10) * 1000 * 1000 * (J / mol)  # in meV
        with open(f'{runs_dir}/aimd_activation_energy.txt', 'w') as f:
            f.write(f'# Masgent AIMD Analysis\n\n')
            f.write(f'Activation Energy: {activation_energy:.2f} meV\n')
        
        # Plot Arrhenius plot
        fig = plt.figure(figsize=(8, 6), constrained_layout=True)
        ax = plt.subplot()
        x_fit = np.linspace(min(inv_T), max(inv_T), 100)
        y_fit = slope * x_fit + intercept
        ax.scatter(inv_T, logD, color='C2', s=150, edgecolors='white', linewidths=1, label='Calculated', zorder=5)
        ax.plot(x_fit, y_fit, color='C0', linestyle='--', linewidth=3.0, label='Fitted')
        ax.text(0.05, 0.1, f'Activation Energy: {activation_energy:.2f} meV', color='C3', transform=ax.transAxes, fontsize='small', verticalalignment='top', fontdict={'weight': 'bold'}, bbox=dict(facecolor='white', edgecolor='none', pad=0.5))
        ax.set_xlabel('1000 / T $(K^{-1})$')
        ax.set_ylabel('$log_{10}D$ $(cm^2/s)$')
        ax.set_title('Masgent AIMD Arrhenius Plot of Diffusion Coefficient')
        ax.legend(frameon=True, loc='upper right')
        plt.savefig(f'{runs_dir}/aimd_arrhenius_plot.png', dpi=330)
        plt.close()


        return {
            'status': 'success',
            'message': f'Analyzed VASP workflow of AIMD simulations in {runs_dir}.',
            'diffusion_coefficients_csv': f'{runs_dir}/aimd_diffusion_coefficients.csv',
            'arrhenius_plot': f'{runs_dir}/aimd_arrhenius_plot.png',
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error analyzing VASP AIMD workflow: {str(e)}'
        }


@with_metadata(schemas.ToolMetadata(
    name='Analyze VASP workflow of nudged elastic band (NEB) calculations',
    description='Analyze VASP workflow of nudged elastic band (NEB) calculations',
    requires=['neb_dir'],
    optional=[],
    defaults={},
    prereqs=[],
))
def analyze_vasp_workflow_of_neb(
    neb_dir: str,
) -> dict:
    '''
    Analyze VASP workflow of nudged elastic band (NEB) calculations
    '''
    try:
        os.path.exists(neb_dir)
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Invalid input parameters: {str(e)}'
        }
    
    try:
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend for plotting
        import matplotlib.pyplot as plt
        import seaborn as sns
        from pymatgen.analysis.transition_state import NEBAnalysis
        
        runs_dir = neb_dir

        neb = NEBAnalysis.from_dir(runs_dir)
        scale = 1 / neb.r[-1]
        xs = np.arange(0, np.max(neb.r), 0.01) * scale
        ys = neb.spline(xs / scale) * 1000
        data = pd.DataFrame({'Normalized Reaction Coordinate': xs, 'Energy (meV)': ys})
        data.to_csv(f'{runs_dir}/neb_data_spline.csv', index=False, float_format='%.8f')

        x = neb.r * scale
        relative_energies = neb.energies - neb.energies[0]
        y = relative_energies * 1000
        data_points = pd.DataFrame({'Normalized Reaction Coordinate': x, 'Relative Energy (meV)': y})
        data_points.to_csv(f'{runs_dir}/neb_data_points.csv', index=False, float_format='%.8f')

        energy_barrier = np.max(ys) - np.min(ys)
        with open(f'{runs_dir}/energy_barrier.txt', 'w') as f:
            f.write('# Masgent NEB Analysis\n\n')
            f.write(f'Energy Barrier: {energy_barrier:.8f} meV\n')

        # Plot NEB energy profile
        sns.set_theme(font_scale=1.2, style='whitegrid')
        matplotlib.rcParams['xtick.direction'] = 'in'
        matplotlib.rcParams['ytick.direction'] = 'in'
        fig = plt.figure(figsize=(8, 6), constrained_layout=True)
        ax = plt.subplot()
        # Scatter and line plot
        ax.plot(xs, ys, color='C0', linewidth=3.0, zorder=5)
        ax.scatter(x, y, color='C2', s=150, edgecolors='white', linewidths=1, zorder=6)
        # Plot the energy barrier
        x_mid = (xs[np.argmax(ys)] + xs[np.argmin(ys)]) / 2
        ax.hlines(np.max(ys), xmin=x_mid-0.2, xmax=x_mid+0.2, colors='C3', linestyles='-', linewidth=1.0)
        ax.hlines(np.min(ys), xmin=x_mid-0.2, xmax=x_mid+0.2, colors='C3', linestyles='-', linewidth=1.0)
        ax.vlines(x_mid, ymin=np.min(ys), ymax=np.max(ys), colors='C3', linestyles='-', linewidth=1.0)
        ax.text(x_mid, np.max(ys), f'{energy_barrier:.2f} meV', color='C3', ha='center', va='center', fontdict={'weight': 'bold'}, fontsize='small', bbox=dict(facecolor='white', edgecolor='none', pad=0.5))
        ax.set_xlabel('Normalized Reaction Coordinate')
        ax.set_ylabel('Energy (meV)')
        ax.set_title('Masgent NEB Analysis')
        plt.savefig(f'{runs_dir}/neb_energy_profile.png', dpi=330)
        plt.close()

        return {
            'status': 'success',
            'message': f'Analyzed VASP workflow of NEB calculations in {runs_dir}.',
            'neb_data_spline_csv': f'{runs_dir}/neb_data_spline.csv',
            'neb_data_points_csv': f'{runs_dir}/neb_data_points.csv',
            'energy_barrier_txt': f'{runs_dir}/energy_barrier.txt',
            'neb_energy_profile_plot': f'{runs_dir}/neb_energy_profile.png',
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error analyzing VASP NEB workflow: {str(e)}'
        }