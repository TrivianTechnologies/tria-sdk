"""Opt-in single-primary freshness and digest-only receiver admission (MPL-2.0)."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import closing, contextmanager
from dataclasses import fields
import json
from pathlib import Path
import sqlite3
import time

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from syzygy_freshness import Cursor, Domain, Query, ZERO, fingerprint, reply

from .core import Relationship
from .events import RelationalEvent, verify_event_chain
from .execution import ExecutionBridge
from .governance import GovernanceEngine
from .providers.base import ProviderRequest, ProviderResponse
from .runtime import InvocationRequest, Runtime
from .store import SQLiteEventStore
from .types import Capability

# Only these audit events can be emitted during an ordinary bridge handoff.
# Every other event, including future unrecognized events, advances the fence.
_AUDIT = frozenset(
    {
        "InvocationProposed",
        "InvocationResolved",
        "InvocationExecutionReserved",
        "InvocationResultRecorded",
        "GovernanceEvaluated",
    }
)


def _digest(value):
    if (
        type(value) is not str
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("expected lowercase SHA-256 digest")
    return value


def _boot_clock():
    # BOOTTIME includes suspend; a changed boot ID invalidates persisted offers.
    return (
        Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        time.clock_gettime_ns(time.CLOCK_BOOTTIME) // 1_000_000,
    )


def _json_metadata(value):
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) in (list, tuple):
        return [_json_metadata(item) for item in value]
    if isinstance(value, Mapping) and all(type(k) is str for k in value):
        return {k: _json_metadata(v) for k, v in value.items()}
    raise ValueError(
        "inbox metadata requires JSON strings, integers, booleans, arrays or objects"
    )


def _request_hash(request):
    def row(value):
        return [getattr(value, f.name) for f in fields(value)]

    if request.action_ref is not None and type(request.action_ref) is not str:
        raise ValueError("action_ref must be a string or None")
    raw = _json_metadata(request.metadata)
    metadata = json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return fingerprint(
        [
            "tria.inbox-request/1",
            request.request_id,
            request.requested_by,
            request.action,
            request.target,
            request.action_ref,
            list(request.context_resources),
            [row(r) for r in request.requirements],
            [row(c) for c in request.consent_requirements],
            metadata,
        ]
    )


class _History:
    def __init__(self, events):
        self.events = events

    def list(self, relationship_id):
        return list(self.events)


class _View:
    def __init__(self, db, domain, stream):
        rows = db.execute(
            "SELECT commit_index,event_json FROM events WHERE relationship_id=? ORDER BY commit_index",
            (domain.relationship,),
        ).fetchall()
        events = [RelationalEvent.from_dict(json.loads(raw)) for _, raw in rows]
        if not events or not verify_event_chain(events):
            raise ValueError("invalid authoritative history")
        self.relationship = Relationship(domain.relationship, _History(events))
        self.relationship.require_valid()
        self.material = {
            index: (event.event_id, event.event_hash)
            for (index, _), event in zip(rows, events)
            if event.event_type not in _AUDIT
        }
        self.genesis = events[0].event_hash
        revision = max(self.material)
        last = db.execute(
            "SELECT generation,publication_hash,source_rev,source_head,subject FROM "
            "fresh_publications WHERE stream=? ORDER BY generation DESC LIMIT 1",
            (stream,),
        ).fetchone()
        self.db, self.stream = db, stream
        self.last = last
        self.cursor = Cursor(
            revision,
            *self.material[revision],
            last[0] if last else 0,
            last[1] if last else ZERO,
        )

    def status(self, subject):
        if self.last is None:
            return "unpublished"
        if (self.last[2], self.last[3], self.last[4]) == (
            self.cursor.revision,
            self.cursor.head,
            subject,
        ):
            return "current"
        known = self.db.execute(
            "SELECT 1 FROM fresh_publications WHERE stream=? AND subject=? LIMIT 1",
            (self.stream, subject),
        ).fetchone()
        return "stale" if known else "unpublished"


class _Primary:
    """The source and receiver must open the same canonical, local filesystem database."""

    def __init__(self, path, domain, key, genesis):
        self.uri = Path(path).resolve().as_uri() + "?mode=rw"
        self.domain, self.genesis = domain, _digest(genesis)
        self.stream = fingerprint(domain.wire())
        self.key_id = fingerprint(
            key.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
        )

    @contextmanager
    def transaction(self, *, write=False):
        with closing(
            sqlite3.connect(self.uri, uri=True, timeout=2, isolation_level=None)
        ) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield db
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    def view(self, db):
        enrolled = db.execute(
            "SELECT key_id,genesis FROM fresh_domains WHERE stream=?", (self.stream,)
        ).fetchone()
        if enrolled != (self.key_id, self.genesis):
            raise ValueError("wrong authority database or enrollment")
        view = _View(db, self.domain, self.stream)
        if view.genesis != self.genesis:
            raise ValueError("source root mismatch")
        return view


class _DigestAdapter:
    def translate(self, plan, *, model):
        return ProviderRequest(
            "tria-inbox",
            plan.request.request_id,
            {"request": _request_hash(plan.request)},
        )

    def normalize_response(self, request_id, response):
        return ProviderResponse(
            "tria-inbox", request_id, "COMPLETED", output_ref=response
        )


_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS fresh_domains(stream TEXT PRIMARY KEY, key_id TEXT NOT NULL, genesis TEXT NOT NULL, relationship TEXT, scope TEXT, UNIQUE(relationship,scope))",
    "CREATE TABLE IF NOT EXISTS fresh_publications(stream TEXT, generation INTEGER, publication_hash TEXT NOT NULL,"
    " source_rev INTEGER, source_head TEXT, subject TEXT, PRIMARY KEY(stream,generation))",
    "CREATE TABLE IF NOT EXISTS fresh_offers(stream TEXT, op TEXT, request_hash TEXT, subject TEXT,"
    " source_rev INTEGER, source_head TEXT, publication_hash TEXT, boot TEXT, issued INTEGER, expires INTEGER, PRIMARY KEY(stream,op))",
    "CREATE TABLE IF NOT EXISTS fresh_inbox(stream TEXT, op TEXT, request_hash TEXT, source_rev INTEGER,"
    " source_head TEXT, PRIMARY KEY(stream,op))",
)


class Authority(_Primary):
    """Trusted host facade over the real SQLite source. Publish with an exact prior cursor."""

    def __init__(self, relationship, domain, private_key, genesis, *, enroll=False):
        if (
            type(relationship) is not Relationship
            or type(relationship._store) is not SQLiteEventStore
            or type(relationship._governance) is not GovernanceEngine
            or relationship._store.path == ":memory:"
            or relationship.relationship_id != domain.relationship
        ):
            raise ValueError(
                "requires the enrolled file-backed relationship and standard governance engine"
            )
        self.relationship, self.private_key = relationship, private_key
        super().__init__(
            relationship._store.path, domain, private_key.public_key(), genesis
        )
        with relationship.execution_guard(), self.transaction(write=enroll) as db:
            if enroll:
                for statement in _SCHEMA:
                    db.execute(statement)
                db.execute(
                    "INSERT OR IGNORE INTO fresh_domains VALUES(?,?,?,?,?)",
                    (
                        self.stream,
                        self.key_id,
                        self.genesis,
                        domain.relationship,
                        domain.scope,
                    ),
                )
            self.view(db)

    def cursor(self):
        with self.transaction() as db:
            return self.view(db).cursor

    def publish(self, subject, *, expected):
        """Host attests to evidence collected at expected. Stale observations cannot be silently rebound."""
        _digest(subject)
        with self.transaction(write=True) as db:
            view = self.view(db)
            prior = view.cursor
            if prior != expected:
                raise ValueError("publication compare-and-swap failed")
            gen = prior.publication + 1
            h = fingerprint(
                ["tria.publication/1", self.stream, prior.wire(), gen, subject]
            )
            db.execute(
                "INSERT INTO fresh_publications VALUES(?,?,?,?,?,?)",
                (self.stream, gen, h, prior.revision, prior.head, subject),
            )
            return Cursor(prior.revision, prior.event_id, prior.head, gen, h)

    def answer(self, query):
        if type(query) is not Query or query.domain != self.domain:
            raise ValueError("unexpected authority or scope")
        with self.transaction() as db:
            view = self.view(db)
            floor = query.floor
            known_source = view.material.get(floor.revision) == (
                floor.event_id,
                floor.head,
            )
            known_publication = (
                floor.publication == 0
                or db.execute(
                    "SELECT 1 FROM fresh_publications WHERE stream=? AND generation=? AND publication_hash=?",
                    (self.stream, floor.publication, floor.publication_hash),
                ).fetchone()
                is not None
            )
            status = (
                view.status(query.subject)
                if known_source and known_publication
                else "conflict"
            )
            return reply(self.private_key, query, view.cursor, status)

    def offer(self, request, subject, *, ttl_ms=5000):
        """Trusted endpoint constructs requirements. This bridge only stages a digest for one enrolled inbox."""
        if type(request) is not InvocationRequest or not any(
            r.resource == request.target and r.capability is Capability.ACT
            for r in request.requirements
        ):
            raise ValueError("inbox request requires explicit ACT on its target")
        if any(
            check.satisfied_conditions
            for check in (*request.requirements, *request.consent_requirements)
        ):
            raise ValueError(
                "external condition attestations require a separate live admission profile"
            )
        if any(not ref.startswith("claim:") for ref in request.context_resources):
            raise ValueError(
                "external resource resolvers are outside the digest inbox profile"
            )
        _digest(subject)
        if type(ttl_ms) is not int or not 0 < ttl_ms <= 30000:
            raise ValueError("offer lifetime must be 1 to 30000 ms")
        op = request.request_id
        request_hash = _request_hash(request)
        with self.relationship.execution_guard():
            with self.transaction() as db:
                view = self.view(db)
                old = db.execute(
                    "SELECT request_hash,subject FROM fresh_offers WHERE stream=? AND op=?",
                    (self.stream, op),
                ).fetchone()
                if old:
                    return (
                        "already_offered"
                        if old == (request_hash, subject)
                        else "conflict"
                    )
                if view.status(subject) != "current":
                    return "freshness_unverified"
                expected = view.cursor

            def stage(wire):
                with self.transaction(write=True) as db:
                    latest = self.view(db)
                    if latest.cursor != expected or latest.status(subject) != "current":
                        return "freshness_unverified"
                    boot, issued = _boot_clock()
                    db.execute(
                        "INSERT INTO fresh_offers VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (
                            self.stream,
                            op,
                            wire.payload["request"],
                            subject,
                            expected.revision,
                            expected.head,
                            expected.publication_hash,
                            boot,
                            issued,
                            issued + ttl_ms,
                        ),
                    )
                    return "offered"

            receipt = ExecutionBridge().execute(
                self.relationship, request, _DigestAdapter(), stage, model="inbox"
            )
            return (
                receipt.result.output_ref if receipt.executed else "governance_withheld"
            )


class Receiver(_Primary):
    """Independent receiver process. Accepted effect is exactly one durable inbox row."""

    def admit(self, request):
        if type(request) is not InvocationRequest:
            raise ValueError("expected exact invocation request")
        identity = _request_hash(request)
        op = request.request_id
        try:
            with self.transaction(write=True) as db:
                view = self.view(db)
                old = db.execute(
                    "SELECT request_hash FROM fresh_inbox WHERE stream=? AND op=?",
                    (self.stream, op),
                ).fetchone()
                if old:
                    return "already_admitted" if old == (identity,) else "conflict"
                offer = db.execute(
                    "SELECT request_hash,subject,source_rev,source_head,publication_hash,boot,issued,expires FROM "
                    "fresh_offers WHERE stream=? AND op=?",
                    (self.stream, op),
                ).fetchone()
                if not offer or offer[0] != identity:
                    return "no_matching_offer"
                point = view.cursor
                if (
                    offer[2:5] != (point.revision, point.head, point.publication_hash)
                    or view.status(offer[1]) != "current"
                ):
                    return "fenced"
                # Re-evaluate actual TRIA floors, including wall-time expiry, inside
                # the transaction that orders admission against every primary write.
                if not Runtime.evaluate(view.relationship, request).allowed:
                    return "governance_withheld"
                boot, now = _boot_clock()
                if boot != offer[5] or not offer[6] <= now < offer[7]:
                    return "expired"
                db.execute(
                    "INSERT INTO fresh_inbox VALUES(?,?,?,?,?)",
                    (self.stream, op, identity, point.revision, point.head),
                )
                return "admitted"
        except (OSError, AttributeError, sqlite3.Error):
            # A lost commit acknowledgement requires reconciliation of the same ID.
            return "unconfirmed"
