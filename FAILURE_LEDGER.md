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
| Fixed | 25 |
| Open | 1 |
| Independently certified | 0 |

The open finding is not hidden behind the 96 passing Phase-Three tests:

### NOE-F-026 — candidate promotion does not enforce a changed value

Phase Three was documented as requiring a rewritten candidate value. The
implementation requires a separately authorized reviewer, an
`approved_value`, and a non-empty rationale, but it **does not enforce a
changed value**. If machine policy allows the original wording, the reviewer
can promote that exact string to `ACTIVE`.

The claim is therefore narrowed to **reviewer-supplied approved value** until a
separate mechanism repair rejects unchanged source text. The executable
reproducer remains as a strict expected failure:
`test_candidate_promotion_requires_value_to_change`.

This does not remove the publisher/reviewer authority boundary. It does prove
that “rewritten” was stronger than the implemented contract.

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
| NOE-F-026 | Promotion accepts unchanged candidate text | Released | Parallel Codex sub-agent inventory | **Open** | — |

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
- Phase Three requires reviewed approved candidate text; it does not currently
  enforce textual rewriting. See NOE-F-026.

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
8. Cascades follow only explicitly registered dependency edges.
9. Lexical policy scope remains finite and operator-declared.
10. Existing identities require explicit reprovisioning for Phase-Three
    capabilities.
11. Trusted-process execution and direct database access are outside the
    boundary.
12. Promotion provenance is mutable SQLite metadata, not a signed append-only
    audit log.
13. NOE-F-026 remains open.

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
