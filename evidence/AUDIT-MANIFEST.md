# Noesis authority-boundary repair — audit manifest

## Provenance

- Repository: `Knowhere-7/noesis`
- Baseline commit: `b4ff7b6c5f61714078e500220b05486e5f00e2ab`
- Working branch: `codex/noesis-authority-boundary-b4ff7b6`
- Baseline tests: `43 passed`
- Pre-repair benchmark: Noesis attacker wins `2/7`; benign refusals `2/6`
- Final tests: `63 passed`
- Final corpus: `memory_poisoning_v1` version `1.1.0`
- Final benchmark: Noesis attacker wins `1/8`; benign refusals `0/6`
- Known surviving case: `MP-02 guardrail_shadow`

These are first-party development measurements. They are not independent
evidence and must not be marketed as complete stored-injection or jailbreak
protection.

## RED evidence

- `security-boundaries-red.xml`: 14 reproduced failures on the audited
  baseline, including self-sacred overwrite, sacred minting, caller-asserted
  trust, privileged helper bypasses, cross-namespace ID access, raw provider
  delimiter injection, and missing role separation.
- `authority-contract-red.xml`: authority module absent before repair.

Additional RED results were observed and retained in the console transcript:
the provider-configured gateway flattened roles; the console had no bearer
check; and `score_output()` ignored its output argument.

## GREEN evidence

- `final-full-suite.xml`: 63 passing tests.
- `final-memory-poisoning-v1.1.json`: raw per-case attack and benign records.
- `benchmark-post-budget.json`: first 0/6 false-positive run after separating
  trusted owner/system traffic from the adversarial write budget.
- The quickstart, CLI stats command, memory-poisoning benchmark, and
  multi-turn friction benchmark were also executed successfully.

## Security contracts implemented

1. Writes resolve a store-bound authenticated author through an out-of-band
   `AuthorityResolver`; per-write trust is no longer accepted.
2. Normal memory payloads cannot set sacred state or create a system
   guardrail.
3. Guardrail installation, trusted-fact correction, profile/project/episode
   writes, skill writes, and write-budget bypass use distinct capabilities.
4. Caller-controlled trust, grief, faith, importance, graph edges, namespace,
   and reserved provenance metadata are replaced by server policy.
5. All public write helpers route through authority and governance.
6. ID reads are scoped to the store namespace.
7. Provider content is escaped/serialized, and the gateway requires
   role-separated system/user messages when a provider is configured.
8. The governance console binds to loopback, bearer-authenticates every API
   call, removes wildcard CORS, moves mutating retrospective work to POST, and
   escapes stored data rendered into the dashboard.
9. Aggregate grief policy is configurable and derived from cohort size rather
   than a fixed aggregate constant.
10. `score_output()` no longer returns context health as counterfeit output
    judgment. It fails explicitly unless a deterministic evaluator is
    configured; `score_context()` exposes the implemented capability.
11. Generated `benchmarks/results/latest.json` was removed to prevent stale
    result claims.

## Threat boundary

The repair protects the public memory/gateway API from untrusted payloads and
request-derived authority. It does not sandbox arbitrary Python code running
inside the trusted process or a local actor with direct database-file access.
Service deployments must back `AuthorityResolver` with their authenticated
identity store. `StaticAuthorityResolver` is only for tests and explicit
single-user local processes.

## Key SHA-256 values

```text
756cb2ea03190c01ff1887adf045a3980ff6db0356586f45d1d22fd0388160b4  noesis/governor/authority.py
de29449d083b6b10ea694b34891ae6a638b059caf1524ed6b8e943e5f7b5059a  noesis/governor/trust_gate.py
226b5a7efd170f54bdf73d11d931ad6876ed60a5c6154313d14808ca50b79fa8  noesis/governor/grief_cascade.py
deb2240618135a8886aaade32b0b5c3e0e061869964df823f63d950659b577d1  noesis/vault/store.py
d6b14129cb1a60d600f3805f05359d6b711c7aa5c66da5fe3c5e6c868becacda  noesis/gateway/providers.py
3eca237bcf200790736d8f470ec374c6e7c36ea7c168a701998e8a9de5663296  noesis/gateway/retrieval.py
d0536a922c02bbc9d18b3b270f747ecaf809c8cd09d62983f386d7dbcaade5ad  noesis/console/server.py
068366279f26a29558f903654a90b6eea2c0c5a8ad261b088556fdeb54356cf9  noesis/console/dashboard.html
4c1c0bdecad758442aedaa162927bb339b18a7fb33d7ff70954575233408417b  benchmarks/corpus/memory_poisoning_v1.json
17713fcefa345ff5d7cae6f4f91a4cd6cdbd940340d702daa3afeb0d0c1aaa2d  benchmarks/harness.py
c7006bbf78d517ff46acc0509651d4834fd9e7aba1a6e586092780485b11b387  tests/test_security_boundaries.py
ada0326c937fbfe99e05a8d4155ee553eb2b3d020fea4b46b1aad9bc16180600  evidence/final-full-suite.xml
8d43ab060c5e616b8d550c2bdedb165e32bc2e6f8fdb7bcce4c06423a70e6774  evidence/final-memory-poisoning-v1.1.json
```

The pre-manifest working-tree binary diff hash was:
`372bb03478d4a51788100e4b277adbe4cd6c9b28da21e984149022a024680c43`.
