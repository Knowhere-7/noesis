# ⚠️ `console/orb-preview` is stale — do not merge, do not run

**Live branch: [`master`](https://github.com/Knowhere-7/noesis/tree/master).**

This branch was parked on 2026-07-25 at `d0fa22d`. As of 2026-07-28 it is **14
commits behind master** and predates the entire authority system — persisted
identity, capability gating, policy scope, retrieval quarantine, and the
candidate/publication boundary all landed on master after this branch stopped.

## Its known defects are already fixed on master — do not "fix" them here

When this branch was parked it carried three real problems. All three were
independently resolved on master by the Codex authority rounds:

| Defect on this branch | Status on master |
|---|---|
| `/store/upsert` wrote via `backend.upsert()`, bypassing the TrustGate | **Endpoint removed entirely** |
| No authentication on any endpoint | **Per-process bearer token on every request**, timing-safe via `secrets.compare_digest`, 401 otherwise |
| Bound `0.0.0.0` | **Loopback**, configurable `bind_host` |

Covered on master by `tests/test_security_boundaries.py::test_console_bearer_check_is_fail_closed`.

Porting fixes backward onto this branch would be wasted work. The console on
master is the maintained one.

## What exists ONLY here

Verified absent from master on 2026-07-28:

- **`noesis/console/swarm.html`** (103 lines) — live swarm topology view.
- **`noesis/console/flatworm.html`** (257 lines) — the flatworm view.
- **`noesis/console/perfect_swarm___MUST_SEE___DONT_DELETE.py`** (591 lines) —
  seed scenario reconstructing the perfect-swarm state inside Noesis: sacred
  guardrails at faith 0.92, earned-trust profiles, dependency chains, and
  deliberately stressed/contaminated nodes proving the grief system is alive.
  Its own docstring: *"This is the demo state. This is what Gemini showed us.
  This is the proof that governance works."*
- **`MemoryNode.contribution`** — influence + authority + activity +
  connectivity, sacred floored at 0.8. Drives agent size in the visualisation.

## If you want the visualisation live, it is a PORT, not a merge

The seed script manipulates the store directly, and master's API has moved
underneath it: `write()` no longer accepts `author_trust`, authority is bound at
store construction, privileged node types are capability-gated, and ordinary
ingestion now lands as a CANDIDATE rather than publishing straight to ACTIVE.
The script will not run unmodified.

The honest scope is: lift the three assets onto master, rebuild the seed against
the current authority model, and decide whether `contribution` should feed
anything in core (it is currently console-only, and is a plausible primitive for
publisher standing).

## Backups

Full history including this branch:
- `K:\backups\noesis\noesis-20260728-all.bundle`
- mirrored to `D:\ghost2-continuity\crown-jewels\`

Restore was **proven**, not assumed: cloned from the bundle alone, master's suite
runs 126 passed, and all three console assets plus `contribution` recover intact.
