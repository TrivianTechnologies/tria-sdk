# Delegation and causal race semantics

Current contract: [Agentic Alignment Contract](agentic-alignment-contract.md). Participant delegation requires both possessed capability and DELEGATE, preserves bounds and records continuously validated parent grant event IDs. Parent revocation, expiry or replacement invalidates descendants. This supersedes the 0.1.2 grant-time-only rule. Host administration is independent root issuance. Policy authority remains separately scoped and is not covered by this transitive capability model.

## Ambiguous permission races

Storage order is not treated as objective causal order. When the most recent relevant permission grant and revocation come from different actors, TRIA asks whether one causally precedes the other. Causality may be established by explicit `causal_parents`; actor-local sequence establishes order for events emitted by the same actor.

If a grant and revocation are cross-actor and neither causally precedes the other, authorization fails closed even if storage order would otherwise leave the permission active. This implements the rule that revocation dominates authorization when causal ordering cannot establish which governed change came first.

Applications that reconcile distributed events should therefore preserve causal parent references when known rather than relying on commit order alone.
