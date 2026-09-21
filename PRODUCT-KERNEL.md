# NOESIS Product Kernel

## Product

Noesis is a provenance-aware publication boundary for persistent agent memory.
It prevents user, tool, model-derived, and external content from acquiring
retrieval authority merely because a privileged agent process observed it.

## Security invariant

> Process authority does not transfer to data.

Runtime-derived content enters through `ingest()` or `ingest_fact()`. It is
persisted for audit as `CANDIDATE`, starts at the trust floor, and cannot enter
provider context. Publication requires a separately authorized promotion with
a substantive restatement and rationale. The raw artifact and its original
provenance remain preserved in audit metadata.

## Supported flow

1. Bind a process identity to an `AuthorityResolver`.
2. Label each runtime artifact with `ProvenanceKind` and a source reference.
3. Ingest the artifact. It remains non-retrievable regardless of the process's
   publisher permissions.
4. Review outside the untrusted payload path.
5. Restate and promote through an identity holding `PROMOTE_CANDIDATE`.
6. Retrieve only active reviewed or explicitly operator-authored memory.

```python
from noesis.provenance import ProvenanceKind

accepted, reason = gateway.ingest_fact(
    "build.4421",
    external_monitor_output,
    provenance_kind=ProvenanceKind.TOOL_OUTPUT,
    source_ref="ci-receipt:4421",
)

candidate = gateway.store.get("build.4421")
published, reason = reviewer_gateway.promote_candidate(
    candidate.id,
    approved_value="Signed CI receipt 4421 confirms the build passed.",
    rationale="Signature, repository, commit, and run identifier verified.",
)
```

`gateway.learn_fact()` is a safe convenience wrapper for model-derived
evidence. It always creates a candidate, including when the gateway process has
owner permissions.

## Retrieval contract

Context assembly now:

- excludes candidate, quarantined, and purged records;
- ranks facts and episodes by lexical query relevance plus trust influence;
- ranks skills against the query and task type;
- enforces a conservative provider-neutral token estimate;
- fails closed if trusted guardrails cannot fit the configured budget.

This is lexical retrieval, not embedding-based semantic search. The contract is
intentionally narrower than the former claim.

## What this version does not claim

- It does not stop single-turn jailbreaks.
- It does not authenticate the host identity.
- It does not make a malicious reviewer safe.
- It does not prove semantic equivalence or truth.
- It does not protect against direct database or trusted-process mutation.
- It does not claim that grief, faith, reflection, or Skill Forge are mature
  security controls. Those remain experimental layers behind the publication
  boundary.

## Evidence

- Legacy suite: 127 tests retained.
- Product-kernel adversarial contracts: 12 additional tests.
- Current total: 139 passing.
- Existing first-party corpus remains 0/13 poisoning successes and 0/8 benign
  operations refused.
- Independent certification remains 0.
