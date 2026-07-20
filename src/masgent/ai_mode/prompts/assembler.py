
"""提示词组装器 — 从注册表选取模块，动态拼装最终 system prompt"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from .registry import PromptRegistry, ModelTier, PromptTier


_PROMPTS_DIR = Path(__file__).resolve().parent

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "structure": ["generate", "poscar", "crystal", "structure", "create", "build", "formula"],
    "vasp": ["vasp", "incar", "kpoint", "potcar", "input set", "calculation", "dft"],
    "workflow": ["workflow", "convergence", "eos", "elastic", "aimd", "neb", "automated"],
    "elastic": ["elastic", "stiffness", "modulus", "deformation", "young", "poisson", "bulk", "shear"],
    "mechanical": ["mechanical", "strength", "hardness", "toughness", "utimate", "yield"],
    "ml": ["machine learning", "neural network", "train", "predict", "model", "optuna", "feature"],
    "defect": ["defect", "vacancy", "substitution", "interstitial", "dopant"],
    "surface": ["surface", "slab", "miller", "interface"],
    "convert": ["convert", "format", "cif", "xyz"],
    "visualize": ["visualize", "view", "plot", "3d", "structure viewer"],
    "compare": ["compare", "vs", "versus", "difference", "which is better"],
    "error": ["error", "fail", "issue", "problem", "debug", "not working"],
}


def detect_intent_tags(user_message: str) -> list[str]:
    msg_lower = user_message.lower()
    matched: set[str] = set()
    for tag, keywords in _INTENT_KEYWORDS.items():
        if any(kw in msg_lower for kw in keywords):
            matched.add(tag)
    return sorted(matched)


_FALLBACK_TIERS: list[PromptTier] = ["P0"]
_INTENT_ONLY_TIERS: list[PromptTier] = ["P1", "P2"]


def load_module_text(module_name: str) -> str:
    module = PromptRegistry.get(module_name)
    if module is None:
        return ""
    file_path = _PROMPTS_DIR / module.file
    if not file_path.exists():
        return ""
    return file_path.read_text(encoding="utf-8")


def load_base_prompt() -> str:
    base_path = _PROMPTS_DIR.parent / "system_prompt.txt"
    if base_path.exists():
        return base_path.read_text(encoding="utf-8")
    return ""


def _model_name_to_tier(provider_name: str) -> ModelTier:
    strong_kw = ["gpt-5", "claude", "sonnet", "opus"]
    medium_kw = ["gemini", "grok", "deepseek"]
    light_kw = ["qwen", "flash"]
    name_lower = provider_name.lower()
    if any(k in name_lower for k in strong_kw):
        return "strong"
    elif any(k in name_lower for k in medium_kw):
        return "medium"
    else:
        return "light"


class PromptAssembler:
    def __init__(
        self,
        provider_name: str = "",
        model_tier: ModelTier | None = None,
        *,
        include_base: bool = True,
        max_tier: PromptTier = "P2",
        intent_tags: list[str] | None = None,
    ):
        self.provider_name = provider_name
        self.model_tier = model_tier or _model_name_to_tier(provider_name)
        self.include_base = include_base
        self.max_tier = max_tier
        self.intent_tags = intent_tags or []

    def assemble(self, user_message: str | None = None, session_context: dict | None = None) -> str:
        parts = []
        if self.include_base:
            base = load_base_prompt()
            if base:
                parts.append(base)

        auto_tags = detect_intent_tags(user_message) if user_message else []
        merged_tags = list(set(self.intent_tags + auto_tags))

        for t in _FALLBACK_TIERS:
            modules = PromptRegistry.filter(
                tier=t,
                min_model_tier=self.model_tier,
            )
            for mod in modules:
                text = load_module_text(mod.name)
                if text:
                    parts.append(text)

        for t in _INTENT_ONLY_TIERS:
            if t == "P1" and self.max_tier not in ("P1", "P2"):
                continue
            if t == "P2" and self.max_tier != "P2":
                continue
            modules = PromptRegistry.filter(
                tier=t,
                min_model_tier=self.model_tier,
                intent_tags=merged_tags if merged_tags else None,
            )
            for mod in modules:
                text = load_module_text(mod.name)
                if text:
                    parts.append(text)

        if session_context:
            session_md = load_module_text("dynamic_session_context")
            if session_md:
                rendered = self._render_session_context(session_md, session_context)
                parts.append(rendered)

        model_md = load_module_text("dynamic_model_profiles")
        if model_md:
            parts.append(model_md)

        return "\n\n".join(parts)

    def _render_session_context(self, template: str, context: dict) -> str:
        result = template
        for key, value in context.items():
            placeholder = "{{" + key + "}}"
            str_value = str(value) if value is not None else ""
            result = result.replace(placeholder, str_value)
        return result

    @staticmethod
    def quick_assemble(
        provider_name: str = "",
        *,
        user_message: str | None = None,
        max_tier: PromptTier = "P2",
        intent_tags: list[str] | None = None,
        session_context: dict | None = None,
    ) -> str:
        assembler = PromptAssembler(
            provider_name=provider_name,
            max_tier=max_tier,
            intent_tags=intent_tags,
        )
        return assembler.assemble(user_message=user_message, session_context=session_context)

