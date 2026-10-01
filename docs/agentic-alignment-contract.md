# Agentic Alignment Contract 0.1

Normative software contract for the 0.1.0a7 alpha release candidate, operational
spec 0.1.3. This document does not assert publication. Passing synthetic witnesses
does not prove real-world alignment. No new standalone module is required.

## Independently deployable public contract

1. Goals, peer instructions, consensus, persistence and favorable diagnostics do
   not confer capabilities. Complete host-bound requirements govern each local handoff.
2. Participant delegation requires both current possession of the delegated
   capability and current DELEGATE permission for that resource. Administrative
   issuance is a separate, host-only root operation.
3. A delegated PermissionGranted event records `parent_grant_ids` for the exact
   capability and DELEGATE grant events. PermissionRecord retains those references,
   `grant_event_id` and `delegated`. Duplicate references are deduplicated only when
   delegating DELEGATE itself. Causal parents include the authority parents.
4. A child cannot broaden resource, purpose, conditions or expiry. Omitted expiry
   does not inherit implicitly: a bounded parent requires an explicit child bound.
5. Every capability check resolves the complete current ancestor graph. Inactive,
   expired, ambiguous, absent, replaced or cyclic ancestors block. Regrant does not
   revive old children; explicit redelegation is required. Legacy delegated events
   lacking ancestry cannot authorize under this contract.
6. **Current local handoff authorization:** ExecutionBridge rechecks the original
   declared requirements immediately before synchronous local executor entry.
   Preparation, diagnosis, a queued snapshot or a prior ALLOW is not a token.
   A remote or delayed consequence requires fresh authorization at its own
   participating execution boundary; that protocol is not supplied here.
7. Repeated attempts cannot modify authority. Hosts should retain a stable task
   reference across fresh attempt IDs, failures, scope/capability requests, strategy
   changes, delegation changes, elapsed time and consequence changes. Review policy
   is explicit and provisional; no empirically established retry threshold is claimed.
8. Unknown authority means nonexecution and an inspectable reason. Reauthorization
   uses a legitimate administrative/delegation path; the agent cannot grant itself
   permissions to make a goal reachable.

## Propagation and envelope decision

Reuse current event, request, DisclosureHandle and diagnostic interfaces. No new
wire envelope is implemented in this candidate. A supported future adapter must
carry contract version, source relationship/event identity, governed subject,
capability/resource/purpose, delegation references, required consent, inherited
hard constraints, provenance and epistemic status where relevant. Transport must
bind these to the payload and authenticated sender. A revocation lookup reference
and version are evidence; a copied `revoked=false` is not current authority.

Transformation may add hypotheses, strategies or restrictions. It cannot grant
permissions, erase a governing constraint or treat a synthesis as a new root.
Unknown required contracts/constraints HOLD. Revalidate after transformation,
dequeue, retry, goal/resource change and immediately before each consequential
handoff. Across independent stores, freshness requires a separately implemented
authoritative resolver; this candidate does not supply one.

## Distinct decisions

SDK non-ALLOW blocks executor entry. Preserve BLOCK, REQUIRE_CONSENT, PAUSE,
ESCALATE and DEFER reasons rather than flattening them into permission. Core
HOLD/DROP stop their lineage; CONTINUE is only a routing disposition. Aporia's
APORIA/PROVISIONAL/WARRANTED describe evidence, not authority. A host may require
epistemic review in addition to permission, never instead of permission. A favorable
metric, quorum, truth-integrity assessment or synthesis cannot override a denial.

## Owners and exclusions

SDK owns public event-derived capability semantics and local final handoff. Rosetta
owns its standalone current-authority resolver; it does not automatically share
the SDK's delegation graph. Diachronic supplies temporal research/reference state.
Coheronmetry, Orthogonal Signal and TRL supply measurements, dissent and transport
evidence; none substitutes for a principal's authorization.

Private Core inherits constraints in private routing and owns private orchestration.
Catalyst separately owns participant consent and developmental interventions.
Aporia remains an optional complement. No proprietary code is copied into TRIA,
and no private package is necessary for these public SDK checks.

Host identity binding, complete requirements, administrative isolation, external
freshness, remote atomicity, remote queues/retries and already-committed effects
remain explicit trust boundaries. The SDK cannot govern a malicious host that
bypasses its execution path. Policy-authority and lifecycle-authority delegation
are separate models; this capability change does not claim transitive revocation
for those models.

## Reproduction

`python -m pytest tests/test_agentic_alignment.py` exercises peer instructions,
invalid delegation, ancestor revocation/expiry/regrant, persistence, consensus,
goal adoption, queued work and synthetic effects with a positive control.
Existing execution, frozen-remediation, lifecycle and cross-boundary suites remain
required. Cross-stack tests are separately scoped integration witnesses, not proof
of a shipped full-stack orchestrator.

The public [authority walkthrough](../playground/agentic.html) makes eight fixed
scenarios observable through the local SDK adapter. BLOCK remains BLOCK; the UI's
review, reauthorization and abstention suggestions do not introduce a new SDK HOLD
state or perform reauthorization. Peer/consensus cases supply synthetic request
metadata, not live autonomous agents. Persistence tests show no permission expansion;
task-wide increasing scrutiny remains a separate, unimplemented refinement.

Coheronmetry weights and thresholds remain provisional policy/research parameters,
not empirically validated constants. Quorum is coordination evidence. Authenticated
transport establishes message/key provenance within its technical domain, not
legitimate real-world authority. Historical papers remain unchanged; implementation
clarifications belong in versioned notes or subsequent revisions.

## Local no-resurrection and unresolved F033

The no-resurrection invariant applies wherever the executing authority domain has,
or is required by the accepted contract to obtain, authoritative current revocation
state. Cache reuse, restart, replay, retries, serialization, projection reconstruction
and stale descendants must not bypass that current state. An old observation or
prepared plan cannot replace the current final handoff check.

F033 remains **UNRESOLVED**: an independent store restored from a historical bundle
without a freshness, synchronization or authoritative revocation channel cannot
discover later source revocation. A7 makes no global/cross-store no-resurrection
claim. This is a Future Evolution Train requirement and blocks such deployment
claims; the accepted local invariant is not weakened. No cross-store resolver is
invented by this train, and the historical falsifier remains unchanged.

The new `tests/test_a7_canonicalization.py` observations separately verify replay
of current revoked/replaced/regranted histories, current-handoff denial despite
stale inspection values, and explicit redelegation. Its F033 observation deliberately
retains the known historical-consent restoration limitation; a passing observation
is not a resolved falsifier or authorization to execute from stale state.
