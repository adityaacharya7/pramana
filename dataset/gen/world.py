"""The generation context plus ordinary (benign) account activity.

Most transactions in the dataset are ordinary: pensions, salaries, rent,
groceries, bills, family transfers and ATM use. They are what the rules have
to stay silent on.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .common import BANKS, IdGen, Statement, Txn
from .people import EMPLOYERS, SHOP_PREFIX, SHOP_WORDS, NameGen

CITY_BILLERS = {
    # One power distributor per city, shared by every victim in that city who
    # pays a bill. SHARED-ID-v1 will see these across cases; they are the
    # documented "known biller" hard negative, not a hidden link.
    "Mumbai": ("Maharashtra Synthetic Power Distribution Ltd", "msynpower.bill@synupi"),
    "Delhi": ("Delhi Demo Electricity Supply Co", "ddemoelec.bill@synupi"),
    "Bengaluru": ("Karnataka Test Power Corporation", "ktestpower.bill@synupi"),
}


@dataclass
class World:
    rng: random.Random
    ids: IdGen
    names: NameGen
    accounts: dict[str, dict] = field(default_factory=dict)
    upis: dict[str, dict] = field(default_factory=dict)
    phones: dict[str, dict] = field(default_factory=dict)
    statements: list[tuple[str, Statement]] = field(default_factory=list)

    def new_account(self, holder: str, role: str, case_id: str | None, bank: str | None = None,
                    number: str | None = None) -> tuple[str, str]:
        bank_code = bank or self.rng.choice(list(BANKS))
        acct = number or self.ids.account()
        self.accounts[acct] = {"holder": holder, "role": role, "bank": bank_code, "case_id": case_id}
        return acct, bank_code

    def note_upi(self, vpa: str, holder: str, role: str, case_id: str | None) -> str:
        self.upis[vpa] = {"holder": holder, "role": role, "case_id": case_id}
        return vpa

    def new_phone(self, holder: str, role: str, case_id: str | None) -> str:
        num = self.ids.phone()
        self.phones[num] = {"holder": holder, "role": role, "case_id": case_id}
        return num


def _rand_time(rng: random.Random, day: datetime, start_h: int = 8, end_h: int = 21) -> datetime:
    return day.replace(hour=rng.randint(start_h, end_h - 1), minute=rng.randint(0, 59), second=rng.randint(0, 59))


def add_benign_activity(world: World, stmt: Statement, *, case_id: str, city: str, profile: str,
                        start: datetime, end: datetime, grocery_per_month: int = 9,
                        pays_power_bill: bool = True, avoid: list[tuple[datetime, datetime]] | None = None,
                        income: float | None = None) -> None:
    """Fill `stmt` with ordinary activity between `start` and `end`.

    `avoid` holds windows (e.g. around a fraud transfer) where no ordinary
    transaction is placed, so the planted pattern stays readable.
    """
    rng, ids = world.rng, world.ids
    avoid = avoid or []

    def ok(t: datetime) -> bool:
        return start <= t <= end and not any(a <= t <= b for a, b in avoid)

    def place(t: datetime, txn: Txn) -> None:
        if ok(t):
            txn.time = t
            stmt.add(txn)

    # Counterparties are per statement, so ordinary payees never become a
    # cross-case "shared identifier" by accident. The city power biller is the
    # one deliberate exception.
    shops = []
    for _ in range(rng.randint(2, 3)):
        name = f"{rng.choice(SHOP_PREFIX)} {rng.choice(SHOP_WORDS)}"
        handle = "".join(ch for ch in name.lower() if ch.isalpha())[:14]
        vpa = world.note_upi(ids.upi(handle), name, "merchant", case_id)
        shops.append((name, vpa))

    family = [world.names.person()[0] for _ in range(2)]
    family_accts = [world.new_account(n, "family", case_id)[0] for n in family]
    landlord_name, _ = world.names.person()
    landlord_acct, _ = world.new_account(landlord_name, "landlord", case_id)

    if profile == "pensioner":
        payer = f"PENSION {rng.choice(['CPAO', 'EPFO', 'STATE TREASURY'])} (SYNTHETIC)"
        payer_acct, _ = world.new_account(payer, "pension_payer", case_id)
        monthly_in = income or rng.choice([28000, 34000, 41000, 52000, 63000])
    elif profile == "business":
        payer, payer_acct = None, None
        monthly_in = income or rng.choice([60000, 85000, 120000])
    else:
        payer = rng.choice(EMPLOYERS)
        payer_acct, _ = world.new_account(payer, "employer", case_id)
        monthly_in = income or rng.choice([32000, 45000, 58000, 76000, 94000])

    month_starts = []
    m = datetime(start.year, start.month, 1)
    while m <= end:
        month_starts.append(m)
        m = datetime(m.year + (m.month // 12), m.month % 12 + 1, 1)

    for ms in month_starts:
        if payer_acct:
            desc = "NEFT PENSION" if profile == "pensioner" else f"NEFT SAL {ms.strftime('%b%y').upper()}"
            place(ms.replace(hour=rng.randint(6, 10), minute=rng.randint(0, 59)),
                  Txn(ms, f"{desc}/{payer}", "NEFT", payer_acct, payer, credit=float(monthly_in),
                      reference=ids.reference(), tag="benign:income"))
        elif profile == "business":
            for _ in range(rng.randint(3, 5)):
                buyer, _g = world.names.person()
                b_acct, _ = world.new_account(buyer, "customer", case_id)
                d = ms + timedelta(days=rng.randint(0, 26))
                amt = float(rng.randrange(8000, 40000, 500))
                place(_rand_time(rng, d), Txn(d, f"IMPS/{buyer}/INVOICE", "IMPS", b_acct, buyer,
                                              credit=amt, reference=ids.reference(), tag="benign:business"))

        if profile != "pensioner" or rng.random() < 0.4:
            rent = float(rng.choice([9000, 12000, 15000, 18000, 22000]))
            d = ms + timedelta(days=rng.randint(3, 6))
            place(_rand_time(rng, d), Txn(d, f"IMPS/RENT/{landlord_name}", "IMPS", landlord_acct, landlord_name,
                                          debit=rent, reference=ids.reference(), tag="benign:rent"))

        for _ in range(max(1, grocery_per_month + rng.randint(-2, 2))):
            d = ms + timedelta(days=rng.randint(0, 27))
            name, vpa = rng.choice(shops)
            amt = float(rng.randrange(120, 3200, 10))
            place(_rand_time(rng, d), Txn(d, f"UPI/P2M/{name}", "UPI-P2M", vpa, name, debit=amt,
                                          reference=ids.reference(), tag="benign:grocery"))

        if pays_power_bill:
            biller, vpa = CITY_BILLERS[city]
            world.note_upi(vpa, biller, "utility_biller", None)
            d = ms + timedelta(days=rng.randint(8, 15))
            place(_rand_time(rng, d), Txn(d, f"UPI/BILLPAY/{biller}", "UPI-P2M", vpa, biller,
                                          debit=float(rng.randrange(900, 4200, 10)), reference=ids.reference(),
                                          tag="benign:utility"))

        for family_name, family_acct in zip(family, family_accts):
            if rng.random() < 0.7:
                d = ms + timedelta(days=rng.randint(10, 25))
                place(_rand_time(rng, d), Txn(d, f"IMPS/{family_name}/FAMILY", "IMPS", family_acct, family_name,
                                              debit=float(rng.randrange(2000, 15000, 500)),
                                              reference=ids.reference(), tag="benign:family"))

        if rng.random() < 0.8:
            d = ms + timedelta(days=rng.randint(0, 27))
            atm = f"SYNATM{rng.randint(10000, 99999)}"
            place(_rand_time(rng, d), Txn(d, f"ATM WDL/{atm}/{city.upper()}", "ATM", atm, "ATM cash withdrawal",
                                          debit=float(rng.choice([2000, 3000, 5000, 10000])), tag="benign:atm"))


def ensure_non_negative(stmt: Statement, buffer: float = 500.0) -> None:
    """Raise the opening balance just enough that the running balance never
    dips below `buffer`. Used only for statements whose exact opening figure
    is not part of the scenario."""
    low = stmt.min_balance()
    if low < buffer:
        stmt.opening = round(stmt.opening + (buffer - low), 2)
