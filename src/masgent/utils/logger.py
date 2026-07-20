"""统一日志配置模块"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
    }

    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = self.COLORS[levelname] + levelname + Style.RESET_ALL
        return super().format(record)


def setup_logger(name='masgent', log_dir=None, level=logging.INFO):
    """
    配置日志系统，返回 logger 实例
    
    Args:
        name: logger 名称
        log_dir: 日志文件目录，默认 ~/masgent_logs
        level: 日志级别，默认 INFO
    """
    if log_dir is None:
        log_dir = Path.home() / 'masgent_logs'
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # 创建 logger
    logger = logging.getLogger(name)
    if logger.handlers:  # 避免重复添加
        return logger

    logger.setLevel(level)

    # 终端 Handler（带颜色）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_format = '%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s'
    console_formatter = ColoredFormatter(console_format, datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件 Handler（无颜色，带详细信息）
    log_filename = datetime.now().strftime('masgent_%Y%m%d.log')
    log_path = log_dir / log_filename
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(level)
    file_format = '%(asctime)s [%(levelname)s] %(name)s.%(funcName)s:%(lineno)d - %(message)s'
    file_formatter = logging.Formatter(file_format, datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


# 默认 logger 实例
logger = setup_logger()