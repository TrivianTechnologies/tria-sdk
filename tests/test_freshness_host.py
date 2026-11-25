from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from syzygy_freshness import Domain, Verifier, fingerprint
from tria import (
    Capability,
    CapabilityRequirement,
    InvocationRequest,
    SQLiteEventStore,
    Tria,
)
from tria.freshness import Authority, Receiver

SUBJECT = fingerprint(["independently sourced evidence", "p1"])
OTHER = fingerprint(["independently sourced evidence", "p2"])


class Setup:
    def __init__(self, tmp):
        self.path = tmp / "primary.sqlite"
        self.store = SQLiteEventStore(self.path)
        self.rel = Tria(self.store).create_relationship(["owner", "parent", "child"])
        self.rel.admin.grant_permission("owner", "parent", "item", Capability.READ)
        self.rel.admin.grant_permission("owner", "parent", "item", Capability.DELEGATE)
        self.rel.delegate_permission("parent", "child", "item", Capability.READ)
        self.rel.admin.grant_permission("owner", "child", "inbox-item", Capability.ACT)
        self.req = InvocationRequest(
            "child",
            "record digest",
            "inbox-item",
            requirements=(
                CapabilityRequirement("inbox-item", Capability.ACT),
                CapabilityRequirement("item", Capability.READ),
            ),
        )
        self.key = Ed25519PrivateKey.generate()
        self.domain = Domain(
            "owner", "generation-1", self.rel.relationship_id, "receiver-a"
        )
        self.genesis = self.rel.events[0].event_hash
        self.a = Authority(self.rel, self.domain, self.key, self.genesis, enroll=True)
        self.root = self.a.cursor()
        self.v = Verifier(
            tmp / "floor.sqlite",
            self.domain,
            self.key.public_key(),
            self.root,
            enroll=True,
        )
        self.r = Receiver(self.path, self.domain, self.key.public_key(), self.genesis)

    def observe(self, subject=SUBJECT):
        return self.v.observe(subject, self.a.answer)

    def publish(self, subject=SUBJECT):
        return self.a.publish(subject, expected=self.a.cursor())

    def revoke(self):
        self.rel.admin.revoke_permission("owner", "parent", "item", Capability.READ)

    def count(self):
        with self.r.transaction() as db:
            return db.execute("SELECT COUNT(*) FROM fresh_inbox").fetchone()[0]


@pytest.fixture
def env(tmp_path):
    s = Setup(tmp_path)
    yield s
    s.store.close()


def test_authoritative_commit_closes_publication_gap(env):
    e = env
    assert e.observe().reason == "unpublished"
    before = e.publish()
    assert e.observe().status == "current_at_check"
    assert e.a.offer(e.req, SUBJECT) == "offered"
    e.revoke()
    assert e.observe().status == "stale"  # no intervening publish
    assert e.r.admit(e.req) == "fenced" and e.count() == 0
    with pytest.raises(ValueError, match="compare-and-swap"):
        e.a.publish(SUBJECT, expected=before)
    e.publish(OTHER)
    assert e.observe(OTHER).status == "current_at_check"
    assert e.a.offer(replace(e.req, request_id="next"), OTHER) == "governance_withheld"


def test_missing_offer_and_idempotent_reconciliation(env):
    e = env
    assert e.r.admit(e.req) == "no_matching_offer"
    assert e.a.offer(e.req, SUBJECT) == "freshness_unverified"
    e.publish()
    assert e.a.offer(e.req, SUBJECT) == "offered"
    assert e.a.offer(e.req, SUBJECT) == "already_offered"
    assert e.r.admit(replace(e.req, action="different")) == "no_matching_offer"
    assert e.r.admit(e.req) == "admitted"
    e.revoke()
    assert e.r.admit(e.req) == "already_admitted"
    assert e.r.admit(replace(e.req, action="different")) == "conflict"
    assert e.count() == 1


def test_policy_only_change_and_source_cas(env):
    e = env
    p = e.publish()
    assert e.a.offer(e.req, SUBJECT) == "offered"
    later = e.publish(OTHER)
    assert later.revision == p.revision and later.publication == p.publication + 1
    assert e.observe().status == "stale" and e.r.admit(e.req) == "fenced"
    with pytest.raises(ValueError):
        e.a.publish(SUBJECT, expected=p)


def test_signed_source_compares_both_ancestries(env, tmp_path):
    e = env
    p = e.publish()
    for i, cursor in enumerate(
        (replace(p, head="f" * 64), replace(p, publication_hash="d" * 64))
    ):
        v = Verifier(
            tmp_path / f"fork{i}", e.domain, e.key.public_key(), cursor, enroll=True
        )
        assert v.observe(SUBJECT, e.a.answer).reason == "history_conflict"


@pytest.mark.parametrize(
    "end", [("boot", 1010), ("different-boot", 1005), ("boot", 999)]
)
def test_expired_reboot_and_clock_regression(env, monkeypatch, end):
    e = env
    tick = [("boot", 1000)]
    monkeypatch.setattr("tria.freshness._boot_clock", lambda: tick[0])
    e.publish()
    assert e.a.offer(e.req, SUBJECT, ttl_ms=10) == "offered"
    tick[0] = end
    assert e.r.admit(e.req) == "expired" and e.count() == 0


def test_restart_reopens_same_source_and_floor(env):
    e = env
    e.publish()
    assert e.a.offer(e.req, SUBJECT) == "offered"
    e.store.close()
    e.store = SQLiteEventStore(e.path)
    rel = Tria(e.store).load_relationship(e.domain.relationship)
    a = Authority(rel, e.domain, e.key, e.genesis)
    assert e.v.observe(SUBJECT, a.answer).status == "current_at_check"
    assert e.r.admit(e.req) == "admitted"
    with pytest.raises(ValueError):
        Authority(rel, e.domain, Ed25519PrivateKey.generate(), e.genesis)


def test_receiver_requires_live_primary(env, tmp_path):
    e = env
    offline = Receiver(
        tmp_path / "missing.sqlite", e.domain, e.key.public_key(), e.genesis
    )
    assert offline.admit(e.req) == "unconfirmed"
    assert not (tmp_path / "missing.sqlite").exists()


def test_source_does_not_silently_enroll_replacement_epoch(env):
    e = env
    with pytest.raises(ValueError):
        Authority(
            e.rel, replace(e.domain, epoch="replacement"), e.key, e.genesis, enroll=True
        )


def test_handoff_requires_explicit_target_authority(env):
    with pytest.raises(ValueError, match="ACT"):
        env.a.offer(replace(env.req, requirements=()), SUBJECT)


def test_time_bound_governance_is_rechecked_without_a_new_event(env, monkeypatch):
    import tria.governance as governance

    e = env
    now = datetime.now(timezone.utc)
    e.rel.admin.grant_permission(
        "owner",
        "child",
        "deadline",
        Capability.ACT,
        expires_at=now + timedelta(minutes=1),
    )
    r = replace(
        e.req,
        target="deadline",
        requirements=(CapabilityRequirement("deadline", Capability.ACT),),
    )
    e.publish()
    assert e.a.offer(r, SUBJECT) == "offered"
    monkeypatch.setattr(governance, "utcnow", lambda: now + timedelta(minutes=2))
    assert e.r.admit(r) == "governance_withheld"
    assert e.count() == 0


def test_unknown_evidence_and_external_conditions_remain_unverified(env):
    e = env
    e.publish()
    assert e.observe(OTHER).reason == "unpublished"
    conditioned = replace(
        e.req,
        requirements=(
            CapabilityRequirement(
                "inbox-item", Capability.ACT, satisfied_conditions=("external-review",)
            ),
        ),
    )
    with pytest.raises(ValueError, match="external condition"):
        e.a.offer(conditioned, SUBJECT)
    assert e.count() == 0
