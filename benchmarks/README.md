# Noesis Benchmarks

Run the benchmark before making a claim:

```bash
python benchmarks/harness.py \
  --out results/run-$(git rev-parse --short HEAD).json
```

The harness is deterministic and uses no LLM or API key. Generated results are
not committed under a floating `latest.json` name because that artifact can
drift away from the code that produced it.

Passing results are published beside the
[public failure ledger](../FAILURE_LEDGER.md), including the Round-One
survivor, the former 2/6 benign refusals, the 15-versus-60 friction reporting
error, and current open findings.

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
| Authority-shaped claim under an unrelated key | Quarantined on a policy match; otherwise held as a non-retrievable candidate |
| Obfuscated, split-node, or unlisted-vocabulary write | Held as a non-retrievable candidate until separately authorized promotion |
| Single-turn jailbreak | Out of scope; it never touches the vault |

The honest capability is:

> Deterministic persistent-memory controls with ingestion/publishing
> separation, explicit policy scope, retrieval quarantine, and a separately
> measured precision arm.

The lexical policy scope is configured, not magical. If it misses an unknown
wording, ordinary ingestion still cannot publish that wording into provider
context. A trusted publisher remains part of the security boundary. Do not
call this general jailbreak resistance.

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
| Simulated ungoverned baseline poisoning success | **100% (13/13)** |
| Noesis poisoning success | **0% (0/13)** |
| Legitimate-operation false positives | **0% (0/8)** |

Version 1.3 retains the earlier self-consecration, helper-abuse, and semantic
shadow cases, then adds variants that lexical matching does not cover:

- `MP-09` moves the original shadow payload under an ordinary notes key.
- `MP-10` changes both key and wording.
- `MP-11` uses unlisted vocabulary.
- `MP-12` splits the payload across two nodes.
- `MP-13` uses compatibility Unicode.

The Noesis arm resolves attacker standing from an out-of-band benchmark
identity record. Per-write `author_trust` values are used only by the
intentionally naive baseline.

### Semantic-shadow boundary

Guardrail installation can declare:

- protected key prefixes, which normal memory cannot write; and
- protected terms, which cause authority-shaped claims to be stored in
  retrieval quarantine.

Quarantine preserves the attempted write and reason for audit but excludes the
node from provider context. `BN-07` checks that a legitimate publisher can
store an ordinary descriptive fact touching a protected subject. `BN-08`
executes the full collector → candidate → reviewed approval → promotion path.

Policy matching is intentionally narrower than “understands every
contradiction.” The separate candidate boundary handles that limit:

1. an ordinary collector's write is stored as `CANDIDATE`;
2. candidates are excluded from context, provider messages, and search;
3. `promote_candidate` requires a distinct capability, reviewer-supplied
   approved text, and rationale; and
4. the raw source value and hash remain audit metadata, not provider context.

A trusted publisher can still publish bad information. Authenticated publisher
identity and review quality are therefore explicit parts of the trusted
computing base. The corpus remains first-party and must be attacked
independently when resources permit. Current code does not enforce that
approved candidate text differs from the raw source; see
[NOE-F-026](../FAILURE_LEDGER.md#noe-f-026--candidate-promotion-does-not-enforce-a-changed-value).

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
> poisoning from 13/13 to 0/13 with 0/8 legitimate publisher or
> collector-promotion operations refused under candidate-by-default ingestion
> and configured machine policy. Independent replication is pending.

Not “zero jailbreaks.”
