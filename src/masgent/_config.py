# src/masgent/_config.py

import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MasgentSettings(BaseSettings):
    """Masgent 全局配置类"""
    
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent / ".env",  # 指向项目根目录
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ===== 会话配置 =====
    runs_dir: str = Field(
        default="",
        description="当前会话运行目录"
    )

    # ===== API Keys =====
    openai_api_key: str = Field(
        default="",
        description="OpenAI API Key"
    )
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API Key"
    )
    google_api_key: str = Field(
        default="",
        description="Google AI API Key"
    )
    grok_api_key: str = Field(
        default="",
        description="xAI Grok API Key"
    )
    deepseek_api_key: str = Field(
        default="",
        description="DeepSeek API Key"
    )
    dashscope_api_key: str = Field(
        default="",
        description="Alibaba DashScope API Key"
    )
    mp_api_key: str = Field(
        default="",
        description="Materials Project API Key"
    )

    # ===== 远程 HPC 配置 =====
    remote_host: str = Field(
        default="",
        description="远程 HPC 主机地址"
    )
    remote_user: str = Field(
        default="",
        description="远程 HPC 用户名"
    )
    remote_key: str = Field(
        default="",
        description="远程 HPC SSH 密钥路径"
    )

    # ===== VASP/Pymatgen 配置 =====
    potcar_dir: str = Field(
        default="",
        description="POTCAR 文件目录 (Pymatgen 环境变量)"
    )

    def get_runs_dir(self) -> Path:
        """获取会话目录，如果未设置则创建默认值"""
        if self.runs_dir:
            return Path(self.runs_dir)
        default_dir = Path.home() / "masgent_runs"
        default_dir.mkdir(parents=True, exist_ok=True)
        return default_dir

    def reload_config():
        """重新加载配置（用于运行时更新后调用）"""
        global config
        config = MasgentSettings()
        return config


# 全局配置实例
config = MasgentSettings()


def reload_config():
    """重新加载配置（用于运行时更新后调用）"""
    global config
    config = MasgentSettings()
    return config