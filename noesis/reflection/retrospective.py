"""
Project Retrospective — Cross-episode pattern detection.

While the SessionAutopsy looks at individual sessions, the
ProjectRetrospective looks across the full episode history to find:

  1. Recurring failure patterns (same type of mistake, different sessions)
  2. Skill effectiveness (are promoted skills actually helping?)
  3. Trust trajectory (is the agent getting better or worse?)
  4. Behavioral drift (is the agent straying from its role?)

When recurring patterns hit a threshold (3+ similar failures),
the retrospective generates a SkillCandidate for the Skill Forge.

From Ghost's original prompt:
  "create this memory as a self-reflective system where agent
   scrutinizes its own performance during its previous session
   and then for the project overall to seek out areas fit for
   optimization and actions that couldve been performed better"
"""

from __future__ import annotations

import logging
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from noesis.schema import (
    Episode,
    GriefState,
    MemoryNode,
    NodeType,
    Skill,
    SkillStatus,
)

if TYPE_CHECKING:
    from noesis.vault.store import MemoryStore

logger = logging.getLogger("noesis.reflection")


# ── Retrospective Results ─────────────────────────────────────────────

@dataclass
class PatternCluster:
    """A recurring pattern detected across multiple episodes.

    When frequency >= promotion_threshold, this becomes a
    SkillCandidate for the Skill Forge.
    """
    pattern_id: str = ""
    pattern_type: str = ""          # "failure", "missed_opportunity", "antipattern"
    description: str = ""
    episode_ids: List[str] = field(default_factory=list)
    frequency: int = 0
    first_seen: float = 0.0
    last_seen: float = 0.0
    severity: float = 0.5           # [0, 1] — impact on outcomes
    suggested_skill: Optional[Dict[str, str]] = None

    @property
    def is_actionable(self) -> bool:
        """Has this pattern been seen enough to warrant a skill?"""
        return self.frequency >= 3


@dataclass
class TrustTrajectory:
    """How trust is trending across recent episodes."""
    current_avg: float = 0.5
    previous_avg: float = 0.5
    trend: str = "stable"           # "improving", "declining", "stable"
    episodes_analyzed: int = 0
    best_episode_score: float = 0.0
    worst_episode_score: float = 1.0
    volatility: float = 0.0         # std dev of scores — high = unstable


@dataclass
class SkillReport:
    """How well are promoted skills performing?"""
    skill_id: str = ""
    skill_key: str = ""
    episodes_with_skill: int = 0
    avg_score_with: float = 0.5
    avg_score_without: float = 0.5
    effectiveness: float = 0.0      # positive = helping, negative = hurting
    recommendation: str = ""        # "keep", "review", "deprecate"


@dataclass
class RetrospectiveResult:
    """Full output of the project retrospective."""
    # Pattern detection
    patterns: List[PatternCluster] = field(default_factory=list)
    actionable_patterns: List[PatternCluster] = field(default_factory=list)

    # Trust analysis
    trust_trajectory: TrustTrajectory = field(default_factory=TrustTrajectory)

    # Skill effectiveness
    skill_reports: List[SkillReport] = field(default_factory=list)

    # Summary
    overall_health: float = 0.5     # [0, 1]
    recommendations: List[str] = field(default_factory=list)
    episodes_analyzed: int = 0
    time_span_hours: float = 0.0


class ProjectRetrospective:
    """Cross-episode pattern detection and trend analysis.

    Runs periodically (or on-demand) to analyze the full episode
    history and surface actionable patterns for the Skill Forge.

    The retrospective is the feedback loop that closes the gap
    between "the agent failed" and "the agent learned not to fail."
    """

    # How many similar failures before we flag it
    PATTERN_THRESHOLD = 3
    # How many recent episodes to analyze for trust trajectory
    TRAJECTORY_WINDOW = 20
    # Minimum episodes before retrospective is meaningful
    MIN_EPISODES = 3

    def __init__(self):
        self._known_patterns: Dict[str, PatternCluster] = {}

    def analyze(
        self,
        store: MemoryStore,
        lookback_hours: float = 168.0,  # 1 week default
    ) -> RetrospectiveResult:
        """Run the full project retrospective.

        Analyzes all episodes within the lookback window and
        produces patterns, trust trajectory, and skill reports.
        """
        result = RetrospectiveResult()

        # Get all episodes
        episodes = store.backend.get_by_type(
            NodeType.EPISODE, store.namespace
        )
        episodes = [
            e for e in episodes
            if isinstance(e, Episode)
            and e.grief_state != GriefState.PURGED
        ]

        # Filter to lookback window
        cutoff = time.time() - (lookback_hours * 3600)
        recent = [e for e in episodes if e.created_at >= cutoff]

        if len(recent) < self.MIN_EPISODES:
            result.recommendations.append(
                f"Only {len(recent)} episodes in the last "
                f"{lookback_hours:.0f}h. Need at least {self.MIN_EPISODES} "
                f"for meaningful retrospective."
            )
            result.episodes_analyzed = len(recent)
            return result

        result.episodes_analyzed = len(recent)
        if recent:
            result.time_span_hours = (
                (recent[0].created_at - recent[-1].created_at) / 3600
            )

        # 1. Detect recurring patterns
        result.patterns = self._detect_patterns(recent)
        result.actionable_patterns = [
            p for p in result.patterns if p.is_actionable
        ]

        # 2. Analyze trust trajectory
        result.trust_trajectory = self._analyze_trust(recent)

        # 3. Evaluate skill effectiveness
        skills = store.backend.get_by_type(
            NodeType.SKILL, store.namespace
        )
        promoted = [
            s for s in skills
            if isinstance(s, Skill) and s.status == SkillStatus.PROMOTED
        ]
        if promoted:
            result.skill_reports = self._evaluate_skills(
                promoted, recent
            )

        # 4. Compute overall health
        result.overall_health = self._compute_health(result)

        # 5. Generate recommendations
        result.recommendations = self._generate_recommendations(result)

        logger.info(
            "Retrospective complete: %d episodes, %d patterns "
            "(%d actionable), health=%.2f",
            result.episodes_analyzed,
            len(result.patterns),
            len(result.actionable_patterns),
            result.overall_health,
        )

        return result

    # ── Pattern Detection ─────────────────────────────────────────────

    def _detect_patterns(
        self, episodes: List[Episode]
    ) -> List[PatternCluster]:
        """Scan episodes for recurring patterns.

        Groups by:
        - Failure type (what went wrong)
        - Missed opportunity type (what could have been better)
        - Reasoning anti-patterns (how the agent thinks)
        """
        # Collect all failure signals
        failure_groups: Dict[str, List[Episode]] = defaultdict(list)
        missed_groups: Dict[str, List[Episode]] = defaultdict(list)
        pattern_groups: Dict[str, List[Episode]] = defaultdict(list)

        for ep in episodes:
            # Group failures by outcome category
            if ep.outcome in ("failure", "partial"):
                # Use task description keywords as grouping key
                task_key = self._normalize_task_key(ep.task_description)
                failure_groups[task_key].append(ep)

            # Group missed opportunities
            for opp in ep.missed_opportunities:
                opp_key = self._normalize_pattern_key(opp)
                missed_groups[opp_key].append(ep)

            # Group reasoning patterns
            for pattern in ep.reasoning_patterns:
                if pattern in (
                    "trial-and-error-loop",
                    "extended-session",
                ):
                    pattern_groups[pattern].append(ep)

        # Build PatternClusters
        clusters = []

        for key, eps in failure_groups.items():
            if len(eps) >= 2:  # flag early, actionable at 3
                cluster = PatternCluster(
                    pattern_id=f"failure:{key}",
                    pattern_type="failure",
                    description=(
                        f"Recurring failure in '{key}' tasks "
                        f"({len(eps)} occurrences)"
                    ),
                    episode_ids=[e.id for e in eps],
                    frequency=len(eps),
                    first_seen=min(e.created_at for e in eps),
                    last_seen=max(e.created_at for e in eps),
                    severity=1.0 - (
                        sum(e.outcome_score for e in eps) / len(eps)
                    ),
                )
                if cluster.is_actionable:
                    cluster.suggested_skill = {
                        "trigger": f"task contains '{key}'",
                        "objective": (
                            f"Prevent recurring failure pattern in "
                            f"{key} tasks"
                        ),
                        "method": self._suggest_skill_method(eps),
                    }
                clusters.append(cluster)

        for key, eps in missed_groups.items():
            if len(eps) >= 2:
                cluster = PatternCluster(
                    pattern_id=f"missed:{key}",
                    pattern_type="missed_opportunity",
                    description=(
                        f"Repeatedly missed: '{key}' "
                        f"({len(eps)} occurrences)"
                    ),
                    episode_ids=[e.id for e in eps],
                    frequency=len(eps),
                    first_seen=min(e.created_at for e in eps),
                    last_seen=max(e.created_at for e in eps),
                    severity=0.4,
                )
                clusters.append(cluster)

        for key, eps in pattern_groups.items():
            if len(eps) >= 2:
                cluster = PatternCluster(
                    pattern_id=f"antipattern:{key}",
                    pattern_type="antipattern",
                    description=(
                        f"Anti-pattern '{key}' detected in "
                        f"{len(eps)} sessions"
                    ),
                    episode_ids=[e.id for e in eps],
                    frequency=len(eps),
                    first_seen=min(e.created_at for e in eps),
                    last_seen=max(e.created_at for e in eps),
                    severity=0.3,
                )
                clusters.append(cluster)

        # Sort by severity * frequency (most urgent first)
        clusters.sort(
            key=lambda c: c.severity * c.frequency, reverse=True
        )
        return clusters

    # ── Trust Trajectory ──────────────────────────────────────────────

    def _analyze_trust(
        self, episodes: List[Episode]
    ) -> TrustTrajectory:
        """Analyze how agent trust is trending over recent episodes."""
        traj = TrustTrajectory()

        if not episodes:
            return traj

        # Sort by creation time (oldest first)
        sorted_eps = sorted(episodes, key=lambda e: e.created_at)
        scores = [e.outcome_score for e in sorted_eps]

        traj.episodes_analyzed = len(scores)
        traj.best_episode_score = max(scores)
        traj.worst_episode_score = min(scores)

        # Overall average
        traj.current_avg = sum(scores) / len(scores)

        # Split into halves for trend
        mid = len(scores) // 2
        if mid > 0:
            first_half = scores[:mid]
            second_half = scores[mid:]
            traj.previous_avg = sum(first_half) / len(first_half)
            current = sum(second_half) / len(second_half)

            delta = current - traj.previous_avg
            if delta > 0.05:
                traj.trend = "improving"
            elif delta < -0.05:
                traj.trend = "declining"
            else:
                traj.trend = "stable"
        else:
            traj.previous_avg = traj.current_avg

        # Volatility (standard deviation)
        if len(scores) > 1:
            mean = traj.current_avg
            variance = sum((s - mean) ** 2 for s in scores) / len(scores)
            traj.volatility = variance ** 0.5

        return traj

    # ── Skill Effectiveness ───────────────────────────────────────────

    def _evaluate_skills(
        self,
        skills: List[Skill],
        episodes: List[Episode],
    ) -> List[SkillReport]:
        """Evaluate how well promoted skills are performing.

        Compares episode scores from sessions where the skill
        was active vs sessions before the skill was promoted.
        """
        reports = []

        for skill in skills:
            report = SkillReport(
                skill_id=skill.id,
                skill_key=skill.key,
            )

            # Find episodes that match this skill's trigger conditions
            matching = [
                e for e in episodes
                if self._skill_matches_episode(skill, e)
            ]

            if not matching:
                report.recommendation = "no_data"
                reports.append(report)
                continue

            # Split by whether episode was before or after skill promotion
            # (Using source_episode_ids as the "before" baseline)
            before_ids = set(skill.source_episode_ids)
            before = [e for e in matching if e.id in before_ids]
            after = [e for e in matching if e.id not in before_ids]

            if before:
                report.avg_score_without = (
                    sum(e.outcome_score for e in before) / len(before)
                )
            if after:
                report.episodes_with_skill = len(after)
                report.avg_score_with = (
                    sum(e.outcome_score for e in after) / len(after)
                )

            report.effectiveness = (
                report.avg_score_with - report.avg_score_without
            )

            # Recommendation
            if report.episodes_with_skill < 3:
                report.recommendation = "insufficient_data"
            elif report.effectiveness > 0.1:
                report.recommendation = "keep"
            elif report.effectiveness < -0.1:
                report.recommendation = "deprecate"
            else:
                report.recommendation = "review"

            reports.append(report)

        return reports

    # ── Health & Recommendations ──────────────────────────────────────

    def _compute_health(self, result: RetrospectiveResult) -> float:
        """Single number for overall project health [0, 1]."""
        health = 0.5

        # Trust trajectory
        if result.trust_trajectory.trend == "improving":
            health += 0.15
        elif result.trust_trajectory.trend == "declining":
            health -= 0.15

        # Actionable patterns (more = worse)
        pattern_penalty = min(
            0.3, len(result.actionable_patterns) * 0.1
        )
        health -= pattern_penalty

        # Average outcome score
        health += (result.trust_trajectory.current_avg - 0.5) * 0.3

        # Volatility penalty
        health -= result.trust_trajectory.volatility * 0.2

        # Skill effectiveness bonus
        if result.skill_reports:
            effective = sum(
                1 for s in result.skill_reports
                if s.recommendation == "keep"
            )
            if result.skill_reports:
                health += (effective / len(result.skill_reports)) * 0.1

        return max(0.0, min(1.0, health))

    def _generate_recommendations(
        self, result: RetrospectiveResult
    ) -> List[str]:
        """Generate actionable recommendations from the analysis."""
        recs = []

        # Trust trajectory
        if result.trust_trajectory.trend == "declining":
            recs.append(
                f"Trust is declining (avg {result.trust_trajectory.current_avg:.2f} "
                f"vs previous {result.trust_trajectory.previous_avg:.2f}). "
                f"Review recent failures and consider reverting recent changes."
            )
        elif result.trust_trajectory.trend == "improving":
            recs.append(
                f"Trust is improving ({result.trust_trajectory.previous_avg:.2f} "
                f"-> {result.trust_trajectory.current_avg:.2f}). "
                f"Current approach is working."
            )

        # High volatility
        if result.trust_trajectory.volatility > 0.25:
            recs.append(
                f"High outcome volatility ({result.trust_trajectory.volatility:.2f}). "
                f"Performance is inconsistent — consider adding guardrails "
                f"for the volatile task types."
            )

        # Actionable patterns
        for pattern in result.actionable_patterns[:3]:
            recs.append(
                f"SKILL CANDIDATE: {pattern.description} "
                f"(severity {pattern.severity:.2f}, "
                f"seen {pattern.frequency}x). "
                f"Feed to Skill Forge."
            )

        # Skill deprecation
        for report in result.skill_reports:
            if report.recommendation == "deprecate":
                recs.append(
                    f"Skill '{report.skill_key}' is underperforming "
                    f"(effectiveness {report.effectiveness:+.2f}). "
                    f"Consider deprecating."
                )

        return recs

    # ── Helpers ────────────────────────────────────────────────────────

    def _normalize_task_key(self, description: str) -> str:
        """Extract a grouping key from a task description.

        For v1, uses simple keyword extraction. Future versions
        will use embedding similarity.
        """
        if not description:
            return "unknown"
        # Take first 3 significant words
        words = [
            w.lower().strip(".,!?;:")
            for w in description.split()
            if len(w) > 3
        ]
        return "_".join(words[:3]) if words else "unknown"

    def _normalize_pattern_key(self, text: str) -> str:
        """Normalize a pattern description for grouping."""
        if not text:
            return "unknown"
        words = [
            w.lower().strip(".,!?;:'\"")
            for w in text.split()
            if len(w) > 3
        ]
        return "_".join(words[:4]) if words else "unknown"

    def _suggest_skill_method(self, episodes: List[Episode]) -> str:
        """Suggest a skill method based on failed episodes.

        Looks at what the successful episodes did differently
        from the failed ones.
        """
        good = [e for e in episodes if e.outcome_score >= 0.7]
        bad = [e for e in episodes if e.outcome_score < 0.4]

        if good and bad:
            good_tools = set()
            bad_tools = set()
            for e in good:
                good_tools.update(e.tools_used)
            for e in bad:
                bad_tools.update(e.tools_used)

            only_in_good = good_tools - bad_tools
            if only_in_good:
                return (
                    f"Use tools: {', '.join(only_in_good)}. "
                    f"These were present in successful sessions "
                    f"but absent in failures."
                )

        if bad:
            common_patterns = Counter()
            for e in bad:
                common_patterns.update(e.reasoning_patterns)
            if common_patterns:
                worst = common_patterns.most_common(1)[0][0]
                return f"Avoid pattern '{worst}' — use research-first approach instead."

        return "Review episode history for effective approaches."

    def _skill_matches_episode(
        self, skill: Skill, episode: Episode
    ) -> bool:
        """Check if a skill's trigger conditions match an episode.

        For v1, simple keyword matching against task description
        and tools used.
        """
        for trigger in skill.trigger_conditions:
            trigger_lower = trigger.lower()
            if (
                trigger_lower in episode.task_description.lower() or
                trigger_lower in " ".join(episode.tools_used).lower()
            ):
                return True
        return False
