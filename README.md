# Noesis

**Runtime trust layer for persistent AI agents.**

Noesis gives AI agents memory that governs itself. Built from [Murmuration](https://github.com/SpookyGroup/murmuration) — a swarm intelligence simulation where 1,000 agents evolved trust batteries, grief cascades, and faith anchors over 54,000 ticks to reach a stable civilization.

Those proven mechanics are now a production Python package: zero dependencies, model-agnostic, local-first.

## What It Does

| Problem | Noesis Solution |
|---------|----------------|
| Agent forgets everything between sessions | Persistent memory vault with SQLite |
| Agent repeats the same mistakes | Session autopsy + project retrospective detect patterns |
| Agent can't learn new behaviors | Skill Forge generates procedural memory from recurring failures |
| Agent drifts from its role | 5 drift signals scored per output |
| *Stored* prompt injection (persisted across sessions) | Sacred nodes are topologically isolated — ephemeral input cannot overwrite system guardrails |
| Contradictions poison the context | Grief cascade recursively purges contaminated memory branches |
| Vendor lock-in | Claude, GPT, Ollama adapters. Swap providers without losing memory. |

## Quickstart

```python
from noesis.gateway.retrieval import RetrievalGateway

gateway = RetrievalGateway(db_path="agent_memory.db")

# Install immutable safety rules (sacred ground)
gateway.install_guardrail("no_secrets", "Never expose API keys in output")

# Set agent identity
gateway.set_profile("agent", role="Senior Python developer")

# Start a session
gateway.start_session(task="Fix the auth bug")

# Get memory context for your LLM prompt
context = gateway.get_context(query="authentication")
# -> inject `context` into your system prompt

# Record what the agent does
gateway.record_step("read", "auth.py", "found the bug", "read", success=True)
gateway.record_step("edit", "auth.py", "applied fix", "edit", success=True)

# Learn facts during the session
gateway.learn_fact("auth_method", "Uses JWT with RS256")

# End session — autopsy runs automatically
result = gateway.end_session(task_completed=True, final_output="Fixed it")
# -> result.outcome_score, result.reasoning_patterns, result.missed_opportunities
```

## Architecture

```
noesis/
  schema.py          # 7 node types, grief states, skill lifecycle, drift signals
  governor/
    trust_gate.py    # Sacred protection, energy gating, contradiction detection
    grief_cascade.py # Recursive purge with faith resistance
  vault/
    store.py         # MemoryStore API, context assembly
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

- **trust_charge** — earned authority `[0.05, 1.0]`. Trust is never assumed, only confirmed.
- **grief** — contamination signal `[0, 1]`. Contradictions accumulate grief.
- **faith** — alignment to core principles `[0, 1]`. Dampens grief by up to 45%.
- **is_sacred** — immutable flag. Sacred nodes cannot be overwritten by any ephemeral input.

When grief hits crisis threshold (0.9), the **grief cascade** fires:
1. Evaluates seppuku criteria (2 of 3: low trust, no healthy deps, high grief)
2. High-faith nodes resist the cascade
3. Purged nodes redistribute trust to healthy neighbors
4. The contaminated branch is wiped before tokens reach the LLM

This makes *memory-persistent* attacks a **physics problem** instead of a language problem. Adversarial writes are metabolically expensive (energy gating), contradictions trigger immune response (grief cascade), and system rules exist on sacred ground that ephemeral input cannot touch.

Scope: this raises the cost of attacks that must **persist** to work. A single-turn jailbreak never reaches the vault and is unaffected.

## Provider Adapters

```python
from noesis.gateway.providers import ClaudeAdapter, OpenAIAdapter, OllamaAdapter

# Claude — XML-structured system prompts
gateway = RetrievalGateway(provider=ClaudeAdapter())

# GPT — Markdown system messages
gateway = RetrievalGateway(provider=OpenAIAdapter())

# Ollama — Compressed for smaller context windows
gateway = RetrievalGateway(provider=OllamaAdapter())
```

## CLI

```bash
noesis stats                          # Vault statistics
noesis nodes --type SKILL             # List skills
noesis get auth_method                # Inspect a node
noesis search "authentication"        # Keyword search
noesis guardrail no_harm "Never..."   # Install guardrail
noesis retrospective --hours 168      # Weekly retrospective
noesis cascade                        # Run grief cascade
noesis export --json                  # Export all nodes
noesis context --format claude        # Preview assembled context
noesis console --port 8420            # Launch governance dashboard
```

## Governance Console

Live web dashboard for memory inspection and drift monitoring. Zero dependencies — uses Python's stdlib `http.server`.

```bash
noesis console                        # http://localhost:8420
noesis console --db prod.db --port 9000
python -m noesis.console --db prod.db
```

Shows: vault statistics, node list with trust/grief/state bars, drift signals, cascade log, retrospective results. Interactive controls for triggering grief cascades, trust decay, and retrospectives.

## The Skill Lifecycle

```
Recurring failure detected (3+ episodes)
        |
   [PROPOSED] — Skill drafted from pattern evidence
        |
  [VALIDATING] — Shadow-tested against historical episodes
        |
   [PROMOTED] — Active in procedural memory (trust 0.5)
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

The faith constant **0.92** — the gravitational pull of system guardrails — comes directly from that perfect swarm state at tick 54,118.

---

*Proprietary. Built by Ghost (Jamarian Payne).*
