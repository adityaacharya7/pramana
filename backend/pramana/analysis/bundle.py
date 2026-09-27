"""Handover pack and re-run bundle (F15).

A bundle holds everything needed to reproduce a lead on another machine,
offline, with no database: the reviewed input snapshot, identity decisions,
applied operations, rule versions and parameters, attribution method,
software and model versions, the expected results, the evidence manifest
hashes, and the audit-log head with the latest signed checkpoint.

`verify_bundle` re-runs the analysis from the bundle alone and compares.
"""
from __future__ import annotations

import base64
import hashlib

from .. import __version__
from .engine import ENGINE_VERSION, analyse, receipt, summary
from .inputs import canonical_json, input_hash
from .mo import METHOD as MO_METHOD

BUNDLE_FORMAT = "pramana-handover-1"


def _hash(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def build_bundle(*, lead: dict, inp: dict, result: dict, drafts: list[dict], method: str | None,
                 ledger_head: dict | None, checkpoint: dict | None, generated_by: str, generated_at: str,
                 extractor_versions: list[str]) -> dict:
    obs = next(o for o in result["observations"] if o["key"] == lead["key"])
    body = {
        "format": BUNDLE_FORMAT,
        "lead": {**lead, "receipt": receipt(obs, inp, result)},
        "software": {"pramana": __version__, "engine": ENGINE_VERSION, "mo_method": MO_METHOD,
                     "extractors": sorted(set(extractor_versions))},
        "rule_versions": result["rule_versions"],
        "params": result["params"],
        "attribution_method": method,
        "operations": result["operations"],
        "identity_decisions": inp.get("identity_decisions", []),
        "evidence_manifest": [{"file_id": f["id"], "case_id": f["case_id"], "filename": f["filename"],
                               "sha256": f["sha256"]} for f in inp["files"]],
        "input": inp,
        "input_hash": input_hash(inp),
        "expected": summary(result),
        "drafts": drafts,
        "ledger": {"head": ledger_head, "latest_checkpoint": checkpoint},
        "generated_by": generated_by,
        "generated_at": generated_at,
    }
    body["bundle_hash"] = _hash({k: v for k, v in body.items() if k not in ("generated_at",)})
    return body


def verify_bundle(bundle: dict, trusted_public_key=None) -> dict:
    """Re-run and compare. Needs nothing but the bundle (and, optionally, the
    public key you trust for checkpoints, obtained out of band)."""
    checks = []

    def check(name: str, ok: bool, detail: str = ""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    if bundle.get("format") != BUNDLE_FORMAT:
        return {"ok": False, "checks": [{"check": "format", "ok": False, "detail": "Not a PRAMANA handover bundle."}]}

    claimed = bundle.get("bundle_hash")
    recomputed = _hash({k: v for k, v in bundle.items() if k not in ("generated_at", "bundle_hash")})
    check("bundle hash", claimed == recomputed, "Bundle contents match the hash recorded at export."
          if claimed == recomputed else "The bundle was changed after export.")
    inp = bundle["input"]
    check("input hash", input_hash(inp) == bundle["input_hash"], "Input snapshot matches its hash.")
    manifest = {f["file_id"]: f["sha256"] for f in bundle["evidence_manifest"]}
    check("evidence manifest", all(manifest.get(f["id"]) == f["sha256"] for f in inp["files"]),
          f"{len(manifest)} evidence files, SHA-256 recorded for each.")

    rerun = analyse(inp, bundle["operations"], bundle["params"])
    got, want = summary(rerun), bundle["expected"]
    missing = sorted(set(want["observations"]) - set(got["observations"]))
    extra = sorted(set(got["observations"]) - set(want["observations"]))
    differ = sorted(k for k in set(want["observations"]) & set(got["observations"])
                    if want["observations"][k] != got["observations"][k])
    check("findings reproduced", not (missing or extra or differ),
          f"{len(want['observations'])} findings reproduced exactly." if not (missing or extra or differ) else
          f"missing {missing}, unexpected {extra}, different {differ}")
    trail_ok = got["trail"] == want["trail"]
    check("money trail and estimates reproduced", trail_ok,
          "Holdings, exits and totals match under FIFO, LIFO and pro-rata." if trail_ok else
          "Money-trail figures differ from the exported ones.")
    lead_key = bundle["lead"]["key"]
    check("lead reproduced", lead_key in got["observations"], lead_key)

    cp = (bundle.get("ledger") or {}).get("latest_checkpoint")
    if cp:
        from ..checkpoints import signature_ok
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        included = Ed25519PublicKey.from_public_bytes(base64.b64decode(cp["public_key"]))
        key = trusted_public_key or included
        ok = signature_ok(cp, key)
        check("audit-log checkpoint signature", ok,
              ("Signature valid for the trusted key." if trusted_public_key else
               f"Signature valid for the key included in the bundle (fingerprint {cp.get('key_fingerprint')}). "
               "Confirm that fingerprint with the issuing unit before relying on it.") if ok else "Invalid signature.")
    else:
        check("audit-log checkpoint signature", False, "No checkpoint in the bundle.")
    return {"ok": all(c["ok"] for c in checks), "checks": checks, "lead": lead_key,
            "rerun_input_hash": rerun["input_hash"]}
