"""会话目录管理与退出清理"""

import os
import sys
import datetime
from masgent._config import config
from masgent.utils.logger import logger


def start_new_session():
    """创建新的 runs 时间戳目录，并设置环境变量"""
    base_dir = config.get_runs_dir()
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    runs_dir = base_dir / f'runs_{timestamp}'
    runs_dir.mkdir(parents=True, exist_ok=True)
    os.environ['MASGENT_SESSION_RUNS_DIR'] = str(runs_dir)
    return str(runs_dir)


def exit_and_cleanup():
    """退出程序，若 runs 目录为空则删除"""
    runs_dir = os.environ.get('MASGENT_SESSION_RUNS_DIR')
    if runs_dir and os.path.exists(runs_dir) and not os.listdir(runs_dir):
        os.rmdir(runs_dir)
    logger.info('Exiting Masgent... Goodbye!')
    sys.exit(0)