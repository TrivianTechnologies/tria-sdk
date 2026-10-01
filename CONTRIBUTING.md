# Contributing to TRIA SDK

TRIA SDK is research infrastructure for governed relational state. Contributions should preserve the current operational invariants in `docs/TRIA_OPERATIONAL_SPEC_v0.1.3.md` and `docs/agentic-alignment-contract.md`; the conceptual core specification remains historical context.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

## Contribution principles

- Preserve immutable event history; corrections are new events.
- Keep current state derivable from committed events.
- Do not introduce provider-specific concepts into `tria.core`.
- Do not promote interpretation into observation or shared claim without admissible provenance and authority.
- Keep governance decisions inspectable and versioned.
- Prefer small, falsifiable changes with tests.

Open an issue before introducing new core event types, lifecycle states, or governance semantics.
