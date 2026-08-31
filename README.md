# FraudMap — Real-Time Crypto Fraud Attribution System

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
5. The investigator dashboard shows the transaction graph, the highlighted path to the
   exchange, the risk score breakdown, a recommended action, and a one-click PDF
   evidence report with a tamper-evident hash.

## Tech stack

| Layer | Tool |
|---|---|
| API | FastAPI (Python) |
| Async tracing | Celery + Redis |
| Graph store | Neo4j |
| Case/metadata store | PostgreSQL |
| Chain data | Etherscan / BscScan / PolygonScan APIs (Ethereum, BSC, Polygon) + Blockstream Esplora API (Bitcoin) |
| Risk scoring | Rule-based, explainable rubric |
| Frontend | React + TypeScript + Vite + Tailwind + Cytoscape.js |
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
- Frontend: http://localhost:5173
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
  chain_clients/   Ethereum/BSC/Polygon + Bitcoin readers (free public APIs)
  labels/          Seed dataset of known exchange/mixer/bridge addresses
  tracer/          BFS tracing engine
  risk/            Explainable rule-based risk scoring
  worker/          Celery async trace task
  db/              Postgres + Neo4j clients
  api/             REST endpoints
  integrations/    Mock NCRP/SAHYOG/VASP stand-ins (clearly labeled simulated)
  reports/         PDF evidence report generator
frontend/src/
  pages/           Case list, new-trace form, case detail
  components/      Graph visualization, risk gauge, status/flag badges
```

## Honest scope note

This is a hackathon prototype, not a production system. The label dataset is a small,
hand-verified starter set (see `backend/app/labels/seed_labels.json` for sources) —
a production deployment would use a licensed attribution feed or SAHYOG-mediated VASP
data. The NCRP/SAHYOG integrations are simulated and clearly marked as such in the
dashboard's Integration Log. See [PLAN.md](PLAN.md) for the full roadmap.
