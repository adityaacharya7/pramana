"""Evidence store: sealed files plus their SHA-256 manifest entries.

Files are stored as ``<case_id>/<file_id>`` - on disk under the evidence
directory, or as a row in the database on serverless hosts. The uploader's
filename never becomes part of a path. A file is re-hashed every time its
content is loaded; a mismatch blocks it.

A matching hash shows the file is unchanged since upload. It does not show
that its content is true or who created it.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import BinaryIO

TYPES = {".csv": "CSV", ".txt": "TXT", ".log": "TXT", ".pdf": "PDF"}
KINDS = {
    "complaint", "witness_statement", "supplementary_statement", "bank_statement", "kyc_response",
    "cdr", "chat_log", "other", "unclassified",
}
CHUNK = 1024 * 1024


class UploadRejected(ValueError):
    pass


class IntegrityMismatch(RuntimeError):
    def __init__(self, expected: str, actual: str | None):
        super().__init__("integrity mismatch")
        self.expected, self.actual = expected, actual


def clean_filename(name: str) -> str:
    base = re.split(r"[\\/]", name or "")[-1]
    base = "".join(ch for ch in base if ch.isprintable()).strip()
    return base[:200] or "unnamed"


def detect_type(filename: str, head: bytes) -> str:
    ext = os.path.splitext(filename.lower())[1]
    ftype = TYPES.get(ext)
    if ftype is None:
        raise UploadRejected(f"Unsupported file type {ext or '(none)'}. Accepted: CSV, TXT, PDF.")
    if ftype == "PDF":
        if not head.startswith(b"%PDF-"):
            raise UploadRejected("File has a .pdf name but is not a PDF.")
    else:
        if b"\x00" in head:
            raise UploadRejected("Text files must not contain binary data.")
        try:
            head.decode("utf-8")
        except UnicodeDecodeError as e:
            # A multi-byte character may straddle the sniff boundary.
            if e.start < len(head) - 4:
                raise UploadRejected("Text files must be UTF-8 encoded.") from e
    return ftype


def _read_upload(stream: BinaryIO, max_bytes: int, filename: str, sink) -> tuple[str, int, str]:
    """Stream an upload into `sink` while hashing and checking it."""
    digest = hashlib.sha256()
    size = 0
    ftype = None
    while True:
        chunk = stream.read(CHUNK)
        if not chunk:
            break
        if ftype is None:
            ftype = detect_type(filename, chunk[:4096])
        size += len(chunk)
        if size > max_bytes:
            raise UploadRejected(f"File exceeds the {max_bytes / (1024 * 1024):g} MB limit.")
        digest.update(chunk)
        sink(chunk)
    if size == 0:
        raise UploadRejected("File is empty.")
    return digest.hexdigest(), size, ftype  # type: ignore[return-value]


# --- file backend (local / Docker) ---------------------------------------------------

def _file_store(evidence_dir: Path, rel: str, stream: BinaryIO, max_bytes: int, filename: str):
    dest = evidence_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    try:
        with open(tmp, "wb") as out:
            sha, size, ftype = _read_upload(stream, max_bytes, filename, out.write)
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()
    try:
        os.chmod(dest, 0o444)
    except OSError:
        pass
    return sha, size, ftype


def _file_bytes(evidence_dir: Path, rel: str) -> bytes | None:
    path = evidence_dir / rel
    return path.read_bytes() if path.exists() else None


# --- database backend (serverless) -------------------------------------------------
# Serverless functions have no persistent disk, so sealed bytes live in the
# database, in their own table. The integrity guarantee is unchanged: the hash
# recorded at upload is re-checked against the stored bytes on every load.

def _db_session(settings):
    from .db import make_engine, make_sessionmaker
    return make_sessionmaker(make_engine(settings.db_url, settings.serverless))()


def _db_store(settings, rel: str, stream: BinaryIO, filename: str):
    from .models import EvidenceBlob
    parts: list[bytes] = []
    sha, size, ftype = _read_upload(stream, settings.max_upload_bytes, filename, parts.append)
    with _db_session(settings) as s:
        s.merge(EvidenceBlob(storage_path=rel, data=b"".join(parts)))
        s.commit()
    return sha, size, ftype


def _db_bytes(settings, rel: str) -> bytes | None:
    from .models import EvidenceBlob
    with _db_session(settings) as s:
        blob = s.get(EvidenceBlob, rel)
        return bytes(blob.data) if blob is not None else None


# --- interface ---------------------------------------------------------------------

def store(settings, case_id: str, file_id: str, stream: BinaryIO, filename: str) -> tuple[str, str, int, str]:
    """Seal an upload. Returns (storage_path, sha256, size, type)."""
    rel = f"{case_id}/{file_id}"
    if settings.evidence_store == "db":
        sha, size, ftype = _db_store(settings, rel, stream, filename)
    else:
        sha, size, ftype = _file_store(settings.evidence_dir, rel, stream, settings.max_upload_bytes, filename)
    return rel, sha, size, ftype


def discard(settings, rel: str) -> None:
    """Remove a sealed file whose manifest row was never committed."""
    if settings.evidence_store == "db":
        from .models import EvidenceBlob
        with _db_session(settings) as s:
            blob = s.get(EvidenceBlob, rel)
            if blob is not None:
                s.delete(blob)
                s.commit()
    else:
        (settings.evidence_dir / rel).unlink(missing_ok=True)


def _bytes(settings, rel: str) -> bytes | None:
    return _db_bytes(settings, rel) if settings.evidence_store == "db" else _file_bytes(settings.evidence_dir, rel)


def rehash(settings, rel: str) -> str | None:
    data = _bytes(settings, rel)
    return None if data is None else hashlib.sha256(data).hexdigest()


def read_verified(settings, rel: str, expected: str) -> bytes:
    data = _bytes(settings, rel)
    if data is None:
        raise IntegrityMismatch(expected, None)
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise IntegrityMismatch(expected, actual)
    return data
