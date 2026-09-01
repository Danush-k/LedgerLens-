# LedgerLens — Real-Time Crypto Fraud Attribution System

Traces a victim-reported cryptocurrency wallet address across its on-chain transaction
history and identifies the nearest known exchange/VASP that received the funds — turning
a manual, hours-long blockchain-tracing task into a seconds-to-minutes automated lookup.

Built for the SIH problem statement: *Real-Time Identification of Fraud-Linked
Cryptocurrency Exchanges from Victim-Reported Suspect Wallet Addresses through Automated
Blockchain Analytics.* See [PLAN.md](PLAN.md) for the full design rationale, build plan,
and learning path behind this implementation.

## What it does

1. An investigator (or a mock NCRP intake call) submits a wallet address + chain.
2. A background worker walks the address's real on-chain outgoing transactions, hop by
   hop, using free public block-explorer APIs — no node, no funds, no custody, ever.
3. Each hop is checked against a curated set of known exchange/mixer/bridge addresses.
   The trace stops a branch the moment it reaches a known exchange (the "nearest VASP"
   answer) or a mixer (a laundering signal).
4. An explainable, rule-based risk score (0–100) is computed from the trace: mixer/bridge
   hits, fan-out, timing, and whether the same wallet has been reported before.
5. Two explainable clustering heuristics run alongside the trace: common-input-ownership
   (Bitcoin, strong signal) and shared-funder fan-out (any chain, weaker signal) — grouping
   wallets likely controlled by the same actor.
6. A rule-based fraud-typology tagger classifies the complaint narrative (investment scam,
   sextortion, ransomware, phishing, task-based fraud, darknet) from the PS's own list.
7. The investigator dashboard (behind login) shows a portfolio-level analytics overview,
   the transaction graph with the highlighted path to the exchange, wallet clusters, the
   risk score breakdown (plus an illustrative ML-assisted v2 score once enough cases exist
   to train on), a recommended action, and a one-click PDF evidence report with a
   tamper-evident hash. Investigators can also submit a whole CSV of wallets at once.

## Tech stack

| Layer | Tool |
|---|---|
| API | FastAPI (Python) |
| Auth | JWT (PyJWT + bcrypt), two seeded demo accounts |
| Async tracing | Celery + Redis |
| Graph store | Neo4j |
| Case/metadata store | PostgreSQL |
| Chain data | Etherscan / BscScan / PolygonScan APIs (Ethereum, BSC, Polygon) + Blockstream Esplora API (Bitcoin), with retry/backoff on transient failures |
| Clustering | Common-input-ownership (Bitcoin) + shared-funder fan-out (any chain) |
| Risk scoring | Rule-based explainable rubric (v1) + scikit-learn-assisted score (v2, illustrative) |
| Typology tagging | Rule-based keyword classifier over the complaint narrative |
| Frontend | React + TypeScript + Vite + Tailwind + Cytoscape.js, with a GitHub-inspired light/dark theme, a Cmd+K command palette (`cmdk`), and toast notifications (`sonner`) |
| Reports | PDF via ReportLab, SHA-256 chain-of-custody hash |

Nothing in this system ever holds a private key, custodies funds, or requires a paid
API key — see [PLAN.md §0](PLAN.md#0-answering-the-practical-question-first-do-you-need-a-crypto-account)
for why.

## Running it

### Docker Compose (recommended — one command)

```bash
cp backend/.env.example backend/.env   # fill in free Etherscan/BscScan/PolygonScan keys
cp frontend/.env.example frontend/.env
docker compose up --build
```

- API: http://localhost:8000/docs
- Frontend: http://localhost:5173 — sign in with `investigator` / `changeme123` (or `admin` /
  `changeme123`), seeded automatically on first startup. Change these via env vars for
  anything beyond a local demo.
- Neo4j browser: http://localhost:7474 (neo4j / fraudmap123)

### Manually, without Docker

**Backend** (needs a running Postgres, Redis, and Neo4j — or point `.env` at Docker's):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in API keys
uvicorn app.main:app --reload          # API
celery -A app.worker.celery_app worker --loglevel=info   # in a second terminal
```

**Frontend:**

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

### Tests

```bash
cd backend && source .venv/bin/activate && pytest -q
```

Backend tests are self-contained (chain API calls are mocked) — no live services needed.

## Project structure

```
backend/app/
  auth/            JWT auth: password hashing, token issuing/verification
  chain_clients/    Ethereum/BSC/Polygon + Bitcoin readers (free public APIs, retry/backoff)
  labels/          Seed dataset of known exchange/mixer/bridge addresses
  tracer/          BFS tracing engine + clustering heuristics
  risk/            Rule-based scoring (v1), ML-assisted scoring (v2), typology tagging
  worker/          Celery async trace task
  db/              Postgres + Neo4j clients
  api/             REST endpoints (auth, trace, bulk upload, cases, analytics, integrations)
  integrations/    Mock NCRP/SAHYOG/VASP stand-ins (clearly labeled simulated)
  reports/         PDF evidence report generator
frontend/src/
  auth/            Auth context, login redirect, protected routes
  pages/           Overview dashboard, case list, new-trace form, bulk upload, case detail
  components/      Graph visualization, risk gauge, clusters, typology, status/flag badges
```

## Honest scope note

This is a hackathon prototype, not a production system. A few things worth being upfront
about:

- The label dataset is a small, hand-verified starter set (see
  `backend/app/labels/seed_labels.json` for sources) — a production deployment would use
  a licensed attribution feed or SAHYOG-mediated VASP data.
- The NCRP/SAHYOG integrations are simulated and clearly marked as such in the dashboard's
  Integration Log.
- The ML-assisted risk score (v2) is bootstrapped from the rule-based score itself (no real
  labelled fraud dataset exists to train on) — it demonstrates the pipeline, not a trained
  fraud detector. The rule-based score stays authoritative.
- The database uses `create_all()` at startup, not real migrations (no Alembic yet) — it
  creates missing tables but won't alter existing ones. A schema change means resetting the
  dev database (`docker compose down -v`), which is fine for a hackathon but is the first
  thing a production deployment would fix.

See [PLAN.md](PLAN.md) for the full roadmap.
