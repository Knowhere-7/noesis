# Local `/code-review high` pass on PR #1 — 2026-09-24

**Provenance.** Launched by the repository owner as `/code-review high`
(forked-skill subagent within this Claude Code session, not the cloud
ultrareview). Scope: `git diff master...HEAD` on `adversarial-review-fixes` at
commit `d12722f`. 8 finder angles run in parallel, 15 deduplicated candidates,
independently verified by 3 verifier agents; all 15 returned CONFIRMED. Top 10
by severity were reported; 5 more were named but cut by the output cap.

Classed `first_party_adversarial`: this is a Claude subagent working inside the
same account, not an external party (NOE-L-001 unchanged).

## Verification and outcome

Each of the top 10 was re-checked against source before any change.

| # | Finding | Verified | Outcome |
|---|---|---|---|
| 1 | Benchmark episode selection via `next()` lets an importance tie decide which episode is checked | **Confirmed** — both episode writes get importance 0.6 from `_IMPORTANCE_POLICY`, so an unordered scan's tie-break is undefined | **Fixed** (NOE-F-051) |
| 2 | Successful step output absent from audit trail | **Confirmed** — `_find_effective_actions` never included `step["output"]` | **Fixed** (NOE-F-052) |
| 3 | Sacred faith tamper logged every session forever | **Confirmed** — sacred branch logged and `continue`d without correcting or upserting | **Fixed** (NOE-F-053) |
| 4 | Scrub allowlist and emission allowlist can drift | **Confirmed** as a structural risk; no current live gap | **Guarded** (cross-check test, NOE-F-054) |
| 5 | Unrecognized trigger format silently permanent | **Confirmed** | **Fixed**, diagnostic added (NOE-F-055) |
| 6 | `evaluate()`/`cusp()` re-scan the table 3-4x | **Confirmed** | **Fixed** (efficiency, folded into this commit) |
| 7 | `register_correction` N+1 per-dependent DB round trips | **Confirmed** | Not fixed — batched in the limitations list |
| 8 | `promote_skill` re-runs `validate_skill` unconditionally | **Confirmed**, but intentional (prevents forged evidence) | Not fixed — documented tradeoff, in limitations |
| 9 | `get_context_nodes` deep-copies the full node graph | **Confirmed** | Not fixed — isolation was the deliberate choice (NOE-F-036); in limitations |
| 10 | Live-nodes visibility filter duplicated in two benchmark functions | **Confirmed** | Not fixed — in limitations |

Five more named but cut by the cap (all confirmed, all cosmetic/low severity):
a loop-based dict lookup that could be direct (`_scrub_unreviewed`), three
`Fact` counters that are write-only and never read to decide anything, a
discarded `Evaluation` object in `promote_skill`, and duplicated provider-
adapter enumeration between the harness and the console server. None fixed;
recorded in the same batched limitation.

## Scope decision

Five findings with direct correctness or security consequence were fixed with
failing tests first. The `evaluate()`/`cusp()` scan cost was fixed alongside
them since every session pays it. The remaining six (7-10 plus the five
cut) are efficiency or cosmetic observations with no security consequence;
engineering all of them individually was judged lower priority than the work
already in this PR, so they are recorded as one honest limitation rather than
partially or hastily fixed.
