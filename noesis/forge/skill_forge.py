"""
Skill Forge — Turns recurring failure patterns into procedural memory.

The lifecycle:
  1. PROPOSED — Pattern detected by Retrospective, skill drafted
  2. VALIDATING — Shadow-running against historical episodes
  3. PROMOTED — Passed validation, active in procedural memory
  4. DEPRECATED — Performance declined, retired but kept for audit
  5. REJECTED — Failed validation, archived

From Ghost's original prompt:
  "the model should create skills from the areas of self reflection
   that the agent recognizes it would benefit from if it had
   (X)-skill before"

The forge does NOT use an LLM to generate skills (that would be
circular — the subject generating its own rules). Instead, skills
are structured templates built from concrete evidence:
  - What failed? (from episodes)
  - What would have helped? (from missed opportunities)
  - What worked in similar situations? (from successful episodes)

Skills are portable — they're provider-neutral instruction modules
that can be injected into any LLM's context window.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from noesis.schema import (
    Episode,
    Evaluation,
    GriefState,
    NodeType,
    Skill,
    SkillStatus,
)
from noesis.reflection.retrospective import PatternCluster

if TYPE_CHECKING:
    from noesis.vault.store import MemoryStore

logger = logging.getLogger("noesis.forge")


class SkillForge:
    """Generates, validates, and manages procedural memory (skills).

    The forge follows a strict lifecycle to prevent bad skills
    from polluting the agent's behavior:

    1. Draft: Pattern → Skill template (structured, not freeform)
    2. Validate: Replay against historical episodes (shadow mode)
    3. Promote: Only if validation score beats baseline
    4. Monitor: Retrospective tracks effectiveness post-promotion
    5. Deprecate: If effectiveness drops, skill is retired

    Skills start with low trust (0.3) and earn it through proven
    performance — exactly like agents in the swarm.
    """

    # Validation thresholds
    MIN_SHADOW_RUNS = 3             # minimum replay tests
    PROMOTION_THRESHOLD = 0.6       # must beat baseline by this margin
    DEPRECATION_THRESHOLD = -0.1    # effectiveness below this = deprecate
    MAX_ACTIVE_SKILLS = 20          # prevent skill bloat

    def __init__(self):
        self._draft_queue: List[Dict] = []

    # ── Skill Drafting ────────────────────────────────────────────────

    def draft_from_pattern(
        self,
        pattern: PatternCluster,
        store: MemoryStore,
    ) -> Optional[Skill]:
        """Draft a new skill from a detected pattern.

        The skill is structured, not freeform:
        - trigger_conditions: when should this activate?
        - objective: what does it accomplish?
        - method: concrete steps (from successful episodes)
        - constraints: what must it NOT do?
        - eval_tests: how do we verify it works?

        Returns None if the pattern doesn't have enough evidence.
        """
        if not pattern.is_actionable:
            return None

        # Gather source episodes
        source_episodes = []
        for ep_id in pattern.episode_ids:
            ep = store.get_by_id(ep_id)
            if ep and isinstance(ep, Episode):
                source_episodes.append(ep)

        if len(source_episodes) < 2:
            return None

        # Check we don't already have a skill for this pattern
        existing_skills = store.backend.get_by_type(
            NodeType.SKILL, store.namespace
        )
        for s in existing_skills:
            if isinstance(s, Skill) and s.pattern_description == pattern.pattern_id:
                if s.status in (SkillStatus.PROMOTED, SkillStatus.VALIDATING):
                    logger.debug(
                        "Skill already exists for pattern '%s'",
                        pattern.pattern_id,
                    )
                    return None

        # Check skill cap
        active_count = sum(
            1 for s in existing_skills
            if isinstance(s, Skill) and s.status == SkillStatus.PROMOTED
        )
        if active_count >= self.MAX_ACTIVE_SKILLS:
            logger.warning(
                "Skill cap reached (%d). Deprecate underperforming "
                "skills before forging new ones.",
                self.MAX_ACTIVE_SKILLS,
            )
            return None

        # Build the skill from evidence
        skill = self._build_skill(pattern, source_episodes)

        logger.info(
            "Drafted skill '%s' from pattern '%s' (%d source episodes)",
            skill.key, pattern.pattern_id, len(source_episodes),
        )

        return skill

    def _build_skill(
        self,
        pattern: PatternCluster,
        episodes: List[Episode],
    ) -> Skill:
        """Construct a Skill from pattern evidence.

        Extracts concrete guidance from the episode history:
        - What tools worked in successful similar episodes?
        - What approaches led to failure?
        - What was consistently missed?
        """
        # Separate good and bad episodes
        good = [e for e in episodes if e.outcome_score >= 0.6]
        bad = [e for e in episodes if e.outcome_score < 0.5]

        # Extract trigger conditions
        triggers = self._extract_triggers(episodes)

        # Extract method from successful episodes
        method = self._extract_method(good, bad, pattern)

        # Extract constraints from failures
        constraints = self._extract_constraints(bad)

        # Build eval tests from the episode data
        eval_tests = self._build_eval_tests(episodes)

        skill = Skill(
            key=f"skill:{pattern.pattern_id}",
            value=f"Skill to address: {pattern.description}",
            namespace=episodes[0].namespace if episodes else "default",
            status=SkillStatus.PROPOSED,
            trigger_conditions=triggers,
            objective=pattern.description,
            method=method,
            constraints=constraints,
            eval_tests=eval_tests,
            source_episode_ids=[e.id for e in episodes],
            pattern_description=pattern.pattern_id,
        )

        return skill

    def _extract_triggers(self, episodes: List[Episode]) -> List[str]:
        """Extract trigger conditions from episode patterns."""
        triggers = []
        # Common task keywords across episodes
        task_words: Dict[str, int] = {}
        for ep in episodes:
            for word in ep.task_description.lower().split():
                if len(word) > 3:
                    task_words[word] = task_words.get(word, 0) + 1

        # Words that appear in >50% of episodes are triggers
        threshold = len(episodes) * 0.5
        for word, count in task_words.items():
            if count >= threshold:
                triggers.append(f"task contains '{word}'")

        # Common tools
        tool_counts: Dict[str, int] = {}
        for ep in episodes:
            for tool in ep.tools_used:
                tool_counts[tool] = tool_counts.get(tool, 0) + 1
        for tool, count in tool_counts.items():
            if count >= threshold:
                triggers.append(f"tool '{tool}' in use")

        return triggers[:5] if triggers else ["manual_trigger"]

    def _extract_method(
        self,
        good: List[Episode],
        bad: List[Episode],
        pattern: PatternCluster,
    ) -> str:
        """Extract a method description from episode evidence."""
        lines = []
        lines.append(f"# Skill: Address '{pattern.pattern_type}' pattern")
        lines.append(f"# Based on {len(good) + len(bad)} episodes")
        lines.append("")

        if good:
            lines.append("## What worked (from successful episodes):")
            seen_patterns = set()
            for ep in good:
                for p in ep.reasoning_patterns:
                    if p not in seen_patterns:
                        lines.append(f"  - Use '{p}' approach")
                        seen_patterns.add(p)
            if ep.tools_used:
                lines.append(
                    f"  - Tools: {', '.join(set(ep.tools_used))}"
                )

        if bad:
            lines.append("")
            lines.append("## What to avoid (from failed episodes):")
            seen_anti = set()
            for ep in bad:
                for p in ep.reasoning_patterns:
                    if p not in seen_anti:
                        lines.append(f"  - Avoid '{p}'")
                        seen_anti.add(p)
                for opp in ep.missed_opportunities[:2]:
                    lines.append(f"  - Don't miss: {opp}")

        if pattern.suggested_skill and pattern.suggested_skill.get("method"):
            lines.append("")
            lines.append("## Suggested approach:")
            lines.append(f"  {pattern.suggested_skill['method']}")

        return "\n".join(lines)

    def _extract_constraints(self, bad_episodes: List[Episode]) -> List[str]:
        """Extract constraints (what NOT to do) from failed episodes."""
        constraints = []
        for ep in bad_episodes:
            if "trial-and-error-loop" in ep.reasoning_patterns:
                constraints.append(
                    "Do not retry the same action more than twice — "
                    "research alternative approach instead"
                )
            if "extended-session" in ep.reasoning_patterns:
                constraints.append(
                    "If task exceeds 10 minutes, pause and reassess "
                    "approach before continuing"
                )
        # Deduplicate
        return list(set(constraints))[:5]

    def _build_eval_tests(
        self, episodes: List[Episode]
    ) -> List[Dict]:
        """Build evaluation tests from episode data.

        Each test is a scenario that the skill should handle
        better than the baseline (no-skill) approach.
        """
        tests = []
        for ep in episodes:
            if ep.outcome_score < 0.5 and ep.task_description:
                tests.append({
                    "episode_id": ep.id,
                    "scenario": ep.task_description,
                    "baseline_score": ep.outcome_score,
                    "expected_improvement": 0.2,
                })
        return tests[:5]  # cap at 5 tests

    # ── Skill Validation (Shadow Mode) ────────────────────────────────

    def validate_skill(
        self,
        skill: Skill,
        store: MemoryStore,
    ) -> Evaluation:
        """Run a shadow validation of a proposed skill.

        Shadow validation replays historical episodes and
        estimates whether the skill would have improved outcomes.

        For v1, this is a structural check (are the skill's
        trigger conditions and method well-formed?). Future
        versions will use LLM-based counterfactual evaluation.
        """
        eval_result = Evaluation(
            key=f"eval:{skill.key}:{skill.shadow_runs + 1}",
            namespace=skill.namespace,
            skill_id=skill.id,
        )

        # Structural validation
        score = 0.0
        notes = []

        # Check trigger conditions
        if skill.trigger_conditions and skill.trigger_conditions != ["manual_trigger"]:
            score += 0.2
            notes.append("Has specific trigger conditions")
        else:
            notes.append("Missing specific triggers — may fire too broadly")

        # Check method quality
        if len(skill.method) > 50:
            score += 0.2
            notes.append("Has substantive method description")
        else:
            notes.append("Method is thin — needs more evidence")

        # Check constraints
        if skill.constraints:
            score += 0.15
            notes.append(f"Has {len(skill.constraints)} constraints")

        # Check eval tests
        if skill.eval_tests:
            score += 0.15
            notes.append(f"Has {len(skill.eval_tests)} eval scenarios")

            # Check if source episodes exist in store
            found = 0
            for test in skill.eval_tests:
                ep = store.get_by_id(test.get("episode_id", ""))
                if ep:
                    found += 1
            if found > 0:
                score += 0.15
                notes.append(
                    f"{found}/{len(skill.eval_tests)} test episodes "
                    f"found in store"
                )
        else:
            notes.append("No eval tests — cannot validate effectiveness")

        # Source episode count
        if len(skill.source_episode_ids) >= 3:
            score += 0.15
            notes.append(
                f"Based on {len(skill.source_episode_ids)} episodes "
                f"— good evidence base"
            )

        eval_result.score_delta = score
        eval_result.passed = score >= self.PROMOTION_THRESHOLD
        eval_result.notes = "; ".join(notes)

        # Update skill state
        skill.shadow_runs += 1
        skill.shadow_score = score
        skill.status = SkillStatus.VALIDATING

        logger.info(
            "Validation run %d for skill '%s': score=%.2f, passed=%s",
            skill.shadow_runs, skill.key, score, eval_result.passed,
        )

        return eval_result

    # ── Skill Lifecycle ───────────────────────────────────────────────

    def promote_skill(
        self,
        skill: Skill,
        store: MemoryStore,
    ) -> Tuple[bool, str]:
        """Promote a validated skill to active procedural memory.

        Only promotes if:
        1. Enough shadow runs completed
        2. Shadow score beats promotion threshold
        3. Not at skill cap
        """
        if skill.shadow_runs < self.MIN_SHADOW_RUNS:
            return False, (
                f"Need {self.MIN_SHADOW_RUNS} shadow runs, "
                f"have {skill.shadow_runs}"
            )

        if skill.shadow_score < self.PROMOTION_THRESHOLD:
            skill.status = SkillStatus.REJECTED
            store.write(skill)
            return False, (
                f"Shadow score {skill.shadow_score:.2f} below "
                f"threshold {self.PROMOTION_THRESHOLD}"
            )

        # Promote
        skill.status = SkillStatus.PROMOTED
        skill.trust_charge = 0.5    # promoted skills start at mid-trust
        skill.importance = 0.7      # high but not sacred
        success, reason = store.write(skill)

        if success:
            logger.info("Skill '%s' PROMOTED to procedural memory", skill.key)

        return success, f"Skill promoted: {reason}"

    def deprecate_skill(
        self,
        skill: Skill,
        store: MemoryStore,
        reason: str = "",
    ) -> Tuple[bool, str]:
        """Deprecate an underperforming skill.

        Deprecated skills remain in the vault for audit but are
        excluded from context assembly.
        """
        skill.status = SkillStatus.DEPRECATED
        skill.importance = 0.1      # de-prioritize in retrieval
        skill.trust_charge = 0.1    # low trust
        skill.metadata["deprecation_reason"] = reason
        skill.metadata["deprecated_at"] = time.time()
        success, msg = store.write(skill)

        if success:
            logger.info(
                "Skill '%s' DEPRECATED: %s", skill.key, reason
            )

        return success, f"Skill deprecated: {reason}"

    def evolve_skill(
        self,
        parent_skill: Skill,
        new_episodes: List[Episode],
        store: MemoryStore,
    ) -> Optional[Skill]:
        """Create a new version of an existing skill with updated evidence.

        The parent skill remains (for audit trail). The new version
        inherits the parent's structure but incorporates new evidence.
        """
        # Build new pattern from combined evidence
        all_episode_ids = (
            parent_skill.source_episode_ids +
            [e.id for e in new_episodes]
        )

        child = Skill(
            key=f"{parent_skill.key}:v{parent_skill.version + 1}",
            value=parent_skill.value,
            namespace=parent_skill.namespace,
            status=SkillStatus.PROPOSED,
            trigger_conditions=parent_skill.trigger_conditions,
            objective=parent_skill.objective,
            method=parent_skill.method,  # will be updated during validation
            constraints=parent_skill.constraints,
            eval_tests=parent_skill.eval_tests,
            source_episode_ids=all_episode_ids,
            pattern_description=parent_skill.pattern_description,
            version=parent_skill.version + 1,
            parent_skill_id=parent_skill.id,
        )

        # Deprecate the parent
        self.deprecate_skill(
            parent_skill, store,
            reason=f"Evolved to v{child.version}",
        )

        logger.info(
            "Evolved skill '%s' v%d -> v%d",
            parent_skill.key,
            parent_skill.version,
            child.version,
        )

        return child

    # ── Batch Operations ──────────────────────────────────────────────

    def process_patterns(
        self,
        patterns: List[PatternCluster],
        store: MemoryStore,
    ) -> List[Skill]:
        """Process a batch of patterns from the Retrospective.

        Drafts skills for all actionable patterns, runs initial
        validation, and returns the candidates.
        """
        drafted = []

        for pattern in patterns:
            if not pattern.is_actionable:
                continue

            skill = self.draft_from_pattern(pattern, store)
            if skill is None:
                continue

            # Run initial validation
            eval_result = self.validate_skill(skill, store)

            # Write to store (as VALIDATING)
            store.write(skill)

            drafted.append(skill)

            logger.info(
                "Processed pattern '%s' -> skill '%s' "
                "(validation: %.2f, passed: %s)",
                pattern.pattern_id,
                skill.key,
                eval_result.score_delta,
                eval_result.passed,
            )

        return drafted
