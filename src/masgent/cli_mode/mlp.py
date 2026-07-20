"""MLP 模拟相关命令（2.x 系列）"""

import time
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


def call_mlps(mlps_type: str):
    """统一的 MLP 模拟调用函数"""
    choices = [
        '1. Single Point Energy Calculation',
        '2. Equation of State (EOS) Calculation',
        '3. Elastic Constants Calculation',
        '4. Molecular Dynamics Simulation (NVT)',
    ]
    user_input = bullet_menu(choices, title='\nSelect simulation type:')
    if user_input is None:
        return

    task_map = {
        '1. Single Point Energy Calculation': 'single',
        '2. Equation of State (EOS) Calculation': 'eos',
        '3. Elastic Constants Calculation': 'elastic',
        '4. Molecular Dynamics Simulation (NVT)': 'md',
    }
    task_type = task_map[user_input]

    poscar_path = check_poscar()
    if poscar_path is None:
        return

    if task_type in ['single', 'eos', 'elastic']:
        while True:
            fmax_str = color_input('\nEnter the maximum force convergence criterion in eV/Å (default: 0.1): ', 'yellow').strip()
            if not fmax_str:
                fmax = 0.1
                break
            try:
                fmax = float(fmax_str)
                schemas.RunSimulationUsingMlps(poscar_path=poscar_path, fmax=fmax)
                break
            except Exception:
                color_print(f'[Error] Invalid force criterion: {fmax_str}, please double check and try again.\n', 'red')

        while True:
            max_steps_str = color_input('\nEnter the maximum number of optimization steps (default: 500): ', 'yellow').strip()
            if not max_steps_str:
                max_steps = 500
                break
            try:
                max_steps = int(max_steps_str)
                schemas.RunSimulationUsingMlps(poscar_path=poscar_path, max_steps=max_steps)
                break
            except Exception:
                color_print(f'[Error] Invalid maximum steps: {max_steps_str}, please double check and try again.\n', 'red')

        if task_type == 'eos':
            while True:
                scale_factors_str = color_input(
                    '\nEnter the volume scale factors for EOS calculations (e.g., 0.94 0.96 0.98 1.00 1.02 1.04 1.06): ',
                    'yellow'
                ).strip()
                if not scale_factors_str:
                    continue
                try:
                    scale_factors = [float(x) for x in scale_factors_str.split()]
                    schemas.RunSimulationUsingMlps(
                        poscar_path=poscar_path,
                        fmax=fmax,
                        max_steps=max_steps,
                        scale_factors=scale_factors,
                    )
                    break
                except Exception:
                    color_print(f'[Error] Invalid scale factors: {scale_factors_str}, please double check and try again.\n', 'red')

        print('')
        with yaspin(Spinners.dots, text=f'Running simulation using {mlps_type}... See details in the log file.', color='cyan') as sp:
            result = tools.run_simulation_using_mlps(
                poscar_path=poscar_path,
                mlps_type=mlps_type,
                task_type=task_type,
                fmax=fmax,
                max_steps=max_steps,
                scale_factors=scale_factors if task_type == 'eos' else [0.94, 0.96, 0.98, 1.00, 1.02, 1.04, 1.06],
            )
        color_print(result['message'], 'green')
        time.sleep(3)

    else:  # task_type == 'md'
        while True:
            temperature_str = color_input('\nEnter the simulation temperature in K (default: 1000): ', 'yellow').strip()
            if not temperature_str:
                temperature = 1000
                break
            try:
                temperature = int(temperature_str)
                schemas.RunSimulationUsingMlps(poscar_path=poscar_path, temperature=temperature)
                break
            except Exception:
                color_print(f'[Error] Invalid temperature: {temperature_str}, please double check and try again.\n', 'red')

        while True:
            md_steps_str = color_input('\nEnter the number of MD steps (default: 1000): ', 'yellow').strip()
            if not md_steps_str:
                md_steps = 1000
                break
            try:
                md_steps = int(md_steps_str)
                schemas.RunSimulationUsingMlps(poscar_path=poscar_path, md_steps=md_steps)
                break
            except Exception:
                color_print(f'[Error] Invalid MD steps: {md_steps_str}, please double check and try again.\n', 'red')

        while True:
            md_timestep_str = color_input('\nEnter the MD timestep in fs (default: 5.0 fs): ', 'yellow').strip()
            if not md_timestep_str:
                md_timestep = 5.0
                break
            try:
                md_timestep = float(md_timestep_str)
                schemas.RunSimulationUsingMlps(poscar_path=poscar_path, md_timestep=md_timestep)
                break
            except Exception:
                color_print(f'[Error] Invalid MD timestep: {md_timestep_str}, please double check and try again.\n', 'red')

        print('')
        with yaspin(Spinners.dots, text=f'Running simulation using {mlps_type}... See details in the log file.', color='cyan') as sp:
            result = tools.run_simulation_using_mlps(
                poscar_path=poscar_path,
                mlps_type=mlps_type,
                task_type=task_type,
                temperature=temperature,
                md_steps=md_steps,
                md_timestep=md_timestep,
            )
        color_print(result['message'], 'green')
        time.sleep(3)


@register('2.1', 'SevenNet')
@handle_keyboard_interrupt
def command_2_1():
    call_mlps('SevenNet')


@register('2.2', 'CHGNet')
@handle_keyboard_interrupt
def command_2_2():
    call_mlps('CHGNet')


@register('2.3', 'Orb-v3')
@handle_keyboard_interrupt
def command_2_3():
    call_mlps('Orb-v3')


@register('2.4', 'MatterSim')
@handle_keyboard_interrupt
def command_2_4():
    call_mlps('MatterSim')