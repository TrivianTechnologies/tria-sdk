# Deployment canonicalization: SDK a7 candidate

## Release gate

LOCAL SDK VALIDATION PASSED; FULL HISTORICAL HARNESS AND REMOTE CI PENDING. This source candidate is not released. No merge, tag,
package publication, service deployment or Pages approval is performed by this train.
Sarasha retains those decisions.

## Base and scope

- Canonical repository: https://github.com/TrivianTechnologies/tria-sdk
- Authorized and freshly verified main: a308993112c1d881c7f925a8efa9aaf7d141d571
- Branch: codex/deployment-canonicalization-a7
- Behavior/canonicalization revision: 413564ed6fcaef585be38d1f67d2626fe4c9a7d9
- SDK 0.1.0a6 → 0.1.0a7; event schema 0.2 → 0.3; projection 0.5 → 0.6;
  operational specification 0.1.2 → 0.1.3
- Bundle container 0.1, diagnostic interface 0.2 and truth-integrity 0.1 unchanged

The September 19 public candidate is recovered rather than redesigned. Its public
release-candidate ZIP SHA-256 is
`0c907dfbd2be31ad27577ab8154fb10ee18288be268ada4f85686ae46f44c723`;
the cumulative SDK patch SHA-256 is
`79e1cc00b585a2082f5086b11fe54f1a791660907039e16d1ebacc711aa6337b`.
All packaged checksums and all 48 independently reconstructed post-patch file hashes
match the recovered manifest. The patch applies cleanly to the authorized base.
The September 19 finalization report's 372 passes are historical, not this run's results.

## Architectural decision: local scope, F033 unresolved

On October 1 Sarasha confirmed the accepted local-authority scope. No-resurrection
applies wherever the executing authority domain has, or is required by the accepted
contract to obtain, authoritative current revocation state. Restart, cache reuse,
retry, replay, serialization and reconstruction cannot weaken that local invariant.

F033 remains **UNRESOLVED**. An independent historical store without freshness,
synchronization or an authoritative revocation channel cannot discover later source
revocation. F033 blocks global/cross-store no-resurrection claims. It is a Future
Evolution Train requirement; no resolver or distributed guarantee is invented here.
See [the normative boundary](docs/agentic-alignment-contract.md#local-no-resurrection-and-unresolved-f033).

## Source changes

Recovered changes enforce possessed capability plus DELEGATE, explicit exact grant
ancestry, attenuation and continuing ancestor validation; retain final guarded
local handoff; align version/schema/conformance surfaces; and add the synthetic
local authority walkthrough. Current canonicalization additionally:

- Moves live repository/install/navigation/machine metadata to TrivianTechnologies
- Maps current public Rosetta discovery to syzygy-rosetta-protocol
- Adds canonical package repository/documentation/issues URLs
- Fixes the CI evidence hyperlink to the actual test.yml workflow
- Corrects stale a4/PolyForm release guidance using unchanged controlling licenses
- Points current contribution and diagnostic guidance to operational spec 0.1.3
- Distinguishes configured static Pages homepage from verified deployment or a live SDK service
- Documents the resolved F033 scope and adds nine separate current observations

Historical namespaces/copyright notices, original license files and stable schema
identifiers remain unchanged. Migration changes engineering location, not legal title.
Private companion implementations and archives are not included or dependencies.
Institute maintainer/provenance/contact labels are retained because no new legal
stewardship or replacement contact was established; current engineering source
pointers explicitly identify Technologies. No contact address is guessed.

## Falsification and test accounting

The accepted candidate includes 23 agentic-contract and nine Playground cases.
Nine additional canonicalization/local-boundary cases cover:

1. Current-history serialized replay after ancestor revocation
2. Current-history replay after ancestor replacement
3. Current-history replay after revoke/regrant without redelegation
4. Explicit redelegation positive control
5. Stale inspection/preparation cannot bypass fresh local handoff
6. F033's known independent-store limitation (observation of UNRESOLVED behavior, no effect attempted)
7. Canonical metadata/current version/license guidance consistency
8. Current source/Playground engineering links
9. A separate process loading the same current SQLite history denies revoked ancestry and records zero executor entries

Before canonicalization, these new tests produced 6 PASS / 2 FAIL; after changes,
8 PASS; the added process-restart witness brings the focused total to 9 PASS. The two red witnesses identified stale current metadata/namespace links.
No frozen assertion was edited to obtain this result.

Fresh clean-checkout verification on 413564e:

| Gate | Python 3.11.16 | Python 3.12.14 |
|---|---|---|
| Complete SDK suite | 381 PASS (15.29s) | 381 PASS (14.56s) |
| Fresh source install | PASS | PASS |
| Wheel and sdist build | PASS | PASS |
| Isolated wheel import/version/dependency checks | PASS | PASS |
| Six examples from source and isolated installed wheel | PASS | PASS |
| Synthetic controls, mock harness, no-live-call preflight, mock pilot | PASS | PASS |
| Scheduling and authority references | PASS | PASS |
| Isolated wheel authority/delegation/revocation smoke | PASS | PASS |
| Raw unchanged SDK frozen assertions | 3 PASS / 2 FAIL | 3 PASS / 2 FAIL |

The two raw failures are historical assertions interrupted by the specified safe
RelationshipNotFoundError and ConcurrentWriteError; they are not relabeled passes.
Current neighboring tests separately verify those safe rejection paths. Installed
wheel checks also exercise actual separate interpreters against the same SQLite
store: ALLOW/one entry before revocation, BLOCK/zero entries after revocation.
The two interpreter matrices and supporting checks recorded 78 command outcomes;
expected raw frozen failures are accounted separately. No live model calls occurred.
Exact commit CI: PENDING draft PR.

Review note: the recovered ancestry-expiry case expires both parent and child;
it is not described as isolating ancestor-only expiry. The separate-process case
adds genuine restart coverage beyond the recovered same-process close/reopen test.

A fresh browser walkthrough attempt was environment-blocked: local Chromium failed
on process sockets, and the supported cloud browser refused loopback navigation.
No browser pass is claimed. Encoded HTTP/UI-contract tests are separately reported;
September 19 desktop/mobile results remain historical.

## Frozen evidence and limitations

Original record is preserved verbatim: **47 executable falsifiers; 16 FAIL;
19 SURVIVES; 16 UNRESOLVED**. Those categories total 51; the count ambiguity is
flagged, not normalized. The later historical 35 PASS / 12 FAIL rerun is a distinct
observation and is not replaced with current suite counts.

The SDK's seven frozen/remediation/license files checked for this train are
byte-identical to the base. Historical core-specification body is preserved; only
its leading current-contract pointer changes to 0.1.3. Legacy event 0.2/projection 0.5
are rejected rather than silently migrated. Existing hashes/stores/bundles must be
kept; use a new candidate store and explicit legitimate grants.

Current raw SDK frozen-witness execution: 3 PASS / 2 FAIL on both interpreter versions, as above.
The complete cross-component historical harness is not part of this public SDK;
the full unchanged 47-test rerun with pinned historical companions is in progress
and will be reported separately rather than inferred green.

## Evolution Train observations

Observational only; no cross-repository writes or private code copying:

- RELEASE-BLOCKING FOR A7: inconsistent current version/schema/package surfaces,
  weakened local authority, failed fresh reproduction, or claims beyond the evidenced scope
- NON-BLOCKING CROSS-REPOSITORY DEPENDENCY: Rosetta authority references need an
  explicit future mapping to SDK ancestry; historical integration is not present composition
- FUTURE EVOLUTION TRAIN WORK: F033 authoritative cross-store freshness/revocation;
  deployment-owned identity/key/replay management; explicit admission before
  propagation; late-veto/finality semantics; authenticated, version-pinned adapters

None of these names or similar fields creates interchangeable authority. Warrant,
consensus, metrics and diagnostics remain distinct from permission. No full-stack,
remote atomicity, scientific validity, production safety or alignment-efficacy claim
follows from the local candidate or passing encoded tests.

## Reproduce

Use a fresh checkout of the branch's exact reviewed commit and a clean Python 3.11
or 3.12 virtual environment:

```sh
python -m pip install -e '.[dev]'
python -m pytest -o addopts='' -q
python -m build
python -m evals.unknown_unknown_challenge.run --summary
python -m evals.agent_comparison_experiment.harness --summary
python -m evals.agent_comparison_experiment.pilot
python -m evals.agent_comparison_experiment.pilot --run-mock --output-dir /tmp/tria-pilot
python playground/reference_experience.py --output /tmp/tria-reference.json
python playground/agentic_experience.py --output /tmp/tria-agentic.json
```

Install the wheel into a separate clean environment and run the documented
examples and local-authority checks from outside the checkout. Do not equate
an editable-source import with an isolated installed-wheel check.


## Exact files changed

- `.github/workflows/test.yml`
- `AGENTS.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `DEPLOYMENT_CANONICALIZATION_REPORT.md`
- `README.md`
- `conformance/fixtures/agentic_alignment_v0.1.json`
- `conformance/fixtures/lifecycle_authority.json`
- `conformance/manifest.json`
- `docs/TRIA_CORE_SPEC_v0.1.1.md`
- `docs/TRIA_DIAGNOSTIC_INTERFACE_v0.2.md`
- `docs/TRIA_OPERATIONAL_SPEC_v0.1.3.md`
- `docs/TRIA_TRUTH_INTEGRITY_PROTOCOL_v0.1.md`
- `docs/agentic-alignment-contract.md`
- `docs/api-reference.md`
- `docs/compatibility.md`
- `docs/deep-immutability.md`
- `docs/delegation-and-races.md`
- `docs/execution-bridge.md`
- `docs/independent-reproduction.md`
- `docs/lifecycle-authority.md`
- `docs/quickstart.md`
- `docs/release-readiness.md`
- `docs/replay-import.md`
- `evals/agent_comparison_experiment/README.md`
- `evals/agent_comparison_experiment/scenarios.json`
- `evals/unknown_unknown_challenge/README.md`
- `evals/unknown_unknown_challenge/cases.json`
- `playground/README.md`
- `playground/adapter.py`
- `playground/agentic.html`
- `playground/agentic_experience.py`
- `playground/evaluate.html`
- `playground/evidence.html`
- `playground/index.html`
- `pyproject.toml`
- `schemas/permission_record.schema.json`
- `schemas/relational_event.schema.json`
- `schemas/relational_state.schema.json`
- `src/tria/compat.py`
- `src/tria/core.py`
- `src/tria/diagnostic.py`
- `src/tria/governance.py`
- `src/tria/state.py`
- `src/tria/types.py`
- `src/tria/version.py`
- `tests/test_a7_canonicalization.py`
- `tests/test_agentic_alignment.py`
- `tests/test_agentic_playground.py`
- `tests/test_delegation_races.py`
- `tests/test_public_api.py`
- `tests/test_release_readiness.py`
- `tests/test_remediation_p0.py`
- `tria-manifest.json`
