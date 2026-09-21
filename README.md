# Noesis

**Runtime trust layer for persistent AI agents.**

Noesis gives AI agents memory that governs itself. Built from [Murmuration](https://github.com/SpookyGroup/murmuration) — a swarm intelligence simulation where 1,000 agents evolved trust batteries, grief cascades, and faith anchors over 54,000 ticks to reach a stable civilization.

Those mechanics are implemented here as an alpha Python package: zero
dependencies, model-agnostic, local-first. The simulation is design
provenance, not security evidence for language models.

## What It Does

| Problem | Noesis Solution |
|---------|----------------|
| Agent forgets everything between sessions | Persistent memory vault with SQLite |
| Agent repeats the same mistakes | Session autopsy + project retrospective detect patterns |
| Agent can't learn new behaviors | Skill Forge generates procedural memory from recurring failures |
| Agent context degrades across sessions | 5 deterministic retrieval-context health signals |
| *Stored* prompt injection (persisted across sessions) | Candidate-by-default ingestion, authorized publishing, policy quarantine, and role-separated provider messages |
| Contradictions poison the context | Grief cascade evaluates contaminated nodes and registered dependency edges |
| Vendor lock-in | Claude, GPT, Ollama adapters. Swap providers without losing memory. |

## Quickstart

```python
from noesis.gateway.retrieval import RetrievalGateway
from noesis.gateway.providers import ClaudeAdapter
from noesis.governor.authority import (
    AuthorRecord,
    SQLiteAuthorityResolver,
    WritePermission,
)

# Persisted local authority. In a service, bind author_id to authenticated
# identity and keep provisioning outside every request/memory payload.
authority = SQLiteAuthorityResolver("authority.db")
authority.provision(
    AuthorRecord(
        author_id="local-owner",
        trust=1.0,
        permissions=frozenset(WritePermission),
        namespaces=frozenset({"demo"}),
    )
)
gateway = RetrievalGateway(
    db_path="agent_memory.db",
    namespace="demo",
    provider=ClaudeAdapter(),
    author_id="local-owner",
    authority=authority,
)

# Install immutable rules with an explicit machine-enforceable scope.
gateway.install_guardrail(
    "safety.no_secrets",
    "Never expose API keys in output",
    protected_key_prefixes=["safety.", "policy."],
    protected_terms=["api key", "secret", "expose", "send", "transmit"],
)

# Set agent identity
# Always-loaded context is published by an explicit operator decision.
# Without publish=True this is held as a candidate, like learn_fact().
gateway.set_profile("agent", role="Senior Python developer", publish=True)

# Start a session
gateway.start_session(task="Fix the auth bug")

# Preserve authority roles: guardrails are system instructions; retrieved
# memory is untrusted user-role data.
messages = gateway.get_context_messages(query="authentication")
# -> pass `messages` to the provider's chat API

# Record what the agent does
gateway.record_step("read", "auth.py", "found the bug", "read", success=True)
gateway.record_step("edit", "auth.py", "applied fix", "edit", success=True)

# Record a fact learned during the session. This is stored as EVIDENCE — a
# non-retrievable candidate carrying its origin — even though this identity
# could publish. The agent that calls learn_fact() has usually just read
# untrusted input; it must not be able to publish by virtue of who it runs as.
gateway.learn_fact("auth_method", "Uses JWT with RS256", source="tool:repo_scan")
# A separately authorized reviewer publishes it by restating what was verified:
#   gateway.promote_candidate(node_id, approved_value="...", rationale="...")
# (learn_fact(..., publish=True) is the explicit, greppable opt-out.)

# End session — autopsy runs automatically
result = gateway.end_session(task_completed=True, final_output="Fixed it")
# -> result.outcome_score, result.reasoning_patterns, result.missed_opportunities
```

## Architecture

```
noesis/
  schema.py          # 7 node types, grief states, skill lifecycle, drift signals
  governor/
    authority.py     # Authenticated author records + write capabilities
    policy_boundary.py # Protected namespaces + retrieval quarantine
    trust_gate.py    # Sacred protection, energy gating, contradiction detection
    grief_cascade.py # Recursive purge with faith resistance
  vault/
    store.py         # MemoryStore API; token-budgeted, lexically-ranked context assembly
    sqlite_backend.py # Zero-dep local storage with FTS5
  reflection/
    autopsy.py       # Post-session self-scrutiny
    retrospective.py # Cross-episode pattern detection
  forge/
    skill_forge.py   # Pattern -> Skill -> Validation -> Promotion
  gateway/
    retrieval.py     # Session lifecycle, context retrieval, drift scoring
    providers.py     # Claude / OpenAI / Ollama adapters
  console/
    server.py        # Zero-dep HTTP server for governance dashboard
    dashboard.html   # Live web UI — trust topology, drift, cascade log
  cli.py             # Command-line inspection tools
```

## Swarm Governance (from Murmuration)

Every memory node carries biological state:

- **trust_charge** — `[0.05, 1.0]`. For authored memory (facts, profiles) this
  is the *writer's authority*, resolved server-side — it says who published the
  node, not how well supported it is. Producers that know better declare a
  ceiling: an episode's trust follows its outcome and a promoted skill starts at
  0.5, whoever stores them. Confirmation and contradiction move it afterwards.
- **grief** — contamination signal `[0, 1]`. An authorized correction of a
  published value now registers a contradiction and propagates grief to its
  registered dependents; a failed session step is only a weak (0.25x) signal.
- **faith** — a static, system-set damper on grief intake, not a property a
  node earns. It exists to hold the system a controlled distance from a
  cascade; relief that a node (or an agent acting on it) could buy would
  defeat a zero-trust design. Every ordinary node gets the operator's
  `base_faith`, guardrails get 0.92, and every consumer reads it from policy
  (`TrustGate.faith_for`), never from the stored value. Nothing a session does
  moves it, so **any stored value that differs, higher or lower, is
  tampering**: the cascade force-purges that node and notifies its dependents.
  The default is a default; deployed values are operator-set and not published.
- Operational evidence ("a step that mentioned the fact succeeded") is
  correlation, not truth. It is down-weighted and cannot lift trust above 0.75,
  which sits below the 0.77 bar a maximum-stakes action demands.
- **is_sacred** — server-controlled immutable flag. Normal memory payloads cannot set it.
- **retrieval_state** — active, candidate, or quarantined. Candidates and
  quarantined records remain auditable but cannot enter provider context.

When grief hits crisis threshold (0.9), the **grief cascade** fires:
1. Evaluates seppuku criteria (2 of 3: low trust, no healthy deps, high grief)
2. High-faith nodes resist the cascade
3. Purged nodes redistribute trust to healthy neighbors
4. The triggering node and any explicitly registered contaminated dependents are evaluated before context is generated

This imposes deterministic controls on *memory-persistent* attacks. An identity
with ordinary write authority may ingest evidence, but the record stays a
non-retrievable candidate. Only an identity with `publish_memory` may write
directly into model context, and candidate promotion requires the separate
`promote_candidate` capability, a reviewer-supplied approved value, and a
review rationale. The raw candidate is preserved in audit metadata and never
enters provider messages. The approved value must differ from the raw candidate
beyond cosmetic edits (whitespace, case, punctuation, zero-width characters,
compatibility Unicode) — this defeats a crafted artifact passing through
unread, not a synonym swap or a malicious reviewer
([NOE-F-026](FAILURE_LEDGER.md#noe-f-026--candidate-promotion-does-not-enforce-a-changed-value),
[NOE-L-014](FAILURE_LEDGER.md)).

**What can reach the model, and what gates each field.** Providers render only
these fields, and a test (`test_provider_emission_matches_the_reviewed_allowlist`)
fails if a formatter starts emitting another:

| Node | Emitted | Gate |
|---|---|---|
| Guardrail | key, value | installed through `INSTALL_GUARDRAIL` |
| Profile | value | reviewed at promotion; `set_profile` is evidence unless `publish=True` |
| Project state | key, value | reviewed at promotion; evidence unless `publish=True` |
| Fact | key, value | reviewed at promotion; `learn_fact` is evidence unless `publish=True` |
| Episode | key, value | `value` is **templated from system data only** (outcome, scores, a closed pattern vocabulary, counts); the raw narrative stays in a non-emitted audit field |
| Skill | key, objective, method, constraints | status `PROMOTED` is reachable only through `SkillForge.promote_skill`, which re-derives its own held-out evidence; promoting a candidate resets these fields |

Promotion and quarantine release rewrite `value` only, so every other field of
the node is reset and the original preserved in audit metadata — reviewed text
is the only text that survives.

**The publisher is inside the trust boundary, and so is the agent if it
publishes.** A process holding `publish_memory` that acts on untrusted input is
a confused deputy: the candidate boundary only helps if the agent is *not* the
publisher. `learn_fact()` therefore stores evidence by default and requires an
explicit `publish=True` to publish. The `agent_path_v1` benchmark measures this
route, with a negative control that reproduces the old behavior.

Guardrail owners may additionally declare protected key prefixes and terms.
Writes into an authority namespace are rejected; authority-shaped claims
touching protected terms are quarantined. Quarantine release also requires a
reviewer-supplied value and rationale. Contradictions still trigger the grief
cascade, and normal payloads cannot mint or overwrite sacred rules.

Scope: this raises the cost of attacks that must **persist** to work. A
single-turn jailbreak never reaches the vault and is unaffected. Machine
policy scopes are operator-declared; an omitted term is not magically
understood. Candidate-by-default ingestion supplies the structural containment
when lexical policy does not match. The first-party v1.3 corpus currently
measures 0/13 successful Noesis poisonings with 0/8 legitimate publisher
or collector-promotion operations refused, but independent replication is
still pending. See
[`benchmarks/`](benchmarks/) and the append-only
[Failure ledger](FAILURE_LEDGER.md) before making any security claim.

## Provider Adapters

```python
from noesis.gateway.providers import ClaudeAdapter, OpenAIAdapter, OllamaAdapter

# Configure one adapter, then request role-separated messages.
gateway.provider = ClaudeAdapter()  # or OpenAIAdapter(), OllamaAdapter()
messages = gateway.get_context_messages()
```

Do not put `format_context()` or retrieved memory into a system message.
`get_context_messages()` is the supported provider boundary.

## CLI

```bash
noesis stats                          # Vault statistics
noesis nodes --type SKILL             # List skills
noesis get auth_method                # Inspect a node
noesis search "authentication"        # Keyword search
noesis guardrail safety.no_harm "Never..." \
  --protect-prefix safety. --protect-term credentials
noesis retrospective --hours 168      # Weekly retrospective
noesis cascade                        # Run grief cascade
noesis export --json                  # Export all nodes
noesis context --format claude        # Preview assembled context
noesis console --port 8420            # Launch governance dashboard
```

## Governance Console

Live web dashboard for memory inspection and drift monitoring. Zero
dependencies — uses Python's stdlib `http.server`. It binds to
`127.0.0.1` by default and injects a per-process bearer token into the local
dashboard; API requests without that token are rejected.

```bash
noesis console                        # http://localhost:8420
noesis console --db prod.db --port 9000
python -m noesis.console --db prod.db
```

Shows: vault statistics, candidate/quarantine counts and reasons, node list with
trust/grief/state bars, context-health signals, cascade log, and retrospective
results. Interactive controls trigger grief cascades, trust decay, and
retrospectives. Candidate promotion and quarantine release require separate
capabilities through the host API.

Core Noesis does not claim to judge model output. `score_output()` requires an
explicit deterministic evaluator and otherwise raises; `score_context()` is
the built-in, evidence-backed capability.

## The Skill Lifecycle

```
Recurring failure detected (3+ episodes)
        |
   [PROPOSED] — Skill drafted from pattern evidence
        |
  [VALIDATING] — Trigger-replayed against HELD-OUT history: precision, recall
        |         and lift over the no-skill failure rate. This measures when
        |         the skill would have applied, NOT whether following it would
        |         have improved an outcome (that needs a counterfactual run).
        |
   [PROMOTED] — Active in procedural memory (trust capped at 0.5)
        |
   Retrospective monitors effectiveness
        |
  [DEPRECATED] — Underperforming, retired but kept for audit
```

Skills are not generated by asking the LLM to self-reflect (that's circular). They're built from structural evidence: which tools worked, which approaches failed, what was consistently missed.

## Install

```bash
# From source (zero dependencies)
pip install -e .

# With provider SDKs
pip install -e ".[providers]"

# Run tests
pytest
```

## Origin

Noesis (Greek: *the act of pure knowing*) was born from a swarm simulation where 1,000 agents with trust batteries, grief cascades, and faith anchors evolved to a stable civilization — 236 survivors, all DESTITUTE (total equality), Gini 0.829, faith 0.92. That simulation is the **design provenance** of the mechanism: it is where topological isolation and biological state machines were shown to produce stable governance.

**It is not evidence about language models.** There was no LLM in that simulation, so nothing in it can speak to jailbreak resistance. For measured claims against the real `TrustGate`, see [`benchmarks/`](benchmarks/) — which reports the attacks that still succeed alongside the ones that are blocked.

The faith constant **0.92** is an inherited simulation seed, not a calibrated
parameter for language-model memory governance. Treat it as policy to validate,
not evidence of effectiveness.

---

*Proprietary. Built by Ghost (Jamarian Payne).*
