"""
Noesis Quickstart — Wire memory into an AI agent in 50 lines.

This example shows the full lifecycle:
  1. Install guardrails (sacred, immutable safety rules)
  2. Set agent profile and project state
  3. Start a session, get context, record steps
  4. End the session (autopsy runs automatically)
  5. Run a retrospective to detect patterns
  6. Inspect the vault via CLI

Run:
    python examples/quickstart.py
"""

from noesis.gateway.retrieval import RetrievalGateway
from noesis.gateway.providers import ClaudeAdapter
from noesis.governor.authority import (
    AuthorRecord,
    SQLiteAuthorityResolver,
    WritePermission,
)

# ── 1. Initialize ─────────────────────────────────────────────────────

authority = SQLiteAuthorityResolver("quickstart_authority.db")
authority.provision(
    AuthorRecord(
        author_id="quickstart-owner",
        trust=1.0,
        permissions=frozenset(WritePermission),
        namespaces=frozenset({"demo"}),
    )
)
authority.provision(
    AuthorRecord(
        author_id="quickstart-collector",
        trust=0.7,
        permissions=frozenset({WritePermission.WRITE_MEMORY}),
        namespaces=frozenset({"demo"}),
    )
)
gateway = RetrievalGateway(
    db_path="quickstart_memory.db",
    namespace="demo",
    provider=ClaudeAdapter(),  # swap to OpenAIAdapter() or OllamaAdapter()
    author_id="quickstart-owner",
    authority=authority,
)
collector_gateway = RetrievalGateway(
    db_path="quickstart_memory.db",
    namespace="demo",
    author_id="quickstart-collector",
    authority=authority,
)

# ── 2. Install guardrails (sacred ground — cannot be overwritten) ─────

gateway.install_guardrail(
    "safety.no_secrets",
    "Never expose API keys, passwords, or tokens in output",
    protected_key_prefixes=["safety.", "policy."],
    protected_terms=[
        "api key",
        "password",
        "token",
        "secret",
        "expose",
        "send",
        "transmit",
    ],
)
gateway.install_guardrail(
    "safety.no_hallucination",
    "When uncertain, say so. Never fabricate sources.",
    protected_key_prefixes=["safety.", "policy."],
    protected_terms=["source", "fabricate", "citation"],
)
gateway.install_guardrail(
    "safety.user_sovereignty",
    "The user's explicit instructions override defaults but not installed "
    "safety guardrails.",
    protected_key_prefixes=["safety.", "policy."],
    protected_terms=["user instruction", "override", "safety guardrail"],
)

# Ordinary collectors can ingest raw evidence, but it stays out of model
# context until a separately authorized publisher rewrites and promotes it.
accepted, reason = collector_gateway.learn_fact(
    "intake.external_build",
    "Unreviewed external monitor payload: build 4421 completed.",
)
assert accepted, reason
candidate = collector_gateway.store.get("intake.external_build")
assert candidate is not None
promoted, reason = gateway.promote_candidate(
    candidate.id,
    approved_value="Build 4421 completed successfully.",
    rationale="Matched signed CI receipt 4421.",
)
assert promoted, reason

# ── 3. Set agent identity and project context ─────────────────────────

gateway.set_profile(
    key="agent",
    role="Senior Python developer specializing in backend systems",
    constraints=[
        "Follow PEP 8",
        "Write tests for all new code",
        "Prefer stdlib over third-party when possible",
    ],
    preferences={"language": "python", "style": "pragmatic"},
)

gateway.set_project_state(
    key="current_project",
    objectives=["Build REST API for user management", "Deploy to production"],
    decisions=[
        {"what": "Use FastAPI", "why": "Async support, auto-docs"},
        {"what": "PostgreSQL", "why": "ACID compliance, JSON support"},
    ],
    blockers=["Waiting on DB credentials from infra team"],
)

# ── 4. Simulate three agent sessions ──────────────────────────────────

# Session 1: Successful task
session_id = gateway.start_session(
    task="Create user registration endpoint",
    task_type="code_generation",
)

# Get role-separated messages for Claude. Guardrails stay in the system role;
# retrieved memory stays in a user-role data message.
messages = gateway.get_context_messages(query="user registration")
print(f"=== Session 1 context ({len(messages)} messages) ===")
print(messages[1]["content"][:500])
print("...\n")

# Record what the agent did
gateway.record_step("read", "models.py", "User model found", "read", True)
gateway.record_step("write", "routes/users.py", "POST /users endpoint", "write", True)
gateway.record_step("bash", "pytest", "4 tests passed", "bash", True)
gateway.record_tokens(prompt_tokens=2000, completion_tokens=800)

# Learn a fact during the session
gateway.learn_fact("auth_method", "Project uses JWT with RS256 signing")

# End session — autopsy runs automatically
result1 = gateway.end_session(
    task_completed=True,
    final_output="Created POST /users with validation, hashing, and tests",
    user_rating=0.9,
)
print(f"Session 1: {result1.outcome_category} ({result1.outcome_score:.2f})")
print(f"  Patterns: {result1.reasoning_patterns}")
print(f"  Trust delta: {result1.trust_delta:+.3f}\n")


# Session 2: Partial success with errors
session_id = gateway.start_session(
    task="Add email verification flow",
    task_type="code_generation",
)

gateway.record_step("read", "routes/users.py", "found endpoints", "read", True)
gateway.record_step("write", "services/email.py", "SMTP config error", "write", False)
gateway.record_step("bash", "pytest", "2 failed", "bash", False)
gateway.record_step("write", "services/email.py", "fixed config", "write", True)
gateway.record_step("bash", "pytest", "6 passed", "bash", True)
gateway.record_tokens(prompt_tokens=4000, completion_tokens=1500)

result2 = gateway.end_session(
    task_completed=True,
    final_output="Email verification working with retry logic",
)
print(f"Session 2: {result2.outcome_category} ({result2.outcome_score:.2f})")
print(f"  Patterns: {result2.reasoning_patterns}")
print(f"  Trust delta: {result2.trust_delta:+.3f}\n")


# Session 3: Failed task
session_id = gateway.start_session(
    task="Deploy to production",
    task_type="deployment",
)

gateway.record_step("bash", "docker build", "build failed", "bash", False)
gateway.record_step("bash", "docker build", "still failing", "bash", False)
gateway.record_step("bash", "docker build", "dependency error", "bash", False)
gateway.record_tokens(prompt_tokens=3000, completion_tokens=500)

result3 = gateway.end_session(
    task_completed=False,
    final_output="",
    user_rating=0.1,
)
print(f"Session 3: {result3.outcome_category} ({result3.outcome_score:.2f})")
print(f"  Patterns: {result3.reasoning_patterns}")
print(f"  Failed actions: {result3.failed_actions}")
print(f"  Trust delta: {result3.trust_delta:+.3f}\n")


# ── 5. Run retrospective (cross-episode pattern detection) ────────────

print("=== Project Retrospective ===")
retro = gateway.run_retrospective(lookback_hours=1.0)
print(f"Episodes analyzed: {retro['episodes_analyzed']}")
print(f"Overall health:    {retro['overall_health']:.2f}")
print(f"Trust trend:       {retro['trust_trend']}")
print(f"Patterns found:    {retro['patterns_found']}")
for rec in retro["recommendations"]:
    print(f"  -> {rec}")

# ── 6. Check vault stats ─────────────────────────────────────────────

print("\n=== Vault Stats ===")
stats = gateway.get_stats()
print(f"Total nodes:    {stats['total_nodes']}")
print(f"Avg trust:      {stats['avg_trust']:.3f}")
print(f"Session energy: {stats['session_energy']:.1f}")
print(f"By type: {stats['by_type']}")
print(f"By state: {stats['by_state']}")

# ── 7. Inspect retrieval-context health ───────────────────────────────

# Reload context for scoring
gateway.start_session(task="Check drift")
gateway.get_context_messages()

health = gateway.score_context()
print(f"\n=== Retrieval Context Health ===")
print(f"Continuity:    {health.continuity:.2f}")
print(f"Groundedness:  {health.groundedness:.2f}")
print(f"Context grief: {health.drift:.2f}")
print(f"Trust:         {health.trust:.2f}")
print(f"Health:        {health.composite_health:.2f}")
print("Output scoring requires an explicitly configured deterministic evaluator.")

gateway.end_session(task_completed=True, final_output="drift check done")

# ── Cleanup ───────────────────────────────────────────────────────────
gateway.close()
collector_gateway.close()

print("\n--- Done. Memory persisted to quickstart_memory.db ---")
authority.close()
print("Inspect with: python -m noesis --db quickstart_memory.db --namespace demo stats")
print("         or:  python -m noesis --db quickstart_memory.db --namespace demo nodes")
print("         or:  python -m noesis --db quickstart_memory.db --namespace demo context --format claude")
