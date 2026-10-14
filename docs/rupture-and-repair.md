# Rupture and repair records

TRIA now exposes an additive append-only grammar for recording relational rupture and repair.

This does not replace consent, re-consent, lifecycle, claim dispute, correction, or covenant mechanisms.

## Invariants

1. A rupture assertion does not establish blame or objective truth.
2. A repair offer does not create an obligation to accept.
3. A declined repair does not imply hostility or renewed consent.
4. A repair outcome MUST separately record:
   - what was restored;
   - what remains changed;
   - what remains unresolved.
5. Repair never silently restores permissions, authority, consent, or lifecycle state.
6. Repair does not require continuation; transformation or dissolution remain legitimate.

## Events

`RuptureRecorded`

Records the participant-attributed rupture description and scope.

`RepairOffered`

Records a bounded set of proposed repair actions and causally references the rupture event.

`RepairResponded`

Records acceptance, partial acceptance, decline, hold, or unresolved response. Accepted and declined actions must be drawn from the offered set.

`RepairOutcomeRecorded`

Records effects of an accepted or partially accepted repair. The event explicitly separates restoration from persistent change.

## Example

```python
import tria
from tria.repair import RepairResponseStatus, RuptureStatus

system = tria.Tria()
rel = system.create_relationship(["human", "agent"])

rupture = rel.record_rupture(
    "human",
    affected_scope=("scheduling", "personalization"),
    expectation_or_boundary="Current explicit instruction supersedes stale inference.",
    observed_impact="An unwanted scheduling action occurred.",
    status=RuptureStatus.ACKNOWLEDGED,
)

offer = rel.offer_repair(
    "agent",
    rupture.payload["rupture_id"],
    offered_actions=(
        "correct scheduling state",
        "disable stale inference",
        "require re-consent before persistent scheduling",
    ),
)

rel.respond_to_repair(
    "human",
    offer.payload["repair_id"],
    RepairResponseStatus.PARTIALLY_ACCEPTED,
    accepted_actions=("correct scheduling state", "disable stale inference"),
    declined_actions=("require re-consent before persistent scheduling",),
)

rel.record_repair_outcome(
    "agent",
    offer.payload["repair_id"],
    restored=("current scheduling state",),
    remains_changed=("future scheduling authority remains narrower",),
    unresolved=("whether retained context should be intentionally released",),
)
```

A valid repair record does not imply that trust returned to its prior state.
