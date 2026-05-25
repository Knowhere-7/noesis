"""
Session Autopsy — Post-session self-scrutiny.

After each agent session, the autopsy examines:
  1. What task was attempted? What happened?
  2. What worked? What failed?
  3. What opportunities were missed?
  4. What reasoning patterns were used?
  5. What should the agent learn from this?

The autopsy produces an Episode node that gets written to the vault.
If recurring failure patterns emerge (detected by the ProjectRetrospective),
the Skill Forge will generate new procedural memory to prevent the failure
from happening again.

This is where the agent becomes self-improving — not by asking an LLM
to self-reflect (which is circular), but by analyzing session traces
against structured criteria.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from noesis.schema import Episode, MemoryNode, NodeType

if TYPE_CHECKING:
    from noesis.vault.store import MemoryStore

logger = logging.getLogger("noesis.reflection")


# ── Analysis Criteria ─────────────────────────────────────────────────

@dataclass
class SessionTrace:
    """Raw input to the autopsy — what actually happened in the session.

    This is provider-neutral. Any agent framework can produce a
    SessionTrace. The autopsy doesn't care which LLM ran — it cares
    about what happened.
    """
    session_id: str = ""
    task_description: str = ""
    task_type: str = ""                 # e.g., "code_generation", "debugging"

    # Timeline
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    duration_seconds: float = 0.0

    # Actions taken
    steps: List[Dict[str, Any]] = field(default_factory=list)
    # Each step: {"action": str, "input": str, "output": str,
    #             "tool": str, "success": bool, "timestamp": float}

    tools_used: List[str] = field(default_factory=list)
    errors_encountered: List[Dict[str, Any]] = field(default_factory=list)
    # Each error: {"type": str, "message": str, "step_index": int,
    #              "recovered": bool}

    # Outcome
    final_output: str = ""
    user_feedback: Optional[str] = None     # explicit feedback if given
    user_rating: Optional[float] = None     # [0, 1] if given
    task_completed: bool = False

    # Token cost
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # Context that was injected (for groundedness analysis)
    context_node_ids: List[str] = field(default_factory=list)


# ── Autopsy Results ───────────────────────────────────────────────────

@dataclass
class AutopsyResult:
    """Structured output of the autopsy analysis.

    This feeds into both:
    - The Episode node that gets written to the vault
    - The ProjectRetrospective for cross-episode pattern detection
    """
    # Scoring
    outcome_score: float = 0.5          # [0, 1] — overall quality
    efficiency_score: float = 0.5       # [0, 1] — steps/tokens per result
    groundedness_score: float = 0.5     # [0, 1] — context utilization

    # What happened
    outcome_category: str = "partial"   # success / partial / failure
    reasoning_patterns: List[str] = field(default_factory=list)
    effective_actions: List[str] = field(default_factory=list)
    failed_actions: List[str] = field(default_factory=list)
    missed_opportunities: List[str] = field(default_factory=list)

    # What to learn
    reflection_summary: str = ""        # human-readable autopsy
    skill_candidates: List[Dict[str, str]] = field(default_factory=list)
    # Each candidate: {"pattern": str, "description": str,
    #                  "trigger": str, "frequency": int}

    # Trust impact — how should this session affect the agent's trust
    trust_delta: float = 0.0            # positive = earned trust, neg = lost
    facts_confirmed: List[str] = field(default_factory=list)
    facts_contradicted: List[str] = field(default_factory=list)


class SessionAutopsy:
    """Post-session analysis engine.

    Two modes:
    1. Rule-based (v1) — structured analysis using heuristics.
       No LLM in the loop for the autopsy itself. The agent is
       the subject, not the judge.

    2. LLM-assisted (v2, future) — use a separate LLM call to
       analyze the session trace. The autopsy LLM is a different
       instance with read-only access to the vault.

    For v1, the analysis is based on:
    - Step success/failure ratios
    - Error recovery patterns
    - Context utilization (were retrieved memories used?)
    - Tool selection efficiency
    - Token economy (cost per useful output)
    - User feedback integration
    """

    # Scoring weights
    COMPLETION_WEIGHT = 0.35        # did the task get done?
    EFFICIENCY_WEIGHT = 0.20        # how efficiently?
    ERROR_RECOVERY_WEIGHT = 0.15    # did it recover from failures?
    GROUNDEDNESS_WEIGHT = 0.15      # did it use its memory?
    FEEDBACK_WEIGHT = 0.15          # what did the user say?

    # Thresholds
    HIGH_ERROR_RATE = 0.4           # > 40% of steps failed
    LOW_CONTEXT_USE = 0.2           # < 20% of context was referenced
    EXCESSIVE_TOKEN_RATIO = 5.0     # > 5x tokens vs output length

    def __init__(self):
        self._pattern_registry: Dict[str, int] = {}

    def analyze(
        self,
        trace: SessionTrace,
        store: Optional[MemoryStore] = None,
    ) -> AutopsyResult:
        """Run the full autopsy on a session trace.

        Returns an AutopsyResult with scores, patterns, and
        recommendations for the vault.
        """
        result = AutopsyResult()

        # 1. Score the outcome
        result.outcome_score = self._score_outcome(trace)
        result.efficiency_score = self._score_efficiency(trace)
        result.groundedness_score = self._score_groundedness(trace, store)
        result.outcome_category = self._categorize_outcome(
            result.outcome_score
        )

        # 2. Extract reasoning patterns
        result.reasoning_patterns = self._extract_patterns(trace)
        result.effective_actions = self._find_effective_actions(trace)
        result.failed_actions = self._find_failed_actions(trace)
        result.missed_opportunities = self._find_missed_opportunities(
            trace, store
        )

        # 3. Compute trust impact
        result.trust_delta = self._compute_trust_delta(result)

        # 4. Check for skill candidates
        result.skill_candidates = self._detect_skill_candidates(
            trace, result
        )

        # 5. Generate reflection summary
        result.reflection_summary = self._generate_reflection(trace, result)

        # 6. Cross-reference with stored facts
        if store:
            result.facts_confirmed, result.facts_contradicted = (
                self._check_facts(trace, store)
            )

        logger.info(
            "Autopsy complete for session '%s': outcome=%.2f, "
            "efficiency=%.2f, trust_delta=%+.2f, patterns=%d",
            trace.session_id,
            result.outcome_score,
            result.efficiency_score,
            result.trust_delta,
            len(result.reasoning_patterns),
        )

        return result

    def to_episode(
        self,
        trace: SessionTrace,
        result: AutopsyResult,
        namespace: str = "default",
    ) -> Episode:
        """Convert autopsy results into an Episode node for the vault."""
        episode = Episode(
            key=f"episode:{trace.session_id}",
            value=result.reflection_summary,
            namespace=namespace,
            session_id=trace.session_id,
            task_description=trace.task_description,
            approach=self._summarize_approach(trace),
            outcome=result.outcome_category,
            outcome_score=result.outcome_score,
            reasoning_patterns=result.reasoning_patterns,
            tools_used=trace.tools_used,
            missed_opportunities=result.missed_opportunities,
            cost_tokens=trace.total_tokens,
            duration_seconds=trace.duration_seconds,
            reflection=result.reflection_summary,
        )
        # Trust proportional to outcome
        episode.trust_charge = max(0.1, result.outcome_score * 0.8)
        episode.importance = self._compute_episode_importance(result)
        return episode

    # ── Scoring ───────────────────────────────────────────────────────

    def _score_outcome(self, trace: SessionTrace) -> float:
        """Score the session outcome [0, 1].

        Factors:
        - Task completion (binary, heavily weighted)
        - User feedback (if provided)
        - Error rate (penalty for excessive errors)
        - Step success ratio
        """
        score = 0.0

        # Task completion is the biggest signal
        if trace.task_completed:
            score += 0.5
        elif trace.final_output:
            score += 0.2  # produced something, even if incomplete

        # User feedback overrides heuristics
        if trace.user_rating is not None:
            score = (score * 0.4) + (trace.user_rating * 0.6)
            return max(0.0, min(1.0, score))

        # Step success ratio
        if trace.steps:
            successes = sum(1 for s in trace.steps if s.get("success", True))
            success_ratio = successes / len(trace.steps)
            score += success_ratio * 0.3

        # Error recovery bonus — recovering from errors is good
        if trace.errors_encountered:
            recovered = sum(
                1 for e in trace.errors_encountered if e.get("recovered")
            )
            recovery_rate = recovered / len(trace.errors_encountered)
            score += recovery_rate * 0.1

        # Penalty for no output at all
        if not trace.final_output and not trace.task_completed:
            score *= 0.5

        return max(0.0, min(1.0, score))

    def _score_efficiency(self, trace: SessionTrace) -> float:
        """Score token and step efficiency [0, 1].

        Lower tokens-per-useful-output = higher score.
        Fewer wasted steps (retries, dead ends) = higher score.
        """
        if not trace.total_tokens:
            return 0.5  # no data

        # Token efficiency: output length vs total tokens
        output_len = len(trace.final_output) if trace.final_output else 0
        if output_len > 0 and trace.total_tokens > 0:
            ratio = trace.total_tokens / output_len
            if ratio < 2.0:
                token_score = 1.0
            elif ratio < self.EXCESSIVE_TOKEN_RATIO:
                token_score = 1.0 - (
                    (ratio - 2.0) / (self.EXCESSIVE_TOKEN_RATIO - 2.0)
                )
            else:
                token_score = 0.2
        else:
            token_score = 0.3

        # Step efficiency: what proportion of steps were productive?
        if trace.steps:
            failed = sum(
                1 for s in trace.steps if not s.get("success", True)
            )
            step_score = 1.0 - (failed / len(trace.steps))
        else:
            step_score = 0.5

        return (token_score * 0.5) + (step_score * 0.5)

    def _score_groundedness(
        self,
        trace: SessionTrace,
        store: Optional[MemoryStore],
    ) -> float:
        """Score how well the session used its memory context [0, 1].

        Did the agent actually reference the context it was given?
        Sessions that ignore their retrieved memory context are
        "ungrounded" — they're operating on the LLM's priors, not
        on earned knowledge.
        """
        if not store or not trace.context_node_ids:
            return 0.5  # no context to evaluate

        # Check how many context nodes were actually referenced in steps
        referenced = set()
        for step in trace.steps:
            output = step.get("output", "")
            for node_id in trace.context_node_ids:
                node = store.get_by_id(node_id)
                if node and node.key and node.key in output:
                    referenced.add(node_id)

        if trace.context_node_ids:
            return len(referenced) / len(trace.context_node_ids)
        return 0.5

    def _categorize_outcome(self, score: float) -> str:
        """Map outcome score to category."""
        if score >= 0.7:
            return "success"
        elif score >= 0.4:
            return "partial"
        return "failure"

    # ── Pattern Extraction ────────────────────────────────────────────

    def _extract_patterns(self, trace: SessionTrace) -> List[str]:
        """Identify reasoning patterns from the session trace.

        Patterns are reusable observations about HOW the agent worked,
        not WHAT it produced.
        """
        patterns = []

        # Pattern: trial-and-error (many retries)
        if trace.steps:
            retries = 0
            for i, step in enumerate(trace.steps[1:], 1):
                prev = trace.steps[i - 1]
                if (step.get("action") == prev.get("action") and
                        not prev.get("success", True)):
                    retries += 1
            if retries > 2:
                patterns.append("trial-and-error-loop")

        # Pattern: tool switching (many different tools)
        if len(set(trace.tools_used)) > 5:
            patterns.append("broad-tool-exploration")

        # Pattern: single-tool focus
        if trace.tools_used and len(set(trace.tools_used)) == 1:
            patterns.append("single-tool-focus")

        # Pattern: error-then-recovery
        for error in trace.errors_encountered:
            if error.get("recovered"):
                patterns.append("error-recovery")
                break

        # Pattern: no errors at all (clean execution)
        if trace.steps and not trace.errors_encountered:
            patterns.append("clean-execution")

        # Pattern: front-loaded research (reading before writing)
        if len(trace.steps) >= 4:
            first_quarter = trace.steps[:len(trace.steps) // 4]
            read_actions = sum(
                1 for s in first_quarter
                if "read" in s.get("action", "").lower() or
                   "search" in s.get("action", "").lower() or
                   "get" in s.get("action", "").lower()
            )
            if read_actions >= len(first_quarter) * 0.6:
                patterns.append("research-first")

        # Pattern: long session (potential sign of struggle)
        if trace.duration_seconds > 600:  # > 10 minutes
            patterns.append("extended-session")

        return list(set(patterns))

    def _find_effective_actions(self, trace: SessionTrace) -> List[str]:
        """Identify actions that directly contributed to the outcome."""
        effective = []
        for step in trace.steps:
            if step.get("success", True) and step.get("output"):
                action = step.get("action", "unknown")
                tool = step.get("tool", "")
                desc = f"{action}"
                if tool:
                    desc += f" ({tool})"
                effective.append(desc)
        return effective[:10]  # top 10

    def _find_failed_actions(self, trace: SessionTrace) -> List[str]:
        """Identify actions that failed or were unproductive."""
        failed = []
        for step in trace.steps:
            if not step.get("success", True):
                action = step.get("action", "unknown")
                error_msg = ""
                # Find associated error
                step_idx = trace.steps.index(step)
                for err in trace.errors_encountered:
                    if err.get("step_index") == step_idx:
                        error_msg = err.get("message", "")[:80]
                        break
                desc = f"{action}"
                if error_msg:
                    desc += f": {error_msg}"
                failed.append(desc)
        return failed[:10]

    def _find_missed_opportunities(
        self,
        trace: SessionTrace,
        store: Optional[MemoryStore],
    ) -> List[str]:
        """Identify things the agent could have done better.

        This is where the autopsy generates signal for the Skill Forge.
        """
        missed = []

        # Missed: didn't use context that was available
        if store and trace.context_node_ids:
            for node_id in trace.context_node_ids:
                node = store.get_by_id(node_id)
                if node and node.trust_charge > 0.6:
                    # High-trust node was available but might not have been used
                    referenced = False
                    for step in trace.steps:
                        if node.key in step.get("output", ""):
                            referenced = True
                            break
                    if not referenced:
                        missed.append(
                            f"Available high-trust memory '{node.key}' "
                            f"was not referenced"
                        )

        # Missed: could have stopped earlier (excessive retries after success)
        if trace.task_completed and trace.steps:
            last_success_idx = -1
            for i, step in enumerate(trace.steps):
                if step.get("success") and i > len(trace.steps) * 0.7:
                    last_success_idx = i
                    break
            if last_success_idx > 0 and last_success_idx < len(trace.steps) - 3:
                missed.append(
                    "Task was likely complete before final steps — "
                    "could have stopped earlier"
                )

        # Missed: high error rate suggests wrong approach
        if trace.steps:
            error_rate = len(trace.errors_encountered) / len(trace.steps)
            if error_rate > self.HIGH_ERROR_RATE:
                missed.append(
                    f"Error rate {error_rate:.0%} suggests the initial "
                    f"approach was suboptimal"
                )

        return missed[:5]

    # ── Trust & Skill ─────────────────────────────────────────────────

    def _compute_trust_delta(self, result: AutopsyResult) -> float:
        """How much trust did this session earn or lose?

        Good sessions build trust. Bad sessions drain it.
        Neutral sessions have no effect.
        """
        # Weighted composite of scores
        composite = (
            result.outcome_score * self.COMPLETION_WEIGHT +
            result.efficiency_score * self.EFFICIENCY_WEIGHT +
            result.groundedness_score * self.GROUNDEDNESS_WEIGHT
        )
        # Map to [-0.1, +0.1] range
        return (composite - 0.5) * 0.2

    def _detect_skill_candidates(
        self,
        trace: SessionTrace,
        result: AutopsyResult,
    ) -> List[Dict[str, str]]:
        """Detect patterns that could become skills.

        A skill candidate emerges when:
        1. A specific failure pattern recurs (tracked in _pattern_registry)
        2. The autopsy identifies a corrective action that would help
        3. The pattern has appeared in 3+ sessions

        The actual skill generation happens in the Skill Forge.
        The autopsy just flags candidates.
        """
        candidates = []

        # Track failure patterns
        for action in result.failed_actions:
            action_type = action.split(":")[0].strip()
            key = f"failure:{trace.task_type}:{action_type}"
            self._pattern_registry[key] = (
                self._pattern_registry.get(key, 0) + 1
            )

            if self._pattern_registry[key] >= 3:
                candidates.append({
                    "pattern": key,
                    "description": (
                        f"Recurring failure in {action_type} during "
                        f"{trace.task_type} tasks"
                    ),
                    "trigger": f"task_type == '{trace.task_type}'",
                    "frequency": str(self._pattern_registry[key]),
                })

        # Track missed opportunity patterns
        for opp in result.missed_opportunities:
            key = f"missed:{opp[:40]}"
            self._pattern_registry[key] = (
                self._pattern_registry.get(key, 0) + 1
            )
            if self._pattern_registry[key] >= 3:
                candidates.append({
                    "pattern": key,
                    "description": opp,
                    "trigger": f"task_type == '{trace.task_type}'",
                    "frequency": str(self._pattern_registry[key]),
                })

        # Track reasoning anti-patterns
        if "trial-and-error-loop" in result.reasoning_patterns:
            key = f"antipattern:trial-and-error:{trace.task_type}"
            self._pattern_registry[key] = (
                self._pattern_registry.get(key, 0) + 1
            )
            if self._pattern_registry[key] >= 2:
                candidates.append({
                    "pattern": key,
                    "description": (
                        f"Agent repeatedly uses trial-and-error instead "
                        f"of research-first approach for {trace.task_type}"
                    ),
                    "trigger": f"task_type == '{trace.task_type}'",
                    "frequency": str(self._pattern_registry[key]),
                })

        return candidates

    # ── Summary Generation ────────────────────────────────────────────

    def _generate_reflection(
        self,
        trace: SessionTrace,
        result: AutopsyResult,
    ) -> str:
        """Generate a structured reflection summary.

        This is what gets stored in the Episode.reflection field
        and surfaced to future sessions as few-shot context.
        """
        lines = []
        lines.append(f"Session: {trace.session_id}")
        lines.append(f"Task: {trace.task_description}")
        lines.append(f"Outcome: {result.outcome_category} ({result.outcome_score:.2f})")
        lines.append(f"Efficiency: {result.efficiency_score:.2f}")
        lines.append(f"Groundedness: {result.groundedness_score:.2f}")

        if result.reasoning_patterns:
            lines.append(f"Patterns: {', '.join(result.reasoning_patterns)}")

        if result.effective_actions:
            lines.append(f"Effective: {'; '.join(result.effective_actions[:3])}")

        if result.failed_actions:
            lines.append(f"Failed: {'; '.join(result.failed_actions[:3])}")

        if result.missed_opportunities:
            lines.append("Missed opportunities:")
            for opp in result.missed_opportunities[:3]:
                lines.append(f"  - {opp}")

        if result.skill_candidates:
            lines.append("Skill candidates detected:")
            for sc in result.skill_candidates[:3]:
                lines.append(f"  - {sc['description']} (seen {sc['frequency']}x)")

        lines.append(f"Trust impact: {result.trust_delta:+.3f}")

        return "\n".join(lines)

    def _summarize_approach(self, trace: SessionTrace) -> str:
        """Summarize the approach taken (for the Episode.approach field)."""
        if not trace.steps:
            return "No steps recorded."

        tools = list(set(trace.tools_used))[:5]
        total_steps = len(trace.steps)
        error_count = len(trace.errors_encountered)

        parts = [f"{total_steps} steps"]
        if tools:
            parts.append(f"tools: {', '.join(tools)}")
        if error_count:
            parts.append(f"{error_count} errors")
        if trace.duration_seconds:
            parts.append(f"{trace.duration_seconds:.0f}s")

        return "; ".join(parts)

    def _compute_episode_importance(self, result: AutopsyResult) -> float:
        """How important is this episode for future retrieval?

        High-impact sessions (good or bad) are important.
        Middling sessions are less important.
        Failures that teach something are important.
        """
        # Extreme outcomes are interesting
        outcome_interest = abs(result.outcome_score - 0.5) * 2
        # Skill candidates make the episode valuable
        skill_bonus = min(0.3, len(result.skill_candidates) * 0.1)
        # Missed opportunities are learning material
        learning_bonus = min(0.2, len(result.missed_opportunities) * 0.05)

        importance = 0.3 + outcome_interest * 0.3 + skill_bonus + learning_bonus
        return max(0.1, min(1.0, importance))

    def _check_facts(
        self,
        trace: SessionTrace,
        store: MemoryStore,
    ) -> Tuple[List[str], List[str]]:
        """Check if session results confirm or contradict stored facts.

        Returns (confirmed_keys, contradicted_keys).
        For v1, this is basic text matching. Future versions will
        use semantic similarity.
        """
        confirmed = []
        contradicted = []

        facts = store.backend.get_by_type(
            NodeType.SEMANTIC_FACT, store.namespace
        )

        for fact in facts:
            if not fact.value:
                continue
            # Check if the session output references this fact
            for step in trace.steps:
                output = step.get("output", "")
                if fact.key in output or fact.value[:50] in output:
                    # Referenced — does the output agree?
                    # v1: if the step succeeded and referenced the fact,
                    # we count it as confirmed
                    if step.get("success", True):
                        confirmed.append(fact.key)
                    else:
                        contradicted.append(fact.key)
                    break

        return confirmed, contradicted
