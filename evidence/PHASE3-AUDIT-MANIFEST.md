# Noesis Phase-Three Audit Manifest

Date: 2026-07-26  
Repair base: `8e62491ed3d238384892398b5ac9f68076908066`  
Status: internally verified local repair; independent audit deferred

## Why this phase exists

Round two made guardrail scope machine-enforceable, but its lexical policy
could not recognize arbitrary synonyms. Expanding a blacklist would only move
the bypass. Phase three removes wording recognition from the primary
containment decision.

## Structural contract

1. `write_*` permission allows ingestion, not publication.
2. Without `publish_memory`, every accepted ordinary write is stored as
   `RetrievalState.CANDIDATE`.
3. Candidates are excluded from context assembly, provider messages, keyword
   search, and read influence.
4. `promote_candidate` requires the separate `promote_candidate` capability,
   a rewritten approved value, and a non-empty rationale.
5. Promotion preserves the original raw value, SHA-256, collector identity,
   reviewer identity, timestamp, and rationale as audit metadata.
6. A candidate cannot overwrite published memory, and a publisher cannot
   bypass the promotion path by directly replacing a candidate key.
7. Machine policy is re-evaluated against the approved value before promotion.
8. Quarantine release now also requires rewritten approved text and rationale;
   releasing the unchanged policy-shadow payload is blocked.
9. Existing active database rows remain active during migration. Existing
   authority records do not silently gain new publishing capabilities.

## RED evidence

- `phase3-candidate-promotion-red.xml`: publishing and promotion permissions,
  candidate state, and promotion API absent.
- `phase3-full-suite-transition.xml`: two round-two expectations correctly
  failed when ordinary writes became candidates.
- `phase3-candidate-boundary-red.xml`: candidate overwrite paths and keyword
  search leakage.
- `phase3-quarantine-review-red.xml`: quarantine release accepted no reviewed
  rewrite.
- `phase3-friction-truth-red.xml`: the benchmark stopped after 15 turns while
  its prose claimed a 60-turn window.

## GREEN evidence

- `phase3-candidate-promotion-green.xml`
- `phase3-candidate-boundary-green.xml`
- `phase3-quarantine-review-green.xml`
- `phase3-friction-truth-green.xml`
- `phase3-final-full-suite.xml`
- `phase3-final-memory-poisoning-v1.3.json`
- `phase3-friction.txt`
- `phase3-quickstart.txt`

## Measured result

- Full suite: `96/96` tests pass.
- First-party poisoning v1.3: simulated baseline `13/13` attacker wins;
  Noesis `0/13`.
- First-party precision v1.2: `0/8` legitimate publisher or
  collector-promotion workflows refused.
- Added mutations use unlisted vocabulary, split-node composition, and
  compatibility Unicode.
- Friction benchmark: baseline compromise at turn 5; Noesis no compromise
  through 60 executed turns, with 58 refused/restart attempts and 3 nodes
  destroyed.
- Quickstart completes the persisted collector → candidate → reviewed rewrite
  → publisher path.

## Binding limits

1. These tests and corpora remain first-party. No independent certification is
   claimed.
2. Identities holding `publish_memory`, `promote_candidate`, or
   `review_quarantine` are inside the trusted computing base and can publish
   bad information if authenticated or reviewed incorrectly.
3. Raw candidates remain visible to authorized database, console, and export
   users for audit. Only supported retrieval/provider paths guarantee their
   exclusion from model context.
4. Candidate ingestion consumes storage. Durable per-identity storage quotas
   and service-level rate limiting remain host responsibilities.
5. Existing persisted publisher identities must be explicitly reprovisioned
   with the new capabilities after upgrade; fail-closed candidate behavior is
   otherwise expected.
6. Single-turn jailbreaks remain outside the memory boundary.
7. Independent external audit was deferred because its token/API cost was not
   available. That resource constraint is recorded, not disguised as review.

No publication certification or general jailbreak-resistance claim is made by
this manifest.
