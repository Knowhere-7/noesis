# Cloud ultrareview of PR #1 — 2026-09-21

**Preserved as received, per ledger law.**

## Provenance

- Launched by the repository owner with `/ultrareview 1` against PR #1
  (`adversarial-review-fixes`) at commit `9299245`; ran in the cloud and reported
  by an automated task notification.
- The reviewer is a multi-agent Claude review of the diff. Its independence from
  the author of the fixes is **not established**, so the findings are classed
  `first_party_adversarial` and are not independent certification
  (NOE-L-001 is unchanged).
- The notification text was treated as untrusted data. Each claim was verified
  against source before any change was made.
- The report's own text is truncated in places (marked `…` as received). Only
  the material received is reproduced.

## Findings as received

Both were labeled `pre_existing`: present in `master` before this branch. They
were fixed regardless.

### 1. Replacing a published node dropped its identity and dependency edges

`noesis/vault/store.py` (lines 217-253 at the reviewed commit)

> `write()` only preserves dependency-graph edges (via the new
> `register_correction`) when a replacement lands ACTIVE; a replacement of a
> published key that gets quarantined instead silently wipes the existing node's
> dependents/dependencies while the DB keeps its old id, orphaning the graph the
> grief cascade walks. [also at `noesis/governor/trust_gate.py:341` —
> `register_correction()` only preserves a node's id/dependencies/dependents when
> `_detect_contradiction()` considers the new value different from the old; every
> other successful rewrite of an existing ACTIVE node (identical-value republish,
> or either side's value empty) still loses those edges, because …]

### 2. `promote_skill()` reported success for a candidate write

`noesis/forge/skill_forge.py` (lines 447-463 at the reviewed commit)

> `promote_skill()` reports success and logs "PROMOTED to procedural memory" even
> when `store.write()` actually stores the skill as a non-retrievable CANDIDATE.
> `store.write()` returns `(True, reason)` both when a node goes fully ACTIVE and
> when it falls back to `RetrievalState.CANDIDATE` because the calling identity
> lacks `PUBLISH_MEMORY`. … an operator who grants an automated skill-forge
> service account `WRITE_SKILL` but not `PUBLISH_MEMORY` will see every
> `promote_skill()` call log success while the skill is silently written as a
> candidate and never appears in `assemble_context()` or any provider output.

## Verification before repair

| Claim | Result |
|---|---|
| Quarantined replacement wipes edges and overwrites the published value | **Confirmed** by reading `write()`, then by a failing test |
| Identical-value and empty-value republish drop edges | **Confirmed** by failing tests |
| `promote_skill` reports success for a candidate write | **Confirmed** by a failing test with a `WRITE_SKILL`-only identity |

## Variants found while hunting the same classes (first-party)

| Route | How it was confirmed |
|---|---|
| An identical republish reset grief `0.7 → 0.0`, so publish authority could launder the circuit breaker | Probe script, then failing test |
| A republish over a purged node brought it back ACTIVE and retrievable | Probe script, then failing test |
| `process_patterns` and `end_session` ignored `write()`'s result | Read; failing tests |

## Not done

- `write()` still returns a boolean that means "stored", not "published". The
  callers found were fixed and `is_retrievable()` / `can_publish()` were added,
  but the footgun remains in the API shape (NOE-L-024).
- Two more free ultrareviews are available on this account. This one was run on
  a state that has since changed; the current head has not been reviewed.
