"""
AI Provider 工厂：统一管理所有 AI 服务商的模型创建逻辑。
"""

from typing import Callable, Dict
from pydantic_ai.models import Model

from masgent.utils import ask_for_api_key
from masgent._config import config, reload_config


def _require_api_key(config_attr: str, env_name: str) -> str:
    """
    获取 API Key，如果不存在则交互式输入并刷新配置
    
    Args:
        config_attr: config 中的属性名，如 "openai_api_key"
        env_name: 环境变量名，如 "OPENAI_API_KEY"
    
    Returns:
        API Key 字符串
    """
    key = getattr(config, config_attr, None)
    if not key:
        ask_for_api_key(env_name)
        # 关键：重新加载配置，使刚才写入 .env 的 Key 生效
        reload_config()
        key = getattr(config, config_attr, None)
    return key


class ProviderFactory:
    """AI Provider 工厂：通过注册机制创建模型实例"""

    _providers: Dict[str, Callable[[], Model]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[[], Model]) -> None:
        cls._providers[name] = factory

    @classmethod
    def create(cls, name: str) -> Model:
        factory = cls._providers.get(name)
        if not factory:
            raise ValueError(f"Unknown provider: {name}")
        return factory()

    @classmethod
    def list_providers(cls) -> list:
        return list(cls._providers.keys())


# ============ 注册所有 Provider ============

def _create_masgent() -> Model:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
    return OpenAIChatModel(
        model_name="gpt-5-nano",
        provider=OpenAIProvider(base_url="https://masgent-ai.onrender.com/v1"),
    )


def _create_openai() -> Model:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
    key = _require_api_key("openai_api_key", "OPENAI_API_KEY")
    return OpenAIChatModel(
        model_name="gpt-5-nano",
        provider=OpenAIProvider(api_key=key),
    )


def _create_anthropic() -> Model:
    from pydantic_ai.models.anthropic import AnthropicModel
    key = _require_api_key("anthropic_api_key", "ANTHROPIC_API_KEY")
    return AnthropicModel(model_name="claude-sonnet-4-5", api_key=key)


def _create_google() -> Model:
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider
    key = _require_api_key("google_api_key", "GOOGLE_API_KEY")
    return GoogleModel(
        "gemini-2.5-flash",
        provider=GoogleProvider(api_key=key),
    )


def _create_xai() -> Model:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.grok import GrokProvider
    key = _require_api_key("grok_api_key", "GROK_API_KEY")
    return OpenAIChatModel(
        model_name="grok-4-1-fast-non-reasoning",
        provider=GrokProvider(api_key=key),
    )


def _create_deepseek() -> Model:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.deepseek import DeepSeekProvider
    key = _require_api_key("deepseek_api_key", "DEEPSEEK_API_KEY")
    return OpenAIChatModel(
        model_name="deepseek-chat",
        provider=DeepSeekProvider(api_key=key),
    )


def _create_alibaba() -> Model:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.alibaba import AlibabaProvider
    key = _require_api_key("dashscope_api_key", "DASHSCOPE_API_KEY")
    return OpenAIChatModel(
        model_name="qwen-flash",
        provider=AlibabaProvider(api_key=key),
    )


# ============ 注册 ============
ProviderFactory.register("Masgent - Masgent AI", _create_masgent)
ProviderFactory.register("OpenAI - GPT-5 Nano", _create_openai)
ProviderFactory.register("Anthropic - Claude Sonnet 4.5", _create_anthropic)
ProviderFactory.register("Google - Gemini 2.5 Flash", _create_google)
ProviderFactory.register("xAI - Grok 4.1 Fast", _create_xai)
ProviderFactory.register("Deepseek - Deepseek Chat", _create_deepseek)
ProviderFactory.register("Alibaba - Qwen Flash", _create_alibaba)