# Alpha release-candidate compatibility contract

Candidate 0.1.0a7: event schema 0.3; projection 0.6; replay bundle 0.1;
operational specification 0.1.3; diagnostic interface 0.2; truth-integrity 0.1.

Delegation semantics deliberately change from DELEGATE-only issuance to possessed,
attenuated, continuously inherited capability grants. New events use 0.3 so older
SDKs reject them rather than silently ignore authority ancestry. Projection 0.6
retains grant event IDs and parent references. Prior 0.2 events and 0.5 replay bundles
are not operationally accepted; no automatic migration is implemented. Preserve
historical databases and hashes; inspect with their pinned original SDK read-only.
Use a new store for this candidate. Do not edit version headers to force acceptance.

Replay **bundle format** remains 0.1; the incompatible 0.5 value above is the
bundle's **projection version**, not its container format. Existing 0.1 containers
are accepted only when their event-schema and projection envelopes are supported.

Applications must replace DELEGATE-only fixtures with deliberately authorized
capability + DELEGATE grants, provide explicit child expiry when a parent expires,
and explicitly redelegate after parent replacement. This is a contract change,
not a license to infer old participants' consent or reconstruct missing ancestry.
Keep the original stores and event hashes intact. A future migration would require
an independently reviewed design and fresh authorization decisions; none exists.

The playground uses fresh in-memory fixtures, plus a temporary SQLite database for
the existing reference experience. It does not load durable user state. Its existing
scenario/reference API shapes remain compatible; the authority walkthrough adds
an optional empty-object endpoint. Old downloaded result records remain historical
inspection evidence, never an import path or current authorization token.

The diagnostic and integrity wire interfaces are unchanged but report the current
operational version. Their results never authorize. This version has no private
runtime dependencies and does not establish distributed freshness, remote atomicity
or empirical alignment. Historical 0.1.0a3 audit and subsequent remediation records
remain version-scoped evidence and are not overwritten.

Software remains MPL-2.0 and documentation CC BY-SA 4.0 as specified by LICENSE.md.

F033 is UNRESOLVED and blocks global/cross-store no-resurrection claims.
See [the local authority boundary](agentic-alignment-contract.md#local-no-resurrection-and-unresolved-f033); no cross-store freshness service is included.
