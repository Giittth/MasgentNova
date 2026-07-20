import os
import sys
import re
from pathlib import Path
from masgent.utils.utils import color_input
from masgent.utils.logger import logger
from masgent._config import config


# 项目根目录（与 _config.py 保持一致）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _get_env_path() -> Path:
    """返回 .env 文件的绝对路径（项目根目录）"""
    return PROJECT_ROOT / ".env"


def ask_for_api_key(key_name):
    """
    通用 API Key 输入与持久化。
    支持：OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY,
          GROK_API_KEY, DEEPSEEK_API_KEY, DASHSCOPE_API_KEY
    """
    key = color_input(f'Enter your API key: ', 'yellow').strip()
    if not key:
        logger.error('API key cannot be empty. Exiting...')
        sys.exit(1)

    # 设置环境变量（当前进程有效）
    os.environ[key_name] = key

    # 同时更新 config 实例
    attr_map = {
        'OPENAI_API_KEY': 'openai_api_key',
        'ANTHROPIC_API_KEY': 'anthropic_api_key',
        'GOOGLE_API_KEY': 'google_api_key',
        'GROK_API_KEY': 'grok_api_key',
        'DEEPSEEK_API_KEY': 'deepseek_api_key',
        'DASHSCOPE_API_KEY': 'dashscope_api_key',
        'MP_API_KEY': 'mp_api_key',
    }
    attr_name = attr_map.get(key_name)
    if attr_name and hasattr(config, attr_name):
        setattr(config, attr_name, key)
        logger.info(f'{key_name} set in current config.')

    save = color_input('Save this key to .env file for future? (y/n): ', 'yellow').strip().lower()
    if save == 'y':
        env_path = _get_env_path()
        # 检查是否已存在该 key，避免重复
        if env_path.exists():
            content = env_path.read_text(encoding='utf-8')
            if re.search(rf'^{key_name}=', content, re.MULTILINE):
                # 替换已有 key
                new_content = re.sub(rf'^{key_name}=.*$', f'{key_name}={key}', content, flags=re.MULTILINE)
                env_path.write_text(new_content, encoding='utf-8')
                logger.info(f'{key_name} updated in {env_path}')
                return

        # 追加新 key
        with open(env_path, 'a', encoding='utf-8') as f:
            f.write(f'{key_name}={key}\n')
        logger.info(f'{key_name} saved to {env_path}')


def validate_mp_api_key(key):
    """
    验证 Materials Project API Key 是否有效。
    如果无效，打印错误并退出。
    """
    try:
        from mp_api.client import MPRester
        with MPRester(key, mute_progress_bars=True) as mpr:
            # 简单查询验证 key 有效性
            _ = mpr.materials.search(formula='Si', fields=['material_id'])
    except Exception as e:
        logger.error(f'Invalid Materials Project API key: {e}')
        sys.exit(1)


def ask_for_mp_api_key():
    """
    交互式输入 Materials Project API Key。
    验证通过后保存到 .env 并同步 config。
    """
    key = color_input('Enter your Materials Project API key: ', 'yellow').strip()
    if not key:
        logger.error('Materials Project API key cannot be empty. Exiting...')
        sys.exit(1)

    validate_mp_api_key(key)

    # 设置环境变量
    os.environ['MP_API_KEY'] = key

    # 同步更新 config
    if hasattr(config, 'mp_api_key'):
        config.mp_api_key = key
        logger.info('MP_API_KEY set in current config.')

    save = color_input('Save this key to .env file for future? (y/n): ', 'yellow').strip().lower()
    if save == 'y':
        env_path = _get_env_path()
        if env_path.exists():
            content = env_path.read_text(encoding='utf-8')
            if re.search(r'^MP_API_KEY=', content, re.MULTILINE):
                # 替换已有 key
                new_content = re.sub(r'^MP_API_KEY=.*$', f'MP_API_KEY={key}', content, flags=re.MULTILINE)
                env_path.write_text(new_content, encoding='utf-8')
                logger.info(f'MP_API_KEY updated in {env_path}')
                return

        # 追加新 key
        with open(env_path, 'a', encoding='utf-8') as f:
            f.write(f'MP_API_KEY={key}\n')
        logger.info(f'MP_API_KEY saved to {env_path}')