"""Complaint narrative templates for the noise cases.

Each template belongs to a template family (family + language + variant).
The family id is recorded per narrative so held-out evaluation can split by
template family and never test on a paraphrase of a tuning example.

Patterns follow publicly reported fraud types; every name, number and
account is invented.
"""
from __future__ import annotations

from datetime import datetime

MONTHS_HI = {7: "जुलाई", 8: "अगस्त"}


def d_en(t: datetime) -> str:
    return f"{t.day} {t.strftime('%B')} {t.year}"


def t_en(t: datetime) -> str:
    h = t.hour % 12 or 12
    return f"{h}:{t.minute:02d} {'am' if t.hour < 12 else 'pm'}"


def d_hi(t: datetime) -> str:
    return f"{t.day} {MONTHS_HI[t.month]} {t.year}"


def t_hi(t: datetime) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def pay_lines(ctx: dict, lang: str) -> str:
    lines = []
    for p in ctx["payments"]:
        t, amt = p["time"], p["amount_fmt"]
        unauth = p.get("unauthorised")
        if lang == "en":
            if p.get("vpa") and unauth:
                lines.append(f"On {d_en(t)} at {t_en(t)}, Rs. {amt} was debited from my account by UPI to "
                             f"{p['vpa']} without my permission (UPI reference {p['ref']}).")
            elif p.get("vpa"):
                lines.append(f"On {d_en(t)} at {t_en(t)} I paid Rs. {amt} by UPI to UPI ID {p['vpa']} "
                             f"({p['name']}), UPI reference {p['ref']}.")
            elif unauth:
                lines.append(f"On {d_en(t)} at {t_en(t)}, Rs. {amt} was transferred out of my account by "
                             f"{p['channel']} without my permission to account {p['acct']} (IFSC {p['ifsc']}), "
                             f"reference {p['ref']}.")
            else:
                lines.append(f"On {d_en(t)} at {t_en(t)} I transferred Rs. {amt} by {p['channel']} to account "
                             f"number {p['acct']}, IFSC {p['ifsc']} ({p['bank']}), in the name of {p['name']}. "
                             f"Reference number {p['ref']}.")
        elif lang == "hg":
            if p.get("vpa") and unauth:
                lines.append(f"{d_en(t)} ko {t_en(t)} par mere account se bina permission ke Rs. {amt} UPI se "
                             f"{p['vpa']} par kat gaye (UPI ref {p['ref']}).")
            elif p.get("vpa"):
                lines.append(f"{d_en(t)} ko {t_en(t)} par maine Rs. {amt} UPI ID {p['vpa']} ({p['name']}) par "
                             f"bheje, UPI ref {p['ref']}.")
            else:
                lines.append(f"{d_en(t)} ko {t_en(t)} par maine Rs. {amt} {p['channel']} se account number "
                             f"{p['acct']} (IFSC {p['ifsc']}, {p['bank']}, naam {p['name']}) mein bheje. "
                             f"Reference no. {p['ref']}.")
        else:  # hi
            if p.get("vpa") and unauth:
                lines.append(f"{d_hi(t)} को {t_hi(t)} बजे मेरी अनुमति के बिना मेरे खाते से ₹ {amt} UPI आईडी "
                             f"{p['vpa']} पर कट गए (UPI रेफरेंस {p['ref']})।")
            elif p.get("vpa"):
                lines.append(f"{d_hi(t)} को {t_hi(t)} बजे मैंने ₹ {amt} UPI आईडी {p['vpa']} ({p['name']}) पर "
                             f"भेजे, UPI रेफरेंस {p['ref']}।")
            else:
                lines.append(f"{d_hi(t)} को {t_hi(t)} बजे मैंने ₹ {amt} {p['channel']} द्वारा खाता संख्या "
                             f"{p['acct']} (IFSC {p['ifsc']}, {p['bank']}, खाताधारक {p['name']}) में भेजे। "
                             f"रेफरेंस नंबर {p['ref']}।")
    return "\n".join(lines)


def header_en(ctx: dict, subject: str) -> str:
    return (f"To,\nThe Officer in Charge,\n{ctx['station']}\n\nSubject: {subject}\n\n"
            f"I, {ctx['victim']}, aged {ctx['age']} years, {ctx['occupation']}, residing at {ctx['address']}, "
            f"mobile {ctx['phone']}, submit this complaint.\n\n")


def footer_en(ctx: dict) -> str:
    return (f"\n\nI reported this on the 1930 helpline (acknowledgement number {ctx['ack']}). My bank account is "
            f"{ctx['victim_acct']} with {ctx['victim_bank']}. I request you to register my complaint and help "
            f"recover the amount.\n\n{ctx['victim']}\n{d_en(ctx['complaint_date'])}\n")


# --- English families ---------------------------------------------------------

def da_en(ctx):
    return header_en(ctx, "Loss of money to persons posing as customs and CBI officers on video call") + (
        f"On {d_en(ctx['contact_date'])} in the morning I received a call from {ctx['caller']}. The caller said he was from "
        f"the customs department at Mumbai airport and that a parcel sent in my name contained drugs and fake "
        f"passports. He transferred the call to a man who said he was an officer of the Narcotics Control Bureau, "
        f"and later to a lady who said she was a CBI officer named {ctx['persona_f']}.\n\n"
        f"They made me join a Skype video call and told me that I was under digital arrest until the enquiry was "
        f"over. I was not allowed to disconnect or speak to my family. They said the Enforcement Directorate "
        f"would freeze all my accounts unless I moved my savings to a supervisory account of the RBI for "
        f"verification of the legality of my funds, and that the full amount would be refunded after "
        f"verification.\n\n{pay_lines(ctx, 'en')}\n\nAfter the transfer they asked for more money for a "
        f"\"clearance certificate\". Then I understood that this was a fraud."
    ) + footer_en(ctx)


def job_en(ctx):
    first = ctx["payments"][0]["time"]
    return header_en(ctx, "Cheating in the name of online part-time job (task fraud)") + (
        f"On {d_en(first)} I received a WhatsApp message from {ctx['caller']} offering a part-time job of "
        f"rating hotels on Google Maps for Rs. 50 per task. I was added to a Telegram group called "
        f"\"{ctx['group']}\" where a person named {ctx['persona_m']} gave tasks. For the first few tasks I "
        f"received small payments of Rs. 150 and Rs. 210 in my account, so I trusted them.\n\n"
        f"Then they gave me \"prepaid merchant tasks\" where I had to deposit money first and was promised 30% "
        f"return.\n\n{pay_lines(ctx, 'en')}\n\nThe website showed a balance of more than double the amount, but "
        f"when I tried to withdraw they said my account was frozen and I must pay a \"credit score repair fee\". "
        f"I did not pay any further amount."
    ) + footer_en(ctx)


def inv_en(ctx):
    return header_en(ctx, "Fraud through fake stock market investment app") + (
        f"In July 2026 I was added to a WhatsApp group named \"{ctx['group']}\" where a person calling himself "
        f"{ctx['persona_m']} shared daily stock tips and claimed to be a SEBI registered advisor. The group admin "
        f"used number {ctx['caller']}. They asked me to install an app called \"{ctx['app']}\" for institutional "
        f"trading and IPO allotment at a discount.\n\n{pay_lines(ctx, 'en')}\n\nThe app showed a profit of "
        f"more than Rs. {ctx['fake_profit']}. When I tried to withdraw on {d_en(ctx['withdraw_date'])} they "
        f"asked me to pay a "
        f"20% service charge first. Then the app stopped working and the group was deleted."
    ) + footer_en(ctx)


def inv_en_crypto(ctx):
    return header_en(ctx, "Cheating in the name of crypto trading platform") + (
        f"A person who called herself {ctx['persona_f']} contacted me on Instagram and later on WhatsApp from "
        f"{ctx['caller']}. After chatting for some weeks she told me about a crypto trading platform "
        f"\"{ctx['app']}\" where she had earned good profits and helped me open an account on it.\n\n"
        f"{pay_lines(ctx, 'en')}\n\nThe platform dashboard showed my holdings growing every day. When I asked "
        f"for withdrawal, customer support on the platform said I had to pay tax of 18% before release. I "
        f"realised it was fraud and did not pay."
    ) + footer_en(ctx)


def kyc_en(ctx):
    first = ctx["payments"][0]["time"]
    return header_en(ctx, "Unauthorised debits after fake KYC update SMS") + (
        f"On {d_en(first)} I received an SMS saying \"Dear customer your {ctx['victim_bank']} account will be "
        f"blocked today. Please update your PAN KYC immediately\" with a link, from the number {ctx['caller']}. "
        f"I opened the link, which looked like my bank's website, and entered my customer ID, password and the "
        f"OTP that came on my phone.\n\n{pay_lines(ctx, 'en')}\n\nI immediately called my bank and blocked my "
        f"net banking. I never shared my details with anyone else."
    ) + footer_en(ctx)


def mkt_en(ctx):
    first = ctx["payments"][0]["time"]
    return header_en(ctx, "Cheating by fake buyer on online marketplace") + (
        f"I had posted an advertisement to sell my {ctx['item']} on an online marketplace. On {d_en(first)} a "
        f"person called me from {ctx['caller']} and said he was an army officer named {ctx['persona_m']} posted "
        f"at {ctx['place']}, and that he wanted to buy it. He said army payments are made only through QR code "
        f"and sent me QR codes on WhatsApp, asking me to scan them to receive the money.\n\n"
        f"{pay_lines(ctx, 'en')}\n\nEvery time he said the payment failed because of a technical problem and "
        f"that the money would come back double. When I asked for my money he blocked my number."
    ) + footer_en(ctx)


def elec_en(ctx):
    first = ctx["payments"][0]["time"]
    return header_en(ctx, "Fraud through electricity disconnection message") + (
        f"On {d_en(first)} I received an SMS: \"Dear consumer, your electricity power will be disconnected "
        f"tonight at 9.30 pm because your previous month bill was not updated. Please immediately contact our "
        f"electricity officer {ctx['caller']}\". I called the number. The person asked me to install an app "
        f"called \"{ctx['app']}\" to update the bill and to pay Rs. 10 from my net banking.\n\n"
        f"{pay_lines(ctx, 'en')}\n\nI later came to know that the app gives full control of the phone to "
        f"another person. My electricity bill had already been paid."
    ) + footer_en(ctx)


def loan_en(ctx):
    return header_en(ctx, "Harassment and extortion by instant loan app") + (
        f"In July 2026 I took a loan of Rs. 5,000 through a mobile app called \"{ctx['app']}\". I received only "
        f"Rs. 3,200 after deductions. Within seven days they started calling me from {ctx['caller']} and other "
        f"numbers, abusing me and threatening to send morphed photos to all my contacts. They sent a morphed "
        f"photo to two of my relatives.\n\nOut of fear I made the following payments:\n{pay_lines(ctx, 'en')}"
        f"\n\nThey are still demanding more money."
    ) + footer_en(ctx)


def cour_en(ctx):
    first = ctx["payments"][0]["time"]
    return header_en(ctx, "Fraud in the name of courier customs duty") + (
        f"On {d_en(first)} I received a call from {ctx['caller']}. The caller said that an international "
        f"parcel with a gift for me was held at customs and that I must pay customs duty to release it. He sent "
        f"a receipt on WhatsApp that looked official.\n\n{pay_lines(ctx, 'en')}\n\nAfter the payment they asked "
        f"for more money for an anti-money-laundering certificate. No parcel was delivered."
    ) + footer_en(ctx)


def cc_en(ctx):
    return header_en(ctx, "Fraud by fake customer care number") + (
        f"I wanted a refund for a cancelled {ctx['service']} booking. I searched online and called a number "
        f"shown as customer care, {ctx['caller']}. The person said he would process my refund and asked me to "
        f"install \"{ctx['app']}\" and fill a refund form. He told me to enter my debit card details for "
        f"verification.\n\n{pay_lines(ctx, 'en')}\n\nNo refund was received.{ctx.get('family_phone_note', '')}"
    ) + footer_en(ctx)


# --- Hinglish -----------------------------------------------------------------

def hg_footer(ctx):
    return (f"\n\nMaine 1930 par complaint ki hai, acknowledgement number {ctx['ack']}. Mera account "
            f"{ctx['victim_acct']} ({ctx['victim_bank']}) hai. Kripya meri madad karein aur paise wapas "
            f"dilwayein.\n\n{ctx['victim']}\nMobile: {ctx['phone']}\n{d_en(ctx['complaint_date'])}\n")


def hg_intro(ctx):
    live = "rehti hoon" if ctx["gender"] == "F" else "rehta hoon"
    return (f"To,\nThe Officer in Charge,\n{ctx['station']}\n\nSir/Madam,\n\nMain {ctx['victim']}, umar "
            f"{ctx['age']} saal, {ctx['address']} mein {live}. ")


def job_hg(ctx):
    first = ctx["payments"][0]["time"]
    return hg_intro(ctx) + (
        f"{d_en(first)} ko mujhe WhatsApp par {ctx['caller']} se message aaya ki part-time job hai, YouTube "
        f"videos like karke roz Rs. 2,000 se 5,000 kama sakte hain. Phir unhone mujhe Telegram group "
        f"\"{ctx['group']}\" mein add kiya. Pehle do task mein Rs. 150 commission mila isliye bharosa ho "
        f"gaya. Uske baad \"prepaid task\" ke naam par paise jama karwaye.\n\n{pay_lines(ctx, 'hg')}\n\n"
        f"Ab withdrawal nahi ho raha aur woh \"tax\" ke naam par aur paise maang rahe hain."
    ) + hg_footer(ctx)


def elec_hg(ctx):
    first = ctx["payments"][0]["time"]
    return hg_intro(ctx) + (
        f"{d_en(first)} ko mujhe SMS aaya ki aaj raat 9:30 baje aapki bijli kaat di jayegi kyunki pichle mahine "
        f"ka bill update nahi hua, electricity officer se {ctx['caller']} par baat karein. Maine call kiya to "
        f"usne \"{ctx['app']}\" app download karwaya aur Rs. 10 pay karne ko bola.\n\n{pay_lines(ctx, 'hg')}"
        f"\n\nMera bill pehle se paid tha. Baad mein pata chala ki app se phone ka control unke paas chala gaya "
        f"tha."
    ) + hg_footer(ctx)


def da_hg(ctx):
    return hg_intro(ctx) + (
        f"{d_en(ctx['contact_date'])} ko mujhe {ctx['caller']} se call aaya. Bola ki woh Mumbai Police se hai aur mere Aadhaar "
        f"par nikla ek SIM card money laundering case mein use hua hai. Phir WhatsApp video call par ek aadmi "
        f"police uniform mein aaya, jisne apna naam {ctx['persona_m']} (CBI) bataya. Usne kaha ki main \"digital "
        f"arrest\" mein hoon, camera band nahi karna hai aur ghar walon ko kuch nahi batana hai.\n\n"
        f"Do din tak video call chalti rahi. Unhone kaha ki RBI verification ke liye saare paise ek \"secret "
        f"supervision account\" mein transfer karne honge, verification ke baad 24 ghante mein refund ho "
        f"jayega.\n\n{pay_lines(ctx, 'hg')}\n\nUske baad call kat gaya aur number band aa raha hai."
    ) + hg_footer(ctx)


# --- Hindi (Devanagari) ---------------------------------------------------------

def hi_intro(ctx):
    live = "रहती हूँ" if ctx["gender"] == "F" else "रहता हूँ"
    return (f"सेवा में,\nथाना प्रभारी,\n{ctx['station']}\n\nविषय: ऑनलाइन धोखाधड़ी की शिकायत\n\n"
            f"महोदय,\n\nमैं {ctx['victim']}, उम्र {ctx['age']} वर्ष, {ctx['address']} में {live}। "
            f"मेरा मोबाइल नंबर {ctx['phone']} है।\n\n")


def hi_footer(ctx):
    return (f"\n\nमैंने 1930 हेल्पलाइन पर शिकायत दर्ज की है, पावती संख्या {ctx['ack']}। मेरा खाता "
            f"{ctx['victim_acct']} ({ctx['victim_bank']}) में है। कृपया मेरी शिकायत दर्ज करके उचित कार्रवाई "
            f"करें।\n\n{ctx['victim']}\n{d_hi(ctx['complaint_date'])}\n")


def kyc_hi(ctx):
    first = ctx["payments"][0]["time"]
    return hi_intro(ctx) + (
        f"{d_hi(first)} को मेरे मोबाइल पर {ctx['caller']} से SMS आया कि आपका बैंक खाता आज बंद हो जाएगा, "
        f"तुरंत KYC अपडेट करें, और साथ में एक लिंक था। मैंने लिंक खोलकर अपना कस्टमर आईडी, पासवर्ड और मोबाइल "
        f"पर आया OTP डाल दिया।\n\n{pay_lines(ctx, 'hi')}\n\nमैंने तुरंत बैंक को फोन करके नेट बैंकिंग बंद करवाई।"
    ) + hi_footer(ctx)


def mkt_hi(ctx):
    first = ctx["payments"][0]["time"]
    return hi_intro(ctx) + (
        f"मैंने ऑनलाइन मार्केटप्लेस पर अपना {ctx['item_hi']} बेचने का विज्ञापन डाला था। {d_hi(first)} को "
        f"{ctx['caller']} से एक व्यक्ति का फोन आया जिसने खुद को आर्मी ऑफिसर {ctx['persona_m']} बताया। उसने कहा "
        f"कि आर्मी में पेमेंट QR कोड से होता है और WhatsApp पर QR कोड भेजकर स्कैन करने को कहा।\n\n"
        f"{pay_lines(ctx, 'hi')}\n\nहर बार उसने कहा कि तकनीकी दिक्कत है और पैसे दोगुने वापस आएंगे। बाद में उसने "
        f"मेरा नंबर ब्लॉक कर दिया।"
    ) + hi_footer(ctx)


def loan_hi(ctx):
    return hi_intro(ctx) + (
        f"जुलाई 2026 में मैंने \"{ctx['app']}\" नाम के मोबाइल ऐप से ₹ 5,000 का लोन लिया था, जिसमें से केवल "
        f"₹ 3,200 मिले। सात दिन के अंदर {ctx['caller']} और दूसरे नंबरों से धमकी भरे फोन आने लगे। उन्होंने मेरी "
        f"फोटो से छेड़छाड़ करके मेरे रिश्तेदारों को भेजने की धमकी दी।\n\nडर के कारण मैंने ये भुगतान किए:\n"
        f"{pay_lines(ctx, 'hi')}\n\nवे अब भी और पैसे मांग रहे हैं।"
    ) + hi_footer(ctx)


def supplementary_en(ctx):
    extra = ctx["supp_note"]
    return (f"SUPPLEMENTARY STATEMENT\n{ctx['station']}\nStatement of {ctx['victim']}, recorded on "
            f"{d_en(ctx['supp_date'])}\n\n{extra}\n\nI am submitting screenshots of the chats and the bank SMS "
            f"alerts. I have not received any amount back so far.\n\n{ctx['victim']}\n")


TEMPLATES = {
    ("DA", "en"): ("DA-EN-2", da_en),
    ("DA", "hg"): ("DA-HG-1", da_hg),
    ("JOB", "en"): ("JOB-EN-1", job_en),
    ("JOB", "hg"): ("JOB-HG-1", job_hg),
    ("INV", "en"): ("INV-EN-1", inv_en),
    ("INVC", "en"): ("INV-EN-2", inv_en_crypto),
    ("KYC", "en"): ("KYC-EN-1", kyc_en),
    ("KYC", "hi"): ("KYC-HI-1", kyc_hi),
    ("MKT", "en"): ("MKT-EN-1", mkt_en),
    ("MKT", "hi"): ("MKT-HI-1", mkt_hi),
    ("ELEC", "en"): ("ELEC-EN-1", elec_en),
    ("ELEC", "hg"): ("ELEC-HG-1", elec_hg),
    ("LOAN", "en"): ("LOAN-EN-1", loan_en),
    ("LOAN", "hi"): ("LOAN-HI-1", loan_hi),
    ("COUR", "en"): ("COUR-EN-1", cour_en),
    ("CC", "en"): ("CC-EN-1", cc_en),
}
