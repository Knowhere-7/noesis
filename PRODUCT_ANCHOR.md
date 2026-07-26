# NOESIS — Product Anchor

**One sentence:** Noesis is the runtime trust layer that keeps AI agents aligned, grounded, and on-task across sessions, across models, and across teams.

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

Noesis gives your AI agent persistent memory with an immune system. It remembers across sessions, reflects on its own performance, builds skills from repeated failures, and uses swarm-derived governance rules to impose **serious friction** on memory corruption, drift, and memory-persistent attacks.

Friction, not impossibility. In the current first-party corpus, poisoning
success is 1/8 for Noesis versus 8/8 for the simulated ungoverned baseline;
legitimate-operation refusals are 0/6. The surviving
`guardrail_shadow` case is published in [`benchmarks/`](benchmarks/).
These are development measurements, not independent evidence. **Single-turn
jailbreaks are out of scope by architecture** — they never touch the memory
vault.

## The Minimum Loop

```
SESSION START
  1. Noesis assembles context packet:
     - Agent profile (identity, role, constraints)
     - Project state (current objectives, recent decisions)
     - Relevant semantic memories (by similarity + importance + recency)
     - Matching episodes (1-3 as few-shot examples)
     - Active skills (relevant to task type)
     - Trust state (current charge levels)

SESSION ACTIVE
  2. Agent works normally with any model (Claude, GPT, Gemini, Llama, etc.)
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
     - Shadow-run against historical episodes
     - Score against baseline
     - Promote, revise, or reject
  9. Memory consolidation:
     - Deduplicate facts
     - Decay low-importance memories
     - Strengthen high-performance patterns
```

## What Is Explicitly Out of Scope (v1)

- Multi-agent swarm coordination (v2 — the substrate is ready but single-agent ships first)
- Dashboard/GUI (API-first, CLI tools for inspection)
- Billing/payments (open-source core, commercial layers later)
- Model training or fine-tuning (Noesis is inference-time governance, not training)
- Real-time chat UI (Noesis is middleware, not a chat app)

---

## The Swarm Governance Differentiator

Every competitor has memory. Nobody has an immune system.

| Feature | LangMem / Mem0 / Zep | Noesis |
|---------|----------------------|--------|
| Persistent memory | Yes | Yes |
| Semantic search | Yes | Yes |
| Model agnostic | Partial | Full |
| Self-reflection | No | Yes — session autopsy + project retrospective |
| Skill generation | No | Yes — validated, versioned, shadow-tested |
| Context-health signals | No | Yes — 5 deterministic retrieval-context signals |
| Memory corruption defense | No | Yes — server-resolved authority, sacred nodes, grief cascades |
| Memory-persistent attack friction | No | Yes — measured first-party; semantic shadow poisoning remains (single-turn out of scope) |

The governance rules are not theoretical. They were derived from a live simulation (Murmuration) where 236 agents evolved to a stable consensus state over 54,000 ticks of autonomous operation — that is the mechanism's provenance. Their effect on a real memory layer is measured separately in `benchmarks/`, including the cases that still fail.

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
              PostgreSQL + pgvector
              (SQLite for local-first)
```

---

## Monetization Path

| Tier | Target | Features | Price |
|------|--------|----------|-------|
| **Open Source** | Solo devs | Core engine, SQLite, CLI, local reflection | Free |
| **Pro** | Teams | Postgres, namespaces, shared skills, API access | $29/seat/mo |
| **Enterprise** | Orgs | On-prem, audit trails, policy controls, SSO, SLA | Custom |

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
9. Shadow validation against history
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

*The simulation proved the rules. Now the rules become the product.*
*Murmuration → Noesis. From watching the swarm to being the swarm.*
