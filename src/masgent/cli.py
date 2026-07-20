"""Masgent CLI 入口

直接转发到 cli_entries.command_0()，避免重复的主循环代码。
"""

from masgent.cli_mode.cli_entries import command_0


def main():
    """Masgent CLI 主入口"""
    command_0()


if __name__ == "__main__":
    main()