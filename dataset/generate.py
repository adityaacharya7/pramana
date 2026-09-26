"""Generate the PRAMANA synthetic demo dataset.

    python dataset/generate.py                 # writes dataset/tri_city_v1/
    python dataset/generate.py --out /tmp/x    # somewhere else
    python dataset/generate.py --seed 7        # a different (still valid) draw

The same seed always produces byte-identical files. The run fails if the
generated data does not match its own ground truth (see gen/checks.py).
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from gen.checks import run_checks  # noqa: E402
from gen.common import IdGen, DatasetWriter  # noqa: E402
from gen.noise import build_noise  # noqa: E402
from gen.people import NameGen  # noqa: E402
from gen.tri_city import BRANCHES, OFFICIALS, build_tri_city  # noqa: E402
from gen.world import World  # noqa: E402

DATASET = "tri_city_v1"
GENERATOR_VERSION = "1.0.0"
DEFAULT_SEED = 26189

UNITS = [
    {"code": "MUM-CYB", "name": "Mumbai Cyber Police (synthetic unit)", "city": "Mumbai"},
    {"code": "DEL-CYB", "name": "Delhi Cyber Police (synthetic unit)", "city": "Delhi"},
    {"code": "BLR-CEN", "name": "Bengaluru CEN Police (synthetic unit)", "city": "Bengaluru"},
    {"code": "VIG", "name": "Vigilance and internal oversight (synthetic unit)", "city": None},
    {"code": "IT", "name": "IT cell (synthetic unit)", "city": None},
]
UNIT_BY_CITY = {u["city"]: u["code"] for u in UNITS if u["city"]}

# Demo-build users only. The demo build has its own database and a role
# switcher; nothing here is ever loaded into a standard build.
USERS = [
    {"username": "io.mumbai", "name": "Insp. Aparna Deshmukh", "role": "IO", "unit": "MUM-CYB"},
    {"username": "io.delhi", "name": "SI Rohit Malik", "role": "IO", "unit": "DEL-CYB"},
    {"username": "io.bengaluru", "name": "PSI Chaitra Gowda", "role": "IO", "unit": "BLR-CEN"},
    {"username": "analyst.mumbai", "name": "Tanvi Kelkar", "role": "ANALYST", "unit": "MUM-CYB"},
    {"username": "sup.mumbai", "name": "ACP Suhas Pawar", "role": "SUPERVISOR", "unit": "MUM-CYB"},
    {"username": "sup.delhi", "name": "ACP Ritu Khanna", "role": "SUPERVISOR", "unit": "DEL-CYB"},
    {"username": "sup.bengaluru", "name": "DySP Manjunath B.", "role": "SUPERVISOR", "unit": "BLR-CEN"},
    {"username": "auditor", "name": "K. Srinivasan (Vigilance)", "role": "AUDITOR", "unit": "VIG"},
    {"username": "admin", "name": "IT Cell Administrator", "role": "ADMIN", "unit": "IT"},
]
IO_BY_UNIT = {"MUM-CYB": "io.mumbai", "DEL-CYB": "io.delhi", "BLR-CEN": "io.bengaluru"}

TRI_CITY_CASES = [
    {"id": "C-101", "fir_no": "0412/2026", "city": "Mumbai", "station": "Cyber Police Station (West Region), Mumbai",
     "title": "Digital arrest impersonation complaint", "registered_on": "2026-08-13",
     "complainant": "Shobha Anant Kulkarni"},
    {"id": "C-102", "fir_no": "0287/2026", "city": "Delhi", "station": "Cyber Police Station, North-West District, Delhi",
     "title": "Digital arrest impersonation complaint", "registered_on": "2026-08-14",
     "complainant": "Harish Chandra Bhatia"},
    {"id": "C-103", "fir_no": "0198/2026", "city": "Bengaluru", "station": "CEN Police Station, South Division, Bengaluru",
     "title": "Digital arrest impersonation complaint", "registered_on": "2026-08-16",
     "complainant": "Kavitha Ramesh"},
]
# The Tri-City cases are worked as a joint probe: the Mumbai IO, analyst and
# supervisor are members of all three. Every other cross-unit view needs an
# access request.
JOINT_PROBE = {"cases": ["C-101", "C-102", "C-103"], "members": ["io.mumbai", "analyst.mumbai", "sup.mumbai"]}


def build(out_dir: Path, seed: int) -> dict:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    rng = random.Random(seed)
    world = World(rng=rng, ids=IdGen(rng), names=NameGen(rng))
    writer = DatasetWriter(out_dir)

    tri = build_tri_city(world, writer)
    noise_cases, noise_truth, quality = build_noise(world, writer)

    cases = []
    for c in TRI_CITY_CASES + noise_cases:
        unit = UNIT_BY_CITY[c["city"]]
        members = [{"username": IO_BY_UNIT[unit], "access": "owner"}]
        if c["id"] in JOINT_PROBE["cases"]:
            members += [{"username": u, "access": "member"} for u in JOINT_PROBE["members"]
                        if u != IO_BY_UNIT[unit]]
        elif unit == "MUM-CYB":
            members.append({"username": "analyst.mumbai", "access": "member"})
        cases.append({**c, "unit": unit, "status": "OPEN", "members": members})
    cases.sort(key=lambda c: c["id"])

    truth = {
        "dataset": DATASET,
        "tri_city": tri,
        "noise_cases": noise_truth,
        "quality_issues": quality,
        "bank_branches": {k: {**v, "bank_name": None} for k, v in BRANCHES.items()},
        "bank_officials": {k: {"name": v[0], "branch": v[1]} for k, v in OFFICIALS.items()},
        "hard_negatives": [
            {"id": "HN-billers", "what": "Each city's power distributor is paid by several victims, so its UPI ID "
                                         "appears in many cases.",
             "expected": "SHARED-ID-v1 may observe it; the Receipt's ordinary explanation (utility biller) applies; "
                         "an officer can dismiss with a logged reason."},
            {"id": "HN-same-script", "what": "C-114 and C-126 use the fake-CBI digital-arrest script but share no "
                                             "identifier with the Tri-City cases (FX-18 pattern).",
             "expected": "MO similarity may propose them; no shared-operation claim."},
            {"id": "HN-family-phone", "what": "C-118 complainant shares one mobile number with a brother (FX-20 "
                                              "pattern).", "expected": "No identity merge."},
            {"id": "HN-below-threshold", "what": "E-46, E-51, E-52, E-63 and E-64 each opened exactly two "
                                                 "complaint-linked or flagged accounts.",
             "expected": "FACILITATOR-v1 silent for them (threshold is 3)."},
            {"id": "HN-ordinary", "what": "Most transactions are pensions, salaries, rent, groceries, bills, family "
                                          "transfers and ATM use.", "expected": "No lead."},
        ],
    }

    writer.write_json("cases.json", cases)
    writer.write_json("units.json", UNITS)
    writer.write_json("demo_users.json", USERS)
    writer.write_json("ground_truth.json", truth)

    report = run_checks(out_dir, writer.files, world, truth, quality)
    manifest = {
        "dataset": DATASET,
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "synthetic": True,
        "notice": "Entirely synthetic. Every person, number, account, bank and organisation is invented.",
        "stats": report["stats"],
        "files": sorted(writer.files, key=lambda f: f["path"]),
    }
    writer.write_json("manifest.json", manifest)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=HERE / DATASET)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    report = build(args.out, args.seed)
    stats = report["stats"]
    print(f"{DATASET} -> {args.out}")
    for k, v in stats.items():
        if k != "shared_identifiers":
            print(f"  {k:32s} {v}")
    print(f"  {'shared identifiers':32s} {len(stats['shared_identifiers'])}")
    if report["problems"]:
        print("\nSELF-CHECK FAILED:")
        for p in report["problems"]:
            print(f"  - {p}")
        return 1
    print("\nself-check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
