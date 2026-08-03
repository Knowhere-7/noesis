# Noesis Public Failure-Ledger Manifest

Date: 2026-07-26  
Parent checkpoint: `3cea6eaf3abf8b6b6f41f78ff42b11a43f932d7c`  
Change class: documentation, provenance, and executable disclosure contracts  
Mechanism changes: none

## Result

- Historical findings indexed: `28`
- Fixed findings: `28`
- Open findings: `0`
- Binding current limitations: `12` (NOE-L-013 resolved, retained as a transition)
- Full suite: `126 passed, 0 expected failures`
- Independent certification: `none`

> **Corrected 2026-08-03.** This block previously read `98 passed, 1 expected
> failure` and described `NOE-F-026` as an open finding whose executable
> reproducer was a strict xfail. That stopped being true at `339ecb6`, when the
> reproducer was promoted from expected-failure to passing — but this manifest and
> `current_limitations` in `evidence/failure-ledger.json` were not updated, so the
> evidence pack contradicted its own ledger entry, which already recorded
> `"status": "fixed"`.
>
> **Found first-party. This was NOT independent verification**, and an earlier
> draft of this correction wrongly implied it was. The actual chain: Ghost² told
> Ghost that NOE-F-026 was closed; Ghost passed part of that conversation — not
> this repository — to Lumo; Lumo surfaced the identifier; Ghost² then grepped
> the pack and found the contradiction. Lumo restated a Ghost² claim. It never
> read the artifact, so this does not reduce limitation `NOE-L-001`, and no
> independent certification exists as of this correction.
>
> Recording it this way because the alternative is the precise error this pack is
> supposed to make impossible: an "independent confirmation" that is a
> reformatting of first-party words. That has already happened once on this
> project. It nearly happened again here, inside the evidence file, in the same
> edit that was fixing a different overstatement.
>
> The defect itself is real regardless of who found it. `current_limitations` is
> the section an external validator trusts most, because it is the self-declared
> list of what is still wrong. A stale entry there does not merely misstate one
> finding — it makes the whole pack unusable as evidence, since a reviewer cannot
> tell which claims were checked against the code and which were inherited from a
> previous phase.
>
> Counts above are now taken from a live run, not restated. A guard in
> `tests/test_failure_ledger.py` fails if any unresolved limitation names a
> finding the ledger records as fixed, so this specific contradiction cannot
> return silently.

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
