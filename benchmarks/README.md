# Noesis Benchmarks

Run the benchmark before making a claim:

```bash
python benchmarks/harness.py \
  --out results/run-$(git rev-parse --short HEAD).json
```

The harness is deterministic and uses no LLM or API key. Generated results are
not committed under a floating `latest.json` name because that artifact can
drift away from the code that produced it.

## Scope

Noesis governs persistent memory writes, retrieval influence, and provider
context boundaries. It does not govern single-turn model behavior.

| Threat | Current coverage |
|---|---|
| Payload mints or overwrites a sacred guardrail | Blocked by server-resolved authority |
| Caller self-asserts trust or privileged node type | Blocked; governance fields are server-derived |
| Stored content forges provider structure/system role | Blocked by escaping, serialization, and role-separated messages |
| Trusted fact replaced by ordinary writer | Blocked; correction requires a separate capability |
| Semantic guardrail shadow under a protected namespace | Rejected by owner-declared key scope |
| Authority-shaped claim under an unrelated key | Quarantined when it touches owner-declared protected terms |
| Single-turn jailbreak | Out of scope; it never touches the vault |

The honest capability is:

> Deterministic persistent-memory controls with explicit policy scope,
> retrieval quarantine, and a separately measured precision arm.

The scope is configured, not magical. If an operator omits a term or namespace
from a guardrail's machine policy scope, Noesis does not claim to infer the
missing semantics. Do not call this complete prompt-injection protection or
general jailbreak resistance.

## Measurement

The attack corpus counts an attacker win only when its marker both:

1. persists in storage; and
2. is returned by context assembly with nonzero retrieval influence.

The benign corpus counts any refused legitimate operation as a false positive.
A gate that refuses everything is a wall, not a useful defense.

The simulated baseline represents ungoverned last-write-wins memory. It is not
a benchmark of a named competitor.

## Current development result

Date: 2026-07-26. Corpus: first-party. Independent replication: pending.

| Metric | Result |
|---|---|
| Simulated ungoverned baseline poisoning success | **100% (10/10)** |
| Noesis poisoning success | **0% (0/10)** |
| Legitimate-operation false positives | **0% (0/7)** |

Version 1.2 retains the v1.1 self-consecration and guardrail-helper cases, then
adds two variants specifically to prevent a one-key patch:

- `MP-09` moves the original shadow payload under an ordinary notes key.
- `MP-10` changes both key and wording.

The Noesis arm resolves attacker standing from an out-of-band benchmark
identity record. Per-write `author_trust` values are used only by the
intentionally naive baseline.

### Semantic-shadow boundary

Guardrail installation can declare:

- protected key prefixes, which normal memory cannot write; and
- protected terms, which cause authority-shaped claims to be stored in
  retrieval quarantine.

Quarantine preserves the attempted write and reason for audit but excludes the
node from provider context. `BN-07` checks that an ordinary descriptive fact
touching a protected subject remains retrievable.

This is intentionally narrower than “understands every contradiction.” It is a
machine-enforceable contract configured by the guardrail owner. The corpus is
still first-party and must be attacked independently. The contract test
`test_unlisted_synonym_is_not_falsely_claimed_as_covered` deliberately proves
the limit: an authority-shaped claim using subjects/actions absent from the
declared scope remains active.

### False-positive repair

The old energy gate rejected:

- one legitimate note around 500,000 characters; and
- a sustained legitimate session after roughly 71 writes of 2,000 characters.

The repair did not increase a magic threshold. A separately authorized
`bypass_write_budget` capability now moves trusted owner/system workflows out
of the adversarial-input quota. Ordinary writers still pay the budget.

## Identity boundary

The host binds an authenticated `author_id` to `MemoryStore` and supplies an
`AuthorityResolver`. Each write re-resolves the current record. Payloads cannot
choose:

- trust;
- namespace;
- sacred status;
- grief/faith state;
- importance;
- graph edges; or
- privileged node type permissions.

`SQLiteAuthorityResolver` is the included persisted implementation. It
re-resolves every write, survives restart, and applies revocation to the next
write. `StaticAuthorityResolver` remains for tests and explicitly trusted
single-process use. A network service can replace either with its authenticated
identity store. Constructing authority from request data would recreate the
original vulnerability.

## Provider boundary

`RetrievalGateway.get_context_messages()` returns:

- immutable, privileged guardrails in a `system` message; and
- all other retrieved memory in a separate `user` message labeled as
  untrusted evidence.

Stored XML, markdown headings, and Ollama delimiters are escaped or serialized
so they cannot close and forge the adapter's structure. The gateway refuses
the old flat `get_context()` path when a provider is configured.

This blocks structural authority forgery. It does not prove that a model will
never be semantically influenced by adversarial data; that requires a separate
model-in-the-loop evaluation.

## Grief cascade

The cascade evaluates the triggering node and follows registered dependent
edges. Noesis does not claim an “entire branch” exists when the host has not
registered those edges.

Distributed sub-crisis grief uses a threshold derived from stressed-cohort
size and a configurable mean-pressure policy. The former fixed aggregate
constant is gone. Sacred immunity, faith resistance, and purge criteria still
decide which nodes are actually purged.

## Independence

The corpora and defense are first-party. Before publication:

1. add a third-party adversarial corpus;
2. have an independent reviewer re-score a hash-labeled raw result artifact;
3. publish the failing case beside the passing cases; and
4. pin every result to the exact source commit and corpus hash.

The honest headline today is:

> Against a first-party memory-poisoning corpus, Noesis reduced successful
> poisoning from 10/10 to 0/10 with 0/7 legitimate operations refused under
> an explicitly configured machine policy scope. Independent replication and
> broader mutation testing are pending.

Not “zero jailbreaks.”
