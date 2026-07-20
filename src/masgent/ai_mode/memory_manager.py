"""Layered conversation memory manager."""
from __future__ import annotations
from pydantic_ai.messages import (
    ModelMessage, ModelRequest, ModelResponse,
    SystemPromptPart, UserPromptPart,
    ToolCallPart, ToolReturnPart, RetryPromptPart,
)

class LayeredMemoryManager:
    def __init__(self, message_window: int = 20):
        self.message_window = message_window
        self._pinned: dict[str, str] = {}

    def pin(self, key: str, value: str) -> None:
        self._pinned[key] = value

    def unpin(self, key: str) -> None:
        self._pinned.pop(key, None)

    def get_pinned_summary(self) -> str:
        if not self._pinned:
            return ""
        lines = ["[Session State]"]
        for key, value in self._pinned.items():
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    def is_critical_tool_result(self, msg) -> bool:
        if isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    return True
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, ToolReturnPart):
                    return True
        return False

    def is_user_decision(self, msg) -> bool:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, UserPromptPart):
                    text = part.content.lower() if isinstance(part.content, str) else ""
                    decision_words = ["yes","no","proceed","confirm","modify",
                                      "continue","skip","use","try","change"]
                    if any(w in text for w in decision_words):
                        return True
        return False

    async def process(self, messages) -> list:
        if len(messages) <= self.message_window:
            return messages
        system_prompt = None
        for i, msg in enumerate(messages):
            if isinstance(msg, ModelRequest) and any(
                isinstance(p, SystemPromptPart) for p in msg.parts
            ):
                system_prompt = msg
                break
        layer_a = []
        rest = []
        for msg in messages:
            if self.is_critical_tool_result(msg) or self.is_user_decision(msg):
                layer_a.append(msg)
            else:
                rest.append(msg)
        budget = self.message_window - len(layer_a) - (1 if system_prompt else 0)
        if budget <= 0:
            kept = layer_a
        else:
            kept = layer_a + rest[-budget:]
        if system_prompt is not None and system_prompt not in kept:
            kept.insert(0, system_prompt)
        return kept

_global_memory = LayeredMemoryManager()

def create_memory_processor():
    return _global_memory.process

def get_memory_manager():
    return _global_memory
