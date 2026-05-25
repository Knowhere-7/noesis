"""
Retrieval Gateway — Context assembly and session orchestration.

The gateway is the main API for agent frameworks. It handles:
  1. Session lifecycle (start → run → end → autopsy)
  2. Context assembly (vault → formatted prompt injection)
  3. Output scoring (drift detection per response)
  4. Memory writes (facts, episodes from session activity)

This is model-agnostic. The gateway doesn't know or care
which LLM is running — it operates on the memory layer.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from noesis.schema import (
    DriftScore,
    Episode,
    Fact,
    GriefState,
    MemoryNode,
    NodeType,
    Profile,
    ProjectState,
    Skill,
    SkillStatus,
)
from noesis.vault.store import MemoryStore
from noesis.vault.sqlite_backend import SQLiteBackend
from noesis.governor.trust_gate import TrustGate
from noesis.reflection.autopsy import (
    AutopsyResult,
    SessionAutopsy,
    SessionTrace,
)
from noesis.reflection.retrospective import ProjectRetrospective
from noesis.forge.skill_forge import SkillForge
from noesis.gateway.providers import ProviderAdapter

logger = logging.getLogger("noesis.gateway")


class RetrievalGateway:
    """Main entry point for agent frameworks.

    Typical usage:

        gateway = RetrievalGateway(db_path="agent_memory.db")

        # Start a session
        session = gateway.start_session(task="Fix the auth bug")

        # Get context to inject into the LLM prompt
        context = gateway.get_context(query="auth middleware")

        # Score an LLM output for drift
        drift = gateway.score_output(output_text)

        # Record a fact learned during the session
        gateway.learn_fact("auth_flow", "Uses JWT with RS256")

        # End the session and run autopsy
        gateway.end_session(
            task_completed=True,
            final_output="Fixed the middleware...",
        )
    """

    def __init__(
        self,
        db_path: str = "noesis.db",
        namespace: str = "default",
        provider: Optional[ProviderAdapter] = None,
    ):
        backend = SQLiteBackend(db_path)
        self.store = MemoryStore(backend, namespace)
        self.autopsy = SessionAutopsy()
        self.retrospective = ProjectRetrospective()
        self.forge = SkillForge()
        self.provider = provider

        # Session state
        self._session_id: str = ""
        self._session_trace: Optional[SessionTrace] = None
        self._context_cache: List[MemoryNode] = []

    # ── Session Lifecycle ─────────────────────────────────────────────

    def start_session(
        self,
        task: str = "",
        task_type: str = "",
        session_id: Optional[str] = None,
    ) -> str:
        """Initialize a new session.

        Resets session energy, loads context, returns session ID.
        """
        self._session_id = session_id or str(uuid.uuid4())[:12]
        self.store.new_session()

        self._session_trace = SessionTrace(
            session_id=self._session_id,
            task_description=task,
            task_type=task_type,
            start_time=time.time(),
        )

        # Pre-load context
        self._context_cache = self.store.assemble_context(
            query=task, task_type=task_type
        )

        logger.info(
            "Session '%s' started. Task: '%s'. Context: %d nodes.",
            self._session_id, task, len(self._context_cache),
        )

        return self._session_id

    def end_session(
        self,
        task_completed: bool = False,
        final_output: str = "",
        user_rating: Optional[float] = None,
        user_feedback: Optional[str] = None,
    ) -> AutopsyResult:
        """End the session, run autopsy, and write the episode.

        Returns the autopsy result for inspection.
        """
        if not self._session_trace:
            raise RuntimeError("No active session. Call start_session first.")

        # Finalize trace
        trace = self._session_trace
        trace.end_time = time.time()
        trace.duration_seconds = trace.end_time - trace.start_time
        trace.task_completed = task_completed
        trace.final_output = final_output
        trace.user_rating = user_rating
        trace.user_feedback = user_feedback
        trace.context_node_ids = [n.id for n in self._context_cache]

        # Run autopsy
        result = self.autopsy.analyze(trace, self.store)

        # Write episode to vault
        episode = self.autopsy.to_episode(
            trace, result, self.store.namespace
        )
        self.store.write_episode(episode)

        # Update trust on confirmed/contradicted facts
        for key in result.facts_confirmed:
            node = self.store.get(key)
            if node:
                self.store.trust_gate.confirm_node(node)
                self.store.backend.upsert(node)

        for key in result.facts_contradicted:
            node = self.store.get(key)
            if node:
                self.store.trust_gate.contradict_node(node)
                self.store.backend.upsert(node)

        # Run grief cascade to clean contaminated nodes
        purged = self.store.run_grief_cascade()
        if purged:
            logger.info(
                "Post-session grief cascade purged %d nodes",
                len(purged),
            )

        # Apply passive trust decay
        self.store.decay_all()

        # Clean up
        self._session_trace = None
        self._context_cache = []

        logger.info(
            "Session '%s' ended. Outcome: %s (%.2f). "
            "Trust delta: %+.3f.",
            trace.session_id,
            result.outcome_category,
            result.outcome_score,
            result.trust_delta,
        )

        return result

    # ── Context Retrieval ─────────────────────────────────────────────

    def get_context(
        self,
        query: str = "",
        task_type: str = "",
        max_tokens: int = 4000,
    ) -> str:
        """Get formatted context for LLM prompt injection.

        Returns a string ready to be inserted into the system prompt
        or message context. If a ProviderAdapter is set, uses its
        formatting. Otherwise returns plain text.
        """
        nodes = self.store.assemble_context(
            query=query, task_type=task_type, max_tokens=max_tokens
        )
        self._context_cache = nodes

        if self.provider:
            return self.provider.format_context(nodes)
        return self._format_plain(nodes)

    def get_context_nodes(
        self,
        query: str = "",
        task_type: str = "",
    ) -> List[MemoryNode]:
        """Get raw context nodes (for custom formatting)."""
        nodes = self.store.assemble_context(
            query=query, task_type=task_type
        )
        self._context_cache = nodes
        return nodes

    def _format_plain(self, nodes: List[MemoryNode]) -> str:
        """Format context nodes as plain text."""
        if not nodes:
            return ""

        sections = []
        current_type = None

        for node in nodes:
            if node.node_type != current_type:
                current_type = node.node_type
                sections.append(f"\n## {current_type.name}")

            line = f"- [{node.key}] {node.value}"
            if node.trust_charge < 0.3:
                line += " (low confidence)"
            sections.append(line)

        return "\n".join(sections)

    # ── Output Scoring ────────────────────────────────────────────────

    def score_output(self, output: str) -> DriftScore:
        """Score an LLM output for drift against current context.

        Returns a DriftScore with 5 signals. The calling framework
        decides what to do with it (retrieve more, reflect, refuse).
        """
        profile = None
        for node in self._context_cache:
            if node.node_type == NodeType.PROFILE:
                profile = node
                break

        return self.store.trust_gate.score_output(
            output, self._context_cache, profile
        )

    # ── Memory Operations ─────────────────────────────────────────────

    def learn_fact(
        self,
        key: str,
        value: str,
        source: str = "session",
        trust: float = 0.5,
    ) -> Tuple[bool, str]:
        """Record a fact learned during the session."""
        episode_id = self._session_id if self._session_trace else None
        success, reason = self.store.write_fact(
            key=key,
            value=value,
            source_episode_id=episode_id,
            author_trust=trust,
        )

        if success and self._session_trace:
            self._session_trace.steps.append({
                "action": "learn_fact",
                "input": key,
                "output": value,
                "tool": "noesis",
                "success": True,
                "timestamp": time.time(),
            })

        return success, reason

    def record_step(
        self,
        action: str,
        input_text: str = "",
        output_text: str = "",
        tool: str = "",
        success: bool = True,
    ):
        """Record a step in the current session trace.

        Call this from the agent framework to feed the autopsy.
        """
        if not self._session_trace:
            return

        self._session_trace.steps.append({
            "action": action,
            "input": input_text,
            "output": output_text,
            "tool": tool,
            "success": success,
            "timestamp": time.time(),
        })

        if tool and tool not in self._session_trace.tools_used:
            self._session_trace.tools_used.append(tool)

        if not success:
            self._session_trace.errors_encountered.append({
                "type": "step_failure",
                "message": output_text[:200],
                "step_index": len(self._session_trace.steps) - 1,
                "recovered": False,
            })

    def record_tokens(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ):
        """Record token usage for the current session."""
        if not self._session_trace:
            return
        self._session_trace.prompt_tokens += prompt_tokens
        self._session_trace.completion_tokens += completion_tokens
        self._session_trace.total_tokens += (
            prompt_tokens + completion_tokens
        )

    # ── Guardrails ────────────────────────────────────────────────────

    def install_guardrail(self, key: str, rule: str) -> Tuple[bool, str]:
        """Install a system guardrail (sacred, immutable)."""
        return self.store.write_guardrail(key, rule)

    def set_profile(
        self,
        key: str,
        role: str,
        constraints: Optional[List[str]] = None,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str]:
        """Set or update the agent profile."""
        profile = Profile(
            key=key,
            value=role,
            role=role,
            constraints=constraints or [],
            preferences=preferences or {},
        )
        return self.store.write_profile(profile)

    def set_project_state(
        self,
        key: str,
        objectives: Optional[List[str]] = None,
        decisions: Optional[List[Dict[str, str]]] = None,
        blockers: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """Set or update the project state."""
        state = ProjectState(
            key=key,
            value=f"Project: {key}",
            objectives=objectives or [],
            decisions=decisions or [],
            blockers=blockers or [],
        )
        return self.store.write_project_state(state)

    # ── Retrospective & Forge ─────────────────────────────────────────

    def run_retrospective(
        self,
        lookback_hours: float = 168.0,
    ) -> Dict[str, Any]:
        """Run the project retrospective and process any skill candidates.

        Returns a summary dict with patterns found, skills drafted,
        and recommendations.
        """
        # Run retrospective
        retro = self.retrospective.analyze(
            self.store, lookback_hours
        )

        # Process actionable patterns through the forge
        new_skills = []
        if retro.actionable_patterns:
            new_skills = self.forge.process_patterns(
                retro.actionable_patterns, self.store
            )

        return {
            "episodes_analyzed": retro.episodes_analyzed,
            "overall_health": retro.overall_health,
            "trust_trend": retro.trust_trajectory.trend,
            "trust_avg": retro.trust_trajectory.current_avg,
            "patterns_found": len(retro.patterns),
            "actionable_patterns": len(retro.actionable_patterns),
            "skills_drafted": len(new_skills),
            "skill_reports": [
                {
                    "key": r.skill_key,
                    "effectiveness": r.effectiveness,
                    "recommendation": r.recommendation,
                }
                for r in retro.skill_reports
            ],
            "recommendations": retro.recommendations,
        }

    # ── Utility ───────────────────────────────────────────────────────

    def search(self, query: str, limit: int = 10) -> List[MemoryNode]:
        """Search the vault by keyword."""
        return self.store.backend.search(
            query, self.store.namespace, limit
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get current vault statistics."""
        all_nodes = self.store.all_nodes()

        by_type: Dict[str, int] = {}
        by_state: Dict[str, int] = {}
        total_trust = 0.0

        for node in all_nodes:
            type_name = node.node_type.name
            by_type[type_name] = by_type.get(type_name, 0) + 1

            state_name = node.grief_state.name
            by_state[state_name] = by_state.get(state_name, 0) + 1

            total_trust += node.trust_charge

        avg_trust = total_trust / len(all_nodes) if all_nodes else 0

        return {
            "total_nodes": len(all_nodes),
            "by_type": by_type,
            "by_state": by_state,
            "avg_trust": avg_trust,
            "session_energy": self.store.trust_gate.session_energy,
        }

    def close(self):
        """Clean up database connection."""
        self.store.backend.close()
