"""F14: signed checkpoints kept outside the database (FX-12, FX-23, FX-24, FX-30)."""
from sqlalchemy import delete

from pramana import checkpoints, ledger
from pramana.models import LedgerEntry

from .conftest import entries


def fill(db, n):
    for i in range(n):
        ledger.record(db, actor="t", action="TEST", payload={"i": i})


def recompute_from(db, rows, start_index):
    prev = rows[start_index - 1].hash if start_index else ledger.GENESIS
    for e in rows[start_index:]:
        e.payload_hash = ledger.sha256_hex(e.payload)
        e.prev_hash = prev
        e.hash = ledger.entry_hash(prev, e.seq, e.ts, e.actor, e.action, e.payload_hash)
        prev = e.hash
    db.commit()


def test_checkpoint_taken_every_50_entries(app, db):
    fill(db, 55)
    cp = checkpoints.latest_retained(checkpoints.keyring_for(app.state.settings))
    assert cp and cp["seq"] == 50
    report = ledger.verify(db, checkpoints.keyring_for(app.state.settings))
    assert report["ok"] and report["latest_trusted_checkpoint"]["seq"] == 50
    assert report["entries_after_checkpoint"] == 5


def test_fully_recomputed_chain_fails_against_the_checkpoint(app, db):
    """FX-23: the internal check passes, the retained checkpoint does not."""
    fill(db, 55)
    rows = entries(db)
    rows[10].payload = rows[10].payload.replace('"i":10', '"i":999')
    assert '"i":999' in rows[10].payload
    recompute_from(db, rows, 10)
    assert ledger.verify(db)["ok"]  # chain alone: fooled
    report = ledger.verify(db, checkpoints.keyring_for(app.state.settings))
    assert not report["ok"] and "#50" in report["reason"]


def test_rollback_is_detected(app, db):
    """FX-24: the database restored to a state before the checkpoint."""
    fill(db, 55)
    db.execute(delete(LedgerEntry).where(LedgerEntry.seq > 40))
    db.commit()
    report = ledger.verify(db, checkpoints.keyring_for(app.state.settings))
    assert not report["ok"] and "Rollback" in report["reason"]


def test_tampering_after_the_checkpoint_is_outside_the_guarantee(app, db):
    """FX-30: rewrite only entries after the checkpoint - reported as outside
    the guaranteed region, with their count; the region before is intact."""
    fill(db, 55)
    rows = entries(db)
    rows[52].payload = rows[52].payload.replace('"i":52', '"i":1000')
    recompute_from(db, rows, 52)
    report = ledger.verify(db, checkpoints.keyring_for(app.state.settings))
    assert report["ok"] and report["entries_after_checkpoint"] == 5
    assert "outside the guaranteed region" in report["limitation"]


def test_forged_checkpoint_is_rejected(app, db):
    fill(db, 55)
    cp = checkpoints.latest_retained(checkpoints.keyring_for(app.state.settings))
    forged = {**cp, "head_hash": "0" * 64}
    report = ledger.verify(db, checkpoints.keyring_for(app.state.settings), checkpoint=forged)
    assert not report["ok"] and "signature" in report["reason"]
