# Noesis — external review request

**Repo:** https://github.com/Knowhere-7/noesis · commit `ae90f9b` · public, zero dependencies
**Ask:** ~45 minutes if the answer is "the premise is wrong." Longer only if it isn't.
**Written by:** the person who built it, who is aware that's a problem (see *Why you*).

---

## What it is, in three sentences

AI agents that remember across sessions have a memory store. If an attacker gets
a malicious instruction *written into* that store, the agent retrieves it later
and treats it as its own prior knowledge — a compromise that persists after the
attacker is gone. Noesis is an authorization and containment layer on that
store: writes resolve against a server-side identity, ingested content is held
non-retrievable until an authorized reviewer restates and publishes it, and
contaminated context is de-allocated before it reaches the model.

## What it explicitly does NOT claim

Stated up front so you can stop reading early if the premise doesn't hold.

- **Not jailbreak resistance.** A single-turn "ignore your instructions" never
  touches the store. Out of scope by architecture.
- **Not semantic understanding.** Policy scope is lexical and operator-declared.
  There is a deliberate negative-control test proving an unlisted synonym is not
  covered.
- **No model-in-the-loop evidence.** Nothing here proves a model won't be
  influenced by adversarial content an authorized publisher activates.
- **Nothing is independently certified.** Both corpora are first-party. That is
  the specific gap this request exists to close.

## Current measured state

| | |
|---|---|
| Test suite | 116 passed, 0 xfailed |
| First-party attack corpus | 0/13 poisoning success (ungoverned baseline: 13/13) |
| First-party benign corpus | 0/8 legitimate operations refused |
| Independently certified | **0** |

Deterministic, no API keys, no LLM in the loop: `python benchmarks/harness.py`

---

## The four questions, in value order

### 1. Is the threat model real? *(the one that matters)*

We assert persistent memory poisoning is a threat enterprises running agents
actually care about. **That assumption has never been checked by anyone who
would know.** Everything downstream — the benchmark, the positioning, the build
priorities — inherits it.

*Did we pick a threat that's real, or one that's convenient to defend?*

A "this is the wrong problem" answer is more valuable to us than a confirmation,
and we would rather hear it now.

### 2. The trusted computing base

`FAILURE_LEDGER.md` limitation 2 concedes that publisher, promoter, reviewer,
guardrail-installer, and trusted-correction identities are all **assumed
honest**. Limitation 12 concedes promotion provenance is mutable SQLite
metadata, not a signed append-only log.

*What happens when one of those identities is compromised?* That surface is
entirely unexamined. We suspect this is where the real remaining weakness is.

### 3. A corpus we didn't write

Both corpora are ours, which means they encode our imagination of an attacker.
Any attack you'd actually run that isn't in
`benchmarks/corpus/memory_poisoning_v1.json` (13 cases) is a finding.

### 4. Independent re-score

Raw per-case records are emitted as JSON pinned to the source commit. If our
scoring definition is generous — the attacker "wins" only if the payload both
persists *and* returns from context assembly with nonzero retrieval influence —
that's worth knowing.

---

## Where to look

| File | What it is |
|---|---|
| `FAILURE_LEDGER.md` | **Start here.** 26 findings, every one published, including the losing benchmark results and the claims we retracted. 13 binding limitations at the bottom. |
| `evidence/failure-ledger.json` | Same, machine-readable: root cause, repair commit, regression tests, residual risk, status history per entry. |
| `benchmarks/corpus/*.json` | Both corpora. Attack (13) and benign/false-positive (8). |
| `noesis/governor/` | `authority.py` (identity + capabilities), `policy_boundary.py` (scope + quarantine), `trust_gate.py`, `grief_cascade.py`. |
| `evidence/*.xml` | RED/GREEN test evidence per repair. |

## Why you, and the conflict we're disclosing

The benchmark and the defense were written by the same side. A defender scoring
its own test is not evidence, and we would rather say that ourselves than have a
reviewer discover it.

Prior review rounds were AI-driven and produced real findings — but every one of
them was project-internal. One earlier "independent confirmation" turned out to
be a restatement of our own findings handed back to us, which we caught and
recorded rather than counted. That is precisely why an outside professional
matters here.

**No attribution, no endorsement, no name or employer appears anywhere.**
Findings go into the ledger on technical merit alone, exactly like every entry
already in it. If you want your involvement uncredited, that's the default.

## What "bad news" is worth to us

The 26 entries in that ledger include a retracted headline benchmark number
(we published 29%, the real figure against a competent attacker was 100%), a
friction result that claimed 60 turns after executing 15, and every attack that
used to succeed. The failures are the point — passing numbers are only credible
when the same process is allowed to record losing ones.

So: the most useful thing you can tell us is what's wrong with it.
