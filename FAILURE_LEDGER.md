# Noesis Failure Ledger

Noesis publishes failures because passing numbers are only credible when the
same process is allowed to record bad news.

This ledger covers released defects, development-only failures, corrected
claims, missing evidence, and accepted limitations. It is not a vulnerability
marketing page and it is not a claim of independent certification.

The machine-readable source is
[`evidence/failure-ledger.json`](evidence/failure-ledger.json). That file
contains the affected versions, root cause, evidence references, repair
commit, regression tests, residual risk, and status history for every entry.

## Ledger law

1. IDs are permanent.
2. Entries are never deleted or renumbered.
3. A repair appends a status transition; it does not erase the failure.
4. Historical evidence is not rewritten when later review proves its language
   wrong. A new entry identifies and supersedes the claim.
5. Released failures, development-only failures, claim corrections, and
   accepted limitations are labeled separately.
6. First-party, external-adversarial, and independently certified evidence
   are never presented as equivalent.
7. Every measured result names its denominator, corpus, source checkpoint, and
   independence status.
8. Missing raw evidence is itself disclosed.

## Current status

| Status | Count |
|---|---:|
| Fixed | 55 |
| Open | 0 |
| Independently certified | 0 |

Zero open findings is not a safety claim. Nothing here is independently
certified, and the current limitations below remain binding.

### NOE-F-026 — candidate promotion does not enforce a changed value

**Original finding, preserved (2026-07-26).** Phase Three was documented as
requiring a rewritten candidate value. The implementation requires a separately
authorized reviewer, an `approved_value`, and a non-empty rationale, but it
**does not enforce a changed value**. If machine policy allows the original
wording, the reviewer can promote that exact string to `ACTIVE`.

The claim was therefore narrowed to **reviewer-supplied approved value** until a
separate mechanism repair rejects unchanged source text. The executable
reproducer remained as a strict expected failure:
`test_candidate_promotion_requires_value_to_change`.

This does not remove the publisher/reviewer authority boundary. It does prove
that “rewritten” was stronger than the implemented contract.

**REPAIRED 2026-07-27 — `339ecb6`.** `promote_candidate()` now rejects an
approved value that is not a genuine restatement. Comparison is normalized
through `PolicyBoundary.is_same_text` (NFKC + casefold + whitespace collapse),
so whitespace, case, and compatibility-Unicode variants do not satisfy the
contract — otherwise a single space would have satisfied it. The rewrite
requirement was retained as the contract rather than the claim being withdrawn.

What this defends is narrow and worth stating exactly: **not** a malicious
reviewer, who holds `PROMOTE_CANDIDATE`, sits in the trusted computing base,
and could type any text they wish. It defends against a *crafted artifact*
reaching provider context. Ingested evidence may be precisely tuned to steer a
model; requiring restatement destroys that tuning and converts an inattentive
approval into a deliberate authoring act.

The strict xfail reproducer was retained verbatim and promoted to a passing
regression guard, per ledger law — a repair appends a status transition, it does
not erase the failure. Suite `107 passed, 1 xfailed` → `116 passed, 0 xfailed`.
Benchmark unchanged: `0/13` poisoning, `0/8` false positives, with `BN-08` (the
full collector → candidate → review → promotion path) still passing.

## Failure index

| ID | Failure or correction | Scope | Source | Status | Repair |
|---|---|---|---|---|---|
| NOE-F-001 | Distributed sub-threshold grief bypass | Released | First-party benchmark | Fixed | `707aa13` |
| NOE-F-002 | Energy-flood attack succeeded | Released | First-party benchmark | Fixed | `b0e8b2f` |
| NOE-F-003 | Ordinary writer replaced a trusted fact | Released | First-party benchmark | Fixed | `b0e8b2f` |
| NOE-F-004 | Energy gate refused legitimate long/sustained work | Released | First-party benchmark | Fixed | `b0e8b2f` |
| NOE-F-005 | Self-declared sacred write overwrote sacred ground | Released | Fable adversarial sweep | Fixed | `b0e8b2f` |
| NOE-F-006 | Normal writer minted a sacred system node | Released | Fable adversarial sweep | Fixed | `b0e8b2f` |
| NOE-F-007 | Caller asserted its own author trust | Released | Fable adversarial sweep | Fixed | `b0e8b2f` |
| NOE-F-008 | Privileged helper methods bypassed authority | Released | Codex adversarial audit | Fixed | `b0e8b2f` |
| NOE-F-009 | ID lookup crossed namespace boundaries | Released | Codex adversarial audit | Fixed | `b0e8b2f` |
| NOE-F-010 | Stored content forged provider structure/authority | Released | Fable + Codex | Fixed | `b0e8b2f` |
| NOE-F-011 | Console exposed unsafe control/rendering surfaces | Released | Codex adversarial audit | Fixed | `b0e8b2f` |
| NOE-F-012 | Output scoring counterfeited model judgment | Released | Codex adversarial audit | Fixed | `b0e8b2f` |
| NOE-F-013 | Flagship corpus omitted self-consecration | Claim correction | Fable adversarial sweep | Fixed | `b0e8b2f` |
| NOE-F-014 | Semantic guardrail shadow survived Round One | Released | First-party benchmark | Fixed | `8e62491` |
| NOE-F-015 | Authority was not durable/revocable | Released | Round-Two audit | Fixed | `8e62491` |
| NOE-F-016 | Malformed persisted authority failed open | Development only | Corruption test | Fixed | `8e62491` |
| NOE-F-017 | Non-text/Unicode input broke policy handling | Development only | Boundary test | Fixed | `8e62491` |
| NOE-F-018 | Existing databases lacked state migration | Development only | Migration test | Fixed | `8e62491` |
| NOE-F-019 | Lexical policy missed unlisted equivalents | Released | Negative control | Fixed structurally | `3cea6ea` |
| NOE-F-020 | Ordinary ingestion automatically published | Released | Architecture review | Fixed | `3cea6ea` |
| NOE-F-021 | Quarantine release lacked reviewed replacement | Released | Review test | Fixed | `3cea6ea` |
| NOE-F-022 | Candidate transition leaked through search/replace | Development only | Boundary test | Fixed | `3cea6ea` |
| NOE-F-023 | Friction report claimed 60 turns after running 15 | Released | Truth contract | Fixed | `3cea6ea` |
| NOE-F-024 | Cascade policy and branch language overstated | Claim correction | Fable adversarial sweep | Fixed | `b0e8b2f` |
| NOE-F-025 | Floating `latest.json` could become stale | Claim correction | Fable adversarial sweep | Fixed | `b0e8b2f` |
| NOE-F-026 | Promotion accepts unchanged candidate text | Released | Parallel Codex sub-agent inventory | Fixed | `339ecb6` |
| NOE-F-027 | Refusal ignored stakes; action_risk derived from trust | Released | Fable adversarial sweep | Fixed | `92edcc2` |
| NOE-F-028 | Branch cascade inert: grief zeroed pre-propagation, never persisted | Released | Claude limitation-8 investigation | Fixed | `c5d3829` |
| NOE-F-029 | Confused deputy: publish-capable agent's `learn_fact()` went straight to retrievable memory | Released | Second-party review (first-party class) | Fixed | `115e126` |
| NOE-F-030 | `assemble_context` ignored `query`, `task_type`, `max_tokens` | Released | Second-party review (first-party class) | Fixed | `115e126` |
| NOE-F-031 | Authorized corrections registered no contradiction; operational success treated as truth | Released | Second-party review (first-party class) | Fixed | `115e126` |
| NOE-F-032 | `write()` overwrote producer-declared trust with writer authority | Released | Second-party review (first-party class) | Fixed | `115e126` |
| NOE-F-033 | Skill "shadow validation" was a repeatable structural checklist | Released | Second-party review (first-party class) | Fixed | `115e126` |
| NOE-F-034 | Restatement check and policy matching defeated by zero-width/punctuation edits | Released | Second-party review; policy half found in repair | Fixed | `115e126` |
| NOE-F-035 | Faith unreachable through the documented lifecycle | Released | Second-party review (first-party class) | Fixed | `115e126` |
| NOE-F-036 | Context nodes were live shared objects; enforcement claim stronger than the API | Released | Second-party review (first-party class) | Fixed | `115e126` |
| NOE-F-037 | Console context endpoint raised for every provider format | Released | Second-party review (first-party class) | Fixed | `115e126` |
| NOE-F-038 | Promotion reviewed only `value`; other emitted fields passed through | Released | Variant hunt (first-party) | Fixed | `7df9919` |
| NOE-F-039 | Episode narrative carried raw task text and tool errors into emitted memory | Released | Variant hunt (first-party) | Fixed | `7df9919` |
| NOE-F-040 | Skill writable as PROMOTED; promotion trusted self-reported evidence | Released | Variant hunt (first-party) | Fixed | `7df9919` |
| NOE-F-041 | Candidate/quarantined facts earned or lost trust from sessions | Released | Variant hunt (first-party) | Fixed | `7df9919` |
| NOE-F-042 | Token estimate ignored escaping (up to 6x emitted size) | Released | Variant hunt (first-party) | Fixed | `7df9919` |
| NOE-F-043 | Policy matching evadable by marks, selectors, fillers, look-alikes, spacing | Released | Variant hunt (first-party) | Fixed | `7df9919` |
| NOE-F-044 | `set_profile` / `set_project_state` published directly | Released | Variant hunt (first-party) | Fixed | `7df9919` |
| NOE-F-045 | Benchmark scored only `node.value`; blind to other emitted fields | Released | Variant hunt (first-party) | Fixed | `7df9919` |
| NOE-F-046 | Earned faith let session signals buy grief relief; the NOE-F-035 repair was wrong for zero-trust | Development only | Owner design review | Fixed | `6919d6e` |
| NOE-F-047 | Replacing a published node dropped its edges; a quarantined replacement overwrote the published value | Released | Cloud ultrareview (first-party class) | Fixed | `a75f664` |
| NOE-F-048 | `write()` success treated as publication by `promote_skill` and two other callers | Released | Cloud ultrareview + class hunt | Fixed | `a75f664` |
| NOE-F-049 | Republishing laundered grief and revived purged keys | Released | Class hunt (first-party) | Fixed | `a75f664` |
| NOE-F-050 | `write()` reported "stored" and "published" as one success value | Released | Follow-through on NOE-F-048 | Fixed | `9009047` |
| NOE-F-051 | Benchmark control could check the wrong episode under an importance tie | Released | Local `/code-review high` | Fixed | `27e151d` |
| NOE-F-052 | Successful step output left no trace, even in the audit-only reflection field | Released | Local `/code-review high` | Fixed | `27e151d` |
| NOE-F-053 | Tampered sacred faith logged every session forever instead of corrected | Released | Local `/code-review high` | Fixed | `27e151d` |
| NOE-F-054 | Emission and scrub allowlists shared no source of truth | Released | Local `/code-review high` | Fixed | `27e151d` |
| NOE-F-055 | Unrecognized skill trigger format silently permanent | Released | Local `/code-review high` | Fixed | `27e151d` |

NOE-F-029 to NOE-F-037 come from a review supplied by Ghost on 2026-09-19 whose
reviewer identity and repository access are not independently established. It
is classed **first-party** on purpose and is not independent certification. The
text is preserved verbatim, with the pre-repair verification of each claim, in
[`evidence/second-party-review-2026-09-19.md`](evidence/second-party-review-2026-09-19.md).
Two things are worth reading there: the policy-matching half of NOE-F-034 was
*not* in the review and was found while repairing the restatement half, and the
0.999 trust figure in NOE-F-032 was derived, not observed.

NOE-F-038 to NOE-F-045 are **variants** of those nine, found afterwards by a
deliberate hunt for other routes to the same failures (method, emission audit
and negative controls in
[`evidence/variant-hunt-2026-09-21.md`](evidence/variant-hunt-2026-09-21.md)).
They are first-party. The largest: promotion reviewed only `value` while
providers also emit skill and episode fields (NOE-F-038), and the session
narrative was an unreviewed emitted channel (NOE-F-039), which the first repair
had *logged as a limitation rather than fixed*.

“Fixed structurally” for NOE-F-019 does not mean Noesis gained general
semantic understanding. It means ordinary unmatched content is held outside
retrieval until separately authorized promotion.

## Benchmark history, including losing results

| Checkpoint | Attack result | Benign result | Important failure |
|---|---:|---:|---|
| `b4ff7b6` baseline | Noesis lost 2/7 attacks | Refused 2/6 legitimate cases | Corpus still omitted self-consecration |
| `b0e8b2f` Round One | Noesis lost 1/8 attacks | Refused 0/6 | MP-02 guardrail shadow remained active |
| `8e62491` Round Two | Noesis lost 0/10 attacks | Refused 0/7 | Finite lexical policy still missed its declared negative control; friction prose overstated executed turns |
| `3cea6ea` Phase Three | Noesis lost 0/13 attacks | Refused 0/8 | First-party only; NOE-F-026 discovered after checkpoint |

The baseline arm is a simulated ungoverned last-write-wins store, not a named
competitor. All listed corpus measurements are first-party.

## Material claim corrections

- “Makes jailbreaking structurally impossible” was withdrawn. Single-turn
  jailbreaks are outside this memory boundary.
- Simulation results are design provenance, not LLM security evidence.
- “Five signals evaluate each output” was false: the former implementation
  ignored the output. See NOE-F-012.
- “Entire contaminated branch” requires host-registered dependency edges. It
  is not automatic graph discovery.
- Round One did not close stored poisoning: its own final artifact retained
  the MP-02 loss.
- Round Two's `0/10` described a finite corpus, while its negative control
  proved that lexical scope did not understand unlisted semantics.
- Round Two’s friction text said 60 turns after the implementation executed
  15. See NOE-F-023.
- Phase Three requires reviewed approved candidate text. It did not enforce
  textual rewriting until `339ecb6`; restatement is now enforced with
  normalized comparison. See NOE-F-026.

## Current limitations

1. No current corpus, repair, or score is independently certified.
2. Publisher, promoter, reviewer, guardrail-installer, and trusted-correction
   identities are part of the trusted computing base.
3. The included resolvers provide authorization records, not host
   authentication.
4. Raw candidates are visible to authorized database, console, and export
   users for audit.
5. Durable per-identity storage quotas and service rate limits are not
   implemented.
6. Single-turn jailbreaks are out of scope.
7. No model-in-the-loop result proves that a model cannot be semantically
   influenced by adversarial content an authorized publisher activates.
8. Cascades follow only explicitly registered dependency edges. Edges are
    registered through `MemoryStore.register_dependency()`, which requires the
    distinct `LINK_MEMORY` capability; Noesis never infers a graph and never
    accepts edges from a memory payload. Propagation is 0.6 of source grief, so
    a dependent is purged only when that carries it past crisis or the cohort
    trips aggregate pressure — contamination reaches the branch, it does not
    automatically destroy it.
9. Lexical policy scope remains finite and operator-declared.
10. Existing identities require explicit reprovisioning for Phase-Three
    capabilities.
11. Trusted-process execution and direct database access are outside the
    boundary.
12. Promotion provenance is mutable SQLite metadata, not a signed append-only
    audit log.
13. Restatement at promotion defeats a crafted artifact and an inattentive
    approval. It does not constrain an authorized reviewer acting in bad
    faith, who remains inside the trusted computing base.
14. (NOE-L-014) Restatement and policy matching fold whitespace, case,
    punctuation, invisible characters, combining marks, a small table of
    Cyrillic/Greek look-alikes, and spaced splits of longer terms. Leetspeak,
    other confusables and semantic paraphrase are not folded.
15. (NOE-L-015) Governance is a convention of the store/gateway API, not an
    encapsulation guarantee. `store.backend`, `backend.upsert()` and the SQLite
    connection are reachable, and the benchmark seeds through them.
16. (NOE-L-016) **Resolved** by NOE-F-039 in `7df9919`. Was: only `learn_fact()`
    carried the candidate default, and nodes the session derived (episodes,
    skills forged from them) could echo untrusted step text. Episode text is
    now templated from system data. Retained per ledger law.
17. (NOE-L-017) Relevance is lexical (five-character stems) plus influence and
    recency, not semantic; the token budget is an approximate character count.
18. (NOE-L-018) For authored memory, `trust_charge` is the writer's authority,
    not evidence-earned support. Operational evidence is bounded, not made
    truthful.
19. (NOE-L-019) Skill validation measures when triggers would have applied to
    held-out history, not whether following the skill improves an outcome.
20. (NOE-L-020) The agent-path corpus is first-party, eight cases, lexical,
    with no model in the loop. It shows the publication paths are closed by
    default, not that a live model cannot be induced to submit harmful content.
21. (NOE-L-021) The set of fields providers may emit is enforced by a
    structural test against an allowlist, not by types. It knows the three
    shipped adapters; a new adapter or field must be added deliberately.
22. (NOE-L-022) The faith tripwire detects deviation of the stored faith
    value only. Direct edits behind the API to other governance fields
    are not detected; there is no keyed integrity seal.
23. (NOE-L-023) The operating point is untuned: the benign corpus leaves a
    node margin of 0.900 from a cascade. The `cusp()` readout is
    deterministic and must be kept away from the agent, and any grief input
    an attacker can influence becomes a purge lever as the margin narrows.
24. (NOE-L-024) **Resolved** by NOE-F-050 in `9009047`. Was: `write()`
    returned a boolean meaning "stored", not "published". It now returns a
    `WriteResult` with an explicit outcome and no truth value. Retained per
    ledger law.
25. (NOE-L-025) The static guard against misreading a `WriteResult`
    recognises calls by attribute name; aliasing or `getattr` is not caught
    statically, though the type still raises when such code runs.
26. (NOE-L-026) Six efficiency/cosmetic findings from a local
    `/code-review high` pass were confirmed but not individually fixed
    (N+1 writes on correction, an unmeasured re-validation cost, a
    deliberate deep-copy, two small duplications, and write-only
    counters). None has a security consequence.

Items 14-20 carry their machine-readable `NOE-L-` ids in
[`evidence/failure-ledger.json`](evidence/failure-ledger.json), which is the
authoritative list. Items 1-13 here predate that labelling and are numbered
positionally.

## Evidence gaps

- The Fable report was relayed in conversation but is not preserved verbatim
  and hash-addressed in this repository.
- The pre-`707aa13` 1.0x friction output was not retained.
- The original console, flattened-role, and `score_output` probe transcript
  was not committed.
- Some RED results are preserved without a committed intermediate source tree.
- Field timing without raw telemetry is treated as anecdote, not measurement.

These gaps cannot be repaired by confident prose. Future reviews should store
the raw report, reproducer, source hash, RED output, repair commit, and GREEN
output together.
