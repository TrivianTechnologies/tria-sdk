# Local correction safety candidate

This candidate implements the existing Truth-Integrity v0.2 governed-application
requirements using canonical claim provenance, fresh context and atomic local
mutation. It does not change the Twelve Invariants, Seven Vows, Four Field Constants,
event schema 0.3, projection 0.6, replay bundle 0.1 or truth authority boundary.

`CORRECTION_SAFETY_VERSION = "0.1"` identifies this implementation surface.
`tria.runtime-context/0.2` identifies the additive context fields. Package version
remains 0.1.0a7 during branch validation; consume this candidate only through its
exact reviewed commit and source fingerprint, not the version number alone.
This is not publication of a new package or a compatibility claim for other a7 trees.

## Canonical graph and snapshot

`snapshot_correction_graph(rel, target_ref)` is a host-level read-only snapshot of
stored `derived_from` links reachable downstream from an existing target. It returns
dependencies and the current event-head hash. It creates no permission and does not
authenticate a correction. Governed application rejects missing/duplicate/invented
links, invalid canonical parents, cycles and caller graphs that omit descendants.
External `RELIES_ON` and `CONTEXT_ONLY` links remain available to the unchanged pure
advisory assessor; this canonical-claim mutation path rejects them.

Pass `expected_head=snapshot.head_hash` to reject stale snapshot application.
Without it, legacy callers request fresh current-graph application and receive no
snapshot-continuity guarantee. The Rosetta correction profile requires this guard.
Snapshot construction requires a canonical lowercase SHA-256 head, a valid target
string and a tuple of exact dependency-link values. The Rosetta boundary revalidates
these fields before use; missing or malformed heads cannot disable its guard.

## Current authority and all-or-none correction

Under the supported shared store guard, application validates the canonical graph,
checks ACT on `truth-integrity:corrections`, records the decision and detects
reentrant changes. It stages ClaimDisputed events and their CorrectionUptakeApplied
receipt, checks current authority again, and appends the whole batch atomically.
A rejected/failed batch leaves no correction disputes or success receipt. An earlier
GovernanceEvaluated audit event may remain; it does not imply application success.
After failure, take a fresh snapshot and independently decide whether to retry.

Built-in memory and SQLite stores supply atomic compare-and-append. Custom stores
must uphold the same guard and append_many contract; hostile raw-process/database
writes are outside this boundary. A revocation taking the guard before commit is
seen; one arriving after the batch commits cannot retrospectively undo it.

## Next consumption

Claim ContextItem values include `claim_status`, `claim_version` (latest relevant
event hash) and `contestation_refs`. Public provider translations preserve them.
A correction during translation prevents release of a stale prepared claim context.
A fresh READ may inspect contested content with its status; this change does not
silently turn advisory classification into a universal READ denial.

The represented status is preserved, including existing REVISED/SUPERSEDED enum
values if supplied by a compatible state producer. This candidate adds no new
revision/supersession event or automated replacement-content authority. Its canonical
correction transition is CONTESTED. Rosetta's declared consequential-claim profile
withholds use of non-ACTIVE required claims until attributable resolution; it does
not infer every latent dependency in arbitrary host text or code.

## Evidence and limits

Status transport tests exercise all five existing ClaimStatus values through
explicit compatible projected-state fixtures and both provider translators.
They do not establish event-driven REVISED, WITHDRAWN or SUPERSEDED transitions:
the existing reducer creates ACTIVE claims and applies CONTESTED disputes only.
Malformed projected-provenance tests likewise inject state fixtures without
creating new normative events. Race tests cover specified injected schedules only.

New tests are in `tests/test_correction_safety.py`. The byte-preserved historical
failure witnesses in `evidence/open-rosetta-19919d8/` belong to commit
19919d8c2562cc00381b30ac3a303a83ce6787fa, not current pytest conformance.
Tests cover both built-in stores, graph rejection, stale snapshots, reentrant and
threaded revocation schedules, injected batch failure/recovery, next consumption
and provider propagation. They do not prove all concurrent schedules or external
evidence authenticity. F033 remains UNRESOLVED: no independent-store freshness,
distributed convergence or global no-resurrection claim is made.
