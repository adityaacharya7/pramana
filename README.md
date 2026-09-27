# PRAMANA

**Find the Connection. Show the Evidence. Test the Lead.**

PRAMANA turns fragmented case evidence into traceable, challengeable investigative leads. It is an
investigation-support tool: the system proposes, the officer decides. Built for SIH problem
statement 26189; the full plan is in the MVP specification of 25 Sep 2026, written under the earlier working name "AROHAN — MVP Specification".

> Decision support only. The legal basis and final action rest with the officer and the competent authority.

## Status: MVP P0 complete (Weeks 1-5)

| Spec item | State |
|---|---|
| F1 Login, RBAC, case scoping | Done: bcrypt + TOTP (replay-protected) + short-lived JWT; permission matrix enforced server-side; out-of-scope requests get 403 **and** a ledger entry |
| F1 Demo role switcher | Done: only in the isolated demo build, which has its own database |
| F2 Evidence intake + manifest + 4 quality checks | Done: SHA-256 sealed, re-hashed on every load; duplicate / gap / reconciliation / ambiguous-date checks gate analysis |
| F3 Extraction + review | Done: identifier rules → role patterns → spaCy NER, every mention with file + span; nothing unreviewed reaches the graph |
| F4 Identity review | Done: per-record people; similar names scored on shared vs conflicting identifiers; merge / keep separate / unresolved / split |
| F5 Graph + timeline | Done: 1–3 hop views; click any node, edge or timeline row to see the exact source text |
| F6 Cross-case + blind match | Done: matches in out-of-scope cases show only count + owning unit; access requests decided by that unit's supervisor |
| F7 MO similarity | Done: rule-based MO attributes with passages + similarity score (see "Known limits"); side-by-side comparison |
| F8 Money Trail Engine | Done: FIFO / LIFO / pro-rata, opening balances, each rupee at one place, "as of" statement end, exits, missing statements, reconciliation |
| F9 Rule library (8 rules) | Done: SHARED-ID, CONVERGENCE, LAYERING, CASHOUT, FACILITATOR, FRONT-ENTITY, MO-MATCH, ORDINARY-PAYMENT; versioned, configurable |
| F10 Evidence Receipt | Done: records, rule + version, unknowns, conflicts, next step, "What could make this wrong?", independent-source count |
| F11 Challenge Mode | Done: exclude source / dispute / simulate non-occurrence on a scenario copy; dependencies listed first; IO proposes, supervisor applies; only then drafts go stale |
| F12 Amount & Draft Assistant | Done: one method per set, assumptions, range across methods, total checked against attributable amount; never sends |
| F13 Lead lifecycle | Done: Detected → Under verification → Verified / Dismissed / Needs evidence; reason required; supervisor approves |
| F14 Tamper-evident log + signed checkpoints | Done: Ed25519 checkpoint every 50 entries and at approvals/exports, kept outside the database; detects edits, deletions, rollbacks and full rewrites up to the latest checkpoint |
| F15 Handover pack | Done: JSON re-run bundle + PDF; `verify-bundle` reproduces findings and estimates offline with no database |
| F16 Crypto wallet as evidence-backed entity | Done: a wallet enters the trail only through a trade record naming the payment |

P1 items (Copilot, voice, Hindi extraction beyond the rule layers, victim/recovery tracker, auditor dashboard, onboarding sandbox,
admin UI) are not built.

## How the analysis works (Weeks 3-5)

* **Pure and reproducible.** `analysis/inputs.py` turns *confirmed* rows into a JSON snapshot; `analysis/engine.py` computes
  everything from that snapshot alone. The same code runs live, on a Challenge Mode copy, and from a handover bundle on another machine.
* **Parties and events.** An account and the UPI ID paying into it are one party once a bank record or KYC response links them; both
  statements of one transfer (same bank reference) are one event with two supporting rows and one source.
* **Money trail.** Victims' payments (complaint-principal's account → an account named in the same complaint) are traced forward through
  accounts with statements under FIFO, LIFO and pro-rata. Matches the spec's worked example exactly (M2: FIFO ₹12,000 / LIFO ₹56,000 /
  pro-rata ₹32,222.22). Where records do not reconcile, figures are reported as uncertain.
* **Challenge Mode.** Operations run on a scenario copy; the diff says why a finding went away ("Threshold not met: 2 of the 3 required
  senders remain"), which estimates move, and which drafts would be affected. Applying needs an IO proposal and a supervisor approval.
* **Demo baseline.** The demo seed preloads everything, runs the analysis for the Tri-City joint probe and creates a supervisor-approved
  pro-rata draft set for the HUB convergence lead (logged as done by the seed on those officers' behalf), which is where the spec's demo
  step 7 starts. `demo-reset --hold-back-complaints` leaves the three complaints out for a live-upload demo instead.

## How Week 2 works

* **Extraction** (`POST /cases/{id}/extract`) proposes mentions in three layers, highest priority first where spans overlap:
  `regex-v1` identifiers (account, IFSC, UPI, wallet, masked Aadhaar, phone, IMEI, with validators),
  `pattern-v1` people named in a role ("I, <name>,", "account name", "Beneficiary name:", "Name:", honorifics, Hinglish/Hindi forms),
  and spaCy `en_core_web_sm` for other people, organisations and places. spaCy alone mislabels many Indian names, which is why the
  rule layers win; it is skipped on Hinglish/Devanagari text. Spreadsheets are read by column (statement, KYC, CDR).
* **Review** (`GET /cases/{id}/review-queue`, `POST /extractions/{id}/decision`) confirms or rejects per mention, per value, or per file.
  Confirmed mentions get entities: identifiers are global (one number = one entity across cases); people are scoped to their record.
* **Edges are derived, not stored separately**: parsing is deterministic, so a file's relationships are re-read from its verified text
  whenever its confirmed mentions change. Each `edge_support` row names the file and span. Both statements of one transfer carry one bank
  reference and count as **one** source; byte-identical files share a source group.
* **Identity** (`POST /identities/decision`): a shared account or phone alone is not identity (co-signatories, family phones);
  decisions are applied when the graph is built, so a merge can be split.
* **Graph** (`GET /cases/{id}/graph?focus=&hops=`) is rebuilt with NetworkX from confirmed rows on every request. Nodes show which *other visible*
  cases mention them; nothing about cases outside the user's scope is revealed.
* **Demo seed**: preloaded files are extracted and their deterministic mentions confirmed on the owning IO's behalf (logged as
  `BASELINE_REVIEW_APPLIED`). NER suggestions, identity questions and quality issues are left open for the demo.

Tables beyond the spec's 20: `deployment` (which build owns the database), `quality_issues` (the spec names the four checks but gives
their results no home) and `evidence_blobs` (sealed files on serverless hosts).

## Demo walkthrough (5 minutes)

1. Sign in as **io.mumbai** → case **C-101** → *Evidence*: the three complaints and the bank, KYC, call-record and chat evidence, all sealed.
2. *Review queue*: extraction highlights, identity questions (two "Rahul Sharma" records stay separate), intake quality checks.
3. *Cross-case*: P-77 links C-101 and C-102; *Similar method (MO)* proposes C-103 for comparison, passages side by side.
4. *Money trail*: M1/M2/M3 → HUB → P2P seller → wallet W-1; switch FIFO / LIFO / pro-rata.
5. *Leads* → **Potential convergence point**: the Evidence Receipt, unknowns (HUB beneficial owner), "What could make this wrong?".
6. *Challenge Mode*: exclude the M3 → HUB record → threshold not met, estimates uncertain, 4 approved drafts listed as affected but still
   live. Propose; switch role to **sup.mumbai**; approve → drafts marked *Needs re-approval*.
7. Export the handover bundle; *Verify handover* re-runs it; *Audit log* verifies against the signed checkpoint.

## Known limits

* **MO similarity** uses rule-based MO attributes plus TF-IDF text similarity, not the multilingual embedding model the spec names (it
  needs PyTorch, which neither the offline nor the serverless build carries). The 0.45 threshold was tuned on the demo data, not on
  held-out cases, and a Hindi complaint does not match its English equivalent.
* **Checkpoint key.** Locally the signing key lives in `var/keys/`, outside the data directory but on the same machine; the spec wants it
  on a supervisor's token. On Vercel, set `PRAMANA_CHECKPOINT_KEY` (`python -m pramana.cli checkpoint-key`); without it, checkpoints are
  skipped rather than signed with a throwaway key.
* **Analyst proposals** (`POST /proposals`) have no table in the spec's data model and are not built.
* No login rate limiting; no admin UI (users and cases are created with the CLI).

## Run it

```bash
# backend (Python 3.11)
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # Linux/macOS: .venv/bin/pip
.venv/Scripts/python -m spacy download en_core_web_sm    # optional: without it, extraction runs rules only
.venv/Scripts/python -m pramana.cli demo-reset            # after pulling schema changes
.venv/Scripts/python -m pramana.cli serve --demo          # demo build on :8000, seeds itself on first start

# frontend (Node 20+)
cd frontend && npm install && npm run dev                 # http://localhost:5173
```

Offline, one command: `docker compose up --build` → http://localhost:8080 (demo build by default).

Useful commands (`python -m pramana.cli …` from `backend/`):

| Command | What it does |
|---|---|
| `demo-reset [--preload-all]` | Wipe and reseed the demo build. By default the three Tri-City complaints are held back so the IO can upload them live in the demo |
| `create-user --username … --name … --role IO --unit MUM-CYB` | Standard build: create an account and print its TOTP enrolment URI once |
| `create-case`, `add-member` | Standard build: cases and membership (Admin UI is P1) |
| `verify-ledger [--demo]` | Verify the audit chain from the command line |

Tests: `cd backend && .venv/Scripts/python -m pytest`

## Builds

* **standard**: the real application. Password + TOTP sign-in, no role switcher, no seeded data. Data in `var/standard/`.
* **demo**: the isolated synthetic demo build. Role switcher, seeded from `dataset/tri_city_v1`. Data in `var/demo/` locally.

Each database records which build created it; the other build refuses to open it.

## Deploying to Vercel

The whole app deploys as one Vercel project: the React build is served statically and the API runs as a Python
function (`api/index.py`) under `/api`. Serverless hosts have no persistent disk and run many short-lived instances, so a
Vercel deployment differs from a local one:

| | Local / Docker | Vercel |
|---|---|---|
| Database | SQLite in `var/` | PostgreSQL (Vercel Postgres / Neon) |
| Sealed evidence | files in `var/<build>/evidence/` | `evidence_blobs` table in the same database, still re-hashed on every load |
| Audit-log serialisation | process lock | process lock + PostgreSQL advisory lock (safe across instances) |
| Schema + demo data | created on start-up | created once from the CLI; a cold start never creates or seeds |
| Extraction | rules + spaCy NER | rules only (spaCy is too large for a function; NER suggestions come from the seeded data) |
| Upload limit | 25 MB | 4 MB (Vercel caps request bodies at 4.5 MB) |

**Steps**

1. Import the repository into Vercel with the **repository root** as the project root. `vercel.json` sets the build.
2. In the project, add **Storage → Postgres** (Neon). This sets `POSTGRES_URL` for the project.
3. Add environment variables:
   * `PRAMANA_BUILD` = `demo` (or `standard`)
   * `PRAMANA_JWT_SECRET` = a random string of 32+ characters, e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`
   * `PRAMANA_CHECKPOINT_KEY` = the private key from `python -m pramana.cli checkpoint-key` (signs audit-log checkpoints; keep the
     printed public key to verify them)
4. Prepare the database **once, from your machine**, using the database's direct (non-pooled) connection string. For the demo build:

   ```bash
   cd backend
   PRAMANA_DB_URL="postgres://…" .venv/Scripts/python -m pramana.cli demo-reset --yes
   ```

   For the standard build use `init-db`, then `create-user` / `create-case` / `add-member` with the same `PRAMANA_DB_URL`.
   Against a remote database the demo is built locally first and copied in batches (about a minute). Re-run it after pulling changes
   that alter the schema.
5. Deploy. The function refuses to start without a Postgres URL, a JWT secret, or a prepared database, and says which is missing.

The demo build's role switcher lets anyone who can open the URL act as any demo role. The data is synthetic, but
consider Vercel's Deployment Protection if the link should not be public.

To run the test suite against real PostgreSQL (the Vercel configuration): `pip install pgserver` then
`python tests/run_postgres.py`.

## Roles and scope

The role decides what a user can do; case membership decides where. See `backend/pramana/permissions.py`.
Demo users: `io.mumbai`, `io.delhi`, `io.bengaluru`, `analyst.mumbai`, `sup.mumbai`, `sup.delhi`,
`sup.bengaluru`, `auditor`, `admin`. The Mumbai IO, analyst and supervisor are members of all three
Tri-City cases (a joint probe); every other cross-unit view needs an access request.

## Dataset: `dataset/tri_city_v1`

Entirely synthetic. Generated by `python dataset/generate.py` (seed 26189, byte-for-byte reproducible),
which fails if the data drifts from its own ground truth.

* 30 cases, 40 complaint narratives (6 Hindi/Hinglish), 195 accounts, 1,509 transactions, 3 bank branches, 6 bank officials.
* The **Tri-City Digital Arrest** network hidden inside realistic noise, exactly as the spec describes: C-101/C-102/C-103 →
  M1/M2/M3 (all opened at B-17 by E-45) → HUB (Shree Balaji Traders) inside one 43-minute window → P2P seller → wallet W-1
  (linked only by the seized chat). M2 mixes ₹50,000 salary with the victim's ₹58,000 and pays ₹2,000 to a grocer. Two "Rahul Sharma" records.
* Every transfer carries one bank reference on both statements, so two statements of one transfer are recognised as one source (this is what makes FX-26 behave as specified).
* Hard negatives (shared utility billers, same-script unrelated cases, a shared family phone, officials just under the threshold) and one of each planted intake quality issue.
* `ground_truth.json` lists labels, expected rule observations, expected silences, and planted issues. `manifest.json` has every file's SHA-256.

## Security notes and known limits

* The audit log is **tamper-evident, not a blockchain**: guaranteed up to the latest signed checkpoint kept outside the database; entries after it are reported as outside the guaranteed region.
* Ledger appends are serialised by an in-process lock, plus a PostgreSQL advisory lock when running on PostgreSQL. On SQLite, run one API worker process.
* No login rate limiting yet.
* A matching file hash shows the file is unchanged since upload, not that its content is true or who made it.

## Layout

```
api/index.py          Vercel function entry (mounts the API under /api)
vercel.json           Vercel build, function and rewrite settings
requirements.txt      Python dependencies of the Vercel function
backend/pramana/      FastAPI app: config, models, ledger, security, permissions, storage, extraction, identity, graph, routers
backend/tests/        pytest suite; tests/run_postgres.py runs it against PostgreSQL
dataset/generate.py   synthetic dataset generator + self-checks (dataset/gen/)
dataset/tri_city_v1   generated dataset (committed)
frontend/             React + TypeScript + Vite UI
```
