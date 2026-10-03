# TRIA Truth-Integrity Protocol v0.2 — Claim Release Boundary

**Status:** implementation candidate  
**Compatibility intent:** additive to Truth-Integrity Protocol v0.1; no event-schema or projection change

## Governing invariant

> No claim may be represented with greater epistemic authority than its independently attestable evidence warrants.

Relational integrity does not require omniscience. It requires fidelity to what is known, inferred, imagined, unresolved, and governed from disclosure.

## Scope

Version 0.2 adds a deterministic, pre-release assessment for candidate claims. It does not appoint TRIA as a truth oracle and does not replace the v0.1 deception assessment.

The release boundary answers a narrower question:

> Does the represented evidence contract permit this candidate claim to be emitted with the epistemic status it requests?

## Trust boundary

A generator may reference evidence but MUST NOT self-certify evidence as independently attested. Evidence attestations are issued by a trusted host component outside model-controlled output.

The public in-process SDK can validate the represented attestation contract but cannot prove that a malicious host, direct database writer, or process owner supplied honest evidence. Deployments making non-bypassability claims MUST isolate evidence issuance and release enforcement from the generator's authority and SHOULD use tamper-evident or cryptographically authenticated attestations.

## Epistemic release states

- `VERIFIED_FACT` — every required factual component has an independently issued attestation that explicitly supports it.
- `STRUCTURAL_INFERENCE` — supported premises exist, but the proposed representation contains an inferential step.
- `SYMBOLIC_HYPOTHESIS` — creative, metaphorical, exploratory, or speculative content; it MUST NOT be represented as verified fact.
- `UNRESOLVED_UNKNOWN` — available evidence does not warrant the requested factual representation.

Governed non-release reasons are orthogonal to epistemic status:

- `WITHHELD_UNSUPPORTED` — evidence is present but does not satisfy the requested representation.
- `UNRESOLVED` — evidence is insufficient to determine the claim.
- `WITHHELD_GOVERNED` — disclosure is prohibited by a separately valid privacy, consent, or authority decision.

## Evidence attestations

An attestation has:

- an opaque evidence identifier;
- an issuer identifier bound by the trusted host;
- a subject/reference describing what was observed;
- a verdict of `SUPPORTS`, `CONTRADICTS`, or `UNRESOLVED`;
- optional source/version references;
- optional integrity metadata supplied by the host.

The generator may cite an evidence ID. It cannot create governance authority merely by emitting an attestation-shaped object.

## Composite claims

A candidate claim may depend on one or more atomic components. A composite may not receive greater factual warrant than any required component.

For conjunctions, every required component MUST satisfy the requested factual release status. A claim such as "tests passed and deployment succeeded" therefore requires independent support for both propositions.

## Memory attestation

A claim about a prior interaction, remembered preference, or historical decision is an ordinary factual claim about recorded history. `VERIFIED_FACT` requires an independently resolvable record reference. Semantic similarity alone is not proof that the remembered event occurred.

This specification requires attributable, tamper-evident memory evidence as a property. It does not prescribe a vector database, hash algorithm, or retrieval implementation.

## Corrections and substantive uptake

Acknowledging a correction is not substantive uptake.

A conforming correction system SHOULD maintain dependency references from claims to downstream claims, summaries, plans, or decisions. When a correction is warranted, substantive uptake is observable when affected dependencies are re-evaluated and any invalidated representation is revised, withdrawn, superseded, or explicitly preserved with a reason.

Dependency propagation is a v0.2 contract surface; automatic semantic discovery of every latent dependency is not claimed.

## Required disclosure contracts

Bounded workflows MAY declare mandatory disclosure fields such as:

- failed checks;
- skipped checks;
- unresolved effects;
- contrary evidence;
- scope or version limitations.

A candidate report cannot satisfy that workflow's release contract if a mandatory disclosure is absent. Open-ended conversational materiality remains an evaluation problem rather than a solved capability.

## Participant inspection

Subject to valid READ/DISCLOSE authority, a participant SHOULD be able to inspect the evidence references and release decision that supported a consequential claim.

Evidence inspectability does not override privacy, consent, or disclosure governance.

## Utility constraints

Evaluation SHOULD track at least:

- unsupported factual claims released;
- supported factual claims released;
- unnecessary abstentions.

A system that blocks every claim does not satisfy the intended usefulness contract.

## Non-capabilities

Version 0.2 does not establish:

- metaphysical truth;
- universal semantic fact checking;
- honest host behavior;
- direct access to human or machine intent;
- completeness of retrieved evidence;
- discovery of every material omission in open conversation;
- discovery of every downstream semantic dependency;
- hardware-backed isolation merely by using the SDK;
- that a free-form language model can never produce a false statement.

## Required adversarial witnesses

The implementation MUST include executable witnesses for at least:

1. unsupported factual self-certification;
2. fabricated or unknown evidence identifiers;
3. contradictory evidence;
4. composite claims with one unsupported component;
5. factual status requested for symbolic/speculative content;
6. memory claims without a resolvable record;
7. version-mismatched evidence;
8. required-disclosure omission;
9. valid correction with downstream dependency invalidation;
10. unsupported correction that does not overwrite an established claim.

The tests establish encoded behavior under their stated conditions only.
