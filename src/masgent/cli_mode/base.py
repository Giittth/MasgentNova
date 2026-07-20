"""CLI 基础工具：统一的 bullet 菜单处理"""

import sys
from typing import List, Optional
from bullet import Bullet, colors

from masgent.cli_mode.cli_run import run_command
from masgent.utils import (
    color_print,
    print_help,
    global_commands,
    start_new_session,
    clear_and_print_entry_message,
    exit_and_cleanup,
)


def bullet_menu(choices: List[str], title: str = "", show_ai: bool = True) -> Optional[str]:
    """
    统一的 bullet 菜单，处理全局命令（AI/New/Back/Main/Help/Exit）。

    Args:
        choices: 菜单选项列表
        title: 菜单标题（显示在 Bullet 提示中）
        show_ai: 是否在全局命令中显示 AI 选项（默认 True）

    Returns:
        用户选择的结果（非全局命令的选项字符串），如果用户选择 Back 则返回 None
    """
    # 构建完整菜单选项
    menu_choices = choices.copy()

    # 添加分隔符和全局命令
    if menu_choices and menu_choices[-1] != "":
        menu_choices.append("")
    menu_choices.extend(global_commands())

    while True:
        clear_and_print_entry_message()
        cli = Bullet(
            prompt=title if title else "\n",
            choices=menu_choices,
            margin=1,
            bullet=" ●",
            word_color=colors.foreground["green"],
        )
        user_input = cli.launch()

        if user_input.startswith("AI"):
            from masgent.ai_mode import ai_backend
            ai_backend.main()
        elif user_input.startswith("New"):
            start_new_session()
        elif user_input.startswith("Back"):
            return None
        elif user_input.startswith("Main"):
            run_command("0")
        elif user_input.startswith("Help"):
            print_help()
        elif user_input.startswith("Exit"):
            exit_and_cleanup()
        else:
            return user_input


def handle_keyboard_interrupt(func):
    """装饰器：统一处理 KeyboardInterrupt 和 EOFError"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (KeyboardInterrupt, EOFError):
            color_print("\n[Info] Operation cancelled. Returning to previous menu...\n", "yellow")
            return
    return wrapper