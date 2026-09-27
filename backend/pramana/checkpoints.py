"""Signed checkpoints for the audit log (F14).

Every 50 entries, and at every lead approval, draft approval and export, the
ledger head (sequence number + hash) is signed with an Ed25519 key and the
signed checkpoint is written *outside the database*.

Trust comes from two things the database operator must not control:
* the signing key - PRAMANA_CHECKPOINT_KEY (base64 raw private key), or a key
  file kept outside the data directory. In production it belongs on a token
  held by the supervisor, not on the application server;
* the retained checkpoints - a directory outside the database, plus copies in
  every handover pack. Verification compares against the latest *retained*
  checkpoint, never one read from the database.

Guarantee: tampering up to the latest trusted checkpoint is detected.
Entries after it are reported as outside the guaranteed region.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .db import utcnow_iso

INTERVAL = 50


def _raw_pub(pub: Ed25519PublicKey) -> bytes:
    return pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def fingerprint(pub: Ed25519PublicKey) -> str:
    import hashlib
    return hashlib.sha256(_raw_pub(pub)).hexdigest()[:16]


class Keyring:
    def __init__(self, key_dir: Path, checkpoint_dir: Path):
        self.key_dir, self.checkpoint_dir = key_dir, checkpoint_dir

    def private_key(self) -> Ed25519PrivateKey:
        env = os.environ.get("PRAMANA_CHECKPOINT_KEY")
        if env:
            return Ed25519PrivateKey.from_private_bytes(base64.b64decode(env))
        path = self.key_dir / "checkpoint_ed25519.key"
        if path.exists():
            return Ed25519PrivateKey.from_private_bytes(base64.b64decode(path.read_text().strip()))
        self.key_dir.mkdir(parents=True, exist_ok=True)
        key = Ed25519PrivateKey.generate()
        raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                serialization.NoEncryption())
        path.write_text(base64.b64encode(raw).decode())
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return key

    def public_key(self) -> Ed25519PublicKey:
        env = os.environ.get("PRAMANA_CHECKPOINT_PUBLIC_KEY")
        if env:
            return Ed25519PublicKey.from_public_bytes(base64.b64decode(env))
        return self.private_key().public_key()


def _message(cp: dict) -> bytes:
    body = {k: cp[k] for k in ("build", "seq", "head_hash", "taken_at", "reason")}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def sign(keyring: Keyring, build: str, seq: int, head_hash: str, reason: str) -> dict:
    key = keyring.private_key()
    cp = {"build": build, "seq": seq, "head_hash": head_hash, "taken_at": utcnow_iso(), "reason": reason}
    cp["signature"] = base64.b64encode(key.sign(_message(cp))).decode()
    cp["public_key"] = base64.b64encode(_raw_pub(key.public_key())).decode()
    cp["key_fingerprint"] = fingerprint(key.public_key())
    return cp


def signature_ok(cp: dict, pub: Ed25519PublicKey) -> bool:
    try:
        pub.verify(base64.b64decode(cp["signature"]), _message(cp))
        return True
    except (InvalidSignature, KeyError, ValueError):
        return False


def retain(keyring: Keyring, cp: dict) -> Path:
    keyring.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    path = keyring.checkpoint_dir / f"checkpoint-{cp['seq']:08d}.json"
    path.write_text(json.dumps(cp, indent=2))
    return path


def latest_retained(keyring: Keyring) -> dict | None:
    if not keyring.checkpoint_dir.exists():
        return None
    files = sorted(keyring.checkpoint_dir.glob("checkpoint-*.json"))
    for f in reversed(files):
        try:
            return json.loads(f.read_text())
        except ValueError:
            continue
    return None


def check_against(entries: list, cp: dict, pub: Ed25519PublicKey) -> dict:
    """Compare the ledger (list of LedgerEntry) with a trusted checkpoint."""
    if not signature_ok(cp, pub):
        return {"ok": False, "reason": "Checkpoint signature is not valid for the trusted key.", "checkpoint": cp}
    by_seq = {e.seq: e for e in entries}
    head = entries[-1].seq if entries else 0
    if head < cp["seq"]:
        return {"ok": False, "reason": f"Rollback: the log ends at #{head}, but a signed checkpoint covers #{cp['seq']}.",
                "checkpoint": cp}
    at = by_seq.get(cp["seq"])
    if at is None or at.hash != cp["head_hash"]:
        return {"ok": False, "reason": f"Entry #{cp['seq']} does not match the signed checkpoint: the log up to it "
                                       f"has been altered or recomputed.", "checkpoint": cp}
    return {"ok": True, "reason": None, "checkpoint": cp, "entries_after_checkpoint": head - cp["seq"]}


# --- wiring ------------------------------------------------------------------------

def keyring_for(settings) -> Keyring:
    return Keyring(settings.key_dir, settings.checkpoint_dir)


def _head(session):
    from sqlalchemy import select
    from .models import LedgerEntry
    return session.scalar(select(LedgerEntry).order_by(LedgerEntry.seq.desc()).limit(1))


def enabled(settings) -> bool:
    """Serverless instances have no persistent key file: a key generated per
    instance would make signatures meaningless, so there checkpoints need
    PRAMANA_CHECKPOINT_KEY and are skipped without it."""
    return not settings.serverless or bool(os.environ.get("PRAMANA_CHECKPOINT_KEY"))


def take(session, reason: str) -> dict | None:
    """Sign and retain the current head now (lead approval, draft approval,
    export, or every INTERVAL entries)."""
    settings = session.info.get("settings")
    head = _head(session)
    if settings is None or head is None or not enabled(settings):
        return None
    kr = keyring_for(settings)
    cp = sign(kr, settings.build, head.seq, head.hash, reason)
    retain(kr, cp)
    return cp


def maybe_checkpoint(session) -> None:
    settings = session.info.get("settings")
    if settings is None or not enabled(settings):
        return
    head = _head(session)
    if head is None:
        return
    latest = latest_retained(keyring_for(settings))
    last = latest["seq"] if latest else 0
    if head.seq // INTERVAL > last // INTERVAL:
        take(session, f"every {INTERVAL} entries")
