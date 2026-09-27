"""The analysis engine against the dataset's ground truth and the spec's
fixtures. Pure functions: the input is built once from a seeded demo
database, then every check runs without it."""
import json

import pytest

from pramana.analysis.engine import analyse, diff, summary
from pramana.analysis.inputs import build_input
from pramana.analysis.trail import METHODS
from pramana.config import REPO_ROOT
from pramana.main import create_app

from .conftest import make_settings

TRUTH = json.loads((REPO_ROOT / "dataset" / "tri_city_v1" / "ground_truth.json").read_text(encoding="utf-8"))
L = {k: v["value"] for k, v in TRUTH["tri_city"]["labels"].items() if "value" in v}
REF = {t["id"]: t["reference"] for t in TRUTH["tri_city"]["transfers"]}
TRI = ["C-101", "C-102", "C-103"]


@pytest.fixture(scope="module")
def inputs(tmp_path_factory):
    app = create_app(make_settings("demo", tmp_path_factory.mktemp("analysis")))
    with app.state.sessionmaker() as db:
        s = app.state.settings
        return {"tri": build_input(db, s, TRI), "all": build_input(db, s, [f"C-{i}" for i in range(101, 131)]),
                "c104": build_input(db, s, ["C-104"])}


@pytest.fixture(scope="module")
def tri(inputs):
    return analyse(inputs["tri"])


def keys(result, rule):
    return {o["key"] for o in result["observations"] if o["rule_id"] == rule}


def obs(result, key):
    return next(o for o in result["observations"] if o["key"] == key)


def test_all_eight_rules_fire_or_stay_silent_as_expected(tri):
    """F9 done-when on the Tri-City scenario."""
    assert keys(tri, "SHARED-ID-v1") == {
        f"SHARED-ID-v1:phone:{L['P-77']}", f"SHARED-ID-v1:phone:{L['V2-phone']}",
        f"SHARED-ID-v1:bank_account:{L['HUB']}", f"SHARED-ID-v1:bank_account:{L['M2']}",
        f"SHARED-ID-v1:bank_account:{L['M3']}"}
    conv = obs(tri, f"CONVERGENCE-v1:{L['HUB']}")
    assert set(conv["metrics"]["sender_accounts"]) == {L["M1"], L["M2"], L["M3"]}
    assert conv["metrics"]["window_minutes"] <= 60
    assert len(keys(tri, "LAYERING-v1")) == 3
    cash = obs(tri, f"CASHOUT-v1:{L['HUB']}")
    assert cash["metrics"]["wallets"] == [L["W-1"]] and cash["exit_kind"] == "crypto"
    fac = obs(tri, "FACILITATOR-v1:branch+official:XSSB0000017 / E-45")
    assert set(fac["metrics"]["account_list"]) == {L["M1"], L["M2"], L["M3"]}
    assert keys(tri, "FRONT-ENTITY-v1") == set()  # expected silent: no shared address or phone
    mo = keys(tri, "MO-MATCH-v1")
    assert {"MO-MATCH-v1:C-101|C-103", "MO-MATCH-v1:C-102|C-103"} <= mo
    op = [o for o in tri["observations"] if o["rule_id"] == "ORDINARY-PAYMENT-v1"]
    assert len(op) == 1 and op[0]["metrics"]["amount"] == 2000.0
    assert "not cleared" in op[0]["summary"]


def test_wording_rules():
    from pramana.analysis.rules import RULES
    text = json.dumps(RULES).lower()
    for banned in ("criminal", "mastermind", "guilty", "suspicion score"):
        assert banned not in text


def test_attribution_methods_match_the_spec_worked_example(tri):
    """FX-15 pattern on M2: Rs 50,000 salary + Rs 58,000 victim, 2,000 grocery, 60,000 onward."""
    def m2_to(method, party):
        return round(sum(f["amount"] for f in tri["trail"]["methods"][method]["flows"]
                         if f["from"] == L["M2"] and f["to"] == party), 2)
    assert (m2_to("fifo", L["HUB"]), m2_to("lifo", L["HUB"]), m2_to("prorata", L["HUB"])) == (12000.0, 56000.0, 32222.22)
    grocery = next(o for o in tri["observations"] if o["rule_id"] == "ORDINARY-PAYMENT-v1")["subject"]["value"]

    def share(method):
        return round(sum(f["amount"] for f in tri["trail"]["methods"][method]["flows"] if f["event"] == grocery), 2)
    assert (share("fifo"), share("lifo"), share("prorata")) == (0.0, 2000.0, 1074.07)


def test_every_victim_rupee_is_in_exactly_one_place(tri):
    """FX-16: totals never exceed the loss; each rupee at one holding point or exit."""
    for m in METHODS:
        t = tri["trail"]["methods"][m]
        assert t["total_loss"] == 175000.0
        for case, c in t["by_case"].items():
            assert c["held"] + c["exited"] + c["missing_statement"] == pytest.approx(c["loss"], abs=0.05), (m, case)
        assert t["reconciles"]
        assert all(h["as_of"] for h in t["holdings"] if h["has_statement"])


def test_exclude_source_drops_convergence_but_keeps_other_transfers(inputs, tri):
    """FX-26 / FX-29: the M3 -> HUB bank record excluded."""
    after = analyse(inputs["tri"], [{"op": "exclude_source", "source": f"bankref:{REF['M3-HUB']}"}])
    d = diff(tri, after)
    removed = {x["key"]: x for x in d["removed"]}
    conv = removed[f"CONVERGENCE-v1:{L['HUB']}"]
    assert "2 of the 3" in conv["why"]
    events = {e["id"] for f in after["trail"]["methods"]["fifo"]["flows"] for e in [{"id": f["event"]}]}
    assert f"ref:{REF['M1-HUB']}" in events and f"ref:{REF['M2-HUB']}" in events
    # HUB paid out more than the remaining records say it held: uncertain, not a precise figure.
    assert not after["reconciles"]
    assert any(e["party"] == L["HUB"] and e["uncertain_after"] for e in d["estimates"])


def test_dispute_shows_results_with_and_without(inputs):
    """FX-27."""
    r = analyse(inputs["tri"], [{"op": "dispute_txn", "event_id": f"ref:{REF['M2-HUB']}"}])
    assert f"CONVERGENCE-v1:{L['HUB']}" in keys(r, "CONVERGENCE-v1")
    assert f"CONVERGENCE-v1:{L['HUB']}" not in keys(r["without_disputed"], "CONVERGENCE-v1")


def test_simulated_non_occurrence_is_reported_uncertain(inputs):
    """FX-28: without M1 -> HUB, HUB's later outflow is not covered."""
    r = analyse(inputs["tri"], [{"op": "simulate_no_txn", "event_id": f"ref:{REF['M1-HUB']}"}])
    kinds = {(i["party"], i["kind"]) for i in r["trail"]["methods"]["fifo"]["issues"]}
    assert (L["HUB"], "outflow_exceeds_known_funds") in kinds


def test_crypto_exit_needs_the_trade_record(inputs, tri):
    """FX-14 / FX-22: without the seized chat, no CASHOUT and no wallet."""
    chat = next(t for t in inputs["tri"]["trade_records"])
    r = analyse(inputs["tri"], [{"op": "exclude_source", "source": chat["source"]}])
    assert keys(r, "CASHOUT-v1") == set()
    assert not any(x["kind"].startswith("crypto") for x in r["trail"]["methods"]["fifo"]["exits"])
    assert keys(tri, "CASHOUT-v1")


def test_missing_statement_is_not_read_as_no_onward_transfer(inputs):
    """FX-21: C-104's second receiving account has no statement."""
    r = analyse(inputs["c104"])
    t = r["trail"]["methods"]["fifo"]
    assert t["missing_statements"]
    assert all(h["as_of"] is None for h in t["holdings"] if not h["has_statement"])


def test_hard_negatives_across_all_cases(inputs):
    r = analyse(inputs["all"])
    # FX-06: ordinary activity everywhere else produces no convergence or layering.
    assert keys(r, "CONVERGENCE-v1") == {f"CONVERGENCE-v1:{L['HUB']}"}
    assert all(any(o["cases"][0] == c for c in TRI) for o in r["observations"] if o["rule_id"] == "LAYERING-v1")
    # FX-09: a job-offer case is never an MO match for the digital-arrest cases.
    job_cases = {n["case_id"] for n in TRUTH["noise_cases"] if n["family"] == "JOB"}
    for k in keys(r, "MO-MATCH-v1"):
        a, b = k.split(":")[1].split("|")
        assert not ({a, b} & job_cases and {a, b} & set(TRI))
    # FX-18: same fake-CBI script, no shared identifier: similar, but no shared-operation claim.
    same_script = [o for o in r["observations"] if o["rule_id"] == "MO-MATCH-v1" and "C-114" in o["cases"]
                   and set(o["cases"]) & set(TRI)]
    assert same_script and all(not o["metrics"]["shared_identifier"] for o in same_script)
    assert all("not evidence of a shared operation" in o["summary"] for o in same_script)
    # FX-19: a utility biller shared by many cases is explained as a known merchant category.
    billers = [o for o in r["observations"] if o["rule_id"] == "SHARED-ID-v1" and "power" in o["subject"]["label"].lower()]
    assert billers and all("merchant category" in o["ordinary_explanation"] for o in billers)


def test_analysis_is_deterministic(inputs):
    assert summary(analyse(inputs["tri"])) == summary(analyse(inputs["tri"]))
