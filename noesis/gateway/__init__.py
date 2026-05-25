"""
Noesis Gateway — Model-agnostic retrieval and injection.

The gateway assembles context from the vault, formats it for
whatever LLM provider is in use, and injects it into the prompt.
Provider adapters handle the translation.
"""

from noesis.gateway.retrieval import RetrievalGateway
from noesis.gateway.providers import (
    ProviderAdapter,
    ClaudeAdapter,
    OpenAIAdapter,
    OllamaAdapter,
)

__all__ = [
    "RetrievalGateway",
    "ProviderAdapter",
    "ClaudeAdapter",
    "OpenAIAdapter",
    "OllamaAdapter",
]
