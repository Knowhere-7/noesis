# NOESIS — Product Anchor

**One sentence:** Noesis is the provenance-aware publication boundary that prevents runtime-derived content from silently becoming trusted persistent agent memory.

---

## The Exact User

Developers and teams running persistent AI agents (coding assistants, research agents, autonomous workflows) who lose continuity between sessions, watch agents drift from instructions, and can't trust outputs without babysitting.

## The Exact Friction

1. **Context death** — every new session starts blank. The agent forgets what it learned.
2. **Drift** — agents gradually deviate from their role, instructions, and quality standards.
3. **Hallucination propagation** — one bad output enters memory and poisons future sessions.
4. **Jailbreak vulnerability** — adversarial inputs can overwrite safety constraints.
5. **No learning** — agents repeat the same mistakes because there's no reflection or skill formation.

## The Exact Promise

Noesis gives persistent agent memory an explicit ingestion and publication
boundary. Runtime-derived content is labeled by origin, stored outside
retrieval, and can enter provider context only after separately authorized
review, substantive restatement, and publication.

Reflection, grief cascades, and skill formation remain experimental. They are
not part of the product security promise until their production data paths and
effectiveness tests support that claim.

Friction, not impossibility. In the current first-party corpus, poisoning
success is 0/13 for Noesis versus 13/13 for the simulated ungoverned baseline;
legitimate publisher and collector-promotion refusals are 0/8. Ordinary writes
remain non-retrievable candidates until separately authorized review and
promotion. These are development measurements, not independent evidence.
**Single-turn jailbreaks are out of scope by architecture** — they never touch
the memory vault. Historical failures, corrected claims, current limits, and
the open promotion contract gap are published in the
[failure ledger](FAILURE_LEDGER.md).

## The Minimum Loop

```
SESSION START
  1. Noesis assembles context packet:
     - Agent profile (identity, role, constraints)
     - Project state (current objectives, recent decisions)
     - Lexically relevant memories (by query match + trust influence + recency)
     - Matching episodes (1-3 as few-shot examples)
     - Active skills (relevant to task type)
     - Trust state (current charge levels)

SESSION ACTIVE
  2. Agent works normally with any model (Claude, GPT, Gemini, Llama, etc.)
     - Ordinary collector writes remain non-retrievable candidates
     - Publication requires a separately authorized identity
  3. Noesis monitors retrieval context through 5 internal signals:
     - Continuity: are profile and project-state anchors present?
     - Groundedness: what proportion of retrieved memories are high-trust?
     - Drift: how much grief is present in the retrieved context?
     - Trust charge: what is the context's average resolved trust?
     - Action-risk proxy: inverse context trust (not output judgment)
  4. The calling framework may use those signals to:
     - RETRIEVE: get more evidence
     - REFLECT: run self-check
     - REFUSE: abstain and explain why

SESSION END
  5. Session autopsy (background, not blocking):
     - What was tried, what worked, what failed
     - What signals were missed
     - What should be different next time
  6. Episode stored with outcome, reasoning pattern, cost, missed opportunities

PERIODIC (every N sessions)
  7. Project retrospective:
     - Roll episodes into patterns
     - Detect recurring failures (3-5 similar episodes)
     - Propose candidate skills
  8. Skill validation:
     - Check structure and episode references
     - Record a structural score
     - Promote, revise, or reject
  9. Memory consolidation:
     - Deduplicate facts
     - Decay low-importance memories
     - Strengthen high-performance patterns
```

## What Is Explicitly Out of Scope (v1)

- Multi-agent swarm coordination (v2 — the substrate is ready but single-agent ships first)
- Hosted multi-user console (a local inspection console is included)
- Billing/payments (public proprietary core, commercial layers later)
- Model training or fine-tuning (Noesis is inference-time governance, not training)
- Real-time chat UI (Noesis is middleware, not a chat app)

---

## The Swarm Governance Differentiator

Noesis combines memory with explicit provenance, publication, integrity-state,
and authority boundaries. The provenance/publication boundary is the supported
product kernel; adaptive governance remains experimental.
The comparison below is a design comparison with a typical ungoverned memory
library, not a measured benchmark of the named products.

| Feature | LangMem / Mem0 / Zep | Noesis |
|---------|----------------------|--------|
| Persistent memory | Yes | Yes |
| Retrieval approach | Typically semantic/vector | Lexical relevance + trust; no semantic-search claim |
| Model agnostic | Partial | Full |
| Self-reflection | No | Yes — session autopsy + project retrospective |
| Skill generation | No | Experimental — structurally checked, not outcome-validated |
| Context-health signals | No | Yes — 5 deterministic retrieval-context signals |
| Memory corruption defense | Varies / not measured here | Yes — persisted authority, candidate publishing, sacred nodes, grief cascades |
| Memory-persistent attack friction | Not measured here | Yes — first-party development measurement only; single-turn out of scope |

The governance mechanisms were derived from a Murmuration simulation where
236 agents reached a stable consensus state over 54,000 ticks. That is design
provenance, not evidence about language-model security. Effects on this memory
layer are measured separately in `benchmarks/`.

---

## Architecture Stack

```
┌─────────────────────────────────────────────────────┐
│                   ANY LLM MODEL                      │
│         Claude / GPT / Gemini / Llama / etc.         │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                 NOESIS RUNTIME                        │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │  Retrieval   │  │  Trust Gate  │  │  Reflection │ │
│  │  Gateway     │  │  (Swarm Gov) │  │  Engine     │ │
│  └──────┬──────┘  └──────┬───────┘  └──────┬─────┘ │
│         │                │                  │        │
│  ┌──────▼────────────────▼──────────────────▼─────┐ │
│  │              MEMORY VAULT                       │ │
│  │  profiles | facts | episodes | skills | evals   │ │
│  └─────────────────────┬──────────────────────────┘ │
│                        │                             │
│  ┌─────────────────────▼──────────────────────────┐ │
│  │              SKILL FORGE                        │ │
│  │  detect patterns → propose → validate → promote │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
                       │
              SQLite (implemented)
              PostgreSQL + pgvector (future)
```

---

## Proposed Monetization Path

This table is planning, not a current offer. Licensing and prices are not
finalized.

| Tier | Target | Features | Price |
|------|--------|----------|-------|
| **Local Core** | Solo devs | Core engine, SQLite, CLI, local reflection | TBD |
| **Team** | Teams | Postgres, namespaces, shared skills, API access | TBD |
| **Enterprise** | Orgs | On-prem, audit trails, policy controls, SSO, SLA | TBD |

---

## Build Order

### Phase 1: Core Engine (ship this)
1. Memory schema (profiles, facts, episodes, skills, evaluations)
2. Trust gate (swarm governance rules ported from Murmuration)
3. Retrieval gateway (context assembly for any model)
4. Session autopsy (background reflection)
5. CLI tools for inspection and manual memory management
6. Python SDK with provider-neutral interface

### Phase 2: Skill Forge
7. Pattern detection across episodes
8. Candidate skill proposal
9. External deterministic outcome validation (not yet implemented)
10. Skill promotion/rejection pipeline

### Phase 3: Team Layer
11. PostgreSQL + pgvector migration
12. Multi-tenant namespaces
13. Shared skill registries
14. API server (Fastify or FastAPI)

### Phase 4: Governance Console
15. Memory browser (web UI)
16. Skill review/approval workflows
17. Drift monitoring dashboard
18. Audit trail viewer

---

*The simulation inspired the mechanisms. Tests measure the implementation.*
*Murmuration → Noesis. From watching the swarm to being the swarm.*
