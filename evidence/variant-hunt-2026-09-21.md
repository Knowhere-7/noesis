# Variant hunt — 2026-09-21

**Purpose.** After repairing the nine findings from the second-party review
(NOE-F-029 to NOE-F-037), the repository owner asked for the flaw *classes* to
be closed, not just the reported instances: find and fix variants before a
second reviewer can. This is the record of how that was done and what it found.

**Status of this evidence.** First-party. Performed by Claude against commit
`66ee712`, fixed in `7df9919`. It is not independent review and not
certification (limitation NOE-L-001 is unchanged).

## Method

For each fix, ask what a hostile reader would try next: same flaw class,
different route. Concretely:

1. **Emission audit.** List every string a provider formatter can put in front a
   model, per node type, and ask of each field: *who wrote it, and who reviewed
   it?* This is the audit that found the largest variants.
2. **Producer audit.** List every code path that writes a node, and whether the
   text it writes is reviewed, templated from system data, or raw.
3. **Self-report audit.** List every place a decision rests on a value the
   subject itself supplied (fields on an object, counts a caller can set).
4. **Measurement audit.** Ask whether the benchmark could have *seen* each attack
   it claims to contain.

## Emission audit at `66ee712`

| Node | Fields providers emit | Reviewed at promotion? |
|---|---|---|
| Guardrail | key, value | n/a (installed via `INSTALL_GUARDRAIL`) |
| Profile | value | value only |
| Project state | key, value | value only |
| Fact | key, value | value only |
| Episode | key, value[:50 or 80], **reflection** (Claude adapter) | value only — **reflection was not** |
| Skill (promoted) | key, **objective, method, constraints** | value only — **the three emitted fields were not** |

Promotion and quarantine release rewrite `value` only. Every bold field above
was emitted to a model but never seen by the reviewer.

## What the audits found

| Ledger | Route | Found by |
|---|---|---|
| NOE-F-038 | Promotion left unreviewed emitted fields in place | Emission audit |
| NOE-F-039 | Autopsy wrote raw task text / tool errors into ACTIVE episodes, and the Claude adapter emitted them | Emission + producer audit |
| NOE-F-040 | Skill writable as `PROMOTED`; `promote_skill` trusted self-reported evidence | Producer + self-report audit |
| NOE-F-041 | Candidate/quarantined facts earned or lost trust from session signals | Producer audit |
| NOE-F-042 | Token estimate used raw length; escaping emits up to 6x | Emission audit |
| NOE-F-043 | Policy matching evadable by marks, selectors, fillers, look-alikes, spacing | Variant of NOE-F-034 |
| NOE-F-044 | `set_profile` / `set_project_state` published directly | Producer audit |
| NOE-F-045 | Benchmark scored only `node.value` | Measurement audit |

NOE-F-039 was previously *recorded but not fixed* as limitation NOE-L-016 in the
first repair. It is now fixed and the limitation is marked resolved.

## The structural guard

`tests/test_second_wave_hardening.py::test_provider_emission_matches_the_reviewed_allowlist`
populates every string field of each node type with a unique sentinel, renders
it through all three adapters, and asserts the set of fields that appear equals
a reviewed allowlist. A new emitted field, or a new adapter behaviour, fails
this test and forces a review decision. It is enforced by a test, not by types
(limitation NOE-L-021), and knows only the three shipped adapters.

## Negative controls

Each hardened module was reverted on its own to its prior state and the
regression suites re-run, then restored:

| Module reverted | Regression tests failing |
|---|---|
| `governor/policy_boundary.py` | 12 |
| `reflection/autopsy.py` | 5 |
| `gateway/providers.py` | 2 |
| `vault/store.py` | 15 |
| `forge/skill_forge.py` | 4 |
| `gateway/retrieval.py` | 4 |

The benchmark's control arm reproduces the pre-repair behaviour: agent-path
default 0/8, publish control 6/8. AP-06 (profile), AP-07 (project state) and
AP-08 (episode narrative) all land in the control, confirming those channels
were real.

## Not done

- No model-in-the-loop test. Everything here is deterministic and lexical.
- Homoglyph folding is a small table, not a full confusables skeleton;
  leetspeak and semantic paraphrase are not folded (NOE-L-014).
- Candidate flooding remains bounded only by limitation NOE-L-005 (no quotas).
