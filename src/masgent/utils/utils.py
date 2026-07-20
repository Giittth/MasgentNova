"""CLI 工具：彩色输出、输入、全局命令、系统提示加载"""

import sys
from pathlib import Path
from colorama import Fore, Style
from masgent.utils.logger import logger


def get_color_map():
    return {
        'red': Fore.RED,
        'green': Fore.GREEN,
        'yellow': Fore.YELLOW,
        'blue': Fore.BLUE,
        'magenta': Fore.MAGENTA,
        'cyan': Fore.CYAN,
        'white': Fore.WHITE,
    }


def color_print(text, color='cyan'):
    """打印彩色文本（同时输出到日志）"""
    color_map = get_color_map()
    chosen_color = color_map.get(color.lower(), Fore.CYAN)
    print(chosen_color + text + Style.RESET_ALL)
    level_map = {'red': 'error', 'yellow': 'warning', 'green': 'info', 'white': 'info', 'cyan': 'info'}
    level = level_map.get(color.lower(), 'info')
    getattr(logger, level)(text)


def color_input(text, color='cyan'):
    """带颜色的输入提示"""
    color_map = get_color_map()
    chosen_color = color_map.get(color.lower(), Fore.CYAN)
    return input(chosen_color + text + Style.RESET_ALL)


def global_commands():
    return [
        '',
        'AI    ->  Chat with the Masgent AI',
        'New   ->  Start a new session',
        'Back  ->  Return to previous menu',
        'Main  ->  Return to main menu',
        'Help  ->  Show available functions',
        'Exit  ->  Quit the Masgent',
    ]


def load_system_prompts():
    prompts_path = Path(__file__).resolve().parent.parent / 'ai_mode' / 'system_prompt.txt'
    try:
        return prompts_path.read_text(encoding='utf-8')
    except Exception as e:
        return f'Error loading system prompts: {str(e)}'