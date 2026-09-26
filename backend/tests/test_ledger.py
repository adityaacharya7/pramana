from sqlalchemy import delete

from pramana import ledger
from pramana.models import LedgerEntry

from .conftest import entries, login


def activity(client, db):
    headers = login(client, db, "io.mum")
    client.post("/cases/C-1/evidence", headers=headers, files={"file": ("a.txt", b"first")})
    client.post("/cases/C-1/evidence", headers=headers, files={"file": ("b.txt", b"second")})
    client.get("/cases/C-2", headers=headers)


def test_chain_verifies_after_normal_activity(client, world):
    activity(client, world)
    report = client.get("/ledger/verify", headers=login(client, world, "auditor")).json()
    assert report["ok"] is True and report["first_bad_seq"] is None
    assert report["entries"] == len(entries(world)) - 1  # the verify itself is logged after the check


def test_edited_entry_is_detected_at_its_sequence_number(client, world):
    """FX-12."""
    activity(client, world)
    target = entries(world, "EVIDENCE_UPLOADED")[0]
    target.payload = target.payload.replace('"a.txt"', '"innocent.txt"')
    world.commit()
    report = ledger.verify(world)
    assert report["ok"] is False and report["first_bad_seq"] == target.seq


def test_edited_actor_is_detected(client, world):
    activity(client, world)
    target = entries(world, "ACCESS_REFUSED")[0]
    target.actor = "someone.else"
    world.commit()
    assert ledger.verify(world)["first_bad_seq"] == target.seq


def test_deleted_entry_is_detected(client, world):
    activity(client, world)
    victim = entries(world, "EVIDENCE_UPLOADED")[1]
    world.execute(delete(LedgerEntry).where(LedgerEntry.seq == victim.seq))
    world.commit()
    report = ledger.verify(world)
    assert report["ok"] is False and "gap" in report["reason"]


def test_case_reference_outside_the_hash_cannot_be_moved(client, world):
    activity(client, world)
    target = entries(world, "ACCESS_REFUSED")[0]
    target.case_id = "C-1"
    world.commit()
    assert ledger.verify(world)["first_bad_seq"] == target.seq


def test_fully_recomputed_chain_is_not_caught_without_a_checkpoint(client, world):
    """Honest limit: rewriting an entry and recomputing every later hash
    passes an internal check. The report must say so rather than imply
    otherwise; signed checkpoints (F14) are what catch this (FX-23)."""
    activity(client, world)
    rows = entries(world)
    rows[1].payload = rows[1].payload.replace("io.mum", "io.xxx")
    prev = rows[0].hash
    for e in rows[1:]:
        e.payload_hash = ledger.sha256_hex(e.payload)
        e.prev_hash = prev
        e.hash = ledger.entry_hash(prev, e.seq, e.ts, e.actor, e.action, e.payload_hash)
        prev = e.hash
    world.commit()
    report = ledger.verify(world)
    assert report["ok"] is True
    assert report["latest_trusted_checkpoint"] is None
    assert "checkpoint" in report["limitation"]


def test_append_outside_a_transaction_is_refused(world):
    try:
        ledger.append(world, actor="x", action="Y")
    except RuntimeError:
        return
    raise AssertionError("append without the ledger lock should fail")
