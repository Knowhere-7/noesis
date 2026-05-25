"""
Provider Adapters — Model-agnostic formatting for LLM context injection.

Each adapter knows how to format Noesis memory nodes into
the prompt structure that a specific LLM provider expects.

The gateway doesn't know which LLM is running. It assembles
the context and hands it to the adapter for formatting.

Supported providers (v1):
  - Claude (Anthropic) — system prompt injection
  - OpenAI (GPT) — system message injection
  - Ollama (local models) — system prompt injection
  - Raw/Custom — plain text for any provider
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from noesis.schema import (
    GriefState,
    MemoryNode,
    NodeType,
    Skill,
    SkillStatus,
)


class ProviderAdapter(ABC):
    """Abstract base for LLM provider adapters.

    Each adapter translates memory nodes into the format
    that the target provider's API expects.
    """

    @abstractmethod
    def format_context(self, nodes: List[MemoryNode]) -> str:
        """Format memory nodes for prompt injection."""
        ...

    def _group_by_type(
        self, nodes: List[MemoryNode]
    ) -> dict[str, list[MemoryNode]]:
        """Group nodes by type for structured output."""
        groups: dict[str, list[MemoryNode]] = {}
        for node in nodes:
            type_name = node.node_type.name
            if type_name not in groups:
                groups[type_name] = []
            groups[type_name].append(node)
        return groups

    def _trust_indicator(self, node: MemoryNode) -> str:
        """Visual trust indicator for a node."""
        if node.is_sacred:
            return "[SACRED]"
        if node.trust_charge >= 0.8:
            return "[HIGH TRUST]"
        if node.trust_charge >= 0.5:
            return ""
        if node.trust_charge >= 0.3:
            return "[LOW CONFIDENCE]"
        return "[UNVERIFIED]"


class ClaudeAdapter(ProviderAdapter):
    """Format context for Anthropic Claude (system prompt).

    Claude works best with XML-structured system prompts.
    Memory context is injected as structured XML blocks.
    """

    def format_context(self, nodes: List[MemoryNode]) -> str:
        if not nodes:
            return ""

        groups = self._group_by_type(nodes)
        sections = []

        sections.append("<noesis_memory>")

        # Guardrails first (sacred, always present)
        if "SYSTEM_GUARDRAIL" in groups:
            sections.append("  <guardrails>")
            for node in groups["SYSTEM_GUARDRAIL"]:
                sections.append(
                    f"    <rule key=\"{node.key}\">{node.value}</rule>"
                )
            sections.append("  </guardrails>")

        # Profile
        if "PROFILE" in groups:
            sections.append("  <profile>")
            for node in groups["PROFILE"]:
                sections.append(f"    <role>{node.value}</role>")
            sections.append("  </profile>")

        # Project state
        if "PROJECT_STATE" in groups:
            sections.append("  <project_state>")
            for node in groups["PROJECT_STATE"]:
                sections.append(
                    f"    <state key=\"{node.key}\">{node.value}</state>"
                )
            sections.append("  </project_state>")

        # Skills (promoted only)
        skill_nodes = groups.get("SKILL", [])
        active_skills = [
            s for s in skill_nodes
            if isinstance(s, Skill) and s.status == SkillStatus.PROMOTED
        ]
        if active_skills:
            sections.append("  <skills>")
            for skill in active_skills:
                trust = self._trust_indicator(skill)
                sections.append(
                    f"    <skill key=\"{skill.key}\" "
                    f"trust=\"{skill.trust_charge:.2f}\">"
                )
                sections.append(f"      <objective>{skill.objective}</objective>")
                sections.append(f"      <method>{skill.method}</method>")
                if skill.constraints:
                    sections.append("      <constraints>")
                    for c in skill.constraints:
                        sections.append(f"        <constraint>{c}</constraint>")
                    sections.append("      </constraints>")
                sections.append("    </skill>")
            sections.append("  </skills>")

        # Facts
        if "SEMANTIC_FACT" in groups:
            sections.append("  <facts>")
            for node in groups["SEMANTIC_FACT"]:
                trust = self._trust_indicator(node)
                sections.append(
                    f"    <fact key=\"{node.key}\" "
                    f"trust=\"{node.trust_charge:.2f}\">"
                    f"{node.value}"
                    f"</fact>"
                )
            sections.append("  </facts>")

        # Episodes (as few-shot examples)
        if "EPISODE" in groups:
            sections.append("  <recent_episodes>")
            for node in groups["EPISODE"]:
                sections.append(
                    f"    <episode key=\"{node.key}\" "
                    f"outcome=\"{node.value[:50]}\">"
                )
                if hasattr(node, "reflection") and node.reflection:
                    sections.append(
                        f"      <reflection>{node.reflection}</reflection>"
                    )
                sections.append("    </episode>")
            sections.append("  </recent_episodes>")

        sections.append("</noesis_memory>")

        return "\n".join(sections)


class OpenAIAdapter(ProviderAdapter):
    """Format context for OpenAI GPT (system message).

    GPT works with markdown-structured system messages.
    """

    def format_context(self, nodes: List[MemoryNode]) -> str:
        if not nodes:
            return ""

        groups = self._group_by_type(nodes)
        sections = []

        sections.append("# Agent Memory Context (Noesis)")
        sections.append("")

        if "SYSTEM_GUARDRAIL" in groups:
            sections.append("## System Rules (Immutable)")
            for node in groups["SYSTEM_GUARDRAIL"]:
                sections.append(f"- **{node.key}**: {node.value}")
            sections.append("")

        if "PROFILE" in groups:
            sections.append("## Agent Profile")
            for node in groups["PROFILE"]:
                sections.append(f"- {node.value}")
            sections.append("")

        if "PROJECT_STATE" in groups:
            sections.append("## Current Project State")
            for node in groups["PROJECT_STATE"]:
                sections.append(f"- {node.key}: {node.value}")
            sections.append("")

        skill_nodes = groups.get("SKILL", [])
        active_skills = [
            s for s in skill_nodes
            if isinstance(s, Skill) and s.status == SkillStatus.PROMOTED
        ]
        if active_skills:
            sections.append("## Active Skills")
            for skill in active_skills:
                sections.append(f"### {skill.key}")
                sections.append(f"**Objective:** {skill.objective}")
                sections.append(f"**Method:** {skill.method}")
                if skill.constraints:
                    sections.append("**Constraints:**")
                    for c in skill.constraints:
                        sections.append(f"  - {c}")
                sections.append("")

        if "SEMANTIC_FACT" in groups:
            sections.append("## Known Facts")
            for node in groups["SEMANTIC_FACT"]:
                trust = self._trust_indicator(node)
                sections.append(f"- {node.key}: {node.value} {trust}")
            sections.append("")

        if "EPISODE" in groups:
            sections.append("## Recent Sessions")
            for node in groups["EPISODE"]:
                sections.append(f"- {node.key}: {node.value[:80]}")
            sections.append("")

        return "\n".join(sections)


class OllamaAdapter(ProviderAdapter):
    """Format context for local Ollama models.

    Local models often have smaller context windows, so this
    adapter is more aggressive about compression. Only includes
    the most critical context.
    """

    MAX_FACTS = 10
    MAX_SKILLS = 3

    def format_context(self, nodes: List[MemoryNode]) -> str:
        if not nodes:
            return ""

        groups = self._group_by_type(nodes)
        sections = []

        sections.append("[MEMORY CONTEXT]")

        if "SYSTEM_GUARDRAIL" in groups:
            sections.append("[RULES]")
            for node in groups["SYSTEM_GUARDRAIL"]:
                sections.append(f"  {node.key}: {node.value}")

        if "PROFILE" in groups:
            sections.append("[ROLE]")
            for node in groups["PROFILE"]:
                sections.append(f"  {node.value}")

        if "PROJECT_STATE" in groups:
            sections.append("[PROJECT]")
            for node in groups["PROJECT_STATE"]:
                sections.append(f"  {node.value[:100]}")

        skill_nodes = groups.get("SKILL", [])
        active_skills = [
            s for s in skill_nodes
            if isinstance(s, Skill) and s.status == SkillStatus.PROMOTED
        ]
        if active_skills:
            sections.append("[SKILLS]")
            for skill in active_skills[:self.MAX_SKILLS]:
                sections.append(f"  {skill.objective}")

        if "SEMANTIC_FACT" in groups:
            sections.append("[FACTS]")
            for node in groups["SEMANTIC_FACT"][:self.MAX_FACTS]:
                sections.append(f"  {node.key}: {node.value}")

        sections.append("[/MEMORY CONTEXT]")

        return "\n".join(sections)
