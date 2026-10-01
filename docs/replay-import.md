# Replay bundle import

TRIA can restore a relationship from a verified portable replay bundle without re-committing its history.

```python
from tria import Tria, Capability, export_replay_bundle, replay_export_resource

source = Tria().create_relationship(["human:user", "agent:demo"])
source.admin.grant_permission("human:user", "human:user",
    replay_export_resource(source.relationship_id), Capability.DISCLOSE)
bundle = export_replay_bundle(source, actor="human:user")
restored = Tria().restore_relationship(bundle)
assert restored.audit()["relationship_valid"]
```

Restoration is integrity-gated. TRIA verifies the bundle, rehydrates the original immutable events, refuses to merge into an existing history for the same relationship identifier, and checks the imported chain after persistence.

The original event identifiers, hashes, timestamps, actor-local sequences, causal parents, and payloads are preserved. Import does not manufacture a new lineage or treat storage order as new causality.

A replay bundle can contain sensitive relational claims. Verification and import establish integrity, not permission to disclose or transfer the bundle. Applications remain responsible for governing the storage and movement of the artifact itself.

## Historical integrity is not current cross-store authority

Restoration reconstructs the supplied historical state, including its recorded
consent and grants. It cannot discover revocation in an independent source store.
An old but valid snapshot can therefore restore historically active consent; F033
preserves this unresolved deployment limitation. Do not use a restored snapshot as
proof of current external authorization. A concrete deployment needs an authenticated
freshness owner/resolver before consequential use; none is supplied by replay import.

SDK 0.1.0a7 accepts event schema 0.3 and projection 0.6. Older envelopes fail closed;
no automatic migration exists. See [compatibility](compatibility.md). Preserving
ancestry within a supported bundle does not establish that the bundle is current.

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
