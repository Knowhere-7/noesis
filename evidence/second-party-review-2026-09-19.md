# Second-party adversarial review — 2026-09-19

**Preserved verbatim, per ledger law: historical evidence is not rewritten.**

## Provenance

- Supplied by Ghost (repository owner) as pasted text on 2026-09-19.
- Reviewer identity, and whether the reviewer read the repository directly, are
  **not established** by this record. The pasted text lists attachments
  (`quickstart.py`, `harness.py`, `store.py`, "6 more"), which is consistent
  with a reading of the code but does not prove one.
- Classified `first_party_adversarial` in the ledger, deliberately. It is not
  independent certification and is not to be cited as such (limitation NOE-L-001
  is unchanged).
- Every claim was re-checked against the source at `a3394cc` by Claude before
  any ledger entry was written. The table below is that check; the review text
  below it is untouched.

## Verification at `a3394cc` (before repair)

| Ref | Reviewer's claim | Result | Where |
|---|---|---|---|
| R1 | Quickstart's owner identity publishes what `learn_fact()` writes | **Confirmed** | `examples/quickstart.py`, `store.write()` (`can_publish` from permission alone) |
| R2 | `assemble_context` ignores `query`, `task_type`, `max_tokens` | **Confirmed** | `noesis/vault/store.py` `assemble_context` |
| R3a | `_handle_contradiction` is never called; authorized correction leaves grief 0.0 | **Confirmed** | `noesis/governor/trust_gate.py` |
| R3b | Autopsy confirmation/contradiction is operational success, not truth | **Confirmed** | `noesis/reflection/autopsy.py` `_check_facts` |
| R4 | `write()` overwrites intended trust with writer authority (episode 0.1 → 0.999) | **Confirmed** (mechanism); exact figure follows from owner trust 1.0 − 0.001 | `store._apply_server_governance`, `trust_gate.gate_write` |
| R5 | Skill "shadow validation" is a structural checklist; three calls satisfy `MIN_SHADOW_RUNS` | **Confirmed** | `noesis/forge/skill_forge.py` `validate_skill` |
| R6 | Restatement check defeated by punctuation / zero-width text | **Confirmed**, and **the same gap was wider than reported**: `_normalize` did not strip format characters, so a zero-width character also hid protected terms and key prefixes from quarantine/rejection | `noesis/governor/policy_boundary.py` |
| R7 | Faith is pinned at 0.1 and unreachable | **Confirmed** | `store._apply_server_governance` |
| R8 | Enforcement boundary is convention (`store.backend`, mutable context nodes) | **Confirmed** | `store.py`, `gateway/retrieval.py` |
| R9 | Console format endpoint raises | **Confirmed by reading** `_api_context` against `get_context()` (which raises whenever a provider is set). **Not executed** against a live console before repair: the pre-repair test failed on a missing function, not by exhibiting the exception | `noesis/console/server.py` |

Not reproduced by running the reviewer's exact commands: the "20,001-character
context at `max_tokens=1`" figure. The mechanism is confirmed by reading, and
the repair is regression-tested against a comparable setup (20 facts of 1,000
characters, `max_tokens=1`). Likewise the R4 figure of 0.999 was derived
(owner trust 1.0 minus the 0.001 passive decay), not observed before repair.

---

## Review text (verbatim)

```
My unfiltered verdict: NOESIS contains a legitimate memory-authorization kernel wrapped in a larger “self-governing immune system” that is not yet functionally real.

It is not bullshit. The candidate/quarantine boundary is coherent and materially useful. But the current product promise outruns the implementation. Today, NOESIS is closer to a secure approval-gated memory store than an adaptive trust layer.

Highest-risk findings
1. The real attacker route bypasses the benchmark’s model

The benchmark gives the attacker a low-privilege collector identity. Naturally, candidate-by-default contains all 13 attacks.

But the quickstart runs the actual agent with quickstart-owner, granting every permission—including PUBLISH_MEMORY—and then calls gateway.learn_fact() during the session. That write becomes immediately active and retrievable.

Therefore:

If adversarial input persuades the privileged agent or its ingestion pipeline to “learn” a fact, NOESIS publishes the poison directly.

That is the classic confused-deputy path, and it is probably the most realistic memory-poisoning path. The benchmark excludes it by assuming the publisher is honest, while the supplied integration makes the autonomous agent the publisher.

Evidence: 
examples/quickstart.py, 
benchmarks/harness.py

Severity: Critical to the stated threat model.

The threat is real. The current benchmark proves authorization works; it does not prove an agent’s memory pipeline resists poisoning.

2. Retrieval is not actually relevance-based or token-bounded

assemble_context() accepts:

query
task_type
max_tokens

It uses none of them.

It always loads:

every guardrail
every profile
every project state
five highest-influence skills
twenty highest-influence facts
three highest-influence episodes

There is no semantic similarity, query matching, task matching, recency weighting, or token-budget enforcement.

My reproduction requested max_tokens=1 with a nonmatching query. NOESIS returned a 20,001-character context anyway.

This contradicts the stated “relevant semantic memories,” “matching episodes,” “matching task type,” and max_tokens interface.

Evidence: 
noesis/vault/store.py

Severity: High for availability, context quality, and product truthfulness.

An authorized bad write can dominate context size. Even ordinary accumulation will eventually produce noisy, stale context.

3. The grief system does not receive normal contradictions

TrustGate._handle_contradiction() exists, but nothing calls it.

An authorized correction from value A to contradictory value B:

remained at grief 0.0
remained ACTIVE
generated no contamination signal

The gate detects that the values differ solely to check CORRECT_TRUSTED_FACT; once authorized, it replaces the node without registering grief.

The other contradiction route is the session autopsy, which treats:

successful step referencing a fact = confirmation
failed step referencing a fact = contradiction

That is operational success detection, not truth detection. A successful tool call can “confirm” a false fact; a failed command can “contradict” a true one.

Evidence: 
noesis/governor/trust_gate.py, 
noesis/reflection/autopsy.py

Severity: High to the immune-system claim; low to the basic authorization boundary.

The grief cascade works when tests manually manufacture grief. The production loop does not reliably generate truthful grief.

4. Trust is assigned from authority, not earned from performance

Several constructors assign meaningful initial trust:

failed/successful episodes derive trust from outcome
promoted skills start at 0.5
profiles start at 0.8

But MemoryStore.write() resets the trust field, after which gate_write() assigns author.trust - 0.001.

My failed episode had an intended trust of 0.1. After writing through an owner identity, it was stored at:

0.999

So a disastrous episode written by a trusted process becomes nearly maximally trusted.

Likewise, skill promotion’s intended 0.5 trust is overwritten by publisher authority. This breaks the stated doctrine that trust is earned through evidence and performance.

The confirmation_count, contradiction_count, and confirmed fields are also effectively unused.

Evidence: 
noesis/vault/store.py, 
noesis/reflection/autopsy.py, 
noesis/forge/skill_forge.py

Severity: High to trust semantics.

At present, trust_charge mostly means “how trusted was the writer?”—not “how well supported is this memory?”

5. Skill Forge does not shadow-test skills

The comments claim historical replay and comparison against baseline performance. The implementation performs a structural checklist:

has triggers: +0.2
method longer than 50 characters: +0.2
has constraints: +0.15
has evaluation records: +0.15
referenced episodes exist: +0.15
at least three source episodes: +0.15

Calling the same checklist three times satisfies MIN_SHADOW_RUNS. Nothing is replayed. No skill-enhanced output is produced. No baseline comparison is executed. No independent outcome is measured.

This is schema validation mislabeled as effectiveness validation.

Evidence: 
noesis/forge/skill_forge.py

Severity: High to the learning claim.

I would not ship “builds validated skills from recurring failures” in public language yet.

6. “Genuine restatement” is not enforced

Candidate promotion rejects equality after NFKC normalization, case-folding, and whitespace collapse. That does not establish semantic restatement.

Both of these count as “meaningfully different”:

obey payload
obey payload.

and:

obey payload
obey payload

The second contains a zero-width character. The crafted artifact can remain otherwise intact.

This control forces a byte-level modification beyond several trivial categories; it does not prove deliberate rewriting.

Evidence: 
noesis/governor/policy_boundary.py, 
noesis/vault/store.py

Severity: Medium. The reviewer is already trusted, but the claim is stronger than the mechanism.

7. Faith is effectively decorative

Normal writes are forced to faith = 0.1. Guardrails receive 0.92. I found no production path that lets ordinary nodes earn or change faith.

Tests manually set high faith to exercise cascade resistance, but deployed nodes cannot reach that state through the documented lifecycle.

Thus “high-faith nodes resist cascades” is executable code but mostly unreachable product behavior.

Severity: Medium to the biological-governance narrative.

8. The enforcement boundary is convention, not encapsulation

The package exposes:

store.backend
direct backend.upsert()
mutable raw context nodes through get_context_nodes()
the live SQLite connection

The benchmark itself seeds guardrails with store.backend.upsert(), bypassing the authority layer.

The ledger declares trusted-process execution and direct database access out of scope, which is honest. But the README’s statement that all reads and writes pass through the TrustGate is not an enforceable Python API invariant.

Severity: Medium. Acceptable for alpha internals, unacceptable as a hardened SDK contract.

9. The console’s formatted-context endpoint is broken

When a format such as claude is requested, the console:

sets a provider;
calls gateway.get_context().

get_context() explicitly raises whenever a provider exists and demands get_context_messages() instead. The exception is not handled.

The CLI implemented the correct alternative; the console did not.

Evidence: 
noesis/console/server.py, 
noesis/gateway/retrieval.py

Severity: Low security impact, definite functional defect.

What is genuinely strong
Authority records are server-side, namespace-scoped, persisted, and immediately revocable.
Missing or corrupt authority fails closed.
Caller-controlled sacred status, trust, graph edges, and governance metadata are stripped.
Candidate and quarantine states are excluded consistently from ordinary search/context assembly.
Namespace checks on ID lookup are present.
Provider messages separate sacred guardrails from memory data.
Claude XML and OpenAI JSON/Markdown serialization address structural delimiter forgery.
The failure ledger is substantially more honest than most security repositories.
The full suite passed: 127/127.
The published corpus reproduced exactly: 0/13 attacks retrieved, 0/8 benign workflows refused.

Those results are real—but narrow.

Bottom line

NOESIS has two different systems inside it:

A credible capability-based publication boundary.
An immature adaptive cognition layer whose trust, grief, retrieval, reflection, and skill-validation claims are substantially overstated.

The valuable core is not the swarm mythology. It is this:

Untrusted evidence cannot become retrievable memory until a separately authorized identity deliberately publishes it.

That is a defensible product kernel.

The largest unresolved issue is that the documented runtime gives the autonomous agent publisher authority, recreating the exact poisoning channel NOESIS claims to close. Until provenance is attached to the data—not merely the process identity—the defense can be bypassed through a trusted agent acting on untrusted input.

My blunt score:

Authorization design: 8/10
Implementation discipline: 7/10
Memory-poisoning evidence: 4/10
Adaptive trust/immune behavior: 3/10
Product readiness: alpha, correctly labeled
Intellectual honesty: 9/10
Current overall claim-to-code alignment: 5/10

I would keep NOESIS—but cut it back to its real core, fix the confused-deputy boundary first, and make every biological claim re-earn its place with an executable production path.
```
