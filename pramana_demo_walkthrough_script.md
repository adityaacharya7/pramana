# PRAMANA — Official Demo Walkthrough Script

**Problem Statement:** Inter-Jurisdictional Cyber Investigation & Intelligence Fusion  
**Core Motto:** *“The system proposes, the officer decides.”* (Strict decision-support with 100% evidentiary provenance)  
**Total Demonstration Time:** 6–8 minutes (or modular 3-minute fast-track)

---

## 0. Quick Prep & Reset (Before Starting)

Ensure your backend and frontend are running in demo mode:

```bash
# In backend terminal:
.venv/Scripts/python -m pramana.cli demo-reset --preload-all
.venv/Scripts/python -m pramana.cli serve --demo

# In frontend terminal:
npm run dev   # Opens at http://localhost:5173
```

---

## The 30-Second Opening Pitch (For Presenter)

> *“Respected Jury, modern cyber syndicates exploit jurisdictional boundaries. In digital arrest scams, money is layered across three cities in under twelve minutes. Today, police units work in silos with manual spreadsheets. Evidence fails in court because investigators cannot prove how funds moved or defend against defense scrutiny.*
>
> *This is **PRAMANA** (प्रमाण) — an investigation review system built for cross-border cyber probes. It does not replace the investigating officer: **the system proposes, the officer decides**. Every node links to a cryptographically sealed document, every calculation is reproducible offline without a database, and every lead can be stress-tested in Challenge Mode before court.”*

---

## ACT 1: Role-Based Access Control (RBAC) & Scoped Case Intake

### What to Click:
1. Navigate to `http://localhost:5173/roles`.
2. Notice the institutional header: **PRAMANA**, **SIH Prototype**, bilingual title, and statutory disclaimer.
3. Click **Insp. Aparna Deshmukh** (`io.mumbai` — Cyber Police Station West Region, Mumbai).
4. The dashboard loads at `/cases`.

### Spoken Narration:
> *“We begin on the Role Selector. PRAMANA enforces strict institutional RBAC: Investigating Officers, Intelligence Analysts, Supervisory Officers, and Vigilance Auditors each have mathematically distinct permission boundaries.*
>
> *We log in as Inspector Aparna Deshmukh of Mumbai Cyber Cell. Notice our case dashboard: Inspector Deshmukh only sees cases scoped to her unit or where joint-probe membership has been explicitly granted. Out-of-scope cases are strictly shielded.”*

### What Evaluators See:
* Summary Metrics: *Cases in Scope*, *Sealed Evidence Blobs*, *City Jurisdictions*, *Latest Registered FIR*.
* Case Table: Displays FIR numbers, complainant names, police stations, evidence count, and status badges.

---

## ACT 2: Case C-101, Quality Gates & Extraction Review

### What to Click:
1. Click case **C-101** (*Digital arrest impersonation complaint — Shobha Anant Kulkarni*).
2. The page opens on the **Review queue** tab (`/cases/C-101/review`).
3. Point out the **Intake quality checks** section at the top.
4. Scroll down to **Extracted mentions** and click any source text preview.
5. Scroll down to **Identity review** card showing two records for `"Rahul Sharma"`.

### Spoken Narration:
> *“We open Case C-101, an FIR involving an elderly victim extorted under digital arrest. Look at the top of the review queue: **nothing enters the investigative graph automatically**. PRAMANA enforces four automated quality gates:*
> *1. SHA-256 seal integrity check.*
> *2. Bank statement transaction gap check.*
> *3. Balance reconciliation check.*
> *4. Ambiguous date format check.*
>
> *Below, extracted entities are surfaced through a 3-tier pipeline: deterministic regex validators for bank accounts and IFSC codes, role-based syntactic patterns for names, and an NLP model for contextual entities.*
>
> *Look at Identity Review: two individuals named ‘Rahul Sharma’ appear across statements. Traditional AI tools blindly merge them. PRAMANA scores their shared versus conflicting identifiers, flags that their Aadhaar/PAN do not match, and keeps them strictly separate with logged justification.”*

---

## ACT 3: Knowledge Graph & Provenance Source Drawer

### What to Click:
1. In the horizontal case navigation, click **Graph & timeline** (`/cases/C-101/graph`).
2. The interactive NetworkX/Cytoscape graph renders.
3. Toggle the **Hops** selector (`1`, `2`, `3`).
4. Click on any bank account or phone node (e.g., account ending in `…4821` or phone `P-77`).
5. In the right-hand inspection drawer, click the **Source text snippet**.
6. The **Source Drawer** slides open, displaying the raw bank statement / complaint file with the exact character span highlighted.

### Spoken Narration:
> *“Switching to the Graph tab, we view the 1-to-3 hop relational network. Every node shape and color conveys meaning: rectangles for accounts, diamonds for UPI, stars for crypto wallets, and tags for suspects.*
>
> *Crucially, in PRAMANA, no node or edge is an ungrounded hallucination. Watch: I click this mule bank account. The panel displays its exact provenance. When I click the source reference, PRAMANA displays the original, byte-sealed bank statement with the exact line and transaction highlighted. When an officer testifies under Section 65B of the Indian Evidence Act (or BNSS equivalent), every link has verified provenance.”*

---

## ACT 4: Cross-Case Intelligence & Privacy-Preserving Blind Match

### What to Click:
1. Click the **Cross-case** tab (`/cases/C-101/crosscase`).
2. Point to the table **Identifiers seen in other cases**.
3. Note that phone `P-77` links Mumbai case `C-101` and Delhi case `C-102`.
4. Point out the **Hidden match / Outside your scope** indicator: `1 match in cases of DEL-CYB`.
5. Click **Request access**; enter a reason: *"Shared mule phone P-77 linked to cyber extortions"*; click **Send request**.
6. Scroll down to **Similar method (MO)**: Click **Side by side** on case `C-103`.

### Spoken Narration:
> *“Now we open Cross-Case Intelligence. Here lies the core inter-state breakthrough:*
>
> *First: Phone P-77 matches an open probe in Delhi Cyber Cell. But notice what PRAMANA does: if Delhi has not granted access, **the system performs a privacy-preserving blind match**. It discloses only that an identifier matched in unit DEL-CYB. It never leaks the complainant's identity or case details. The Mumbai officer can submit a formal, logged access request directly to Delhi's supervisor.*
>
> *Second: Look at Modus Operandi (MO) Similarity below. PRAMANA analyzes the modus operandi across cities. It flags case C-103 in Bengaluru as a 91% match. When we click ‘Side by side’, officers see the exact matching narrative attributes: fake police arrest warrant, Skype interrogation video call, and fraudulent RBI clearance verification.”*

---

## ACT 5: Multi-Hop Money Trail Engine (FIFO / LIFO / Pro-Rata)

### What to Click:
1. Click the **Money trail** tab (`/cases/C-101/trail`).
2. The multi-hop financial flow diagram renders.
3. Review the top metrics: *Victim loss*, *Still held*, *Left the trail*, *Onward unknown*.
4. Trace the visual flow: Victim `Shobha Kulkarni` → Mule Accounts `M1, M2, M3` → `HUB` account → P2P Crypto Seller → Wallet `W-1`.
5. Toggle the attribution method buttons: click **FIFO**, click **LIFO**, click **Pro-rata**.
6. Watch the live numbers recalculate in real-time.

### Spoken Narration:
> *“This is PRAMANA's Money Trail Engine. Fraudulent funds do not sit still. In this joint probe, victim funds were deposited into three immediate mule accounts: M1, M2, and M3.*
>
> *All three layer into a central HUB account within 45 minutes, which then disperses into cash withdrawals and a P2P crypto trade ending in cold wallet W-1.*
>
> *Now, watch this button group: In banking investigations, attribution accounting is contested. Does the officer apply **FIFO** (first-in-first-out), **LIFO** (last-in-first-out), or **Pro-Rata**?*
> *Watch: When I switch between FIFO, LIFO, and Pro-rata, PRAMANA re-evaluates the mathematical flow of every single rupee. If an account has missing statements, it immediately warns that figures downstream are uncertain rather than presenting false certainty.”*

---

## ACT 6: The Evidence Receipt & Rule Library

### What to Click:
1. Click the **Leads** tab (`/cases/C-101/leads`).
2. Click on the lead: **Potential convergence point: Central Pooling Hub** (`CONVERGENCE-v1`).
3. You are now on the **Lead Details** page (`/leads/...`).
4. Review the **Evidence Receipt** card.
5. Point out **Supporting records** (all clickable).
6. Point out the section: **“What could make this wrong?”**

### Spoken Narration:
> *“Under the Leads tab, PRAMANA's rule library detected CONVERGENCE-v1: multiple independent victim payments converging into a single pooling hub.*
>
> *Opening the lead reveals our signature feature: **The Evidence Receipt**.*
> *Instead of an opaque AI summary, an Evidence Receipt lists:*
> *1. The specific rule and version.*
> *2. Number of independent corroborating sources.*
> *3. Explicitly identified unknowns — such as the unverified beneficial owner of the HUB.*
> *4. And most importantly for judicial integrity: **What could make this wrong?** PRAMANA provides the alternative ordinary explanation (e.g., an e-commerce gateway or payroll distributor) and specifies which banking records would distinguish genuine commerce from a mule hub.”*

---

## ACT 7: Challenge Mode & The Amount & Draft Assistant

### What to Click:
1. Scroll down to the **Challenge Mode** card.
2. Under *Record to challenge*, select the transfer: `M3 → HUB`.
3. Select Operation: `Exclude this source — set the record aside`.
4. Click **Run scenario**.
5. Observe the scenario diff:
   - *Findings removed:* "Threshold not met: 2 of the 3 required senders remain".
   - *Estimates changed:* Downstream amounts recalculate.
   - *Drafts affected:* 4 approved freeze requisitions are flagged as affected.
6. Type a reason in the box: *"Complainant M3 denies authorizing transaction; contesting record"*.
7. Click **Propose applying to the case**.
8. Notice the scenario status: `Proposed by io.mumbai — awaiting supervisor approval`.

### Spoken Narration:
> *“Now, here is PRAMANA's most groundbreaking feature: **Challenge Mode**.*
>
> *Defense attorneys always challenge evidence in trial: ‘What if statement M3 is invalid?’ In standard systems, testing a hypothesis breaks the production database.*
>
> *In PRAMANA, Challenge Mode creates an isolated scenario copy. We choose to exclude the transfer from Mule 3 to the HUB and click ‘Run scenario’. Instantly, the engine recalculates the entire case graph:*
> *• It flags that the convergence threshold has broken because only 2 of the 3 required sources remain.*
> *• Downstream estimates shift.*
> *• Four approved account-freezing draft requisitions are flagged as directly impacted.*
>
> *Because Inspector Deshmukh is an IO, she cannot unilaterally modify approved legal drafts. She submits a formal proposal with a mandatory logged reason for supervisory review.”*

---

## ACT 8: Role Switching & Supervisory Approval

### What to Click:
1. In the top-right header, click the user profile dropdown: click **Switch Role / भूमिका का चयन**.
2. Select **ACP Suhas Pawar** (`sup.mumbai` — Supervisory Officer).
3. Navigate back to case **C-101** → **Leads** → open the **Potential convergence point** lead.
4. Scroll down to the pending Challenge Mode scenario:
   - ACP Suhas Pawar now sees the **Approve and apply** and **Reject** buttons.
5. Enter reason: *"Exclusion verified with branch manager; applying challenge"*; click **Approve and apply**.
6. Look at the **Amount & Draft Assistant** card below:
   - Notice that the drafts are now marked in red: **`Needs re-approval`** with the stale reason displayed!

### Spoken Narration:
> *“We use PRAMANA's instant role switcher to adopt the persona of ACP Suhas Pawar, Supervisory Officer for Mumbai Cyber Cell.*
>
> *ACP Pawar inspects the challenge proposal. Seeing the branch verification reason, he clicks ‘Approve and apply’.*
>
> *Look at the legal drafts table below: Every Section 91 CrPC / BNSS statutory freeze notice linked to that account is instantly marked **‘Needs re-approval’** with an explicit reason logged in the audit ledger. The system safeguards officers from serving inaccurate freeze requisitions to banks.”*

---

## ACT 9: Cross-Unit Access Approval

### What to Click:
1. Open the user profile menu and switch to **ACP Ritu Khanna** (`sup.delhi` — Delhi Cyber Cell).
2. Click **Access Requests** in the left sidebar navigation (`/access`).
3. Under *Requests for your unit’s cases*, find the pending request submitted by Inspector Deshmukh (Mumbai) regarding `P-77`.
4. Click **Approve**.
5. Modal appears: enter reason *"Approved for Joint Inter-State Cyber Investigation"*; click **Approve**.
6. The badge updates to **`approved`**.

### Spoken Narration:
> *“Next, we switch to ACP Ritu Khanna of Delhi Cyber Cell. On her Access Requests dashboard, she sees Mumbai's incoming requisition regarding phone P-77.*
>
> *She reviews the stated reason and approves it with a logged justification. Instantly, cross-case access is granted in the ledger, and the Mumbai team can now view Delhi's corroborating case records.”*

---

## ACT 10: Cryptographic Audit Log & Zero-Database Handover Verification

### What to Click:
1. Click **Audit Log** in the left sidebar (`/audit`).
2. Point to the tamper-evident hash-chained entries.
3. Click the button: **Verify ledger integrity**.
4. The system validates the hash-chain through the latest sequence number with a green confirmation badge.
5. Click **Download checkpoint** (downloads `pramana-checkpoint-<seq>.json`).
6. In the sidebar, click **Verify Handover** (`/verify`).
7. Drag and drop or upload any exported handover JSON pack (or click choose file).
8. The verification panel turns green with a checkmark: **`Reproduced`**.

### Spoken Narration:
> *“Finally, the pillar that ensures court admissibility: **Auditability and Zero-Database Reproducibility**.*
>
> *On the Audit Log screen, every action — logins, extractions, challenge simulations, supervisor approvals, and access grants — is recorded on an append-only, SHA-256 hash-chained ledger. An Ed25519 signature checkpoint is taken every 50 events and at every formal export.*
>
> *When we click ‘Verify ledger integrity’, the engine cryptographically walks the entire chain from genesis to the latest head. If anyone modified a database row directly, the chain would break visibly.*
>
> *And look at ‘Verify Handover’: When a case is transferred to CBI, NIA, or handed over for court trial, PRAMANA exports a self-contained JSON re-run bundle. Any court or receiving agency can open this verification screen on an offline machine with **no database connection whatsoever**. PRAMANA re-runs the graph algorithms and money trail from the raw inputs and mathematically proves that every finding is 100% reproducible.”*

---

## Concluding Statement (30 Seconds)

> *“PRAMANA bridges the critical gap in Indian cyber policing: it brings high-speed automated intelligence to inter-state fraud, while anchoring every calculation in the constitutional and legal requirements of evidence, human supervision, and judicial transparency.*
>
> *Thank you. We are ready for your questions.”*

---

## Evaluator Q&A Cheat Sheet

| Question | Winning Answer |
| :--- | :--- |
| **How does PRAMANA comply with the State Emblem of India Act, 2005?** | *“PRAMANA uses an independent project crest (scales of justice + analytical shield) and does not display the Ashoka Lion Capital or official government seals. The prototype displays clear statutory disclaimers in the header and footer affirming it is an independent student prototype.”* |
| **What happens if an account statement has gaps or does not reconcile?** | *“The intake quality checks immediately flag statement gaps and reconciliation mismatches. Downstream in the Money Trail Engine, any figures passing through an un-reconciled account are marked as ‘uncertain / insufficient evidence’ rather than presenting false precision.”* |
| **Why does PRAMANA offer FIFO, LIFO, and Pro-rata methods?** | *“Different courts and financial intelligence units adopt different accounting precedents. Rather than locking officers into one rigid assumption, PRAMANA computes all three and presents the attributable range so that requisitions are legally defensible.”* |
| **Can an AI agent send freeze notices directly to banks?** | *“No. PRAMANA's Amount & Draft Assistant only prepares draft requisitions. Every action requires human supervisory review and an explicit reason. The system never auto-sends notices.”* |
| **How is offline reproducibility achieved without a database?** | *“The handover bundle contains the sealed input manifests and deterministic extraction snapshots. The verification engine runs purely as a functional pipeline, re-computing the graph and money trail from scratch and verifying hash consistency.”* |
