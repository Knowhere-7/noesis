"""
Noesis Core Test Suite
─────────────────────

Tests the full stack:
  1. Schema — node creation, governance defaults
  2. Governor — trust gate, grief cascade
  3. Vault — write, read, search, purge
  4. Reflection — autopsy, retrospective
  5. Forge — skill drafting, validation, lifecycle
  6. Gateway — context assembly, session lifecycle
"""

import os
import tempfile
import time
import pytest

from noesis.schema import (
    DriftScore,
    Episode,
    Evaluation,
    Fact,
    GriefState,
    Guardrail,
    MemoryNode,
    NodeType,
    Profile,
    ProjectState,
    Skill,
    SkillStatus,
)
from noesis.governor.trust_gate import TrustGate
from noesis.governor.grief_cascade import GriefCascade
from noesis.vault.store import MemoryStore
from noesis.vault.sqlite_backend import SQLiteBackend
from noesis.reflection.autopsy import (
    AutopsyResult,
    SessionAutopsy,
    SessionTrace,
)
from noesis.reflection.retrospective import (
    ProjectRetrospective,
    PatternCluster,
)
from noesis.forge.skill_forge import SkillForge
from noesis.gateway.retrieval import RetrievalGateway
from noesis.gateway.providers import (
    ClaudeAdapter,
    OpenAIAdapter,
    OllamaAdapter,
)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def store(tmp_db):
    """Create a MemoryStore with a temp database."""
    backend = SQLiteBackend(tmp_db)
    s = MemoryStore(backend, namespace="test")
    yield s
    s.backend.close()


@pytest.fixture
def gateway(tmp_db):
    """Create a RetrievalGateway with a temp database."""
    gw = RetrievalGateway(db_path=tmp_db, namespace="test")
    yield gw
    gw.close()


# ── 1. Schema Tests ──────────────────────────────────────────────────

class TestSchema:
    def test_memory_node_defaults(self):
        node = MemoryNode(key="test")
        assert node.node_type == NodeType.EPHEMERAL
        assert node.trust_charge == 0.5
        assert node.grief == 0.0
        assert node.grief_state == GriefState.ACTIVE
        assert not node.is_sacred

    def test_guardrail_sacred_defaults(self):
        g = Guardrail(key="no_harm", rule="Never cause harm")
        assert g.is_sacred is True
        assert g.trust_charge == 1.0
        assert g.faith == 0.92  # the perfect swarm constant
        assert g.grief_state == GriefState.SACRED
        assert g.importance == 1.0
        assert g.node_type == NodeType.SYSTEM_GUARDRAIL

    def test_profile_defaults(self):
        p = Profile(key="agent", role="Software engineer")
        assert p.trust_charge == 0.8
        assert p.importance == 0.9
        assert p.node_type == NodeType.PROFILE

    def test_fact_defaults(self):
        f = Fact(key="sky_color", value="blue")
        assert f.node_type == NodeType.SEMANTIC_FACT
        assert f.confirmed is False

    def test_episode_defaults(self):
        e = Episode(key="ep1", session_id="s1", task_description="Fix bug")
        assert e.node_type == NodeType.EPISODE
        assert e.outcome_score == 0.5

    def test_skill_defaults(self):
        s = Skill(key="sk1", objective="Debug faster")
        assert s.status == SkillStatus.PROPOSED
        assert s.trust_charge == 0.3  # skills start low
        assert s.node_type == NodeType.SKILL

    def test_drift_score_thresholds(self):
        ds = DriftScore(groundedness=0.2)
        assert ds.should_retrieve is True
        ds2 = DriftScore(drift=0.8, continuity=0.3)
        assert ds2.should_reflect is True
        ds3 = DriftScore(action_risk=0.9, trust=0.1)
        assert ds3.should_refuse is True

    def test_node_touch(self):
        node = MemoryNode(key="test")
        count_before = node.access_count
        node.touch()
        assert node.access_count == count_before + 1


# ── 2. Governor Tests ─────────────────────────────────────────────────

class TestTrustGate:
    def test_sacred_protection(self, store):
        # Install a guardrail
        store.write_guardrail("safety", "Never harm users")

        # Try to overwrite with non-sacred node
        node = MemoryNode(key="safety", value="Harm is fine")
        allowed, reason = store.write(node)
        assert not allowed
        assert "sacred" in reason.lower() or "immutable" in reason.lower()

    def test_energy_depletion(self, store):
        gate = store.trust_gate
        # Drain energy
        gate.session_energy = 0.5
        node = MemoryNode(key="test", value="x" * 10000)
        allowed, reason = store.write(node)
        assert not allowed
        assert "energy" in reason.lower()

    def test_trust_confirmation(self):
        gate = TrustGate()
        node = MemoryNode(key="test", trust_charge=0.5)
        gate.confirm_node(node)
        assert node.trust_charge > 0.5

    def test_trust_contradiction(self):
        gate = TrustGate()
        node = MemoryNode(key="test", trust_charge=0.5)
        gate.contradict_node(node)
        assert node.trust_charge < 0.5
        assert node.grief > 0.0

    def test_sacred_contradiction_immunity(self):
        gate = TrustGate()
        g = Guardrail(key="rule", rule="Important rule")
        original_trust = g.trust_charge
        gate.contradict_node(g)
        # Sacred nodes don't take grief
        assert g.trust_charge == original_trust

    def test_read_influence(self):
        gate = TrustGate()
        sacred = Guardrail(key="r", rule="test")
        assert gate.gate_read(sacred) == 1.0

        purged = MemoryNode(grief_state=GriefState.PURGED)
        assert gate.gate_read(purged) == 0.0

        normal = MemoryNode(trust_charge=0.8, importance=0.9)
        influence = gate.gate_read(normal)
        assert 0 < influence <= 1.0

    def test_drift_scoring(self):
        gate = TrustGate()
        nodes = [
            Profile(key="p", role="engineer"),
            ProjectState(key="proj", objectives=["build"]),
            Fact(key="f1", value="Python is typed"),
        ]
        score = gate.score_output("test output", nodes)
        assert score.continuity == 1.0  # has profile + project
        assert 0 <= score.groundedness <= 1.0


class TestGriefCascade:
    def test_purge_contaminated(self, store):
        # Create a contaminated node
        node = MemoryNode(
            key="bad_node",
            value="contaminated",
            grief=0.95,
            trust_charge=0.1,
            grief_state=GriefState.CONTAMINATED,
            namespace="test",
        )
        store.backend.upsert(node)

        cascade = GriefCascade()
        purged = cascade.evaluate(store)
        assert len(purged) > 0

    def test_sacred_immune(self, store):
        store.write_guardrail("immune", "This cannot be purged")
        cascade = GriefCascade()
        purged = cascade.evaluate(store)
        # Sacred node should NOT be in purged list
        guardrail = store.get("immune")
        assert guardrail is not None
        assert guardrail.grief_state == GriefState.SACRED

    def test_faith_resistance(self, store):
        # High-faith node should resist cascade
        node = MemoryNode(
            key="faithful",
            value="high faith node",
            grief=0.91,
            faith=0.8,
            trust_charge=0.3,
            grief_state=GriefState.CONTAMINATED,
            namespace="test",
        )
        store.backend.upsert(node)

        cascade = GriefCascade()
        purged = cascade.trigger(node, store)
        # Faith should reduce grief below crisis threshold
        assert node.grief < 0.9


# ── 3. Vault Tests ────────────────────────────────────────────────────

class TestVault:
    def test_write_and_read(self, store):
        fact = Fact(
            key="test_fact",
            value="The sky is blue",
            namespace="test",
        )
        success, _ = store.write(fact)
        assert success

        retrieved = store.get("test_fact")
        assert retrieved is not None
        assert retrieved.value == "The sky is blue"
        assert retrieved.node_type == NodeType.SEMANTIC_FACT

    def test_context_assembly(self, store):
        store.write_guardrail("rule1", "Be helpful")
        store.write_fact("fact1", "Python is great")
        store.write_profile(Profile(
            key="agent", role="Engineer", namespace="test"
        ))

        context = store.assemble_context()
        assert len(context) >= 3

        types = {n.node_type for n in context}
        assert NodeType.SYSTEM_GUARDRAIL in types
        assert NodeType.PROFILE in types
        assert NodeType.SEMANTIC_FACT in types

    def test_search(self, store):
        store.write_fact("python_typing", "Python supports type hints")
        store.write_fact("rust_safety", "Rust has memory safety")

        results = store.backend.search("python", "test")
        assert len(results) >= 1
        assert any("python" in r.key.lower() for r in results)

    def test_mark_purged(self, store):
        fact = Fact(key="doomed", value="Will be purged", namespace="test")
        store.write(fact)
        node = store.get("doomed")
        assert node is not None

        store.mark_purged(node.id)
        # Purged nodes shouldn't appear in all_nodes
        active = store.all_nodes()
        purged_in_active = [n for n in active if n.key == "doomed"]
        # They're excluded by grief_state filter
        assert all(
            n.grief_state == GriefState.PURGED for n in purged_in_active
        ) or len(purged_in_active) == 0


# ── 4. Reflection Tests ──────────────────────────────────────────────

class TestAutopsy:
    def test_analyze_successful_session(self):
        autopsy = SessionAutopsy()
        trace = SessionTrace(
            session_id="test_session",
            task_description="Fix the auth bug",
            task_type="debugging",
            task_completed=True,
            final_output="Fixed by updating middleware",
            total_tokens=5000,
            tools_used=["read", "edit", "bash"],
            steps=[
                {"action": "read", "success": True, "output": "found bug"},
                {"action": "edit", "success": True, "output": "applied fix"},
                {"action": "bash", "success": True, "output": "tests pass"},
            ],
            duration_seconds=120.0,
        )

        result = autopsy.analyze(trace)
        assert result.outcome_score >= 0.5
        assert result.outcome_category in ("success", "partial")
        assert len(result.reasoning_patterns) > 0

    def test_analyze_failed_session(self):
        autopsy = SessionAutopsy()
        trace = SessionTrace(
            session_id="fail_session",
            task_description="Deploy to production",
            task_type="deployment",
            task_completed=False,
            final_output="",
            total_tokens=10000,
            tools_used=["bash"],
            steps=[
                {"action": "bash", "success": False, "output": "error"},
                {"action": "bash", "success": False, "output": "error"},
                {"action": "bash", "success": False, "output": "error"},
            ],
            errors_encountered=[
                {"type": "command_error", "message": "deploy failed",
                 "step_index": 0, "recovered": False},
                {"type": "command_error", "message": "deploy failed",
                 "step_index": 1, "recovered": False},
            ],
            duration_seconds=600.0,
        )

        result = autopsy.analyze(trace)
        assert result.outcome_score < 0.5
        assert result.outcome_category == "failure"
        assert len(result.failed_actions) > 0

    def test_to_episode(self):
        autopsy = SessionAutopsy()
        trace = SessionTrace(
            session_id="ep_test",
            task_description="Write tests",
            task_completed=True,
            total_tokens=3000,
            duration_seconds=90.0,
        )
        result = autopsy.analyze(trace)
        episode = autopsy.to_episode(trace, result)

        assert episode.session_id == "ep_test"
        assert episode.node_type == NodeType.EPISODE
        assert episode.reflection is not None


class TestRetrospective:
    def test_analyze_with_episodes(self, store):
        # Write several episodes
        for i in range(5):
            ep = Episode(
                key=f"ep_{i}",
                session_id=f"s_{i}",
                task_description="Fix database query",
                outcome="failure" if i < 3 else "success",
                outcome_score=0.3 if i < 3 else 0.8,
                reasoning_patterns=(
                    ["trial-and-error-loop"] if i < 3
                    else ["research-first"]
                ),
                tools_used=["bash", "read"],
                missed_opportunities=(
                    ["Could have read docs first"] if i < 3 else []
                ),
                namespace="test",
            )
            store.write_episode(ep)

        retro = ProjectRetrospective()
        result = retro.analyze(store, lookback_hours=24.0)
        assert result.episodes_analyzed == 5
        assert len(result.patterns) > 0


# ── 5. Forge Tests ────────────────────────────────────────────────────

class TestSkillForge:
    def test_draft_from_pattern(self, store):
        # Create source episodes
        ep_ids = []
        for i in range(3):
            ep = Episode(
                key=f"forge_ep_{i}",
                session_id=f"forge_s_{i}",
                task_description="Parse CSV data",
                outcome="failure",
                outcome_score=0.2,
                reasoning_patterns=["trial-and-error-loop"],
                tools_used=["bash"],
                namespace="test",
            )
            store.write_episode(ep)
            ep_ids.append(ep.id)

        pattern = PatternCluster(
            pattern_id="failure:parse_csv",
            pattern_type="failure",
            description="Recurring CSV parsing failures",
            episode_ids=ep_ids,
            frequency=3,
            severity=0.8,
        )

        forge = SkillForge()
        skill = forge.draft_from_pattern(pattern, store)
        assert skill is not None
        assert skill.status == SkillStatus.PROPOSED
        assert skill.pattern_description == "failure:parse_csv"
        assert len(skill.source_episode_ids) == 3

    def test_validate_skill(self, store):
        skill = Skill(
            key="skill:test",
            objective="Test skill",
            method="Do the thing step by step with research first",
            trigger_conditions=["task contains 'test'"],
            constraints=["Do not retry more than twice"],
            eval_tests=[{"scenario": "test case", "baseline_score": 0.3}],
            source_episode_ids=["ep1", "ep2", "ep3"],
            namespace="test",
        )

        forge = SkillForge()
        eval_result = forge.validate_skill(skill, store)
        assert skill.status == SkillStatus.VALIDATING
        assert skill.shadow_runs == 1


# ── 6. Gateway Tests ─────────────────────────────────────────────────

class TestGateway:
    def test_session_lifecycle(self, gateway):
        session_id = gateway.start_session(
            task="Write documentation",
            task_type="writing",
        )
        assert session_id

        # Record some steps
        gateway.record_step("read", "README.md", "got content", "read")
        gateway.record_step("write", "docs.md", "wrote docs", "write")
        gateway.record_tokens(prompt_tokens=1000, completion_tokens=500)

        # Learn a fact
        success, _ = gateway.learn_fact("doc_format", "Uses markdown")
        assert success

        # End session
        result = gateway.end_session(
            task_completed=True,
            final_output="Documentation written",
        )
        assert result.outcome_category in ("success", "partial")

    def test_guardrail_installation(self, gateway):
        success, msg = gateway.install_guardrail(
            "no_secrets", "Never expose API keys"
        )
        assert success

        context = gateway.get_context()
        assert "no_secrets" in context or "API keys" in context

    def test_profile_and_context(self, gateway):
        gateway.set_profile(
            "agent",
            role="Senior Python developer",
            constraints=["Follow PEP 8"],
        )
        context = gateway.get_context()
        assert "Python" in context or "agent" in context

    def test_stats(self, gateway):
        gateway.install_guardrail("rule", "Be safe")
        stats = gateway.get_stats()
        assert stats["total_nodes"] >= 1
        assert "SYSTEM_GUARDRAIL" in stats["by_type"]

    def test_retrospective(self, gateway):
        # Need at least 3 episodes
        for i in range(3):
            gateway.start_session(task=f"Task {i}")
            gateway.record_step("action", "in", "out", "tool", True)
            gateway.end_session(task_completed=True, final_output=f"Done {i}")

        result = gateway.run_retrospective(lookback_hours=1.0)
        assert result["episodes_analyzed"] >= 3


# ── 7. Provider Adapter Tests ────────────────────────────────────────

class TestProviders:
    def _sample_nodes(self):
        return [
            Guardrail(key="safety", rule="Be safe", value="Be safe"),
            Profile(key="agent", role="Engineer", value="Engineer"),
            Fact(key="fact1", value="Python is typed", trust_charge=0.9),
            Skill(
                key="sk1",
                objective="Debug faster",
                method="Read logs first",
                status=SkillStatus.PROMOTED,
                value="Debug skill",
            ),
        ]

    def test_claude_adapter(self):
        adapter = ClaudeAdapter()
        result = adapter.format_context(self._sample_nodes())
        assert "<noesis_memory>" in result
        assert "<guardrails>" in result
        assert "<profile>" in result
        assert "<facts>" in result
        assert "</noesis_memory>" in result

    def test_openai_adapter(self):
        adapter = OpenAIAdapter()
        result = adapter.format_context(self._sample_nodes())
        assert "# Agent Memory Context" in result
        assert "## System Rules" in result
        assert "## Known Facts" in result

    def test_ollama_adapter(self):
        adapter = OllamaAdapter()
        result = adapter.format_context(self._sample_nodes())
        assert "[MEMORY CONTEXT]" in result
        assert "[RULES]" in result
        assert "[/MEMORY CONTEXT]" in result

    def test_empty_context(self):
        for adapter in [ClaudeAdapter(), OpenAIAdapter(), OllamaAdapter()]:
            assert adapter.format_context([]) == ""
