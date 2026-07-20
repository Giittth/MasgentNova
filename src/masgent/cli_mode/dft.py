"""DFT 相关命令（1.x 系列）"""

import os
import time
from typing import List
from bullet import Bullet, colors
from yaspin import yaspin
from yaspin.spinners import Spinners

import masgent.tools as tools
from masgent.cli_mode.base import bullet_menu, handle_keyboard_interrupt
from masgent.cli_mode.cli_run import register, run_command, check_poscar
from masgent.utils import (
    color_input,
    color_print,
    clear_and_print_entry_message,
    global_commands,
    start_new_session,
    exit_and_cleanup,
)
from masgent.models import schemas
from masgent._config import config


#############################################
#                                           #
# Below are implementations of sub-commands #
#                                           #
#############################################

@register('1.1.1', 'Generate POSCAR from chemical formula.')
@handle_keyboard_interrupt
def command_1_1_1():
    while True:
        formula = color_input('\nEnter chemical formula (e.g., NaCl): ', 'yellow').strip()
        if not formula:
            continue
        try:
            schemas.GenerateVaspPoscarSchema(formula=formula)
            break
        except Exception:
            color_print(f'[Error] Invalid formula: {formula}, please double check and try again.\n', 'red')

    result = tools.generate_vasp_poscar(formula=formula)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.1.2', 'Convert POSCAR coordinates (Direct <-> Cartesian).')
@handle_keyboard_interrupt
def command_1_1_2():
    while True:
        clear_and_print_entry_message()
        choices = [
            'Direct coordinates     —>  Cartesian coordinates',
            'Cartesian coordinates  —>  Direct coordinates',
        ]
        user_input = bullet_menu(choices, title='\nSelect conversion direction:')
        if user_input is None:
            return
        if user_input.startswith('Direct coordinates'):
            to_cartesian = True
            break
        elif user_input.startswith('Cartesian coordinates'):
            to_cartesian = False
            break
        else:
            continue

    poscar_path = check_poscar()
    if poscar_path is None:
        return

    result = tools.convert_poscar_coordinates(poscar_path=poscar_path, to_cartesian=to_cartesian)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.1.3', 'Convert structure file formats (CIF, POSCAR, XYZ).')
@handle_keyboard_interrupt
def command_1_1_3():
    while True:
        clear_and_print_entry_message()
        choices = [
            'POSCAR  ->  CIF',
            'POSCAR  ->  XYZ',
            'CIF     ->  POSCAR',
            'CIF     ->  XYZ',
            'XYZ     ->  POSCAR',
            'XYZ     ->  CIF',
        ]
        user_input = bullet_menu(choices, title='\nSelect conversion direction:')
        if user_input is None:
            return

        if user_input.startswith('POSCAR') and user_input.endswith('CIF'):
            input_format, output_format = 'POSCAR', 'CIF'
            break
        elif user_input.startswith('POSCAR') and user_input.endswith('XYZ'):
            input_format, output_format = 'POSCAR', 'XYZ'
            break
        elif user_input.startswith('CIF') and user_input.endswith('POSCAR'):
            input_format, output_format = 'CIF', 'POSCAR'
            break
        elif user_input.startswith('CIF') and user_input.endswith('XYZ'):
            input_format, output_format = 'CIF', 'XYZ'
            break
        elif user_input.startswith('XYZ') and user_input.endswith('POSCAR'):
            input_format, output_format = 'XYZ', 'POSCAR'
            break
        elif user_input.startswith('XYZ') and user_input.endswith('CIF'):
            input_format, output_format = 'XYZ', 'CIF'
            break
        else:
            continue

    while True:
        input_path = color_input('\nEnter path to input structure file: ', 'yellow').strip()
        if not input_path:
            continue
        try:
            schemas.ConvertStructureFormatSchema(input_path=input_path, input_format=input_format, output_format=output_format)
            break
        except Exception:
            color_print(f'[Error] Invalid input: {input_path}, please double check and try again.\n', 'red')

    result = tools.convert_structure_format(input_path=input_path, input_format=input_format, output_format=output_format)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.1.4', 'Generate structure with defects (Vacancy, Interstitial, Substitution).')
@handle_keyboard_interrupt
def command_1_1_4():
    while True:
        clear_and_print_entry_message()
        choices = [
            'Vacancy                 ->  Randomly remove atoms of a selected element',
            'Substitution            ->  Randomly substitute atoms of a selected element with defect element',
            'Interstitial (Voronoi)  ->  Add atom at interstitial sites using Voronoi method',
        ]
        user_input = bullet_menu(choices, title='\nSelect defect type:')
        if user_input is None:
            return

        if user_input.startswith('Vacancy'):
            run_command('vacancy')
            break
        elif user_input.startswith('Interstitial (Voronoi)'):
            run_command('interstitial')
            break
        elif user_input.startswith('Substitution'):
            run_command('substitution')
            break
        else:
            continue


@register('vacancy', 'Generate structure with vacancy defects.')
@handle_keyboard_interrupt
def command_vacancy():
    poscar_path = check_poscar()
    if poscar_path is None:
        return

    while True:
        original_element = color_input('\nEnter the element to remove (e.g., Na): ', 'yellow').strip()
        if not original_element:
            continue
        try:
            schemas.CheckElement(element_symbol=original_element)
            schemas.CheckElementExistence(poscar_path=poscar_path, element_symbol=original_element)
            break
        except Exception:
            color_print(f'[Error] Invalid element {original_element}, please double check and try again.\n', 'red')

    while True:
        defect_amount_str = color_input('\nEnter the defect amount (fraction between 0 and 1, or atom count >=1): ', 'yellow').strip()
        if not defect_amount_str:
            continue
        try:
            if '.' in defect_amount_str:
                defect_amount = float(defect_amount_str)
            else:
                defect_amount = int(defect_amount_str)
            schemas.GenerateVaspPoscarWithVacancyDefects(poscar_path=poscar_path, original_element=original_element, defect_amount=defect_amount)
            break
        except Exception:
            color_print(f'[Error] Invalid defect amount: {defect_amount_str}, please double check and try again.\n', 'red')

    result = tools.generate_vasp_poscar_with_vacancy_defects(poscar_path=poscar_path, original_element=original_element, defect_amount=defect_amount)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('substitution', 'Generate structure with substitution defects.')
@handle_keyboard_interrupt
def command_substitution():
    poscar_path = check_poscar()
    if poscar_path is None:
        return

    while True:
        original_element = color_input('\nEnter the target element to be substituted (e.g., Na): ', 'yellow').strip()
        if not original_element:
            continue
        try:
            schemas.CheckElement(element_symbol=original_element)
            schemas.CheckElementExistence(poscar_path=poscar_path, element_symbol=original_element)
            break
        except Exception:
            color_print(f'[Error] Invalid element {original_element}, please double check and try again.\n', 'red')

    while True:
        defect_element = color_input('\nEnter the defect element to substitute in (e.g., K): ', 'yellow').strip()
        if not defect_element:
            continue
        try:
            schemas.CheckElement(element_symbol=defect_element)
            break
        except Exception:
            color_print(f'[Error] Invalid element {defect_element}, please double check and try again.\n', 'red')

    while True:
        defect_amount_str = color_input('\nEnter the defect amount (fraction between 0 and 1, or atom count >=1): ', 'yellow').strip()
        if not defect_amount_str:
            continue
        try:
            if '.' in defect_amount_str:
                defect_amount = float(defect_amount_str)
            else:
                defect_amount = int(defect_amount_str)
            schemas.GenerateVaspPoscarWithSubstitutionDefects(poscar_path=poscar_path, original_element=original_element, defect_element=defect_element, defect_amount=defect_amount)
            break
        except Exception:
            color_print(f'[Error] Invalid defect amount: {defect_amount_str}, please double check and try again.\n', 'red')

    result = tools.generate_vasp_poscar_with_substitution_defects(poscar_path=poscar_path, original_element=original_element, defect_element=defect_element, defect_amount=defect_amount)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('interstitial', 'Generate structure with interstitial (Voronoi) defects.')
@handle_keyboard_interrupt
def command_interstitial():
    poscar_path = check_poscar()
    if poscar_path is None:
        return

    while True:
        defect_element = color_input('\nEnter the defect element to add (e.g., Na): ', 'yellow').strip()
        if not defect_element:
            continue
        try:
            schemas.GenerateVaspPoscarWithInterstitialDefects(poscar_path=poscar_path, defect_element=defect_element)
            break
        except Exception:
            color_print(f'[Error] Invalid element {defect_element}, please double check and try again.\n', 'red')

    print('')
    with yaspin(Spinners.dots, text='Generating interstitial defects... See details in the log file.', color='cyan') as sp:
        result = tools.generate_vasp_poscar_with_interstitial_defects(poscar_path=poscar_path, defect_element=defect_element)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.1.5', 'Generate supercell from POSCAR with specified scaling matrix.')
@handle_keyboard_interrupt
def command_1_1_5():
    poscar_path = check_poscar()
    if poscar_path is None:
        return

    while True:
        scaling_matrix = color_input('\nEnter the scaling matrix for 2x2x2 supercell (e.g., 2 0 0; 0 2 0; 0 0 2): ', 'yellow').strip()
        if not scaling_matrix:
            continue
        try:
            schemas.GenerateSupercellFromPoscar(poscar_path=poscar_path, scaling_matrix=scaling_matrix)
            break
        except Exception:
            color_print(f'[Error] Invalid scaling matrix: {scaling_matrix}, please double check and try again.\n', 'red')

    result = tools.generate_supercell_from_poscar(poscar_path=poscar_path, scaling_matrix=scaling_matrix)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.1.6', 'Generate special quasi-random structure (SQS) from POSCAR.')
@handle_keyboard_interrupt
def command_1_1_6():
    poscar_path = check_poscar()
    if poscar_path is None:
        return

    while True:
        target_configurations_str = color_input('\nEnter target configurations (e.g., La: La=0.5,Y=0.5; Co: Al=0.75,Co=0.25): ', 'yellow').strip()
        if not target_configurations_str:
            continue
        try:
            target_configurations = {}
            for sublattice_str in target_configurations_str.split(';'):
                sublattice_str = sublattice_str.strip()
                if not sublattice_str:
                    continue
                element, conc_str = sublattice_str.split(':')
                element = element.strip()
                conc_pairs = conc_str.split(',')
                conc_dict = {}
                for pair in conc_pairs:
                    species, conc = pair.split('=')
                    conc_dict[species.strip()] = float(conc.strip())
                target_configurations[element] = conc_dict
            schemas.GenerateSqsFromPoscar(poscar_path=poscar_path, target_configurations=target_configurations)
            break
        except Exception as e:
            print(e)
            color_print(f'[Error] Invalid target configurations: {target_configurations_str}, please double check and try again.\n', 'red')

    while True:
        cutoffs_str = color_input('\nEnter cluster cutoffs in Å for pairs, triplets, and quadruplets (e.g., 8.0 4.0 4.0): ', 'yellow').strip()
        if not cutoffs_str:
            continue
        try:
            cutoffs = [float(x) for x in cutoffs_str.split()]
            schemas.GenerateSqsFromPoscar(poscar_path=poscar_path, target_configurations=target_configurations, cutoffs=cutoffs)
            break
        except Exception:
            color_print(f'[Error] Invalid cutoffs: {cutoffs_str}, please double check and try again.\n', 'red')

    while True:
        max_supercell_size_str = color_input('\nEnter maximum supercell size (e.g., 8): ', 'yellow').strip()
        if not max_supercell_size_str:
            continue
        try:
            max_supercell_size = int(max_supercell_size_str)
            schemas.GenerateSqsFromPoscar(poscar_path=poscar_path, target_configurations=target_configurations, cutoffs=cutoffs, max_supercell_size=max_supercell_size)
            break
        except Exception:
            color_print(f'[Error] Invalid maximum supercell size: {max_supercell_size_str}, please double check and try again.\n', 'red')

    while True:
        mc_steps_str = color_input('\nEnter number of Monte Carlo steps (e.g., >=1000): ', 'yellow').strip()
        if not mc_steps_str:
            continue
        try:
            mc_steps = int(mc_steps_str)
            schemas.GenerateSqsFromPoscar(poscar_path=poscar_path, target_configurations=target_configurations, cutoffs=cutoffs, max_supercell_size=max_supercell_size, mc_steps=mc_steps)
            break
        except Exception:
            color_print(f'[Error] Invalid number of Monte Carlo steps: {mc_steps_str}, please double check and try again.\n', 'red')

    print('')
    with yaspin(Spinners.dots, text='Generating SQS... See details in the log file.', color='cyan') as sp:
        result = tools.generate_sqs_from_poscar(
            poscar_path=poscar_path,
            target_configurations=target_configurations,
            cutoffs=cutoffs,
            max_supercell_size=max_supercell_size,
            mc_steps=mc_steps,
        )
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.1.7', 'Generate surface slab from POSCAR with specified Miller indices, vacuum thickness, and slab layers.')
@handle_keyboard_interrupt
def command_1_1_7():
    poscar_path = check_poscar()
    if poscar_path is None:
        return

    while True:
        miller_indices_str = color_input('\nEnter the Miller indices (e.g., 1 1 1): ', 'yellow').strip()
        if not miller_indices_str:
            continue
        try:
            miller_indices = [int(x) for x in miller_indices_str.split()]
            schemas.GenerateSurfaceSlabFromPoscar(poscar_path=poscar_path, miller_indices=miller_indices)
            break
        except Exception:
            color_print(f'[Error] Invalid Miller indices: {miller_indices_str}, please double check and try again.\n', 'red')

    while True:
        vacuum_thickness_str = color_input('\nEnter the vacuum thickness in Å (e.g., 15.0): ', 'yellow').strip()
        if not vacuum_thickness_str:
            continue
        try:
            vacuum_thickness = float(vacuum_thickness_str)
            schemas.GenerateSurfaceSlabFromPoscar(poscar_path=poscar_path, miller_indices=miller_indices, vacuum_thickness=vacuum_thickness)
            break
        except Exception:
            color_print(f'[Error] Invalid vacuum thickness: {vacuum_thickness_str}, please double check and try again.\n', 'red')

    while True:
        slab_layers_str = color_input('\nEnter the number of slab layers (e.g., 4): ', 'yellow').strip()
        if not slab_layers_str:
            continue
        try:
            slab_layers = int(slab_layers_str)
            schemas.GenerateSurfaceSlabFromPoscar(poscar_path=poscar_path, miller_indices=miller_indices, vacuum_thickness=vacuum_thickness, slab_layers=slab_layers)
            break
        except Exception:
            color_print(f'[Error] Invalid slab layers: {slab_layers_str}, please double check and try again.\n', 'red')

    result = tools.generate_surface_slab_from_poscar(poscar_path=poscar_path, miller_indices=miller_indices, vacuum_thickness=vacuum_thickness, slab_layers=slab_layers)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.1.8', 'Generate interface structure from two POSCAR files with specified parameters.')
@handle_keyboard_interrupt
def command_1_1_8():
    while True:
        lower_poscar_path = color_input('\nSelect the lower POSCAR file: ', 'yellow').strip()
        if not lower_poscar_path:
            continue
        try:
            schemas.CheckPoscar(poscar_path=lower_poscar_path)
            break
        except Exception:
            color_print(f'[Error] Invalid POSCAR: {lower_poscar_path}, please double check and try again.\n', 'red')

    while True:
        upper_poscar_path = color_input('\nSelect the upper POSCAR file: ', 'yellow').strip()
        if not upper_poscar_path:
            continue
        try:
            schemas.CheckPoscar(poscar_path=upper_poscar_path)
            break
        except Exception:
            color_print(f'[Error] Invalid POSCAR: {upper_poscar_path}, please double check and try again.\n', 'red')

    while True:
        hkl_str = color_input('\nEnter the Miller indices for the lower and upper surfaces (e.g., 1 0 0; 1 0 0): ', 'yellow').strip()
        if not hkl_str:
            continue
        try:
            lower_hkl = [int(x) for x in hkl_str.split(';')[0].strip().split()]
            upper_hkl = [int(x) for x in hkl_str.split(';')[1].strip().split()]
            schemas.GenerateInterfaceFromPoscars(lower_poscar_path=lower_poscar_path, upper_poscar_path=upper_poscar_path, lower_hkl=lower_hkl, upper_hkl=upper_hkl)
            break
        except Exception:
            color_print(f'[Error] Invalid Miller indices: {hkl_str}, please double check and try again.\n', 'red')

    while True:
        slab_layers_str = color_input('\nEnter the number of slab layers for the lower and upper slabs (e.g., 4 4): ', 'yellow').strip()
        if not slab_layers_str:
            continue
        try:
            lower_slab_layers = int(slab_layers_str.split()[0].strip())
            upper_slab_layers = int(slab_layers_str.split()[1].strip())
            schemas.GenerateInterfaceFromPoscars(lower_poscar_path=lower_poscar_path, upper_poscar_path=upper_poscar_path, lower_hkl=lower_hkl, upper_hkl=upper_hkl, lower_slab_layers=lower_slab_layers, upper_slab_layers=upper_slab_layers)
            break
        except Exception:
            color_print(f'[Error] Invalid slab layers: {slab_layers_str}, please double check and try again.\n', 'red')

    while True:
        slab_vacuum_str = color_input('\nEnter the vacuum thickness in Å (e.g., 15.0): ', 'yellow').strip()
        if not slab_vacuum_str:
            continue
        try:
            slab_vacuum = float(slab_vacuum_str)
            schemas.GenerateInterfaceFromPoscars(lower_poscar_path=lower_poscar_path, upper_poscar_path=upper_poscar_path, lower_hkl=lower_hkl, upper_hkl=upper_hkl, lower_slab_layers=lower_slab_layers, upper_slab_layers=upper_slab_layers, slab_vacuum=slab_vacuum)
            break
        except Exception:
            color_print(f'[Error] Invalid vacuum thickness: {slab_vacuum_str}, please double check and try again.\n', 'red')

    while True:
        area_str = color_input('\nEnter the minimum and maximum interface area to search in Å² (e.g., 50.0 500.0): ', 'yellow').strip()
        if not area_str:
            continue
        try:
            min_area = float(area_str.split()[0].strip())
            max_area = float(area_str.split()[1].strip())
            schemas.GenerateInterfaceFromPoscars(lower_poscar_path=lower_poscar_path, upper_poscar_path=upper_poscar_path, lower_hkl=lower_hkl, upper_hkl=upper_hkl, lower_slab_layers=lower_slab_layers, upper_slab_layers=upper_slab_layers, slab_vacuum=slab_vacuum, min_area=min_area, max_area=max_area)
            break
        except Exception:
            color_print(f'[Error] Invalid interface area: {area_str}, please double check and try again.\n', 'red')

    while True:
        interface_gap_str = color_input('\nEnter the interface gap in Å (e.g., 2.0): ', 'yellow').strip()
        if not interface_gap_str:
            continue
        try:
            interface_gap = float(interface_gap_str)
            schemas.GenerateInterfaceFromPoscars(lower_poscar_path=lower_poscar_path, upper_poscar_path=upper_poscar_path, lower_hkl=lower_hkl, upper_hkl=upper_hkl, lower_slab_layers=lower_slab_layers, upper_slab_layers=upper_slab_layers, slab_vacuum=slab_vacuum, min_area=min_area, max_area=max_area, interface_gap=interface_gap)
            break
        except Exception:
            color_print(f'[Error] Invalid interface gap: {interface_gap_str}, please double check and try again.\n', 'red')

    while True:
        tolerance_str = color_input('\nEnter the lattice vector tolerance (%) and angle tolerance (degrees) (e.g., 5.0 5.0): ', 'yellow').strip()
        if not tolerance_str:
            continue
        try:
            uv_tolerance = float(tolerance_str.split()[0].strip())
            angle_tolerance = float(tolerance_str.split()[1].strip())
            schemas.GenerateInterfaceFromPoscars(lower_poscar_path=lower_poscar_path, upper_poscar_path=upper_poscar_path, lower_hkl=lower_hkl, upper_hkl=upper_hkl, lower_slab_layers=lower_slab_layers, upper_slab_layers=upper_slab_layers, slab_vacuum=slab_vacuum, min_area=min_area, max_area=max_area, interface_gap=interface_gap, uv_tolerance=uv_tolerance, angle_tolerance=angle_tolerance)
            break
        except Exception:
            color_print(f'[Error] Invalid lattice vector tolerance: {tolerance_str}, please double check and try again.\n', 'red')

    while True:
        shape_filter_str = color_input('\nDo you want to apply shape filtering to only keep the most square-like interface? [y/n]: ', 'yellow').strip().lower()
        if not shape_filter_str:
            continue
        if shape_filter_str == 'y':
            shape_filter = True
            break
        elif shape_filter_str == 'n':
            shape_filter = False
            break
        else:
            continue

    print('')
    with yaspin(Spinners.dots, text='Generating interface structure... See details in the log file.', color='cyan') as sp:
        result = tools.generate_interface_from_poscars(
            lower_poscar_path=lower_poscar_path,
            upper_poscar_path=upper_poscar_path,
            lower_hkl=lower_hkl,
            upper_hkl=upper_hkl,
            lower_slab_layers=lower_slab_layers,
            upper_slab_layers=upper_slab_layers,
            slab_vacuum=slab_vacuum,
            min_area=min_area,
            max_area=max_area,
            interface_gap=interface_gap,
            uv_tolerance=uv_tolerance,
            angle_tolerance=angle_tolerance,
            shape_filter=shape_filter,
        )
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.1.9', 'Visualize structure from POSCAR file.')
@handle_keyboard_interrupt
def command_1_1_9():
    poscar_path = check_poscar()
    if poscar_path is None:
        return

    result = tools.visualize_structure_from_poscar(poscar_path=poscar_path)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.2.1', 'Prepare full VASP input files (INCAR, KPOINTS, POTCAR, POSCAR).')
@handle_keyboard_interrupt
def command_1_2_1():
    choices = [
        'MPMetalRelaxSet  ->   suggested for metallic structure relaxation',
        'MPRelaxSet       ->   suggested for structure relaxation',
        'MPStaticSet      ->   suggested for static calculations',
        'MPNonSCFBandSet  ->   suggested for non-self-consistent field calculations (Band structure)',
        'MPNonSCFDOSSet   ->   suggested for non-self-consistent field calculations (Density of States)',
        'MPMDSet          ->   suggested for molecular dynamics simulations',
    ]
    user_input = bullet_menu(choices, title='\nSelect VASP input set:')
    if user_input is None:
        return

    vasp_input_sets = {
        'MPMetalRelaxSet': 'MPMetalRelaxSet',
        'MPRelaxSet': 'MPRelaxSet',
        'MPStaticSet': 'MPStaticSet',
        'MPNonSCFBandSet': 'MPNonSCFBandSet',
        'MPNonSCFDOSSet': 'MPNonSCFDOSSet',
        'MPMDSet': 'MPMDSet',
    }[user_input.split()[0]]

    poscar_path = check_poscar()
    if poscar_path is None:
        return

    result = tools.generate_vasp_inputs_from_poscar(poscar_path=poscar_path, vasp_input_sets=vasp_input_sets, only_incar=False)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.2.2', 'Generate INCAR templates (relaxation, static, etc.).')
@handle_keyboard_interrupt
def command_1_2_2():
    choices = [
        'MPMetalRelaxSet  ->   suggested for metallic structure relaxation',
        'MPRelaxSet       ->   suggested for structure relaxation',
        'MPStaticSet      ->   suggested for static calculations',
        'MPNonSCFBandSet  ->   suggested for non-self-consistent field calculations (Band structure)',
        'MPNonSCFDOSSet   ->   suggested for non-self-consistent field calculations (Density of States)',
        'MPMDSet          ->   suggested for molecular dynamics simulations',
        'NEBSet           ->   suggested for NEB calculations',
    ]
    user_input = bullet_menu(choices, title='\nSelect INCAR type:')
    if user_input is None:
        return

    # 直接匹配用户输入的第一个单词
    parts = user_input.split()
    vasp_input_sets = parts[0]  # 'MPMetalRelaxSet' 等

    poscar_path = check_poscar()
    if poscar_path is None:
        return

    result = tools.generate_vasp_inputs_from_poscar(poscar_path=poscar_path, vasp_input_sets=vasp_input_sets, only_incar=True)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.2.3', 'Generate KPOINTS with specified accuracy.')
@handle_keyboard_interrupt
def command_1_2_3():
    choices = [
        'Gamma-centered  ->  Construct an automatic Gamma-centered Kpoint grid.',
        'Monkhorst-Pack  ->  Construct an automatic Monkhorst-Pack Kpoint grid.',
    ]
    user_input = bullet_menu(choices, title='\nSelect K-point grid type:')
    if user_input is None:
        return
    gamma_centered = user_input.startswith('Gamma-centered')

    choices_acc = [
        'Low     ->  Suitable for preliminary calculations, grid density = 1000 / number of atoms',
        'Medium  ->  Balanced accuracy and computational cost, grid density = 3000 / number of atoms',
        'High    ->  High accuracy for production runs, grid density = 5000 / number of atoms',
        'Custom  ->  Specify custom grid density',
    ]
    user_input_acc = bullet_menu(choices_acc, title='\nSelect accuracy level:')
    if user_input_acc is None:
        return

    if user_input_acc.startswith('Custom'):
        while True:
            custom_kppa_str = color_input('\nEnter custom k-points per atom (kppa) as a positive integer (e.g., 2000): ', 'yellow').strip()
            if not custom_kppa_str:
                continue
            try:
                custom_kppa = int(custom_kppa_str)
                if custom_kppa <= 0:
                    color_print(f'\n[Error] K-points per atom must be a positive integer. You entered: {custom_kppa_str}\n', 'red')
                    continue
                break
            except Exception:
                color_print(f'\n[Error] Invalid k-points per atom: {custom_kppa_str}, please enter a positive integer and try again.\n', 'red')
        accuracy_level = 'Custom'
    else:
        accuracy_level = user_input_acc.split()[0]  # 'Low', 'Medium', 'High'
        custom_kppa = None

    poscar_path = check_poscar()
    if poscar_path is None:
        return

    result = tools.customize_vasp_kpoints_with_accuracy(poscar_path=poscar_path, accuracy_level=accuracy_level, gamma_centered=gamma_centered, custom_kppa=custom_kppa)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.2.4', 'Generate HPC Slurm job submission script for VASP calculations.')
@handle_keyboard_interrupt
def command_1_2_4():
    partition = color_input('\nEnter the HPC partition/queue name (default: normal): ', 'yellow').strip() or 'normal'

    while True:
        nodes_str = color_input('\nEnter the number of nodes (default: 1): ', 'yellow').strip()
        try:
            nodes = int(nodes_str) if nodes_str else 1
            if nodes >= 1:
                break
            color_print('\n[Error] Number of nodes must be at least 1.\n', 'red')
        except ValueError:
            color_print(f'\n[Error] Invalid number of nodes: {nodes_str}\n', 'red')

    while True:
        ntasks_str = color_input('\nEnter the number of tasks per node (default: 8): ', 'yellow').strip()
        try:
            ntasks = int(ntasks_str) if ntasks_str else 8
            if ntasks >= 1:
                break
            color_print('\n[Error] Number of tasks must be at least 1.\n', 'red')
        except ValueError:
            color_print(f'\n[Error] Invalid number of tasks: {ntasks_str}\n', 'red')

    while True:
        walltime = color_input('\nEnter the job walltime in format HH:MM:SS (default: 01:00:00): ', 'yellow').strip() or '01:00:00'
        try:
            schemas.GenerateVaspInputsHpcSlurmScript(walltime=walltime)
            break
        except ValueError:
            color_print(f"\n[Error] Invalid walltime format: {walltime}. Please use 'HH:MM:SS' format.\n", 'red')

    jobname = color_input('\nEnter the job name (default: masgent_job): ', 'yellow').strip() or 'masgent_job'

    result = tools.generate_vasp_inputs_hpc_slurm_script(
        partition=partition,
        nodes=nodes,
        ntasks=ntasks,
        walltime=walltime,
        jobname=jobname,
        command='srun vasp_std > vasp.out'
    )
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.3.1', 'Generate VASP workflow for convergence tests for k-points and energy cutoff based on given POSCAR.')
@handle_keyboard_interrupt
def command_1_3_1():
    choices = [
        'All      ->  Convergence tests for both energy cutoff and k-points',
        'ENCUT    ->  Convergence test for energy cutoff only',
        'KPOINTS  ->  Convergence test for k-points only',
    ]
    user_input = bullet_menu(choices, title='\nSelect test type:')
    if user_input is None:
        return
    test_type = {'All': 'all', 'ENCUT': 'encut', 'KPOINTS': 'kpoints'}[user_input.split()[0]]

    poscar_path = check_poscar()
    if poscar_path is None:
        return

    if test_type in ('encut', 'all'):
        while True:
            encut_levels_str = color_input('\nEnter the energy cutoff levels you want to test (e.g., 300 400 500 600 700): ', 'yellow').strip()
            if not encut_levels_str:
                continue
            try:
                encut_levels = [int(x) for x in encut_levels_str.split()]
                schemas.GenerateVaspWorkflowOfConvergenceTests(poscar_path=poscar_path, test_type=test_type, encut_levels=encut_levels)
                break
            except Exception:
                color_print(f'[Error] Invalid energy cutoff levels: {encut_levels_str}, please double check and try again.\n', 'red')

    if test_type in ('kpoints', 'all'):
        while True:
            kpoint_levels_str = color_input('\nEnter the k-point grid density levels you want to test (e.g., 1000 2000 3000 4000 5000): ', 'yellow').strip()
            if not kpoint_levels_str:
                continue
            try:
                kpoint_levels = [int(x) for x in kpoint_levels_str.split()]
                schemas.GenerateVaspWorkflowOfConvergenceTests(poscar_path=poscar_path, test_type=test_type, kpoint_levels=kpoint_levels)
                break
            except Exception:
                color_print(f'[Error] Invalid k-point levels: {kpoint_levels_str}, please double check and try again.\n', 'red')

    print('')
    with yaspin(Spinners.dots, text='Generating VASP workflow for convergence tests...', color='cyan') as sp:
        result = tools.generate_vasp_workflow_of_convergence_tests(
            poscar_path=poscar_path,
            test_type=test_type,
            encut_levels=encut_levels if test_type in ('encut', 'all') else None,
            kpoint_levels=kpoint_levels if test_type in ('kpoints', 'all') else None,
        )
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.3.2', 'Generate VASP workflow of equation of state (EOS) calculations based on given POSCAR.')
@handle_keyboard_interrupt
def command_1_3_2():
    poscar_path = check_poscar()
    if poscar_path is None:
        return

    while True:
        scale_factors_str = color_input('\nEnter the volume scale factors for EOS calculations (e.g., 0.94 0.96 0.98 1.00 1.02 1.04 1.06): ', 'yellow').strip()
        if not scale_factors_str:
            continue
        try:
            scale_factors = [float(x) for x in scale_factors_str.split()]
            schemas.GenerateVaspWorkflowOfEos(poscar_path=poscar_path, scale_factors=scale_factors)
            break
        except Exception:
            color_print(f'[Error] Invalid scale factors: {scale_factors_str}, please double check and try again.\n', 'red')

    print('')
    with yaspin(Spinners.dots, text='Generating VASP workflow for EOS calculations...', color='cyan') as sp:
        result = tools.generate_vasp_workflow_of_eos(poscar_path=poscar_path, scale_factors=scale_factors)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.3.3', 'Generate VASP workflow for elastic constants calculations based on given POSCAR.')
@handle_keyboard_interrupt
def command_1_3_3():
    poscar_path = check_poscar()
    if poscar_path is None:
        return

    print('')
    with yaspin(Spinners.dots, text='Generating VASP workflow for elastic constants calculations...', color='cyan') as sp:
        result = tools.generate_vasp_workflow_of_elastic_constants(poscar_path=poscar_path)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.3.4', 'Generate VASP workflow for ab initio molecular dynamics (AIMD) simulations based on given POSCAR.')
@handle_keyboard_interrupt
def command_1_3_4():
    poscar_path = check_poscar()
    if poscar_path is None:
        return

    while True:
        temperatures_str = color_input('\nEnter the simulation temperature(s) in K (e.g., 500 1000 1500 2000 2500): ', 'yellow').strip()
        if not temperatures_str:
            continue
        try:
            temperatures = [int(x) for x in temperatures_str.split()]
            schemas.GenerateVaspWorkflowOfAimd(poscar_path=poscar_path, temperatures=temperatures)
            break
        except Exception:
            color_print(f'[Error] Invalid temperature: {temperatures_str}, please double check and try again.\n', 'red')

    while True:
        md_steps_str = color_input('\nEnter the number of MD steps (e.g., 1000): ', 'yellow').strip()
        if not md_steps_str:
            continue
        try:
            md_steps = int(md_steps_str)
            schemas.GenerateVaspWorkflowOfAimd(poscar_path=poscar_path, temperatures=temperatures, md_steps=md_steps)
            break
        except Exception:
            color_print(f'[Error] Invalid MD steps: {md_steps_str}, please double check and try again.\n', 'red')

    while True:
        md_timestep_str = color_input('\nEnter the MD timestep in fs (e.g., 2.0): ', 'yellow').strip()
        if not md_timestep_str:
            continue
        try:
            md_timestep = float(md_timestep_str)
            schemas.GenerateVaspWorkflowOfAimd(poscar_path=poscar_path, temperatures=temperatures, md_steps=md_steps, md_timestep=md_timestep)
            break
        except Exception:
            color_print(f'[Error] Invalid MD timestep: {md_timestep_str}, please double check and try again.\n', 'red')

    print('')
    with yaspin(Spinners.dots, text='Generating VASP workflow for AIMD simulations...', color='cyan') as sp:
        result = tools.generate_vasp_workflow_of_aimd(poscar_path=poscar_path, temperatures=temperatures, md_steps=md_steps, md_timestep=md_timestep)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.3.5', 'Generate VASP workflow for Nudged Elastic Band (NEB) calculations based on given initial and final POSCARs.')
@handle_keyboard_interrupt
def command_1_3_5():
    while True:
        initial_poscar_path = color_input('\nEnter the path to the initial POSCAR file: ', 'yellow').strip()
        if not initial_poscar_path:
            continue
        try:
            schemas.CheckPoscar(poscar_path=initial_poscar_path)
            break
        except Exception:
            color_print(f'[Error] Invalid POSCAR: {initial_poscar_path}, please double check and try again.\n', 'red')

    while True:
        final_poscar_path = color_input('\nEnter the path to the final POSCAR file: ', 'yellow').strip()
        if not final_poscar_path:
            continue
        try:
            schemas.CheckPoscar(poscar_path=final_poscar_path)
            break
        except Exception:
            color_print(f'[Error] Invalid POSCAR: {final_poscar_path}, please double check and try again.\n', 'red')

    while True:
        num_images_str = color_input('\nEnter the number of intermediate images (e.g., 5): ', 'yellow').strip()
        if not num_images_str:
            continue
        try:
            num_images = int(num_images_str)
            schemas.GenerateVaspWorkflowOfNeb(initial_poscar_path=initial_poscar_path, final_poscar_path=final_poscar_path, num_images=num_images)
            break
        except Exception:
            color_print(f'[Error] Invalid number of images: {num_images_str}, please double check and try again.\n', 'red')

    print('')
    with yaspin(Spinners.dots, text='Generating VASP workflow for NEB calculations...', color='cyan') as sp:
        result = tools.generate_vasp_workflow_of_neb(initial_poscar_path=initial_poscar_path, final_poscar_path=final_poscar_path, num_images=num_images)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.4.1', 'Convergence test analysis')
@handle_keyboard_interrupt
def command_1_4_1():
    while True:
        convergence_tests_dir = color_input('\nEnter the convergence tests directory path that contains encut and kpoints subdirectories: ', 'yellow').strip()
        if not convergence_tests_dir:
            continue
        if os.path.exists(convergence_tests_dir):
            break
        color_print(f'[Error] Directory does not exist: {convergence_tests_dir}\n', 'red')

    print('')
    with yaspin(Spinners.dots, text='Analyzing VASP convergence tests...', color='cyan') as sp:
        result = tools.analyze_vasp_workflow_of_convergence_tests(convergence_tests_dir=convergence_tests_dir)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.4.2', 'Equation of State (EOS) analysis')
@handle_keyboard_interrupt
def command_1_4_2():
    while True:
        eos_dir = color_input('\nEnter the EOS calculations directory path that contains volume-scaled subdirectories: ', 'yellow').strip()
        if not eos_dir:
            continue
        if os.path.exists(eos_dir):
            break
        color_print(f'[Error] Directory does not exist: {eos_dir}\n', 'red')

    print('')
    with yaspin(Spinners.dots, text='Analyzing VASP EOS calculations...', color='cyan') as sp:
        result = tools.analyze_vasp_workflow_of_eos(eos_dir=eos_dir)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.4.3', 'Elastic constants analysis')
@handle_keyboard_interrupt
def command_1_4_3():
    while True:
        elastic_constants_dir = color_input('\nEnter the elastic constants calculations directory path that contains strain subdirectories: ', 'yellow').strip()
        if not elastic_constants_dir:
            continue
        if os.path.exists(elastic_constants_dir):
            break
        color_print(f'[Error] Directory does not exist: {elastic_constants_dir}\n', 'red')

    print('')
    with yaspin(Spinners.dots, text='Analyzing VASP elastic constants calculations...', color='cyan') as sp:
        result = tools.analyze_vasp_workflow_of_elastic_constants(elastic_constants_dir=elastic_constants_dir)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.4.4', 'Ab initio molecular dynamics (AIMD) analysis')
@handle_keyboard_interrupt
def command_1_4_4():
    while True:
        aimd_dir = color_input('\nEnter the AIMD simulations directory path that contains MD temperature subdirectories: ', 'yellow').strip()
        if not aimd_dir:
            continue
        if os.path.exists(aimd_dir):
            break
        color_print(f'[Error] Directory does not exist: {aimd_dir}\n', 'red')

    while True:
        specie = color_input('\nEnter the atomic specie symbol for MSD calculation (e.g., Li): ', 'yellow').strip()
        if not specie:
            continue
        try:
            schemas.CheckElement(element_symbol=specie)
            # 检查每个 POSCAR 中是否存在该元素
            for root, dirs, files in os.walk(aimd_dir):
                if 'POSCAR' in files:
                    poscar_path = os.path.join(root, 'POSCAR')
                    schemas.CheckElementExistence(poscar_path=poscar_path, element_symbol=specie)
            break
        except Exception:
            color_print(f'[Error] Invalid atomic specie symbol: {specie}, please double check and try again.\n', 'red')

    print('')
    with yaspin(Spinners.dots, text='Analyzing VASP AIMD simulations...', color='cyan') as sp:
        result = tools.analyze_vasp_workflow_of_aimd(aimd_dir=aimd_dir, specie=specie)
    color_print(result['message'], 'green')
    time.sleep(3)


@register('1.4.5', 'Nudged Elastic Band (NEB) analysis')
@handle_keyboard_interrupt
def command_1_4_5():
    while True:
        neb_dir = color_input('\nEnter the NEB calculations directory path that contains image subdirectories: ', 'yellow').strip()
        if not neb_dir:
            continue
        if os.path.exists(neb_dir):
            break
        color_print(f'[Error] Directory does not exist: {neb_dir}\n', 'red')

    print('')
    with yaspin(Spinners.dots, text='Analyzing VASP NEB calculations...', color='cyan') as sp:
        result = tools.analyze_vasp_workflow_of_neb(neb_dir=neb_dir)
    color_print(result['message'], 'green')
    time.sleep(3)