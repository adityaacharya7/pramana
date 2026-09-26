"""Twenty-seven unrelated cases that surround the Tri-City network.

They are hand-specified (family, city, amounts, money pattern) so the hard
negatives and planted quality issues sit exactly where the ground truth says
they are; identifiers and ordinary activity come from the seeded RNG.

Money patterns ("plan") for the receiving account:
  atm        cash withdrawn in chunks soon after the credits
  layer      forwarded (>= 85%) to a second account within the hour
  upi_spray  split across several UPI IDs within two hours
  hold       funds stay put (lien after the 1930 report)
  none       no statement for the receiving account was obtained
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import narratives as N
from .common import BANKS, DatasetWriter, Statement, Txn, fmt_inr, rows_to_csv
from .people import SHOP_PREFIX
from .tri_city import BRANCHES, KYC_COLUMNS, OFFICIALS, kyc_row
from .world import World, add_benign_activity, ensure_non_negative


@dataclass
class Spec:
    case_id: str
    city: str
    family: str
    lang: str
    start: tuple[int, int]  # (month, day)
    hour: int
    amounts: list[int]
    plan: str
    official: str | None = None
    extras: set[str] = field(default_factory=set)


SPECS = [
    Spec("C-104", "Mumbai", "JOB", "en", (7, 14), 11, [5000, 18000, 42000], "atm", "E-52", {"second_mule", "supp"}),
    Spec("C-105", "Delhi", "INV", "en", (7, 22), 14, [100000, 250000], "layer", "E-63", {"supp"}),
    Spec("C-106", "Bengaluru", "KYC", "en", (7, 9), 19, [24999, 24999], "upi_spray"),
    Spec("C-107", "Mumbai", "MKT", "en", (7, 27), 16, [10000, 20000, 15000], "atm", "E-46", {"dup_stmt"}),
    Spec("C-108", "Delhi", "ELEC", "hg", (8, 3), 18, [72500], "hold", "E-51"),
    Spec("C-109", "Bengaluru", "COUR", "en", (7, 18), 12, [8500, 16000], "none"),
    Spec("C-110", "Mumbai", "CC", "en", (8, 6), 13, [45000], "layer", "E-64", {"supp"}),
    Spec("C-111", "Delhi", "JOB", "hg", (8, 5), 15, [9000, 26000], "atm", "E-46", {"gap_stmt"}),
    Spec("C-112", "Bengaluru", "INV", "en", (8, 1), 11, [150000, 150000], "layer", "E-52", {"supp"}),
    Spec("C-113", "Mumbai", "LOAN", "hi", (7, 30), 20, [9000, 12000], "upi_spray"),
    Spec("C-114", "Bengaluru", "DA", "en", (8, 19), 10, [240000], "atm", "E-63", {"supp"}),
    Spec("C-115", "Delhi", "KYC", "hi", (8, 8), 21, [49000], "none"),
    Spec("C-116", "Mumbai", "ELEC", "en", (8, 21), 17, [115000], "hold"),
    Spec("C-117", "Bengaluru", "MKT", "hi", (7, 11), 15, [18500], "atm", "E-64"),
    Spec("C-118", "Delhi", "CC", "en", (7, 25), 12, [32000], "none", None, {"shared_family_phone"}),
    Spec("C-119", "Mumbai", "INVC", "en", (7, 6), 10, [75000, 125000], "layer", None, {"recon_victim", "supp"}),
    Spec("C-120", "Bengaluru", "JOB", "en", (8, 24), 13, [12000, 30000], "upi_spray"),
    Spec("C-121", "Delhi", "COUR", "en", (8, 14), 11, [22000], "hold"),
    Spec("C-122", "Mumbai", "KYC", "en", (8, 7), 9, [38000], "atm", None, {"dmy_mule"}),
    Spec("C-123", "Bengaluru", "ELEC", "en", (8, 26), 19, [6000], "none"),
    Spec("C-124", "Delhi", "MKT", "en", (8, 17), 16, [27000], "atm"),
    Spec("C-125", "Mumbai", "LOAN", "en", (8, 10), 22, [15000], "upi_spray"),
    Spec("C-126", "Delhi", "DA", "hg", (7, 19), 10, [180000], "layer"),
    Spec("C-127", "Bengaluru", "CC", "en", (8, 11), 14, [55000], "layer"),
    Spec("C-128", "Mumbai", "COUR", "en", (7, 3), 12, [11000], "none"),
    Spec("C-129", "Delhi", "INV", "en", (7, 12), 11, [150000, 150000, 150000], "hold", None, {"supp"}),
    Spec("C-130", "Bengaluru", "JOB", "en", (8, 28), 12, [26000], "atm"),
]

STATIONS = {
    "Mumbai": ["Cyber Police Station (West Region), Mumbai", "Cyber Police Station (East Region), Mumbai"],
    "Delhi": ["Cyber Police Station, North-West District, Delhi", "Cyber Police Station, South District, Delhi"],
    "Bengaluru": ["CEN Police Station, South Division, Bengaluru", "CEN Police Station, East Division, Bengaluru"],
}
LOCALITIES = {
    "Mumbai": [("Andheri West", "400058"), ("Borivali East", "400066"), ("Chembur", "400071"), ("Dadar", "400014"),
               ("Ghatkopar East", "400077"), ("Malad West", "400064"), ("Powai", "400076"), ("Vile Parle East", "400057")],
    "Delhi": [("Rohini Sector 11", "110085"), ("Dwarka Sector 7", "110075"), ("Janakpuri", "110058"),
              ("Lajpat Nagar", "110024"), ("Mayur Vihar Phase 1", "110091"), ("Pitampura", "110034"),
              ("Saket", "110017"), ("Karol Bagh", "110005")],
    "Bengaluru": [("Koramangala", "560034"), ("Indiranagar", "560038"), ("Malleshwaram", "560003"),
                  ("Whitefield", "560066"), ("HSR Layout", "560102"), ("Basavanagudi", "560004"),
                  ("Rajajinagar", "560010"), ("Jayanagar", "560041")],
}
TITLES = {
    "DA": "Digital arrest impersonation complaint", "JOB": "Online task-based job offer complaint",
    "INV": "Investment platform complaint", "INVC": "Crypto trading platform complaint",
    "KYC": "KYC update link - unauthorised debits", "MKT": "Marketplace buyer QR payment complaint",
    "ELEC": "Electricity disconnection message complaint", "LOAN": "Loan app harassment and payment complaint",
    "COUR": "Courier customs fee complaint", "CC": "Fake customer care refund complaint",
}
PROFILE = {  # (profile, age range, occupations)
    "DA": ("pensioner", (61, 76), ["retired government employee", "retired professor", "retired bank officer"]),
    "JOB": ("salaried", (21, 31), ["private sector employee", "student", "sales executive"]),
    "INV": ("salaried", (34, 56), ["chartered accountant", "business owner", "IT manager"]),
    "INVC": ("salaried", (29, 45), ["software engineer", "marketing manager"]),
    "KYC": ("pensioner", (48, 72), ["retired teacher", "homemaker", "shop owner"]),
    "MKT": ("salaried", (26, 44), ["private sector employee", "teacher"]),
    "ELEC": ("pensioner", (52, 74), ["retired railway employee", "homemaker"]),
    "LOAN": ("salaried", (22, 32), ["delivery executive", "office assistant"]),
    "COUR": ("salaried", (30, 60), ["nurse", "shop owner", "private tutor"]),
    "CC": ("salaried", (30, 55), ["accountant", "school administrator"]),
}
CHANNEL = {"DA": "account", "INV": "account", "INVC": "account", "ELEC": "account",
           "JOB": "upi", "KYC": "upi", "MKT": "upi", "LOAN": "upi", "COUR": "upi", "CC": "upi"}
UNAUTHORISED = {"KYC", "ELEC", "CC"}
GAP = {  # spacing between multiple payments
    "JOB": timedelta(minutes=47), "INV": timedelta(days=3), "INVC": timedelta(days=3), "KYC": timedelta(minutes=3),
    "MKT": timedelta(minutes=9), "LOAN": timedelta(days=3), "COUR": timedelta(hours=26), "DA": timedelta(hours=2),
    "ELEC": timedelta(minutes=5), "CC": timedelta(minutes=6),
}
APPS = {
    "INV": ["SynthTrade Pro", "Alpha IPO Desk (demo)"], "INVC": ["CoinVista Test", "BitHarbor Sample"],
    "ELEC": ["BillSahayak Remote", "HelpDesk Mirror"], "CC": ["RefundEase Demo", "HelpDesk Mirror"],
    "LOAN": ["QuickRupee Sample", "InstaCash Fixture"],
}
GROUPS = ["Hotel Rating Earners 482", "Daily Task Income Club", "Institutional Alpha Traders 27",
          "Smart Wealth Circle 09", "Work From Home Rewards 311"]
ITEMS = [("sofa set", "सोफा सेट"), ("washing machine", "वॉशिंग मशीन"), ("study table", "स्टडी टेबल"),
         ("bicycle", "साइकिल")]
BIZ = ["Capital Services", "Wealth Advisory LLP", "Enterprises", "Trading Co", "Consultancy Services"]


def build_noise(world: World, out: DatasetWriter) -> tuple[list[dict], list[dict], list[dict]]:
    rng, ids = world.rng, world.ids
    cases, truth, quality = [], [], []

    for spec in SPECS:
        cid = spec.case_id
        profile, (age_lo, age_hi), occupations = PROFILE[spec.family]
        victim, gender = world.names.person()
        locality, pin = rng.choice(LOCALITIES[spec.city])
        station = rng.choice(STATIONS[spec.city])
        v_phone = world.new_phone(victim, "victim", cid)
        v_acct, v_bank = world.new_account(victim, "victim", cid)
        v_vpa = world.note_upi(ids.upi(victim.split()[0].lower()), victim, "victim", cid)
        caller = world.new_phone("unknown caller", "caller", cid)

        # --- receiving account(s) -------------------------------------------
        def new_mule(biz: bool, branch: str | None = None) -> dict:
            if biz:
                name = f"{rng.choice(SHOP_PREFIX)} {rng.choice(BIZ)}"
            else:
                name, _ = world.names.person()
            if branch:
                # An account-opening response ties the account to that branch.
                bank, ifsc = BRANCHES[branch]["bank"], BRANCHES[branch]["ifsc"]
            else:
                bank = rng.choice(list(BANKS))
                ifsc = f"{bank}000{rng.randint(1000, 9999)}"
            acct, bank = world.new_account(name, "mule", cid, bank=bank)
            vpa = world.note_upi(ids.upi("".join(c for c in name.lower() if c.isalpha())[:10]), name, "mule", cid)
            return {"name": name, "acct": acct, "bank": bank, "ifsc": ifsc, "vpa": vpa,
                    "phone": world.new_phone(name, "account_holder", None)}

        biz = spec.family in {"INV", "INVC"}
        mule = new_mule(biz, OFFICIALS[spec.official][1] if spec.official else None)
        mules = [mule]
        if "second_mule" in spec.extras:
            mules.append(new_mule(False))

        # --- payments -------------------------------------------------------
        first = datetime(2026, spec.start[0], spec.start[1], spec.hour, rng.randint(2, 55), rng.randint(0, 59))
        payments = []
        for i, amt in enumerate(spec.amounts):
            t = first + GAP[spec.family] * i + timedelta(minutes=rng.randint(0, 4))
            m = mules[-1] if (len(mules) > 1 and i == len(spec.amounts) - 1) else mules[0]
            ref = ids.reference()
            channel = "RTGS" if amt >= 200000 else "IMPS"
            p = {"time": t, "amount": amt, "amount_fmt": fmt_inr(amt), "ref": ref, "mule": m,
                 "unauthorised": spec.family in UNAUTHORISED, "channel": channel,
                 "acct": m["acct"], "ifsc": m["ifsc"], "bank": BANKS[m["bank"]],
                 "name": m["name"]}
            if CHANNEL[spec.family] == "upi":
                p["vpa"] = m["vpa"]
                p["channel"] = "UPI"
            payments.append(p)
        last_time = payments[-1]["time"]
        complaint_date = last_time + timedelta(days=rng.randint(1, 3))

        # --- victim statement -----------------------------------------------
        st_v = Statement(v_acct, v_bank, victim, opening=float(rng.randrange(40000, 160000, 1000)))
        add_benign_activity(world, st_v, case_id=cid, city=spec.city, profile=profile, start=st_v.start,
                            end=st_v.end, grocery_per_month=14,
                            avoid=[(p["time"] - timedelta(hours=3), p["time"] + timedelta(hours=3)) for p in payments])
        for p in payments:
            cp = p.get("vpa") or p["acct"]
            st_v.add(Txn(p["time"], f"{p['channel']}/DR/{p['ref']}/{p['name']}", p["channel"], cp, p["name"],
                         debit=float(p["amount"]), reference=p["ref"], tag="fraud:debit"))
        ensure_non_negative(st_v, buffer=1500)
        if "recon_victim" in spec.extras:
            benign_rows = [i for i, t in enumerate(st_v.sorted_txns()) if t.tag.startswith("benign:grocery")]
            st_v.drop_row_index = benign_rows[len(benign_rows) // 2]
            quality.append({"issue": "balance_does_not_reconcile", "case_id": cid,
                            "file": f"cases/{cid}/bank_statement_victim_{v_acct}.csv",
                            "detail": "one ordinary debit row omitted; running balance still reflects it"})
        world.statements.append((cid, st_v))
        out.write(f"cases/{cid}/bank_statement_victim_{v_acct}.csv", st_v.to_csv(ids), case_id=cid,
                  kind="bank_statement", note="Victim account statement")

        # --- receiving account statement ------------------------------------
        m = mules[0]
        stmt_files = []
        if spec.plan != "none":
            st_m = Statement(m["acct"], m["bank"], m["name"], opening=float(rng.randrange(300, 4000, 10)))
            friend, _ = world.names.person()
            friend_vpa = world.note_upi(ids.upi(friend.split()[0].lower()), friend, "individual", None)
            shop = f"{rng.choice(SHOP_PREFIX)} Mobile Recharge"
            shop_vpa = world.note_upi(ids.upi("recharge"), shop, "merchant", None)
            for _ in range(rng.randint(8, 14)):
                d = datetime(2026, 7, 1) + timedelta(days=rng.randint(0, max(1, (first - datetime(2026, 7, 1)).days - 1)),
                                                     hours=rng.randint(8, 21), minutes=rng.randint(0, 59))
                if d >= first - timedelta(hours=6):
                    continue
                if rng.random() < 0.5:
                    st_m.add(Txn(d, f"UPI/P2P/CR/{friend}", "UPI", friend_vpa, friend,
                                 credit=float(rng.randrange(200, 3000, 50)), reference=ids.reference(), tag="benign:misc"))
                else:
                    st_m.add(Txn(d, f"UPI/P2M/{shop}", "UPI-P2M", shop_vpa, shop,
                                 debit=float(rng.randrange(100, 800, 10)), reference=ids.reference(), tag="benign:misc"))
            for p in payments:
                if p["mule"] is not m:
                    continue
                cp = v_vpa if p.get("vpa") else v_acct
                st_m.add(Txn(p["time"], f"{p['channel']}/CR/{p['ref']}/{victim.upper()}", p["channel"], cp,
                             victim.upper(), credit=float(p["amount"]), reference=p["ref"], tag="fraud:credit"))
            received = [p for p in payments if p["mule"] is m]
            total_in = sum(p["amount"] for p in received)
            anchor = received[-1]["time"]

            if spec.plan == "atm":
                atm = f"SYNATM{rng.randint(10000, 99999)}"
                to_withdraw = int(total_in * rng.uniform(0.93, 0.99)) // 500 * 500
                t = anchor + timedelta(minutes=rng.randint(18, 55))
                if to_withdraw > 100000:
                    bulk = to_withdraw - 60000
                    st_m.add(Txn(t, "CASH WDL SELF CHQ", "CASH", "", "Self (cheque)", debit=float(bulk), tag="exit:cash"))
                    to_withdraw -= bulk
                    t += timedelta(minutes=rng.randint(20, 40))
                while to_withdraw > 0:
                    chunk = min(10000, to_withdraw)
                    st_m.add(Txn(t, f"ATM WDL/{atm}", "ATM", atm, "ATM cash withdrawal", debit=float(chunk),
                                 tag="exit:atm"))
                    to_withdraw -= chunk
                    t += timedelta(minutes=rng.randint(3, 9))
            elif spec.plan == "layer":
                l2_name = rng.choice([world.names.person()[0], f"{rng.choice(SHOP_PREFIX)} {rng.choice(BIZ)}"])
                l2, _ = world.new_account(l2_name, "second_layer", cid)
                for p in received:
                    fwd = int(p["amount"] * rng.uniform(0.86, 0.98)) // 100 * 100
                    ref = ids.reference()
                    st_m.add(Txn(p["time"] + timedelta(minutes=rng.randint(12, 50)), f"IMPS/DR/{ref}/{l2_name}",
                                 "IMPS", l2, l2_name, debit=float(fwd), reference=ref, tag="layer:forward"))
            elif spec.plan == "upi_spray":
                remaining = int(total_in * rng.uniform(0.92, 0.98))
                n = rng.randint(3, 6)
                t = anchor + timedelta(minutes=rng.randint(10, 30))
                for k in range(n):
                    part = remaining if k == n - 1 else int(remaining / (n - k) * rng.uniform(0.7, 1.2))
                    remaining -= part
                    vpa = world.note_upi(ids.upi("pay"), "individual", "spray_recipient", cid)
                    st_m.add(Txn(t, f"UPI/DR/{vpa}", "UPI", vpa, "individual", debit=float(part),
                                 reference=ids.reference(), tag="spray:out"))
                    t += timedelta(minutes=rng.randint(6, 25))
            # "hold": nothing leaves the account.

            ensure_non_negative(st_m, buffer=100)
            world.statements.append((cid, st_m))

            if "gap_stmt" in spec.extras:
                gap_lo, gap_hi = datetime(2026, 8, 1), datetime(2026, 8, 10)
                part1 = Statement(m["acct"], m["bank"], m["name"], opening=st_m.opening,
                                  start=datetime(2026, 7, 1), end=datetime(2026, 7, 31, 23, 59, 59))
                part1.txns = [t for t in st_m.txns if t.time < gap_lo]
                bal = st_m.opening + sum(t.credit - t.debit for t in st_m.txns if t.time < gap_hi)
                part2 = Statement(m["acct"], m["bank"], m["name"], opening=round(bal, 2),
                                  start=gap_hi, end=datetime(2026, 8, 31, 23, 59, 59))
                part2.txns = [t for t in st_m.txns if t.time >= gap_hi]
                f1 = f"cases/{cid}/bank_statement_{m['acct']}_jul.csv"
                f2 = f"cases/{cid}/bank_statement_{m['acct']}_aug10-31.csv"
                out.write(f1, part1.to_csv(ids), case_id=cid, kind="bank_statement")
                out.write(f2, part2.to_csv(ids), case_id=cid, kind="bank_statement")
                stmt_files += [f1, f2]
                quality.append({"issue": "statement_date_gap", "case_id": cid, "files": [f1, f2],
                                "detail": "no statement covers 2026-08-01 to 2026-08-09; the victim credits and "
                                          "the withdrawals fall inside the gap"})
            elif "dmy_mule" in spec.extras:
                short = Statement(m["acct"], m["bank"], m["name"], opening=0.0, start=datetime(2026, 8, 1),
                                  end=datetime(2026, 8, 12, 23, 59, 59), date_style="dmy")
                short.opening = round(st_m.opening + sum(t.credit - t.debit for t in st_m.txns
                                                         if t.time < short.start), 2)
                short.txns = [t for t in st_m.txns if short.start <= t.time <= short.end]
                f = f"cases/{cid}/bank_statement_{m['acct']}.csv"
                out.write(f, short.to_csv(ids), case_id=cid, kind="bank_statement")
                stmt_files.append(f)
                quality.append({"issue": "ambiguous_date_format", "case_id": cid, "file": f,
                                "detail": "DD/MM/YYYY with every day <= 12, so day and month cannot be told apart "
                                          "from the file alone"})
            else:
                text = st_m.to_csv(ids)
                f = f"cases/{cid}/bank_statement_{m['acct']}.csv"
                out.write(f, text, case_id=cid, kind="bank_statement")
                stmt_files.append(f)
                if "dup_stmt" in spec.extras:
                    f_dup = f"cases/{cid}/bank_statement_{m['acct']}_copy_received_by_email.csv"
                    out.write(f_dup, text, case_id=cid, kind="bank_statement",
                              note="Byte-identical copy of the statement above")
                    stmt_files.append(f_dup)
                    quality.append({"issue": "duplicate_statement", "case_id": cid, "files": [f, f_dup],
                                    "detail": "same statement received twice; must count as one source"})

        if spec.official:
            row = kyc_row(world, acct=m["acct"], holder=m["name"], official=spec.official,
                          opening_date=f"2026-0{rng.choice([5, 6])}-{rng.randint(10, 28)}", mobile=m["phone"],
                          address=f"H.No. {rng.randint(10, 400)}, Ward {rng.randint(1, 12)}, "
                                  f"{rng.choice(['Ranipur', 'Devgarh', 'Kalyanpur'])}",
                          holder_type="Individual", upi=m["vpa"])
            out.write(f"cases/{cid}/kyc_response_{cid}.csv", rows_to_csv(KYC_COLUMNS, [row]), case_id=cid,
                      kind="kyc_response", note="Bank reply to notice: account-opening details")

        # --- narrative ------------------------------------------------------
        template_family, template = N.TEMPLATES[(spec.family, spec.lang)]
        item_en, item_hi = rng.choice(ITEMS)
        ctx = {
            "victim": victim, "gender": gender, "age": rng.randint(age_lo, age_hi),
            "occupation": rng.choice(occupations),
            "address": f"Flat {rng.randint(101, 1204)}, {rng.choice(['Shanti', 'Om', 'Green', 'Lake', 'Sun'])} "
                       f"{rng.choice(['Residency', 'Apartments', 'CHS', 'Enclave'])}, {locality}, {spec.city} {pin}",
            "city": spec.city, "phone": v_phone, "station": station, "caller": caller,
            "ack": f"3{last_time:%d%m%y}{rng.randint(100000, 999999)}", "victim_acct": v_acct,
            "victim_bank": BANKS[v_bank], "payments": payments, "complaint_date": complaint_date,
            "persona_m": world.names.person("M")[0], "persona_f": world.names.person("F")[0],
            "group": rng.choice(GROUPS),
            "app": rng.choice(APPS.get(spec.family, ["SynthTrade Pro"])),
            # A digital arrest runs for a day or two before any money moves.
            "contact_date": first - timedelta(days=rng.randint(1, 2)),
            "withdraw_date": last_time + timedelta(days=2),
            "fake_profit": fmt_inr(sum(spec.amounts) * rng.uniform(1.6, 2.4)),
            "item": item_en, "item_hi": item_hi, "place": rng.choice(["Pune cantonment", "Jaipur", "Ambala"]),
            "service": rng.choice(["flight", "hotel", "train"]),
        }
        if "shared_family_phone" in spec.extras:
            brother, _ = world.names.person("M")
            ctx["family_phone_note"] = (f"\n\nThe mobile number {v_phone} is used jointly by me and my brother "
                                        f"{brother}, who lives with me. He was not present during this call.")
            world.phones[v_phone]["shared_with"] = brother
        text = template(ctx)
        out.write(f"cases/{cid}/complaint_{cid}.txt", text, case_id=cid, kind="complaint",
                  language=spec.lang if spec.lang != "hg" else "hinglish")

        if "supp" in spec.extras:
            if spec.plan == "hold":
                note = (f"My bank has informed me by SMS that Rs. {fmt_inr(sum(spec.amounts))} has been put on "
                        f"hold in the beneficiary account after my 1930 complaint.")
            else:
                new_num = world.new_phone("unknown caller", "caller", cid)
                note = (f"On {N.d_en(complaint_date + timedelta(days=2))} I received another call from "
                        f"{new_num}. The caller said he was from a \"cyber recovery agency\" and could get my money "
                        f"back if I paid Rs. {fmt_inr(rng.choice([4999, 7500, 9999]))} as a processing fee. I did "
                        f"not pay.")
            ctx.update({"supp_note": note, "supp_date": complaint_date + timedelta(days=rng.randint(3, 6))})
            out.write(f"cases/{cid}/supplementary_statement_{cid}.txt", N.supplementary_en(ctx), case_id=cid,
                      kind="supplementary_statement")

        cases.append({
            "id": cid, "fir_no": f"{rng.randint(100, 999):04d}/2026", "city": spec.city, "station": station,
            "title": TITLES[spec.family], "registered_on": (complaint_date + timedelta(days=rng.randint(0, 2))).strftime("%Y-%m-%d"),
            "complainant": victim,
        })
        truth.append({
            "case_id": cid, "family": spec.family, "template_family": template_family, "language": spec.lang,
            "plan": spec.plan, "loss": sum(spec.amounts),
            "receiving_accounts": [{"account": x["acct"], "upi": x["vpa"], "holder": x["name"],
                                    "statement_obtained": (x is m and spec.plan != "none")} for x in mules],
            "opened_by": spec.official, "extras": sorted(spec.extras),
            "caller": caller, "shared_family_phone": v_phone if "shared_family_phone" in spec.extras else None,
        })
    return cases, truth, quality
