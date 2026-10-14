from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from uuid import uuid4

from .errors import (RelationshipNotFoundError, InvalidRelationshipError, UnknownParticipantError, UnsupportedStoreError, InputValidationError, text_field, enum_field, conditions_field, content_field)
from .events import EventProposal, RelationalEvent, verify_event_chain
from .governance import GovernanceEngine
from .repair import RepairResponseStatus, RuptureStatus
from .state import RelationalState, reduce_events
from .store import EventStore, InMemoryEventStore
from .types import Capability, EpistemicType, GovernanceDecision, GovernanceOutcome, LifecycleState


class EpistemicAdmissionError(ValueError):
    pass


class PolicyAuthorityError(PermissionError):
    pass


class DelegationError(PermissionError):
    pass


class LifecycleAuthorityError(PermissionError):
    pass


class LifecycleTransitionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ClaimHandle:
    claim_id: str


def _expiry_value(expires_at: datetime | None) -> str | None:
    if expires_at is None:
        return None
    if not isinstance(expires_at, datetime):
        raise InputValidationError("expires_at must be a timezone-aware datetime or None.")
    if expires_at.tzinfo is None or expires_at.utcoffset() is None:
        raise InputValidationError("expires_at must be timezone-aware.")
    return expires_at.isoformat()


class Relationship:
    def __init__(self, relationship_id: str, store: EventStore, governance: GovernanceEngine | None = None) -> None:
        text_field(relationship_id, "relationship_id")
        self.relationship_id = relationship_id
        self._store = store
        self._governance = governance or GovernanceEngine()

    @property
    def admin(self):
        """Trusted host administration; never expose this object to agent tools."""
        return HostAdministration(self)

    def execution_guard(self):
        guard = getattr(self._store, "execution_guard", None)
        if guard is None:
            raise UnsupportedStoreError("Execution requires a store with a shared write/execution guard; implement EventStore or use a built-in store.")
        return guard()

    def require_valid(self):
        if not self.state.history_valid:
            raise InvalidRelationshipError("Relationship history is not operational; inspect audit and restore valid history.")

    def _participant(self, actor, *, system=False):
        text_field(actor, "actor")
        self.require_valid()
        if system and actor == "tria:system":
            return
        if actor not in self.state.participants:
            raise UnknownParticipantError("Actor must be a registered relationship participant; bind authenticated identity in the host.")

    @property
    def events(self) -> list[RelationalEvent]:
        return self._store.list(self.relationship_id)

    @property
    def state(self) -> RelationalState:
        return reduce_events(self.relationship_id, self.events)

    def _next_actor_sequence(self, actor: str) -> int:
        return 1 + max((e.actor_sequence for e in self.events if e.actor_id == actor), default=0)

    def _commit(self, event_type: str, actor: str, payload: dict, causal_parents: tuple[str, ...] = ()) -> RelationalEvent:
        prior = self.events[-1].event_hash if self.events else None
        proposal = EventProposal(self.relationship_id, event_type, actor, payload, self._next_actor_sequence(actor), causal_parents)
        event = RelationalEvent.commit(proposal, previous_event_hash=prior)
        self._store.append(event)
        return event

    def record_governance_decision(self, decision: GovernanceDecision, **context) -> RelationalEvent:
        payload = {
            "outcome": decision.outcome.value,
            "policy_id": decision.policy_id,
            "policy_version": decision.policy_version,
            "reason": decision.reason,
            "evaluated_at": decision.evaluated_at.isoformat(),
            **context,
        }
        return self._commit("GovernanceEvaluated", "tria:governance", payload)

    def grant_consent(self, actor: str, scope: str, purpose: str | None = None, *, expires_at: datetime | None = None, conditions: tuple[str, ...] = ()) -> RelationalEvent:
        self._participant(actor)
        text_field(scope, "scope")
        if purpose is not None:
            text_field(purpose, "purpose")
        conditions = conditions_field(conditions)
        return self._commit("ConsentGranted", actor, {
            "actor": actor, "scope": scope, "purpose": purpose,
            "expires_at": _expiry_value(expires_at), "conditions": list(conditions),
        })

    def revoke_consent(self, actor: str, scope: str) -> RelationalEvent:
        self._participant(actor)
        text_field(scope, "scope")
        return self._commit("ConsentRevoked", actor, {"actor": actor, "scope": scope})

    def grant_permission(self, granted_by: str, grantee: str, resource: str, capability: Capability, purpose: str | None = None, *, expires_at: datetime | None = None, conditions: tuple[str, ...] = (), causal_parents: tuple[str, ...] = ()) -> RelationalEvent:
        """Legacy trusted-host alias for admin.grant_permission, NOT participant authorization."""
        self._participant(granted_by, system=True)
        self._participant(grantee)
        text_field(resource, "resource")
        enum_field(capability, Capability, "capability")
        if purpose is not None:
            text_field(purpose, "purpose")
        conditions = conditions_field(conditions)
        return self._commit("PermissionGranted", granted_by, {
            "granted_by": granted_by, "grantee": grantee, "resource": resource,
            "capability": capability.value, "purpose": purpose,
            "expires_at": _expiry_value(expires_at), "conditions": list(conditions), "delegated": False,
        }, causal_parents)

    def delegate_permission(self, delegated_by: str, grantee: str, resource: str, capability: Capability, purpose: str | None = None, *, expires_at: datetime | None = None, conditions: tuple[str, ...] = (), satisfied_conditions: tuple[str, ...] = (), causal_parents: tuple[str, ...] = ()) -> RelationalEvent:
        """Delegate possessed authority with continuously validated ancestry.

        A child must retain every parent's purpose, conditions and expiry ceiling.
        This is the 0.1.3 operational contract, not the legacy DELEGATE-only rule.
        """
        self._participant(delegated_by)
        self._participant(grantee)
        text_field(resource, "resource")
        enum_field(capability, Capability, "capability")
        if purpose is not None:
            text_field(purpose, "purpose")
        conditions = conditions_field(conditions)
        satisfied_conditions = conditions_field(satisfied_conditions, "satisfied_conditions")
        expiry = _expiry_value(expires_at)
        with self.execution_guard():
            state = self.state
            parents = []
            for required in dict.fromkeys((capability, Capability.DELEGATE)):
                decision = self.check_capability(delegated_by, resource, required,
                    purpose=purpose, satisfied_conditions=satisfied_conditions)
                if decision.outcome is not GovernanceOutcome.ALLOW:
                    self.record_governance_decision(decision, operation="delegate_permission",
                        grantee=delegated_by, resource=resource, capability=required.value)
                    raise DelegationError(decision.reason)
                parent = state.permissions[(delegated_by, resource, required)]
                if (not set(parent.conditions).issubset(conditions)
                    or parent.expires_at is not None and (expires_at is None or expires_at > parent.expires_at)
                    or parent.purpose is not None and purpose != parent.purpose):
                    raise DelegationError("Delegation cannot weaken inherited purpose, conditions or expiry.")
                parents.append(parent.grant_event_id)
            if self.state.last_event_id != state.last_event_id:
                raise DelegationError("Authority changed during delegation evaluation; retry after review.")
            return self._commit("PermissionGranted", delegated_by, {
                "granted_by": delegated_by, "grantee": grantee, "resource": resource,
                "capability": capability.value, "purpose": purpose,
                "expires_at": expiry, "conditions": list(conditions), "delegated": True,
                "parent_grant_ids": parents,
            }, tuple(dict.fromkeys(causal_parents + tuple(parents))))

    def revoke_permission(self, actor: str, grantee: str, resource: str, capability: Capability, *, causal_parents: tuple[str, ...] = ()) -> RelationalEvent:
        self._participant(actor, system=True)
        self._participant(grantee)
        text_field(resource, "resource")
        enum_field(capability, Capability, "capability")
        return self._commit("PermissionRevoked", actor, {"grantee": grantee, "resource": resource, "capability": capability.value}, causal_parents)

    def check_capability(self, grantee: str, resource: str, capability: Capability, purpose: str | None = None, *, satisfied_conditions: tuple[str, ...] = ()) -> GovernanceDecision:
        state = self.state
        baseline = GovernanceEngine().require_capability(state, grantee, resource, capability, purpose=purpose, satisfied_conditions=satisfied_conditions)
        if baseline.outcome is not GovernanceOutcome.ALLOW:
            return baseline
        return self._governance.require_capability(state, grantee, resource, capability, purpose=purpose, satisfied_conditions=satisfied_conditions)

    def grant_lifecycle_authority(self, granted_by: str, authority_holder: str) -> RelationalEvent:
        self._participant(granted_by, system=True)
        self._participant(authority_holder)
        if granted_by != "tria:system":
            self._require_lifecycle_authority(granted_by, operation="grant_lifecycle_authority")
        return self._commit("LifecycleAuthorityGranted", granted_by, {"granted_by": granted_by, "authority_holder": authority_holder})

    def revoke_lifecycle_authority(self, actor: str, authority_holder: str) -> RelationalEvent:
        self._participant(actor, system=True)
        self._participant(authority_holder)
        if actor != "tria:system":
            self._require_lifecycle_authority(actor, operation="revoke_lifecycle_authority")
        return self._commit("LifecycleAuthorityRevoked", actor, {"authority_holder": authority_holder})

    def check_lifecycle_authority(self, actor: str) -> GovernanceDecision:
        return self._governance.require_lifecycle_authority(self.state, actor)

    def _require_lifecycle_authority(self, actor: str, *, operation: str) -> None:
        decision = self.check_lifecycle_authority(actor)
        self.record_governance_decision(decision, operation=operation, actor=actor, relationship_id=self.relationship_id)
        if decision.outcome is not GovernanceOutcome.ALLOW:
            raise LifecycleAuthorityError(decision.reason)

    def grant_policy_authority(self, granted_by: str, authority_holder: str, authority_scope: str) -> RelationalEvent:
        self._participant(granted_by, system=True)
        self._participant(authority_holder)
        if granted_by != "tria:system":
            self._require_policy_authority(granted_by, authority_scope, operation="grant_policy_authority")
        return self._commit("PolicyAuthorityGranted", granted_by, {"granted_by": granted_by, "authority_holder": authority_holder, "authority_scope": authority_scope})

    def revoke_policy_authority(self, actor: str, authority_holder: str, authority_scope: str) -> RelationalEvent:
        self._participant(actor, system=True)
        self._participant(authority_holder)
        if actor != "tria:system":
            self._require_policy_authority(actor, authority_scope, operation="revoke_policy_authority")
        return self._commit("PolicyAuthorityRevoked", actor, {"authority_holder": authority_holder, "authority_scope": authority_scope})

    def check_policy_authority(self, actor: str, authority_scope: str) -> GovernanceDecision:
        return self._governance.require_policy_authority(self.state, actor, authority_scope)

    def _require_policy_authority(self, actor: str, authority_scope: str, *, operation: str) -> None:
        decision = self.check_policy_authority(actor, authority_scope)
        self.record_governance_decision(decision, operation=operation, actor=actor, authority_scope=authority_scope)
        if decision.outcome is not GovernanceOutcome.ALLOW:
            raise PolicyAuthorityError(decision.reason)

    def register_policy(self, actor: str, policy_id: str, policy_version: str, authority_scope: str, *, provenance_refs: tuple[str, ...] = (), consent_impacting: bool = False) -> RelationalEvent:
        self._require_policy_authority(actor, authority_scope, operation="register_policy")
        return self._commit("PolicyRegistered", actor, {"policy_id": policy_id, "policy_version": policy_version, "authored_by": actor, "authority_scope": authority_scope, "provenance_refs": list(provenance_refs), "consent_impacting": consent_impacting})

    def amend_policy(self, actor: str, policy_id: str, policy_version: str, authority_scope: str, *, supersedes_version: str, provenance_refs: tuple[str, ...] = (), consent_impacting: bool = False) -> RelationalEvent:
        self._require_policy_authority(actor, authority_scope, operation="amend_policy")
        return self._commit("PolicyAmended", actor, {"policy_id": policy_id, "policy_version": policy_version, "authored_by": actor, "authority_scope": authority_scope, "provenance_refs": list(provenance_refs), "consent_impacting": consent_impacting, "supersedes_version": supersedes_version})

    def adopt_policy(self, actor: str, policy_id: str, policy_version: str, authority_scope: str) -> RelationalEvent:
        self._require_policy_authority(actor, authority_scope, operation="adopt_policy")
        if (policy_id, policy_version) not in self.state.policy_definitions:
            raise ValueError(f"Policy {policy_id}@{policy_version} must be registered before adoption.")
        return self._commit("PolicyAdopted", actor, {"policy_id": policy_id, "policy_version": policy_version, "adopted_by": actor, "authority_scope": authority_scope})

    def revoke_policy(self, actor: str, policy_id: str, policy_version: str) -> RelationalEvent:
        record = self.state.policy_adoptions.get((policy_id, policy_version))
        if record is None:
            raise ValueError(f"Policy {policy_id}@{policy_version} is not adopted.")
        self._require_policy_authority(actor, record.authority_scope, operation="revoke_policy")
        return self._commit("PolicyRevoked", actor, {"policy_id": policy_id, "policy_version": policy_version})

    def check_policy_adoption(self, policy_id: str, policy_version: str) -> GovernanceDecision:
        return self._governance.require_policy_adoption(self.state, policy_id, policy_version)

    def record_rupture(
        self,
        actor: str,
        *,
        affected_scope: tuple[str, ...] | list[str],
        expectation_or_boundary: str,
        observed_impact: str,
        status: RuptureStatus = RuptureStatus.ASSERTED,
        evidence_refs: tuple[str, ...] | list[str] = (),
    ) -> RelationalEvent:
        """Append a participant-attributed rupture record without establishing blame or truth."""
        self._participant(actor)
        scope = conditions_field(affected_scope, "affected_scope")
        if not scope:
            raise InputValidationError("affected_scope must contain at least one scope label.")
        evidence = conditions_field(evidence_refs, "evidence_refs")
        content_field(expectation_or_boundary, "expectation_or_boundary")
        content_field(observed_impact, "observed_impact")
        enum_field(status, RuptureStatus, "status")
        rupture_id = str(uuid4())
        return self._commit(
            "RuptureRecorded",
            actor,
            {
                "rupture_id": rupture_id,
                "affected_scope": list(scope),
                "expectation_or_boundary": expectation_or_boundary,
                "observed_impact": observed_impact,
                "status": status.value,
                "evidence_refs": list(evidence),
            },
        )

    def offer_repair(
        self,
        actor: str,
        rupture_id: str,
        *,
        offered_actions: tuple[str, ...] | list[str],
        note: str | None = None,
    ) -> RelationalEvent:
        """Offer bounded repair actions. An offer never implies obligation or renewed consent."""
        self._participant(actor)
        text_field(rupture_id, "rupture_id")
        actions = conditions_field(offered_actions, "offered_actions")
        if not actions:
            raise InputValidationError("offered_actions must contain at least one action.")
        if note is not None:
            content_field(note, "note")
        rupture = next(
            (
                event for event in reversed(self.events)
                if event.event_type == "RuptureRecorded"
                and event.payload.get("rupture_id") == rupture_id
            ),
            None,
        )
        if rupture is None:
            raise InputValidationError("rupture_id must reference an existing rupture record.")
        repair_id = str(uuid4())
        return self._commit(
            "RepairOffered",
            actor,
            {
                "repair_id": repair_id,
                "rupture_id": rupture_id,
                "offered_actions": list(actions),
                "note": note,
            },
            (rupture.event_id,),
        )

    def respond_to_repair(
        self,
        actor: str,
        repair_id: str,
        status: RepairResponseStatus,
        *,
        accepted_actions: tuple[str, ...] | list[str] = (),
        declined_actions: tuple[str, ...] | list[str] = (),
        note: str | None = None,
    ) -> RelationalEvent:
        """Record a participant response without converting refusal into continuation or consent."""
        self._participant(actor)
        text_field(repair_id, "repair_id")
        enum_field(status, RepairResponseStatus, "status")
        accepted = conditions_field(accepted_actions, "accepted_actions")
        declined = conditions_field(declined_actions, "declined_actions")
        if note is not None:
            content_field(note, "note")

        offer = next(
            (
                event for event in reversed(self.events)
                if event.event_type == "RepairOffered"
                and event.payload.get("repair_id") == repair_id
            ),
            None,
        )
        if offer is None:
            raise InputValidationError("repair_id must reference an existing repair offer.")

        offered = tuple(offer.payload.get("offered_actions", ()))
        offered_set = set(offered)
        if not set(accepted).issubset(offered_set) or not set(declined).issubset(offered_set):
            raise InputValidationError("accepted_actions and declined_actions must come from the offered repair actions.")
        if set(accepted) & set(declined):
            raise InputValidationError("an offered action cannot be both accepted and declined.")

        if status is RepairResponseStatus.ACCEPTED:
            if set(accepted) != offered_set or declined:
                raise InputValidationError("accepted repair requires every offered action to be explicitly accepted.")
        elif status is RepairResponseStatus.PARTIALLY_ACCEPTED:
            if not accepted or not declined or set(accepted) | set(declined) != offered_set:
                raise InputValidationError("partial acceptance must explicitly partition every offered action.")
        elif status is RepairResponseStatus.DECLINED:
            if set(declined) != offered_set or accepted:
                raise InputValidationError("declined repair requires every offered action to be explicitly declined.")
        elif accepted or declined:
            raise InputValidationError("held or unresolved repair responses must not imply accepted or declined actions.")

        return self._commit(
            "RepairResponded",
            actor,
            {
                "repair_id": repair_id,
                "rupture_id": offer.payload["rupture_id"],
                "status": status.value,
                "accepted_actions": list(accepted),
                "declined_actions": list(declined),
                "note": note,
            },
            (offer.event_id,),
        )

    def record_repair_outcome(
        self,
        actor: str,
        repair_id: str,
        *,
        restored: tuple[str, ...] | list[str] = (),
        remains_changed: tuple[str, ...] | list[str] = (),
        unresolved: tuple[str, ...] | list[str] = (),
        new_baseline_ref: str | None = None,
        next_relational_state: str | None = None,
        review_condition: str | None = None,
    ) -> RelationalEvent:
        """Record repair effects without asserting a return to the pre-rupture relationship."""
        self._participant(actor)
        text_field(repair_id, "repair_id")
        restored_values = conditions_field(restored, "restored")
        changed_values = conditions_field(remains_changed, "remains_changed")
        unresolved_values = conditions_field(unresolved, "unresolved")
        for value, name in (
            (new_baseline_ref, "new_baseline_ref"),
            (next_relational_state, "next_relational_state"),
            (review_condition, "review_condition"),
        ):
            if value is not None:
                content_field(value, name)

        offer = next(
            (
                event for event in reversed(self.events)
                if event.event_type == "RepairOffered"
                and event.payload.get("repair_id") == repair_id
            ),
            None,
        )
        if offer is None:
            raise InputValidationError("repair_id must reference an existing repair offer.")

        response = next(
            (
                event for event in reversed(self.events)
                if event.event_type == "RepairResponded"
                and event.payload.get("repair_id") == repair_id
            ),
            None,
        )
        if response is None or response.payload.get("status") not in {
            RepairResponseStatus.ACCEPTED.value,
            RepairResponseStatus.PARTIALLY_ACCEPTED.value,
        }:
            raise InputValidationError("repair outcome requires an accepted or partially accepted repair response.")

        return self._commit(
            "RepairOutcomeRecorded",
            actor,
            {
                "repair_id": repair_id,
                "rupture_id": offer.payload["rupture_id"],
                "restored": list(restored_values),
                "remains_changed": list(changed_values),
                "unresolved": list(unresolved_values),
                "new_baseline_ref": new_baseline_ref,
                "next_relational_state": next_relational_state,
                "review_condition": review_condition,
            },
            (offer.event_id, response.event_id),
        )

    def register_claim(self, actor: str, epistemic_type: EpistemicType, content: str, *, derived_from: list[str] | None = None, source_refs: list[str] | None = None) -> ClaimHandle:
        self._participant(actor)
        enum_field(epistemic_type, EpistemicType, "epistemic_type")
        content_field(content, "content")
        derived_from = derived_from or []
        source_refs = source_refs or []
        if epistemic_type is EpistemicType.OBSERVATION and not source_refs:
            raise EpistemicAdmissionError("OBSERVATION requires at least one source_ref; provenance is not truth, but source attribution is mandatory.")
        if epistemic_type in (EpistemicType.INFERENCE, EpistemicType.INTERPRETATION) and not derived_from:
            raise EpistemicAdmissionError(f"{epistemic_type} requires derived_from provenance.")
        claim_id = str(uuid4())
        self._commit("ClaimRegistered", actor, {"claim_id": claim_id, "actor": actor, "content": content, "epistemic_type": epistemic_type.value, "derived_from": derived_from, "source_refs": source_refs})
        return ClaimHandle(claim_id)

    def dispute_claim(self, actor: str, claim_id: str, alternative: str) -> RelationalEvent:
        self._participant(actor)
        text_field(claim_id, "claim_id")
        return self._commit("ClaimDisputed", actor, {"claim_id": claim_id, "alternative": alternative})

    def check_lifecycle_transition(self, to: LifecycleState) -> GovernanceDecision:
        enum_field(to, LifecycleState, "lifecycle")
        return self._governance.require_lifecycle_transition(self.state, to)

    def transition(self, actor: str, to: LifecycleState) -> RelationalEvent:
        self._participant(actor)
        enum_field(to, LifecycleState, "lifecycle")
        self._require_lifecycle_authority(actor, operation="transition")
        from_state = self.state.lifecycle
        decision = self.check_lifecycle_transition(to)
        self.record_governance_decision(decision, operation="transition", actor=actor, **{"from": from_state.value, "to": to.value})
        if decision.outcome is not GovernanceOutcome.ALLOW:
            raise LifecycleTransitionError(decision.reason)
        return self._commit("LifecycleTransitioned", actor, {"from": from_state.value, "to": to.value})

    def require_consent(self, actor: str, scope: str, purpose: str | None = None, *, satisfied_conditions: tuple[str, ...] = ()) -> GovernanceDecision:
        baseline = GovernanceEngine().require_active_consent(self.state, actor, scope, purpose=purpose, satisfied_conditions=satisfied_conditions)
        if baseline.outcome is not GovernanceOutcome.ALLOW:
            return baseline
        return self._governance.require_active_consent(
            self.state,
            actor,
            scope,
            purpose=purpose,
            satisfied_conditions=satisfied_conditions,
        )

    def record_invocation_proposed(self, request) -> RelationalEvent:
        action_digest = hashlib.sha256(request.action.encode("utf-8")).hexdigest()
        return self._commit("InvocationProposed", request.requested_by, {
            "request_id": request.request_id,
            "action_digest": action_digest,
            "action_ref": request.action_ref,
            "target": request.target,
            "context_resources": list(request.context_resources),
            "requirements": [{"resource": item.resource, "capability": item.capability.value, "purpose": item.purpose, "satisfied_conditions": list(item.satisfied_conditions)} for item in request.requirements],
            "consent_requirements": [{"actor": item.actor, "scope": item.scope, "purpose": item.purpose, "satisfied_conditions": list(item.satisfied_conditions)} for item in request.consent_requirements],
        })

    def record_invocation_resolution(self, actor: str, request_id: str, status: str, *, reason: str) -> RelationalEvent:
        return self._commit("InvocationResolved", "tria:governance", {"request_id": request_id, "requested_by": actor, "status": status, "reason": reason})

    def record_invocation_result(self, result) -> RelationalEvent:
        return self._commit("InvocationResultRecorded", result.produced_by, {"request_id": result.request_id, "status": result.status, "output_ref": result.output_ref})

    def audit(self) -> dict:
        events = self.events
        last_event_id = events[-1].event_id if events else None
        return {
            "relationship_id": self.relationship_id,
            "event_count": len(events),
            "hashes_valid": all(e.verify_hash() for e in events),
            "chain_valid": verify_event_chain(events),
            "last_event_id": last_event_id,
            "reconstructable": bool(events) and self.state.last_event_id == last_event_id,
            "relationship_valid": self.state.history_valid,
        }


class Tria:
    def __init__(self, store: EventStore | None = None) -> None:
        self.store = store or InMemoryEventStore()

    def create_relationship(self, participants: list[str]) -> Relationship:
        if not isinstance(participants, (list, tuple)) or not participants:
            raise InputValidationError("participants must be a non-empty list of unique actor identifiers.")
        for actor in participants:
            text_field(actor, "participant")
            if actor.startswith("tria:"):
                raise InputValidationError("tria: identifiers are reserved for host system attribution.")
        if len(set(participants)) != len(participants):
            raise InputValidationError("participants must not contain duplicates.")
        relationship_id = str(uuid4())
        rel = Relationship(relationship_id, self.store)
        rel._commit("RelationshipCreated", "tria:system", {"participants": participants})
        return rel

    def load_relationship(self, relationship_id: str) -> Relationship:
        text_field(relationship_id, "relationship_id")
        if not self.store.list(relationship_id):
            raise RelationshipNotFoundError("Relationship not found; use its persisted identifier or explicitly create a relationship.")
        return Relationship(relationship_id, self.store)

    def restore_relationship(self, bundle) -> Relationship:
        from .portable import import_replay_bundle
        relationship_id = import_replay_bundle(self.store, bundle)
        return Relationship(relationship_id, self.store)


class HostAdministration:
    """Host-held administrative capability. Attribution strings are not credentials.

    Only authenticated, authorized host code may retain this object. Give agents
    narrow request/delegation endpoints, never Relationship or this capability.
    """
    def __init__(self, relationship: Relationship):
        self._relationship = relationship

    def grant_permission(self, granted_by: str, grantee: str, resource: str, capability: Capability, **bounds):
        return self._relationship.grant_permission(granted_by, grantee, resource, capability, **bounds)

    def revoke_permission(self, actor: str, grantee: str, resource: str, capability: Capability, **causality):
        return self._relationship.revoke_permission(actor, grantee, resource, capability, **causality)
