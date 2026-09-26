"""The flagship "Tri-City Digital Arrest" scenario, built by hand.

Hidden structure (spec, "Flagship scenario"):
  C-101 Mumbai     victim V1 loses 78,000 -> M1      caller P-77
  C-102 Delhi      victim V2 loses 58,000 -> M2      caller P-77 (shared with C-101)
  C-103 Bengaluru  victim V3 loses 39,000 -> M3      caller P-81 (no shared identifier)
  M1, M2, M3 each forward to HUB (Shree Balaji Traders) inside one 60-minute window.
  HUB sends 1,60,000 to a P2P seller; a seized chat (the trade record) links
  that payment to USDT sent to wallet W-1.
  M1, M2, M3 were all opened at branch B-17 by official E-45.
  M2 held 50,000 of salary before the victim's 58,000 arrived (mixed funds)
  and paid 2,000 to a grocery merchant in between.
  Two "Rahul Sharma" records: the M2 holder and a C-101 witness.

Every transfer carries one bank reference that appears on both sides, so two
statements showing the same transfer are two views of one bank record.
"""
from __future__ import annotations

from datetime import datetime

from .common import BANKS, DatasetWriter, Statement, Txn, at, fmt_inr, rows_to_csv
from .world import World, add_benign_activity, ensure_non_negative

KYC_COLUMNS = [
    "account_no", "account_type", "holder_name", "holder_type", "authorised_signatories",
    "father_or_spouse_name", "date_of_birth", "registered_mobile", "address", "id_document_type",
    "id_document_masked", "kyc_doc_sha256", "opening_date", "branch_code", "branch_name", "ifsc",
    "opening_official_id", "opening_official_name", "device_id_at_opening", "nominee", "linked_upi_ids",
]
CDR_COLUMNS = [
    "target_number", "other_number", "call_type", "start_time", "duration_sec",
    "imei", "imsi", "first_cell_id", "first_cell_address",
]

BRANCHES = {
    "B-17": {"bank": "XSSB", "ifsc": "XSSB0000017", "name": "Ranipur Main Road"},
    "B-22": {"bank": "XNDB", "ifsc": "XNDB0000022", "name": "Devgarh Market Yard"},
    "B-31": {"bank": "XKTB", "ifsc": "XKTB0000031", "name": "Kalyanpur Station Road"},
}
OFFICIALS = {
    "E-45": ("Vivek Chauhan", "B-17"),
    "E-46": ("Neha Kulshreshtha", "B-17"),
    "E-51": ("Sanjay Patil", "B-22"),
    "E-52": ("Farida Khan", "B-22"),
    "E-63": ("Arvind Nair", "B-31"),
    "E-64": ("Meenakshi Iyer", "B-31"),
}


def spaced_phone(n: str) -> str:
    return f"+91 {n[:5]} {n[5:]}"


def spaced_account(a: str) -> str:
    return " ".join(a[i:i + 4] for i in range(0, len(a), 4))


def kyc_row(world: World, *, acct: str, holder: str, official: str, opening_date: str, mobile: str,
            address: str, dob: str = "", relation: str = "", holder_type: str = "Individual",
            account_type: str = "Savings", signatories: str = "", nominee: str = "", upi: str = "") -> dict:
    name, branch = OFFICIALS[official]
    b = BRANCHES[branch]
    return {
        "account_no": acct, "account_type": account_type, "holder_name": holder, "holder_type": holder_type,
        "authorised_signatories": signatories, "father_or_spouse_name": relation, "date_of_birth": dob,
        "registered_mobile": mobile, "address": address,
        "id_document_type": "Aadhaar" if holder_type == "Individual" else "Partnership deed + PAN",
        "id_document_masked": world.ids.masked_aadhaar() if holder_type == "Individual" else "PAN XXXXX1234X",
        "kyc_doc_sha256": world.ids.sha256_token(), "opening_date": opening_date, "branch_code": branch,
        "branch_name": f"{BANKS[b['bank']]}, {b['name']}", "ifsc": b["ifsc"], "opening_official_id": official,
        "opening_official_name": name, "device_id_at_opening": world.ids.device_id(), "nominee": nominee,
        "linked_upi_ids": upi,
    }


def build_tri_city(world: World, out: DatasetWriter) -> dict:
    rng, ids = world.rng, world.ids

    # ---- identifiers -------------------------------------------------------
    p77 = world.new_phone("unknown caller (Telecom Dept / CBI impersonation)", "caller", "C-101")
    p81 = world.new_phone("unknown caller (Mumbai Police / CBI impersonation)", "caller", "C-103")
    v1_phone = world.new_phone("Shobha Kulkarni", "victim", "C-101")
    v2_phone = world.new_phone("Harish Chandra Bhatia", "victim", "C-102")
    v3_phone = world.new_phone("Kavitha Ramesh", "victim", "C-103")
    witness_phone = world.new_phone("Rahul Sharma (witness, C-101)", "witness", "C-101")
    son_phone = world.new_phone("Nitin Bhatia", "family", "C-102")
    m1_phone = world.new_phone("Sandeep Kumar Verma", "account_holder", None)
    m2_phone = world.new_phone("Rahul Sharma (M2 holder)", "account_holder", None)
    m3_phone = world.new_phone("Pooja Rawat", "account_holder", None)
    hub_phone = world.new_phone("Shree Balaji Traders (registered mobile)", "account_holder", None)
    sbt_chat_phone = world.new_phone("'SBT Accounts' WhatsApp contact", "chat_participant", None)
    seller_phone = world.new_phone("Aakash Jain (P2P seller)", "p2p_seller", None)
    imei_77 = ids.imei()
    imsi_77 = ids.imsi()

    v1_acct, v1_bank = world.new_account("Shobha Anant Kulkarni", "victim", "C-101", bank="XGSB")
    v2_acct, v2_bank = world.new_account("Harish Chandra Bhatia", "victim", "C-102", bank="XKTB")
    v3_acct, v3_bank = world.new_account("Kavitha Ramesh", "victim", "C-103", bank="XYFB")
    m1, _ = world.new_account("Sandeep Kumar Verma", "mule", "C-101", bank="XSSB")
    m2, _ = world.new_account("Rahul Sharma", "mule", "C-102", bank="XSSB")
    m3, _ = world.new_account("Pooja Rawat", "mule", "C-103", bank="XSSB")
    hub, _ = world.new_account("Shree Balaji Traders", "hub", None, bank="XNDB")
    p2p, _ = world.new_account("Aakash Jain", "p2p_seller", None, bank="XYFB")
    w1 = ids.tron_wallet()
    usdt_txid = "%064x" % rng.getrandbits(256)

    grocery_name = "Om Sai Kirana Stores"
    grocery_vpa = world.note_upi(ids.upi("omsaikirana"), grocery_name, "merchant", "C-102")
    m2_employer = "Vardhman Synthetic Textiles Pvt Ltd"
    m2_employer_acct, _ = world.new_account(m2_employer, "employer", "C-102")
    m2_landlord_acct, _ = world.new_account("Suresh Thakur", "landlord", "C-102")
    m2_family_acct, _ = world.new_account("Mohan Lal Sharma", "family", "C-102")
    m1_friend_vpa = world.note_upi(ids.upi("ganeshyadav"), "Ganesh Yadav", "individual", None)
    m3_friend_vpa = world.note_upi(ids.upi("ritunegi"), "Ritu Negi", "individual", None)
    m3_shop_vpa = world.note_upi(ids.upi("ranipurmobile"), "Ranipur Mobile Point", "merchant", None)
    ranipur_power = world.note_upi(ids.upi("ranipurpower"), "Ranipur Synthetic Power Co-op", "utility_biller", None)

    r = {k: ids.reference() for k in ["V1-M1", "V2-M2", "V3-M3", "M1-HUB", "M2-HUB", "M3-HUB", "HUB-P2P"]}
    ack = {c: f"3{d}{rng.randint(100000, 999999)}" for c, d in
           [("C-101", "120826"), ("C-102", "120826"), ("C-103", "130826")]}

    T = {
        "V1-M1": at(12, 10, 5), "V2-M2": at(12, 10, 24), "V3-M3": at(12, 10, 47),
        "M1-HUB": at(12, 10, 31), "M2-HUB": at(12, 10, 52), "M3-HUB": at(12, 11, 14),
        "M2-GROCERY": at(12, 10, 38), "HUB-P2P": at(12, 12, 10),
    }

    # ---- victim statements ------------------------------------------------
    victims = [
        ("C-101", "V1", v1_acct, v1_bank, "Shobha Anant Kulkarni", "Mumbai", 78000, "V1-M1", m1,
         "Sandeep Kumar Verma", at(10, 0, 0)),
        ("C-102", "V2", v2_acct, v2_bank, "Harish Chandra Bhatia", "Delhi", 58000, "V2-M2", m2,
         "Rahul Sharma", at(11, 0, 0)),
        ("C-103", "V3", v3_acct, v3_bank, "Kavitha Ramesh", "Bengaluru", 39000, "V3-M3", m3,
         "Pooja Rawat", at(11, 0, 0)),
    ]
    for case_id, label, acct, bank, holder, city, amount, key, mule, mule_holder, arrest_start in victims:
        st = Statement(acct, bank, holder, opening=float(rng.choice([145000, 190000, 230000])))
        add_benign_activity(world, st, case_id=case_id, city=city, profile="pensioner",
                            start=st.start, end=st.end, grocery_per_month=10,
                            avoid=[(arrest_start, at(12, 23, 59))])
        st.add(Txn(T[key], f"IMPS/P2A/{r[key]}/{mule_holder}", "IMPS", mule, mule_holder,
                   debit=float(amount), reference=r[key], tag=f"tri:{key}"))
        ensure_non_negative(st, buffer=3000)
        world.statements.append((case_id, st))
        out.write(f"cases/{case_id}/bank_statement_{label}_{acct}.csv", st.to_csv(ids), case_id=case_id,
                  kind="bank_statement", note=f"Victim account statement ({label})")

    # ---- M1 ------------------------------------------------------------------
    st_m1 = Statement(m1, "XSSB", "Sandeep Kumar Verma", opening=1250.0)
    st_m1.add(Txn(at(8, 13, 22, month=7), "UPI/P2P/Ganesh Yadav", "UPI", m1_friend_vpa, "Ganesh Yadav",
                  credit=2000.0, reference=ids.reference()))
    st_m1.add(Txn(at(20, 18, 5, month=7), "ATM WDL/SYNATM40417/RANIPUR", "ATM", "SYNATM40417",
                  "ATM cash withdrawal", debit=2000.0))
    st_m1.add(Txn(T["V1-M1"], f"IMPS/P2A/{r['V1-M1']}/Shobha A Kulkarni", "IMPS", v1_acct,
                  "Shobha A Kulkarni", credit=78000.0, reference=r["V1-M1"], tag="tri:V1-M1"))
    st_m1.add(Txn(T["M1-HUB"], f"IMPS/P2A/{r['M1-HUB']}/SHREE BALAJI TRADERS", "IMPS", hub,
                  "SHREE BALAJI TRADERS", debit=77000.0, reference=r["M1-HUB"], tag="tri:M1-HUB"))
    st_m1.add(Txn(at(19, 20, 41), "ATM WDL/SYNATM40417/RANIPUR", "ATM", "SYNATM40417",
                  "ATM cash withdrawal", debit=2000.0))
    world.statements.append(("C-101", st_m1))
    out.write(f"cases/C-101/bank_statement_M1_{m1}.csv", st_m1.to_csv(ids), case_id="C-101",
              kind="bank_statement", note="Bank response: statement of beneficiary account named in complaint")

    # ---- M2 (mixed funds: exact figures are part of the scenario) ------------
    st_m2 = Statement(m2, "XSSB", "Rahul Sharma", opening=1000.0)
    def m2t(day, hh, mm, desc, ch, cp, cpn, debit=0.0, credit=0.0, month=7, ref=True, tag=""):
        st_m2.add(Txn(at(day, hh, mm, month=month), desc, ch, cp, cpn, debit=debit, credit=credit,
                      reference=ids.reference() if ref else "", tag=tag))
    m2t(1, 9, 12, f"NEFT SAL JUL26/{m2_employer}", "NEFT", m2_employer_acct, m2_employer, credit=50000.0)
    m2t(4, 19, 2, f"UPI/P2M/{grocery_name}", "UPI-P2M", grocery_vpa, grocery_name, debit=1240.0)
    m2t(5, 10, 30, "IMPS/RENT/Suresh Thakur", "IMPS", m2_landlord_acct, "Suresh Thakur", debit=14000.0)
    m2t(9, 20, 15, f"UPI/P2M/{grocery_name}", "UPI-P2M", grocery_vpa, grocery_name, debit=860.0)
    m2t(12, 11, 0, "ATM WDL/SYNATM40417/RANIPUR", "ATM", "SYNATM40417", "ATM cash withdrawal", debit=5000.0, ref=False)
    m2t(15, 18, 40, "UPI/BILLPAY/Ranipur Synthetic Power Co-op", "UPI-P2M", ranipur_power,
        "Ranipur Synthetic Power Co-op", debit=1520.0)
    m2t(18, 12, 5, "IMPS/Mohan Lal Sharma/FAMILY", "IMPS", m2_family_acct, "Mohan Lal Sharma", debit=10000.0)
    m2t(22, 19, 48, f"UPI/P2M/{grocery_name}", "UPI-P2M", grocery_vpa, grocery_name, debit=1180.0)
    m2t(26, 17, 30, "ATM WDL/SYNATM40417/RANIPUR", "ATM", "SYNATM40417", "ATM cash withdrawal", debit=5000.0, ref=False)
    m2t(29, 13, 15, "IMPS/Mohan Lal Sharma/FAMILY", "IMPS", m2_family_acct, "Mohan Lal Sharma", debit=9720.0)
    m2t(1, 9, 5, f"NEFT SAL AUG26/{m2_employer}", "NEFT", m2_employer_acct, m2_employer, credit=50000.0, month=8)
    m2t(6, 18, 22, "UPI/BILLPAY/Ranipur Synthetic Power Co-op", "UPI-P2M", ranipur_power,
        "Ranipur Synthetic Power Co-op", debit=2480.0, month=8)
    st_m2.add(Txn(T["V2-M2"], f"IMPS/P2A/{r['V2-M2']}/HARISH C BHATIA", "IMPS", v2_acct, "HARISH C BHATIA",
                  credit=58000.0, reference=r["V2-M2"], tag="tri:V2-M2"))
    st_m2.add(Txn(T["M2-GROCERY"], f"UPI/P2M/{grocery_name}", "UPI-P2M", grocery_vpa, grocery_name,
                  debit=2000.0, reference=ids.reference(), tag="tri:M2-GROCERY"))
    st_m2.add(Txn(T["M2-HUB"], f"IMPS/P2A/{r['M2-HUB']}/SHREE BALAJI TRADERS", "IMPS", hub,
                  "SHREE BALAJI TRADERS", debit=60000.0, reference=r["M2-HUB"], tag="tri:M2-HUB"))
    m2t(14, 11, 10, "IMPS/RENT/Suresh Thakur", "IMPS", m2_landlord_acct, "Suresh Thakur", debit=14000.0, month=8)
    m2t(18, 20, 2, f"UPI/P2M/{grocery_name}", "UPI-P2M", grocery_vpa, grocery_name, debit=740.0, month=8)
    m2t(23, 16, 44, "ATM WDL/SYNATM40417/RANIPUR", "ATM", "SYNATM40417", "ATM cash withdrawal", debit=5000.0,
        month=8, ref=False)
    m2t(27, 12, 30, "IMPS/Mohan Lal Sharma/FAMILY", "IMPS", m2_family_acct, "Mohan Lal Sharma", debit=8000.0, month=8)
    world.statements.append(("C-102", st_m2))
    out.write(f"cases/C-102/bank_statement_M2_{m2}.csv", st_m2.to_csv(ids), case_id="C-102",
              kind="bank_statement", note="Bank response: statement of beneficiary account named in complaint")

    # ---- M3 ------------------------------------------------------------------
    st_m3 = Statement(m3, "XSSB", "Pooja Rawat", opening=640.0)
    st_m3.add(Txn(at(14, 16, 3, month=7), "UPI/P2P/Ritu Negi", "UPI", m3_friend_vpa, "Ritu Negi",
                  credit=500.0, reference=ids.reference()))
    st_m3.add(Txn(at(30, 11, 47, month=7), "UPI/P2M/Ranipur Mobile Point", "UPI-P2M", m3_shop_vpa,
                  "Ranipur Mobile Point", debit=500.0, reference=ids.reference()))
    st_m3.add(Txn(T["V3-M3"], f"IMPS/P2A/{r['V3-M3']}/KAVITHA RAMESH", "IMPS", v3_acct, "KAVITHA RAMESH",
                  credit=39000.0, reference=r["V3-M3"], tag="tri:V3-M3"))
    st_m3.add(Txn(T["M3-HUB"], f"IMPS/P2A/{r['M3-HUB']}/SHREE BALAJI TRADERS", "IMPS", hub,
                  "SHREE BALAJI TRADERS", debit=38500.0, reference=r["M3-HUB"], tag="tri:M3-HUB"))
    world.statements.append(("C-103", st_m3))
    out.write(f"cases/C-103/bank_statement_M3_{m3}.csv", st_m3.to_csv(ids), case_id="C-103",
              kind="bank_statement", note="Bank response: statement of beneficiary account named in complaint")

    # ---- HUB -----------------------------------------------------------------
    st_hub = Statement(hub, "XNDB", "Shree Balaji Traders", opening=0.0)
    cust_a, _ = world.new_account("Gupta Hardware Mart", "customer", None)
    cust_b, _ = world.new_account("Vinayak Plastics", "customer", None)
    supp_a, _ = world.new_account("Devgarh Packaging Co", "supplier", None)
    st_hub.add(Txn(at(1, 12, 40, month=7), "CASH DEP/PARTNER CAPITAL", "CASH", "", "Cash deposit", credit=10000.0))
    st_hub.add(Txn(at(9, 15, 12, month=7), "IMPS/Gupta Hardware Mart/INV 0041", "IMPS", cust_a,
                   "Gupta Hardware Mart", credit=14500.0, reference=ids.reference()))
    st_hub.add(Txn(at(16, 11, 5, month=7), "IMPS/Devgarh Packaging Co/PO 118", "IMPS", supp_a,
                   "Devgarh Packaging Co", debit=12800.0, reference=ids.reference()))
    st_hub.add(Txn(at(24, 14, 30, month=7), "IMPS/Vinayak Plastics/INV 0047", "IMPS", cust_b,
                   "Vinayak Plastics", credit=6200.0, reference=ids.reference()))
    st_hub.add(Txn(at(30, 16, 50, month=7), "IMPS/Devgarh Packaging Co/PO 121", "IMPS", supp_a,
                   "Devgarh Packaging Co", debit=9500.0, reference=ids.reference()))
    st_hub.add(Txn(T["M1-HUB"], f"IMPS/P2A/{r['M1-HUB']}/SANDEEP KUMAR VERMA", "IMPS", m1,
                   "SANDEEP KUMAR VERMA", credit=77000.0, reference=r["M1-HUB"], tag="tri:M1-HUB"))
    st_hub.add(Txn(T["M2-HUB"], f"IMPS/P2A/{r['M2-HUB']}/RAHUL SHARMA", "IMPS", m2,
                   "RAHUL SHARMA", credit=60000.0, reference=r["M2-HUB"], tag="tri:M2-HUB"))
    st_hub.add(Txn(T["M3-HUB"], f"IMPS/P2A/{r['M3-HUB']}/POOJA RAWAT", "IMPS", m3,
                   "POOJA RAWAT", credit=38500.0, reference=r["M3-HUB"], tag="tri:M3-HUB"))
    st_hub.add(Txn(T["HUB-P2P"], f"IMPS/P2A/{r['HUB-P2P']}/AAKASH JAIN", "IMPS", p2p, "AAKASH JAIN",
                   debit=160000.0, reference=r["HUB-P2P"], tag="tri:HUB-P2P"))
    st_hub.add(Txn(at(21, 3, 0), "ACCOUNT MAINTENANCE CHARGES INCL GST", "CHARGES", "", "Bank charges",
                   debit=1180.0))
    world.statements.append(("C-101", st_hub))
    out.write(f"cases/C-101/bank_statement_HUB_{hub}.csv", st_hub.to_csv(ids), case_id="C-101",
              kind="bank_statement", note="Bank response: statement of account receiving funds from M1")

    # ---- KYC responses -------------------------------------------------------
    kyc = {
        "C-101": [kyc_row(world, acct=m1, holder="Sandeep Kumar Verma", official="E-45", opening_date="2026-06-16",
                          mobile=m1_phone, address="H.No. 45, Ward 3, Near Bus Stand, Ranipur",
                          dob="1998-11-02", relation="Ramesh Verma", nominee="Kamla Verma"),
                  kyc_row(world, acct=hub, holder="Shree Balaji Traders", official="E-51", opening_date="2026-07-01",
                          mobile=hub_phone, address="Shop 14, Laxmi Complex, Devgarh Market Yard, Devgarh",
                          holder_type="Partnership firm", account_type="Current",
                          signatories="Mahesh Agarwal; Sunita Agarwal")],
        "C-102": [kyc_row(world, acct=m2, holder="Rahul Sharma", official="E-45", opening_date="2026-06-18",
                          mobile=m2_phone, address="H.No. 112, Ward 7, Ranipur", dob="1995-03-14",
                          relation="Mohan Lal Sharma", nominee="Mohan Lal Sharma")],
        "C-103": [kyc_row(world, acct=m3, holder="Pooja Rawat", official="E-45", opening_date="2026-06-22",
                          mobile=m3_phone, address="Near Hanuman Mandir, Ward 9, Ranipur", dob="2000-07-19",
                          relation="Dinesh Rawat", nominee="Dinesh Rawat")],
    }
    for case_id, rows in kyc.items():
        out.write(f"cases/{case_id}/kyc_response_{case_id}.csv", rows_to_csv(KYC_COLUMNS, rows), case_id=case_id,
                  kind="kyc_response", note="Bank reply to notice: account-opening details")

    # ---- CDR of P-77 (obtained in C-101) ------------------------------------
    cells = [("404-10-2231-45012", "Tower 12, Kalyanpur Industrial Area"),
             ("404-10-2231-45019", "Tower 19, Kalyanpur Bypass Road")]
    cdr_rows = []
    others = [world.new_phone("unidentified subscriber", "other", None) for _ in range(6)]
    def cdr(t: datetime, other: str, kind: str, dur: int):
        cid, addr = rng.choice(cells)
        cdr_rows.append({"target_number": p77, "other_number": other, "call_type": kind,
                         "start_time": t.strftime("%Y-%m-%d %H:%M:%S"), "duration_sec": dur,
                         "imei": imei_77, "imsi": imsi_77, "first_cell_id": cid, "first_cell_address": addr})
    for i, o in enumerate(others):
        cdr(at(8 + i % 2, 10 + i, rng.randint(0, 59)), o, rng.choice(["MOC", "MTC"]), rng.randint(20, 400))
    cdr(at(10, 11, 15), v1_phone, "MOC", 420)
    cdr(at(10, 11, 30), v1_phone, "SMS-MO", 0)
    cdr(at(11, 9, 50), v1_phone, "MOC", 95)
    cdr(at(11, 10, 32), v2_phone, "MOC", 610)
    cdr(at(11, 18, 4), others[2], "MTC", 44)
    cdr(at(12, 9, 35), v1_phone, "MOC", 140)
    cdr(at(12, 9, 58), v2_phone, "MOC", 88)
    cdr(at(12, 12, 41), others[4], "MOC", 31)
    cdr_rows.sort(key=lambda row: row["start_time"])
    out.write(f"cases/C-101/cdr_P-77_{p77}.csv", rows_to_csv(CDR_COLUMNS, cdr_rows), case_id="C-101",
              kind="cdr", note="Telecom service provider response: CDR of calling number")

    # ---- narratives ---------------------------------------------------------
    c101 = f"""To,
The Senior Inspector,
Cyber Police Station (West Region), Mumbai

Subject: Complaint regarding loss of Rs. 78,000 to persons impersonating Telecom Department and CBI officers

I, Shobha Anant Kulkarni, aged 67 years, retired school teacher, residing at Flat 304, Sai Kripa CHS, Andheri East, Mumbai 400069, mobile {spaced_phone(v1_phone)}, state as follows.

On 10 August 2026 at about 11:15 am I received a call on my mobile from {spaced_phone(p77)}. The caller said he was calling from the Telecom Department and that a SIM card issued on my Aadhaar was being used to send illegal advertisements and for money laundering, and that all my numbers would be blocked within two hours. He then transferred the call to a person who introduced himself as Inspector Vinod Rathore of the CBI, Mumbai.

Inspector Rathore asked me to join a WhatsApp video call. On the video call he was wearing a uniform and I could see an office with a CBI logo behind him. He said that an account opened with my Aadhaar had received Rs. 2.6 crore of money laundering proceeds and that a case had been registered against me. He said I was under "digital arrest", that I must keep the camera on at all times and must not tell anyone, including my family, otherwise I would be arrested immediately. He showed me a letter on the screen with Supreme Court and RBI seals.

I remained on the video call for most of the day on 10 and 11 August. On 12 August at about 9:40 am he told me that to prove my innocence I must transfer my funds to an "RBI verification account" for fund verification, and that the money would be returned within 24 hours after verification. He gave me the following account: Account number {m1}, IFSC XSSB0000017, Sahyadri Synthetic Bank, account name Sandeep Kumar Verma.

At 10:05 am on 12 August 2026 I transferred Rs. 78,000 by IMPS from my account {v1_acct} with {BANKS[v1_bank]}, Andheri East branch. The transaction reference number is {r['V1-M1']}.

After the transfer the video call was disconnected. When I called {spaced_phone(p77)} again the phone was switched off. In the evening I told my neighbour Mr. Rahul Sharma, who told me that this was a fraud and helped me report it on the cyber crime helpline 1930 (acknowledgement number {ack['C-101']}).

I request you to register my complaint and take action to recover my money. I am attaching my bank statement and screenshots of the WhatsApp chat.

Date: 13 August 2026
Shobha A. Kulkarni
"""
    out.write("cases/C-101/complaint_C-101_victim.txt", c101, case_id="C-101", kind="complaint",
              live_upload=True, note="Tri-City complaint (Mumbai)")

    witness = f"""STATEMENT OF WITNESS
Recorded on 13 August 2026 at Cyber Police Station (West Region), Mumbai
FIR No. 0412/2026

Name: Rahul Sharma, S/o Rajesh Sharma
Age: 34 years, Occupation: Software tester
Address: Flat 305, Sai Kripa CHS, Andheri East, Mumbai 400069
Mobile: {witness_phone}
Identity document: Aadhaar {ids.masked_aadhaar()}

I am the neighbour of Smt. Shobha Kulkarni. On 12 August 2026 at about 7:30 pm she came to my flat in a distressed state and told me that she had been on a video call with persons claiming to be CBI officers for three days, and that she had transferred Rs. 78,000 to an "RBI verification account" on their instructions.

I checked her phone and saw WhatsApp messages from the number {p77}, including a document titled "Arrest Warrant" with a CBI logo. I told her that this is a known fraud and helped her call the 1930 helpline the same evening.

I do not know the callers. I have not received any call from these numbers myself. I have no connection with any bank account mentioned in her complaint.

Read over and admitted correct.
Rahul Sharma
"""
    out.write("cases/C-101/witness_statement_C-101_rahul_sharma.txt", witness, case_id="C-101",
              kind="witness_statement", note="Witness is a different person from the M2 account holder (FX-01)")

    c102 = f"""To
The Station House Officer
Cyber Police Station, North-West District, Delhi

Sub: Online fraud of Rs 58,000 by fake CBI officers - request for FIR

Sir,

I am Harish Chandra Bhatia, 71 years, retired Section Officer (Government of India), resident of House No. B-9/112, Sector 9, Rohini, Delhi 110085. My mobile number is {v2_phone}. This complaint is written by my son Nitin Bhatia on my behalf.

On 11 August 2026 at around 10:30 am I got a call from mobile no. {p77}. The caller said he was from TRAI / Telecom Department and that my Aadhaar was linked to a SIM used in a money laundering case in Mumbai. He connected me to one Inspector Vinod Rathore, CBI, who then made a WhatsApp video call. Later a senior officer who called himself DCP Anil Mehra also joined the video call.

They said that I was under digital arrest and I must stay on video call and not tell my son or anyone. They showed me an arrest warrant and a Supreme Court order on screen. I stayed on the video call from 11 August till 12 August morning. They said my savings must be verified by RBI and I have to transfer money to an RBI-supervised account, and it will be refunded after verification.

On 12 August 2026 at 10:24 am I transferred Rs 58,000 through IMPS from my {BANKS[v2_bank]} account no. {v2_acct} to the account given by them:
Beneficiary name: Rahul Sharma
Account no.: {spaced_account(m2)}
IFSC: XSSB0000017 (Sahyadri Synthetic Bank)
UTR / reference: {r['V2-M2']}

After this they stopped responding. My son came home in the afternoon and understood it was a fraud. We complained on 1930 on 12 August, acknowledgement no. {ack['C-102']}.

Kindly register FIR and help recover the amount.

Harish Chandra Bhatia
14 August 2026
"""
    out.write("cases/C-102/complaint_C-102_victim.txt", c102, case_id="C-102", kind="complaint",
              live_upload=True, note="Tri-City complaint (Delhi)")

    supp102 = f"""SUPPLEMENTARY STATEMENT
FIR No. 0287/2026, Cyber Police Station, North-West District, Delhi
Statement of Nitin Bhatia, S/o Harish Chandra Bhatia, age 39, mobile {son_phone}

On 15 August 2026 I checked my father's WhatsApp. The number {p77} had sent him a PDF titled "Supreme Court Order - Money Laundering" and a photo of an ID card in the name of "Inspector Vinod Rathore, CBI". The same number made the WhatsApp video calls on 11 and 12 August.

My father also told me that the caller had asked for his PAN card photo, which he sent on 11 August. We have not received any refund. I am submitting the screenshots on a pen drive.

Nitin Bhatia
16 August 2026
"""
    out.write("cases/C-102/supplementary_statement_C-102.txt", supp102, case_id="C-102",
              kind="supplementary_statement")

    c103 = f"""To,
The Police Inspector,
CEN Police Station, South Division, Bengaluru

Subject: Complaint about Rs. 39,000 taken by fake police and CBI officers through video call

Respected Sir/Madam,

I, Kavitha Ramesh, aged 58 years, retired bank officer, residing at No. 27, 11th Cross, Jayanagar 4th Block, Bengaluru 560011, mobile +91-{v3_phone}, submit this complaint.

On 11 August 2026 at about 4:05 pm I received a call from +91-{p81}. The caller said that a courier parcel booked in my name from Mumbai to Taiwan had been stopped, and that it contained five passports, bank cards and 140 grams of MDMA. He said the Mumbai Police Cyber Crime branch had registered a case, and he connected me on a Skype video call to an officer who said he was Rakesh Kumar from the CBI.

The officer said my Aadhaar was used to open accounts for money laundering and that I was now under "digital arrest". I was told to stay on the Skype call with the camera on, not to close the door of my room, and not to inform my husband or anyone else, otherwise my family would also be arrested. I stayed on the call for about 26 hours.

On the morning of 12 August he said that my funds had to be checked by the Reserve Bank and must be kept in an "RBI secure custody account" for verification, and would be returned the same day after the enquiry. At 10:47 am on 12 August 2026 I sent Rs. 39,000 by IMPS from my {BANKS[v3_bank]} account {v3_acct} to account number {m3}, IFSC XSSB0000017, in the name of Pooja Rawat. Reference number {r['V3-M3']}.

After the payment the Skype call ended and the number {p81} has been switched off since then. My husband helped me report on 1930 on 13 August (acknowledgement {ack['C-103']}).

I request you to take necessary action.

Kavitha Ramesh
16 August 2026
"""
    out.write("cases/C-103/complaint_C-103_victim.txt", c103, case_id="C-103", kind="complaint",
              live_upload=True, note="Tri-City complaint (Bengaluru); no identifier shared with C-101/C-102")

    supp103 = f"""SUPPLEMENTARY STATEMENT
FIR No. 0198/2026, CEN Police Station, South Division, Bengaluru
Statement of Kavitha Ramesh, recorded on 18 August 2026

On 14 August 2026 at about 11:00 am I again received a call from {p81}. The same person who called himself Rakesh Kumar of CBI said that my verification was almost complete but that I must pay Rs. 25,000 as a "clearance fee" to release my earlier amount. I did not pay and disconnected the call.

On Skype his display name was "CBI Mumbai Crime Branch". He had asked me to install Skype on 11 August before the video call started. I have given my phone to the police for taking screenshots.

Kavitha Ramesh
"""
    out.write("cases/C-103/supplementary_statement_C-103.txt", supp103, case_id="C-103",
              kind="supplementary_statement")

    # ---- seized chat (the trade record) --------------------------------------
    rate = 89.90
    usdt = int(160000 / rate * 100) / 100  # truncated to cents, as a seller would quote
    chat = f"""WhatsApp chat export
Source: mobile phone of Aakash Jain (P2P USDT seller), seized under seizure memo SM-0412/2026, FIR No. 0412/2026, Cyber Police Station (West Region), Mumbai
Chat with: "SBT Accounts" (+91 {sbt_chat_phone})
Seller's own number: +91 {seller_phone}

12/08/26, 11:20 am - SBT Accounts: need {int(round(usdt))} usdt trc20 today. rate?
12/08/26, 11:24 am - Aakash Jain: 89.90. {int(round(usdt))} usdt = {fmt_inr(round(usdt) * rate)}. send 1,60,000 i will adjust
12/08/26, 11:25 am - SBT Accounts: ok. sending from current a/c Shree Balaji Traders
12/08/26, 11:26 am - SBT Accounts: wallet {w1}
12/08/26, 11:26 am - Aakash Jain: send only after 12. bank limit
12/08/26, 12:10 pm - SBT Accounts: sent 1,60,000 IMPS ref {r['HUB-P2P']}
12/08/26, 12:14 pm - Aakash Jain: received 1,60,000 in a/c ending {p2p[-4:]}. releasing
12/08/26, 12:21 pm - Aakash Jain: sent {usdt:.2f} USDT to {w1}
12/08/26, 12:21 pm - Aakash Jain: txid {usdt_txid}
12/08/26, 12:22 pm - SBT Accounts: recd. thanks
"""
    out.write("cases/C-101/seized_chat_p2p_seller.txt", chat, case_id="C-101", kind="chat_log",
              note="Trade record linking HUB -> P2P payment to USDT sent to W-1")

    labels = {
        "P-77": {"type": "phone", "value": p77, "role": "caller in C-101 and C-102"},
        "P-81": {"type": "phone", "value": p81, "role": "caller in C-103"},
        "V1": {"type": "bank_account", "value": v1_acct, "holder": "Shobha Anant Kulkarni", "case": "C-101"},
        "V2": {"type": "bank_account", "value": v2_acct, "holder": "Harish Chandra Bhatia", "case": "C-102"},
        "V3": {"type": "bank_account", "value": v3_acct, "holder": "Kavitha Ramesh", "case": "C-103"},
        "V1-phone": {"type": "phone", "value": v1_phone},
        "V2-phone": {"type": "phone", "value": v2_phone},
        "M1": {"type": "bank_account", "value": m1, "holder": "Sandeep Kumar Verma", "ifsc": "XSSB0000017"},
        "M2": {"type": "bank_account", "value": m2, "holder": "Rahul Sharma", "ifsc": "XSSB0000017"},
        "M3": {"type": "bank_account", "value": m3, "holder": "Pooja Rawat", "ifsc": "XSSB0000017"},
        "HUB": {"type": "bank_account", "value": hub, "holder": "Shree Balaji Traders", "ifsc": "XNDB0000022",
                "opened": "2026-07-01"},
        "P2P": {"type": "bank_account", "value": p2p, "holder": "Aakash Jain"},
        "W-1": {"type": "crypto_wallet", "value": w1, "network": "TRON (TRC20)"},
        "B-17": {"type": "bank_branch", "value": "XSSB0000017", "name": "Sahyadri Synthetic Bank, Ranipur Main Road"},
        "E-45": {"type": "bank_official", "value": "E-45", "name": "Vivek Chauhan"},
        "GROCERY": {"type": "upi", "value": grocery_vpa, "holder": grocery_name},
        "RAHUL-M2": {"type": "person", "phone": m2_phone, "note": "M2 account holder (KYC in C-102)"},
        "RAHUL-WITNESS": {"type": "person", "phone": witness_phone, "note": "Witness in C-101"},
        "IMEI-P77": {"type": "imei", "value": imei_77},
    }
    transfers = [
        {"id": k, "reference": r[k], "time": T[k].strftime("%Y-%m-%d %H:%M:%S"), "amount": amt}
        for k, amt in [("V1-M1", 78000), ("V2-M2", 58000), ("V3-M3", 39000), ("M1-HUB", 77000),
                       ("M2-HUB", 60000), ("M3-HUB", 38500), ("HUB-P2P", 160000)]
    ]
    return {
        "summary": "Tri-City Digital Arrest: three victims in three cities, three mule accounts opened at one "
                   "branch by one official, converging on a partnership-firm current account that converts "
                   "funds to USDT via a P2P seller.",
        "labels": labels,
        "transfers": transfers,
        "victim_loss_total": 175000,
        "mixed_funds": {
            "account": "M2",
            "before_victim_credit": {"balance": 50000, "source": "August salary"},
            "victim_credit": 58000,
            "grocery_payment": 2000,
            "onward_to_hub": 60000,
            "note": "Attribution of the 60,000 depends on method (FIFO/LIFO/pro-rata); computed by the engine, "
                    "not asserted here.",
        },
        "expected_observations": [
            {"rule": "SHARED-ID-v1", "subject": "P-77", "cases": ["C-101", "C-102"]},
            {"rule": "SHARED-ID-v1", "subject": "HUB", "cases": ["C-101", "C-102", "C-103"],
             "via": "M2 and M3 statements name HUB; HUB statement is in C-101"},
            {"rule": "SHARED-ID-v1", "subject": "M2", "cases": ["C-101", "C-102"], "via": "HUB statement"},
            {"rule": "SHARED-ID-v1", "subject": "M3", "cases": ["C-101", "C-103"], "via": "HUB statement"},
            {"rule": "SHARED-ID-v1", "subject": "V2-phone", "cases": ["C-101", "C-102"],
             "via": "victim number in the P-77 CDR; ordinary explanation: the victim was called"},
            {"rule": "CONVERGENCE-v1", "subject": "HUB", "window": ["2026-08-12 10:31", "2026-08-12 11:14"],
             "accounts": ["M1", "M2", "M3"]},
            {"rule": "LAYERING-v1", "subject": "V -> M -> HUB -> P2P", "note": "HUB forwards 1,60,000 of "
             "1,75,500 received within 56 minutes"},
            {"rule": "CASHOUT-v1", "subject": "HUB -> P2P -> W-1", "requires": "seized_chat_p2p_seller.txt"},
            {"rule": "FACILITATOR-v1", "subject": "B-17 + E-45", "accounts": ["M1", "M2", "M3"]},
            {"rule": "MO-MATCH-v1", "subject": "C-103", "compare_with": ["C-101", "C-102"],
             "matching_attributes": ["impersonated agency (CBI)", "payment instruction (RBI verification / "
                                     "custody account)", "contact channel (video call)", "duration (multi-day "
                                     "digital arrest)"],
             "differs": ["pretext: SIM misuse vs courier parcel"]},
            {"rule": "ORDINARY-PAYMENT-v1", "subject": "M2 -> GROCERY 2,000", "note": "flag for verification, "
             "never clear"},
        ],
        "expected_silent": [
            {"rule": "FRONT-ENTITY-v1", "subject": "HUB", "reason": "opened < 90 days and >= 2 complaint-linked "
             "credits, but its address and phone are not shared with another flagged entity"},
        ],
        "identity": {
            "FX-01": {"records": ["RAHUL-M2", "RAHUL-WITNESS"], "expected": "kept separate; conflict shown",
                      "differences": ["phone", "Aadhaar", "father's name", "address"]},
        },
        "challenge": {
            "FX-26": {"operation": "exclude_source", "target": "bank record for M3 -> HUB",
                      "reference": r["M3-HUB"],
                      "records": ["M3 statement debit row", "HUB statement credit row"],
                      "note": "Both rows carry one bank reference: two views of one record, one source group.",
                      "expected": "CONVERGENCE-v1 threshold not met (2 of 3); M1->HUB and M2->HUB still "
                                  "supported; estimates recompute; live case unchanged until a reviewed change "
                                  "is applied"},
        },
    }
