import os
import time
from bullet import Bullet, colors
from yaspin import yaspin
from yaspin.spinners import Spinners

import masgent.tools as tools
from masgent.models import schemas
from masgent.utils import (
    color_print,
    color_input,
    print_help,
    global_commands,
    start_new_session,
    clear_and_print_entry_message,
    exit_and_cleanup,
)
from masgent._config import config


COMMANDS = {}


def register(code, func):
    def decorator(func):
        COMMANDS[code] = {
            'function': func,
            'description': func.__doc__ or ''
        }
        return func
    return decorator


def run_command(code):
    cmd = COMMANDS.get(code)
    if cmd:
        cmd['function']()
    else:
        color_print(f'[Error] Invalid command code: {code}\n', 'red')


def check_poscar():
    """
    交互式检查并返回 POSCAR 文件路径。
    如果用户取消或输入无效，返回 None。
    """
    while True:
        runs_dir = str(config.get_runs_dir())

        if os.path.exists(os.path.join(runs_dir, 'POSCAR')):
            use_default = True
        else:
            use_default = False

        if use_default:
            runs_dir_name = os.path.basename(runs_dir)
            clear_and_print_entry_message()
            choices = [
                'Yes  ->  Use POSCAR file in current runs directory',
                'No   ->  Provide a different POSCAR file path',
            ] + global_commands()

            prompt = f'\nUse POSCAR file in current runs directory: {runs_dir_name}/POSCAR ?\n'
            cli = Bullet(prompt=prompt, choices=choices, margin=1, bullet=' ●', word_color=colors.foreground['green'])
            user_input = cli.launch()

            if user_input.startswith('AI'):
                from masgent.ai_mode import ai_backend
                ai_backend.main()
            elif user_input.startswith('New'):
                start_new_session()
            elif user_input.startswith('Back'):
                return None
            elif user_input.startswith('Main'):
                run_command('0')
            elif user_input.startswith('Help'):
                print_help()
            elif user_input.startswith('Exit'):
                exit_and_cleanup()
            elif user_input.startswith('Yes'):
                poscar_path = os.path.join(runs_dir, 'POSCAR')
            elif user_input.startswith('No'):
                poscar_path = color_input('\nEnter path to POSCAR file: ', 'yellow').strip()
            else:
                continue
        else:
            poscar_path = color_input('\nEnter path to POSCAR file: ', 'yellow').strip()

        if not poscar_path:
            continue

        try:
            schemas.CheckPoscar(poscar_path=poscar_path)
            return poscar_path
        except Exception:
            color_print(f'[Error] Invalid POSCAR: {poscar_path}, please double check and try again.\n', 'red')