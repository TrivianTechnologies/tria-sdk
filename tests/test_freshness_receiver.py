"""Independent receiver processes and bounded loopback transport fault controls."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
import multiprocessing as mp
import socket

import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from tria import Capability, CapabilityRequirement, InvocationRequest
from tria.freshness import Receiver
from test_freshness_host import SUBJECT, Setup


def _request(op):
    return InvocationRequest(
        "child",
        "record digest",
        "inbox-item",
        request_id=op,
        requirements=(
            CapabilityRequirement("inbox-item", Capability.ACT),
            CapabilityRequirement("item", Capability.READ),
        ),
    )


def _serve(path, domain, key, genesis, ready, gate):
    receiver = Receiver(path, domain, Ed25519PublicKey.from_public_bytes(key), genesis)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        ready.send(listener.getsockname())
        ready.close()
        while True:
            conn, _ = listener.accept()
            with conn, conn.makefile("rb") as reader:
                conn.settimeout(5)
                mode, op = reader.readline(256).decode().strip().split(" ", 1)
                if mode == "quit":
                    return
                if mode == "delayed":
                    conn.sendall(b"received\n")
                    if not gate.wait(6):
                        return
                outcome = receiver.admit(_request(op))
                if mode != "lose_ack":
                    conn.sendall(outcome.encode() + b"\n")


@contextmanager
def server(e):
    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    gate = ctx.Event()
    key = e.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    proc = ctx.Process(
        target=_serve, args=(e.path, e.domain, key, e.genesis, child, gate)
    )
    proc.start()
    child.close()
    try:
        assert parent.poll(8)
        address = parent.recv()
        yield address, gate
    finally:
        gate.set()
        if proc.is_alive() and "address" in locals():
            with socket.create_connection(address, timeout=2) as client:
                client.sendall(b"quit end\n")
        proc.join(8)
        if proc.is_alive():
            proc.terminate()
            proc.join(3)
        parent.close()
        assert proc.exitcode == 0


def call(address, mode, op):
    with (
        socket.create_connection(address, timeout=3) as conn,
        conn.makefile("rb") as reader,
    ):
        conn.sendall(f"{mode} {op}\n".encode())
        return reader.readline(128).decode().strip()


def test_delayed_receiver_admission_and_ack_loss_across_restart(tmp_path):
    e = Setup(tmp_path)
    try:
        e.publish()
        for op in ("early", "late", "offline"):
            assert e.a.offer(_request(op), SUBJECT, ttl_ms=30000) == "offered"
        with server(e) as (one, _), server(e) as (two, gate):
            assert call(one, "lose_ack", "early") == ""  # committed, response lost
            with (
                socket.create_connection(two, timeout=3) as conn,
                conn.makefile("rb") as r,
            ):
                conn.sendall(b"delayed late\n")
                assert r.readline() == b"received\n"
                e.revoke()
                assert e.observe().status == "stale"
                gate.set()
                assert r.readline() == b"fenced\n"
        # With both endpoints gone the client cannot convert an old offer into
        # admission. A fresh endpoint reconciles the previously lost reply.
        with pytest.raises(OSError):
            call(two, "retry", "offline")
        # Requests buffered through a partition and retried at a new process.
        with server(e) as (new, _):
            assert call(new, "retry", "early") == "already_admitted"
            assert call(new, "retry", "offline") == "fenced"
        assert e.count() == 1
    finally:
        e.store.close()


def test_competing_receivers_and_source_have_one_durable_order(tmp_path):
    e = Setup(tmp_path)
    try:
        with e.r.transaction(write=True) as db:
            db.execute(
                "CREATE TABLE ordering(seq INTEGER PRIMARY KEY, kind TEXT, op TEXT)"
            )
            db.execute("""CREATE TRIGGER track_inbox AFTER INSERT ON fresh_inbox BEGIN
                       INSERT INTO ordering(kind,op) VALUES('admit',NEW.op); END""")
            db.execute("""CREATE TRIGGER track_revoke AFTER INSERT ON events
                       WHEN json_extract(NEW.event_json,'$.event_type')='PermissionRevoked' BEGIN
                       INSERT INTO ordering(kind,op) VALUES('revoke',''); END""")
        e.publish()
        for op in ("early", "duplicate", *(f"race-{n}" for n in range(6))):
            assert e.a.offer(_request(op), SUBJECT, ttl_ms=30000) == "offered"
        with (
            server(e) as (one, _),
            server(e) as (two, _),
            ThreadPoolExecutor(10) as pool,
        ):
            assert call(one, "admit", "early") == "admitted"
            futures = [pool.submit(call, a, "admit", "duplicate") for a in (one, two)]
            assert sorted(f.result() for f in futures) == [
                "admitted",
                "already_admitted",
            ]
            futures = [
                pool.submit(call, (one, two)[n % 2], "admit", f"race-{n}")
                for n in range(6)
            ]
            e.revoke()
            answers = [f.result() for f in futures]
        with e.r.transaction() as db:
            trace = db.execute("SELECT kind,op FROM ordering ORDER BY seq").fetchall()
        cut = trace.index(("revoke", ""))
        assert trace[cut + 1 :] == []
        assert sorted(op for kind, op in trace[:cut]) == sorted(
            ["early", "duplicate"]
            + [f"race-{n}" for n, result in enumerate(answers) if result == "admitted"]
        )
        assert set(answers) <= {"admitted", "fenced"}
    finally:
        e.store.close()
