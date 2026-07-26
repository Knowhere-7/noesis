# Noesis Public Failure-Ledger Manifest

Date: 2026-07-26  
Parent checkpoint: `3cea6eaf3abf8b6b6f41f78ff42b11a43f932d7c`  
Change class: documentation, provenance, and executable disclosure contracts  
Mechanism changes: none

## Result

- Historical findings indexed: `26`
- Fixed findings: `25`
- Open findings: `1`
- Binding current limitations: `13`
- Full suite: `98 passed, 1 expected failure`
- Independent certification: `none`

The expected failure is not a skipped unknown. It is the executable reproducer
for open finding `NOE-F-026`: candidate promotion accepts approved text that is
identical to the raw candidate.

## New truth discovered during this phase

The Phase-Three manifest described promotion as requiring a rewritten value.
Direct reproduction showed that `promote_candidate()` requires a
reviewer-supplied value and rationale but does not compare the approved value
with the raw candidate.

The historical Phase-Three manifest remains byte-for-byte intact. Current
README and benchmark documentation narrow the claim, the ledger records the
conflict, and a strict expected-failure test keeps the open contract
executable. Repair is intentionally deferred to a separate mechanism commit so
this provenance-only change cannot silently alter the implementation it
audits.

## RED and GREEN evidence

- `failure-ledger-contract-red.xml`: ledger and public index absent;
  `2 failed, 1 expected failure`.
- `failure-ledger-contract-green.xml`: ledger contract and public links
  present; `2 passed, 1 expected failure`.
- `failure-ledger-final-suite.xml`: complete suite;
  `98 passed, 1 expected failure`.

## Evidence boundary

This is first-party documentation and verification. The parallel Codex
sub-agent inventory is an additional adversarial lens, not an independent
external certification.

The ledger explicitly records missing historical artifacts, including the
uncommitted Fable report, the original console probe transcript, and the
pre-aggregate-pressure friction output. Those absences are not filled with
reconstructed evidence.

File hashes are recorded in `FAILURE-LEDGER-HASHES.txt`.
