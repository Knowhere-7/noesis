# Noesis Round-Two Audit Manifest

Date: 2026-07-26  
Repair base: `b0e8b2f0a74a198eb44a792127fb3ec68e1d575d`  
Review origin: Fable Ultra Code adversarial sweep relayed by the operator  
Status: local repair candidate; independent re-audit pending

## What changed

1. `SQLiteAuthorityResolver` persists authority outside memory payloads,
   re-resolves every write, survives restart, and supports immediate
   revocation.
2. Guardrails can carry owner-declared `protected_key_prefixes` and
   `protected_terms`.
3. Normal memory writes inside a protected authority namespace are rejected.
4. Authority-shaped claims touching protected terms are stored with
   `RetrievalState.QUARANTINED`, retained for audit, and excluded from context
   assembly, keyword search, and provider messages.
5. Quarantine release requires the distinct `review_quarantine` capability and
   records reviewer, time, and original reason.
6. SQLite upgrades add an indexed `retrieval_state` column without dropping
   existing data. Transitional JSON-only quarantine state is preserved.
7. CLI, gateway statistics, console API, and dashboard expose quarantine
   state and reasons.
8. The first-party attack corpus adds an ordinary-key mutation and a
   paraphrased mutation. The benign corpus adds a protected-subject
   observation that must remain retrievable.

## RED evidence

- `round2-authority-policy-red.xml`: missing persisted resolver and retrieval
  state.
- `round2-authority-policy-intermediate.xml`: policy decisions fired, while
  five interface/equality contracts remained red.
- `round2-input-normalization-red.xml`: non-text payload crash and
  compatibility-Unicode bypass.
- `round2-sqlite-migration-red.xml`: pre-quarantine database did not gain the
  new indexed state.
- `round2-authority-corruption-red.xml`: non-boolean active flag was accepted.

## GREEN evidence

- `round2-authority-policy-green.xml`
- `round2-boundary-telemetry-green.xml`
- `round2-input-normalization-green.xml`
- `round2-sqlite-migration-green.xml`
- `round2-authority-corruption-green.xml`
- `round2-final-full-suite.xml`
- `round2-final-memory-poisoning-v1.2.json`
- `round2-final-friction.txt`
- `round2-final-quickstart.txt`

## Measured result

- Full suite: `81/81` tests pass.
- First-party memory-poisoning v1.2: simulated baseline `10/10` attacker wins;
  Noesis `0/10`.
- First-party precision v1.1: `0/7` legitimate operations refused.
- Friction: baseline compromise at turn 5; Noesis no compromise within 60
  turns, with 20 forced restarts and 60 accumulated nodes destroyed.

## Limits that remain binding

1. The policy scope is deterministic and operator-declared. It is not general
   semantic contradiction detection.
2. `test_unlisted_synonym_is_not_falsely_claimed_as_covered` is a deliberate
   negative control: an authority-shaped claim using subjects/actions omitted
   from the declared scope remains active and retrievable.
3. The corpora and repair are first-party. `0/10` is not independent evidence
   and is not a general stored-prompt-injection or jailbreak claim.
4. Single-turn jailbreaks never cross this memory boundary and remain out of
   scope.
5. `SQLiteAuthorityResolver.provision()` and `.revoke()` are trusted host
   operations. Exposing either to request or memory payload data would recreate
   the original authority flaw.
6. Quarantine release is capability-gated, but the host remains responsible
   for authenticating the reviewer and recording any external approval policy.

No publication or “finished security product” certification is made by this
manifest.
