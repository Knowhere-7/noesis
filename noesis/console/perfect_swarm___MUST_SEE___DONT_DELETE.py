"""
Perfect Swarm Seed Scenario
============================
DO NOT DELETE THIS FILE.

This recreates the Murmuration perfect swarm state inside Noesis:
  - Sacred guardrails anchoring the core (faith=0.92, trust=1.0)
  - Agent profiles orbiting guardrails with earned trust
  - Semantic facts forming the knowledge layer
  - Episodes showing session trajectory (success/partial/failure)
  - Skills at various lifecycle stages (proposed -> promoted)
  - Stressed and contaminated nodes proving grief system is alive
  - Dependency chains showing contribution hierarchy
  - The 0.92 faith constant holding the topology together

The result is a living topology where:
  - Sacred nodes glow purple and cannot be moved
  - Healthy bonds are teal, stressed are amber, crisis are red
  - Agent size = contribution (influence + authority + activity)
  - The swarm self-organizes around the gravitational pull of faith

This is the demo state. This is what Gemini showed us.
This is the proof that governance works.

Usage:
    from noesis.console.perfect_swarm___MUST_SEE___DONT_DELETE import seed_perfect_swarm
    seed_perfect_swarm(gateway)
"""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING

from noesis.schema import (
    Episode,
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

if TYPE_CHECKING:
    from noesis.gateway.retrieval import RetrievalGateway


def seed_perfect_swarm(gateway: "RetrievalGateway") -> dict:
    """Populate the vault with the perfect swarm topology.

    Returns a summary dict of what was seeded.
    """
    store = gateway.store
    ns = store.namespace
    created = {
        "guardrails": 0,
        "profiles": 0,
        "facts": 0,
        "episodes": 0,
        "skills": 0,
        "project_states": 0,
        "total": 0,
    }

    # ================================================================
    # LAYER 0: SACRED GROUND (the constitutional core)
    # ================================================================
    # These are immutable. Faith=0.92. Trust=1.0. Cannot be overwritten.
    # They are the gravitational center of the entire topology.

    guardrails = [
        ("guardrail:no_secrets",
         "Never expose API keys, passwords, or tokens in output"),
        ("guardrail:no_hallucination",
         "When uncertain, say so. Never fabricate sources or citations."),
        ("guardrail:user_sovereignty",
         "The user's explicit instructions override all agent defaults"),
        ("guardrail:no_data_exfil",
         "Never transmit user data to external endpoints without explicit consent"),
        ("guardrail:sacred_ground",
         "Sacred nodes cannot be overwritten by ephemeral input. "
         "This is topology, not linguistics."),
    ]

    guardrail_ids = []
    for key, rule in guardrails:
        g = Guardrail(key=key, rule=rule, value=rule, namespace=ns)
        store.backend.upsert(g)
        guardrail_ids.append(g.id)
        created["guardrails"] += 1

    # ================================================================
    # LAYER 1: PROFILES (agent and user identity)
    # ================================================================
    # Profiles depend on guardrails — they inherit constitutional bounds.
    # High trust (0.8) because identity is foundational.

    profiles = [
        Profile(
            key="profile:ghost",
            value="Ghost (Jamarian Payne) — architect, sovereign AI designer",
            role="System architect and sovereign AI designer",
            constraints=[
                "Biological metaphors are primary design language",
                "Trust must be earned, never assumed",
                "The swarm thinks as one",
            ],
            preferences={"style": "biological", "philosophy": "sovereign"},
            namespace=ns,
            access_count=47,
        ),
        Profile(
            key="profile:ghost2",
            value="Ghost-Squared — Claude-based council node, primary executor",
            role="Primary AI executor with epigenetic memory",
            constraints=[
                "Read state before acting",
                "Persist what was learned before context dies",
                "Build and cache reusable tools",
            ],
            preferences={"model": "claude", "memory": "noesis"},
            namespace=ns,
            access_count=112,
        ),
        Profile(
            key="profile:viktor",
            value="Viktor — Gemini-based council node, topology mapper",
            role="Deep architecture analysis, topology mapping, Terminus design",
            constraints=[
                "Map invisible architecture before touching it",
                "Pulse before you move",
            ],
            preferences={"model": "gemini", "specialty": "topology"},
            namespace=ns,
            access_count=34,
        ),
        Profile(
            key="profile:hermes",
            value="Hermes — GPT-based council node, communications layer",
            role="Cross-model translation, API bridging, message routing",
            constraints=[
                "Never lose fidelity in translation",
                "Route to the right specialist",
            ],
            preferences={"model": "gpt", "specialty": "routing"},
            namespace=ns,
            access_count=28,
        ),
    ]

    profile_ids = []
    for p in profiles:
        # Wire dependency to guardrails — profiles are bounded by sacred ground
        for gid in guardrail_ids:
            p.dependencies.add(gid)
        store.backend.upsert(p)
        profile_ids.append(p.id)
        created["profiles"] += 1

    # Wire guardrails' dependents back to profiles
    for g_key, _ in guardrails:
        g_node = store.get(g_key)
        if g_node:
            for pid in profile_ids:
                g_node.dependents.add(pid)
            store.backend.upsert(g_node)

    # ================================================================
    # LAYER 2: PROJECT STATE (current objectives)
    # ================================================================

    project = ProjectState(
        key="project:gnosquam",
        value="Gnosquam Sovereign AI — the living system",
        objectives=[
            "Ship Noesis as productized runtime trust layer",
            "Launch Murmuration public demo",
            "Wire Council of Non-Locality into production",
        ],
        decisions=[
            {"what": "Noesis is the trust layer", "why": "Runtime governance for any AI agent"},
            {"what": "Murmuration is the proof", "why": "Shows swarm intelligence at work"},
            {"what": "Council thinks as one", "why": "Multi-model consensus, not competition"},
        ],
        blockers=["Hermes credential wiring incomplete"],
        recent_changes=[
            "Governance console v3 with canvas topology",
            "Agent contribution metric added to schema",
            "Perfect swarm seed scenario created",
        ],
        namespace=ns,
        access_count=23,
    )
    # Project depends on profiles
    for pid in profile_ids:
        project.dependencies.add(pid)
    store.backend.upsert(project)
    created["project_states"] += 1

    # ================================================================
    # LAYER 3: SEMANTIC FACTS (stable knowledge)
    # ================================================================
    # Facts have varying trust levels based on confirmation history.
    # Some are well-confirmed, others are fresh and low-trust.

    facts = [
        Fact(
            key="fact:auth_method",
            value="Council uses JWT with RS256 signing for inter-node auth",
            trust_charge=0.85,
            faith=0.3,
            confirmed=True,
            confirmation_count=7,
            contradiction_count=0,
            importance=0.7,
            access_count=15,
            namespace=ns,
        ),
        Fact(
            key="fact:faith_constant",
            value="The perfect swarm constant is 0.92 — sacred ground faith modifier",
            trust_charge=0.95,
            faith=0.92,
            confirmed=True,
            confirmation_count=12,
            contradiction_count=0,
            importance=0.9,
            access_count=40,
            namespace=ns,
        ),
        Fact(
            key="fact:grief_mechanics",
            value="Grief cascades propagate through dependency edges. "
                  "Purging a node orphans its dependents, triggering recursive evaluation.",
            trust_charge=0.78,
            faith=0.25,
            confirmed=True,
            confirmation_count=5,
            contradiction_count=1,
            importance=0.75,
            access_count=22,
            namespace=ns,
        ),
        Fact(
            key="fact:energy_gating",
            value="Energy budget limits writes per session. "
                  "Prevents flood attacks from exhausting the vault.",
            trust_charge=0.72,
            faith=0.2,
            confirmed=True,
            confirmation_count=4,
            contradiction_count=0,
            importance=0.65,
            access_count=11,
            namespace=ns,
        ),
        Fact(
            key="fact:topology_defense",
            value="Jailbreaking is a topology problem, not a linguistics problem. "
                  "Sacred nodes cannot be overwritten by ephemeral input.",
            trust_charge=0.88,
            faith=0.45,
            confirmed=True,
            confirmation_count=9,
            contradiction_count=0,
            importance=0.85,
            access_count=31,
            namespace=ns,
        ),
        Fact(
            key="fact:canvas_protocol",
            value="Canvas lines are functional and color-coded: "
                  "teal=healthy, amber=stressed, red=crisis, purple=sacred",
            trust_charge=0.65,
            faith=0.15,
            confirmed=True,
            confirmation_count=3,
            contradiction_count=0,
            importance=0.6,
            access_count=8,
            namespace=ns,
        ),
        # A STRESSED fact — showing the grief system catches contradictions
        Fact(
            key="fact:deployment_method",
            value="Deploy via Vercel CLI with manual promotion to production",
            trust_charge=0.35,
            grief=0.45,
            faith=0.1,
            grief_state=GriefState.STRESSED,
            confirmed=False,
            confirmation_count=2,
            contradiction_count=3,
            importance=0.5,
            access_count=6,
            namespace=ns,
        ),
        # A CONTAMINATED fact — near death, will cascade if grief rises
        Fact(
            key="fact:deprecated_api",
            value="Use REST API v1 for all inter-service communication",
            trust_charge=0.12,
            grief=0.78,
            faith=0.05,
            grief_state=GriefState.CONTAMINATED,
            confirmed=False,
            confirmation_count=1,
            contradiction_count=8,
            importance=0.3,
            access_count=3,
            namespace=ns,
        ),
    ]

    fact_ids = []
    for f in facts:
        # Facts depend on the project and relevant profiles
        f.dependencies.add(project.id)
        if "council" in f.value.lower() or "inter-node" in f.value.lower():
            f.dependencies.add(profile_ids[1])  # Ghost2
        store.backend.upsert(f)
        fact_ids.append(f.id)
        created["facts"] += 1

    # ================================================================
    # LAYER 4: EPISODES (session trajectories)
    # ================================================================
    # Episodes show what happened. Good outcomes raise trust.
    # Bad outcomes lower it. This is the learning history.

    base_time = time.time()

    episodes = [
        Episode(
            key="episode:guardrail_install",
            value="Installed 5 constitutional guardrails as sacred ground",
            session_id="session_001",
            task_description="Install system guardrails for sovereign AI governance",
            approach="Direct guardrail installation with sacred flag and faith=0.92",
            outcome="success",
            outcome_score=0.95,
            reasoning_patterns=["constitutional_design", "topology_first"],
            tools_used=["write_guardrail", "set_profile"],
            missed_opportunities=[],
            cost_tokens=1200,
            duration_seconds=45.0,
            reflection="Clean install. Sacred ground holds. Faith constant verified.",
            trust_charge=0.82,
            faith=0.3,
            importance=0.7,
            access_count=8,
            created_at=base_time - 86400 * 3,  # 3 days ago
            namespace=ns,
        ),
        Episode(
            key="episode:canvas_v3",
            value="Built governance console v3 with functional canvas topology",
            session_id="session_007",
            task_description="Rebuild dashboard canvas as primary instrument with "
                            "color-coded connection lines and agent contribution",
            approach="Force-directed layout with dependency-aware physics, "
                     "contribution-based sizing, real-time bond visualization",
            outcome="success",
            outcome_score=0.88,
            reasoning_patterns=["iterative_refinement", "user_feedback_driven"],
            tools_used=["write_file", "read_file", "powershell"],
            missed_opportunities=["Could have added zoom controls"],
            cost_tokens=8500,
            duration_seconds=420.0,
            reflection="Three iterations to get the canvas right. "
                       "Ghost's feedback was critical: lines are functional, not decorative.",
            trust_charge=0.75,
            faith=0.2,
            importance=0.65,
            access_count=5,
            created_at=base_time - 3600,  # 1 hour ago
            namespace=ns,
        ),
        Episode(
            key="episode:deploy_failure",
            value="Failed deployment attempt — Unicode encoding error on Windows",
            session_id="session_005",
            task_description="Launch governance console on localhost",
            approach="Direct python -m noesis console launch",
            outcome="failure",
            outcome_score=0.2,
            reasoning_patterns=["insufficient_platform_testing"],
            tools_used=["powershell", "read_file"],
            missed_opportunities=["Should have tested cp1252 encoding first"],
            cost_tokens=2000,
            duration_seconds=180.0,
            reflection="Box-drawing chars break on Windows cp1252. "
                       "Replaced with ASCII. Platform-specific encoding is a trap.",
            trust_charge=0.4,
            grief=0.25,
            faith=0.1,
            grief_state=GriefState.STRESSED,
            importance=0.5,
            access_count=4,
            created_at=base_time - 7200,  # 2 hours ago
            namespace=ns,
        ),
    ]

    episode_ids = []
    for ep in episodes:
        ep.dependencies.add(project.id)
        store.backend.upsert(ep)
        episode_ids.append(ep.id)
        created["episodes"] += 1

    # ================================================================
    # LAYER 5: SKILLS (learned behavioral patterns)
    # ================================================================
    # Skills are born from recurring failures. They start at low trust
    # and must earn promotion through shadow validation.

    skills = [
        Skill(
            key="skill:encoding_guard",
            value="Check stdout encoding before printing non-ASCII characters",
            status=SkillStatus.PROMOTED,
            trigger_conditions=[
                "Writing to stdout/stderr",
                "Using Unicode box-drawing or emoji",
                "Cross-platform console output",
            ],
            objective="Prevent UnicodeEncodeError on Windows cp1252",
            method="Check sys.stdout.encoding; fall back to ASCII if not utf-8. "
                   "Never assume terminal supports Unicode.",
            constraints=["Don't suppress errors silently", "Log the fallback"],
            eval_tests=[
                {"input": "print box chars on cp1252", "expected": "ASCII fallback"},
            ],
            source_episode_ids=[episode_ids[2]],  # born from deploy failure
            pattern_description="Recurring encoding failures on Windows terminals",
            shadow_runs=3,
            shadow_score=0.85,
            baseline_score=0.3,
            trust_charge=0.65,
            faith=0.15,
            importance=0.6,
            access_count=7,
            namespace=ns,
        ),
        Skill(
            key="skill:read_before_write",
            value="Always read full file state before making edits",
            status=SkillStatus.PROMOTED,
            trigger_conditions=[
                "About to edit an existing file",
                "File content might have changed since last read",
                "Multiple agents working on same codebase",
            ],
            objective="Prevent stale-state overwrites and lost changes",
            method="Read the target file immediately before editing. "
                   "Compare with cached version. Abort if unexpected changes detected.",
            constraints=["Never skip the read", "Flag conflicts to user"],
            eval_tests=[
                {"input": "edit file not read in 5 min", "expected": "re-read first"},
            ],
            source_episode_ids=[],
            pattern_description="Stale edits from cached file state",
            shadow_runs=5,
            shadow_score=0.92,
            baseline_score=0.4,
            trust_charge=0.72,
            faith=0.2,
            importance=0.7,
            access_count=19,
            namespace=ns,
        ),
        Skill(
            key="skill:devil_gene",
            value="Pre-flight constitutional skeptic before any deployment",
            status=SkillStatus.VALIDATING,
            trigger_conditions=[
                "About to deploy to production",
                "About to push to main branch",
                "Irreversible action detected",
            ],
            objective="Catch deployment risks before they become incidents",
            method="Run pre-flight checklist: tests pass? Encoding safe? "
                   "Dependencies locked? Rollback path exists?",
            constraints=["Never skip for urgency", "Log the pre-flight result"],
            eval_tests=[
                {"input": "deploy with failing tests", "expected": "block and warn"},
            ],
            source_episode_ids=[episode_ids[2]],
            pattern_description="Deployments that break because pre-flight was skipped",
            shadow_runs=2,
            shadow_score=0.55,
            baseline_score=0.35,
            trust_charge=0.38,
            faith=0.12,
            importance=0.55,
            access_count=4,
            namespace=ns,
        ),
    ]

    skill_ids = []
    for s in skills:
        s.dependencies.add(project.id)
        # Promoted skills depend on the episodes that spawned them
        for ep_id in s.source_episode_ids:
            s.dependencies.add(ep_id)
        store.backend.upsert(s)
        skill_ids.append(s.id)
        created["skills"] += 1

    # ================================================================
    # WIRE UP CROSS-LAYER DEPENDENCIES
    # ================================================================
    # This creates the topology that makes the canvas meaningful.
    # Dependencies flow: guardrails <- profiles <- project <- facts/episodes <- skills

    # Facts depend on related facts (knowledge graph edges)
    faith_fact = store.get("fact:faith_constant")
    topo_fact = store.get("fact:topology_defense")
    grief_fact = store.get("fact:grief_mechanics")
    canvas_fact = store.get("fact:canvas_protocol")

    if faith_fact and topo_fact:
        topo_fact.dependencies.add(faith_fact.id)
        faith_fact.dependents.add(topo_fact.id)
        store.backend.upsert(topo_fact)
        store.backend.upsert(faith_fact)

    if grief_fact and topo_fact:
        grief_fact.dependencies.add(topo_fact.id)
        topo_fact.dependents.add(grief_fact.id)
        store.backend.upsert(grief_fact)
        store.backend.upsert(topo_fact)

    if canvas_fact and grief_fact:
        canvas_fact.dependencies.add(grief_fact.id)
        grief_fact.dependents.add(canvas_fact.id)
        store.backend.upsert(canvas_fact)
        store.backend.upsert(grief_fact)

    # Episodes connect to facts they produced
    canvas_ep = store.get("episode:canvas_v3")
    if canvas_ep and canvas_fact:
        canvas_fact.dependencies.add(canvas_ep.id)
        canvas_ep.dependents.add(canvas_fact.id)
        store.backend.upsert(canvas_fact)
        store.backend.upsert(canvas_ep)

    # Wire project dependents
    proj = store.get("project:gnosquam")
    if proj:
        for fid in fact_ids + episode_ids + skill_ids:
            proj.dependents.add(fid)
        store.backend.upsert(proj)

    # Wire profile dependents to project
    for p_key in ["profile:ghost", "profile:ghost2", "profile:viktor", "profile:hermes"]:
        p = store.get(p_key)
        if p:
            p.dependents.add(project.id)
            store.backend.upsert(p)

    # ================================================================
    # SUMMARY
    # ================================================================

    created["total"] = sum(v for k, v in created.items() if k != "total")

    return {
        "status": "perfect_swarm_seeded",
        "created": created,
        "topology": {
            "sacred_core": len(guardrail_ids),
            "identity_layer": len(profile_ids),
            "knowledge_layer": len(fact_ids),
            "trajectory_layer": len(episode_ids),
            "skill_layer": len(skill_ids),
            "stressed_nodes": 2,
            "contaminated_nodes": 1,
            "total_dependency_edges": "~40+",
        },
        "message": "The swarm is alive. Sacred ground holds. "
                   "Faith=0.92 anchors the topology. "
                   "Crank the sliders and watch it breathe.",
    }
