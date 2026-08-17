# Polymarket Trader

A full-stack automated paper trading platform that correlates Polymarket prediction market probabilities with stock trades via the Alpaca API — with a standalone AWS Lambda evaluator that keeps trading on schedule even when the web app isn't running.

**Live Demo:** https://frontend-delta-fawn-63.vercel.app
**Backend API:** https://polymarket-trader-85w9.onrender.com/docs

## What It Does

Watches Polymarket prediction markets in real-time. When a market probability crosses a threshold you define, it automatically places a paper trade on a stock ticker via Alpaca.

**Example:** If the probability of a Fed rate cut rises above 70% → automatically buy TLT (20-year Treasury ETF)

## Architecture

Two independent systems share one database, so trading keeps happening whether or not the web app is open:

```
Vercel (frontend) ──▶ Render (backend) ──▶ Supabase (Postgres)
                                                  ▲
                          AWS Lambda ─────────────┘
                       (EventBridge-scheduled,
                        runs every minute on its own)
```

- The **web app** (Vercel + Render) is what you actually interact with — dashboard, rule builder, backtesting, watchlist.
- The **AWS Lambda** is a separate, self-contained evaluator with its own copy of the rule-matching and trade-execution logic. It reads the same rules and writes to the same trigger log, but doesn't call the backend at all — it connects to Polymarket, Supabase, and Alpaca directly, on its own schedule, independent of whether the backend or frontend are even running.
- **Supabase is the single source of truth.** Local dev, the Render deployment, and the Lambda all point at the same database, so a rule created anywhere is visible everywhere.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, Recharts |
| Backend | FastAPI (Python 3.11) |
| Always-on evaluator | AWS Lambda (container image) + EventBridge Scheduler |
| Database | PostgreSQL (Supabase) — shared by backend, Lambda, and local dev |
| Cache | Redis (Render-managed in production, local container in dev) |
| Trading | Alpaca Paper Trading API |
| Markets | Polymarket Gamma API (`/markets/keyset`, cursor-paginated) |
| Auth | JWT + bcrypt |
| Deployment | Vercel (frontend) + Render (backend + Redis) + AWS (Lambda + EventBridge) |

## Features

- Live market watching — polls Polymarket every 30s, paginates up to 500 markets by 24hr volume, detects probability shifts
- Rule engine, three ways to define entry conditions:
  - **Keyword** — matches any market whose question contains a given phrase
  - **Exact market** — pin to one specific Polymarket market by ID, searched and selected directly (stays watched even if it drops out of the top-volume list)
  - **Multi-market AND** — pin to several markets at once, each with its own condition and threshold; the rule only fires when *all* of them are true simultaneously
- Full rule editing — change any field on an existing rule without deleting and recreating it
- Dynamic position sizing — scales shares between a min and max based on probability confidence (keyword/single-market rules only)
- Exit strategies — take profit, stop loss, probability-based exits
- Cooldowns and max-trade-size guards to prevent runaway repeat firing
- P&L tracking — realized/unrealized P&L, win rate, per-rule performance
- Backtesting — simulate rules against historical Polymarket and stock data, either by keyword or by picking an exact market
- Watchlist — track any ticker with price alerts
- Multi-user auth — register/login with bcrypt passwords and JWT tokens
- Market hours — enforces no trades outside 9:30am-4pm ET, Mon-Fri, on both the backend and the Lambda
- **Runs independently of the web app** — the AWS Lambda evaluator keeps checking rules and placing trades on a 1-minute schedule even if the frontend and backend are both down

## How Rules Work

Each rule has three parts:

**Entry signal** — pick one of:
- *Keyword*: matches any market whose question contains the text (e.g. "Fed", "recession", "tariff")
- *Exact market*: search Polymarket directly and pin to one specific market by ID
- *Multiple markets (AND)*: pin to several markets, each with its own probability condition — all must be true at once to fire

Each condition (or the single keyword condition) specifies: probability above or below a threshold, and the ticker/action (buy or sell) to trade.

**Position sizing**
- Fixed: same number of shares every time
- Dynamic: scales shares between a min and max based on confidence (only available for keyword or single-exact-market rules)

**Exit strategy**
- Probability drops/rises past a threshold
- Take profit at X% gain
- Stop loss at X% loss
- No exit (hold indefinitely)

## Always-On Trading (AWS Lambda)

The web app's rule evaluation only runs when the dashboard is open and polling. The `lambda/` directory contains a completely separate, self-contained port of the same evaluation logic — packaged as a Docker container image and deployed to AWS Lambda, triggered every minute by an EventBridge schedule.

It has no HTTP interface and doesn't talk to the backend at all — it connects directly to:
- **Polymarket's Gamma API** for current odds
- **Supabase** to read active rules and write trigger logs
- **Alpaca** to place orders

This means trades keep happening on schedule regardless of whether your laptop is on, Docker is running, or the deployed backend is asleep. See `lambda/handler.py` for the entry point.

## Quick Start (local dev)

### Prerequisites
- Docker Desktop
- Alpaca paper trading account (free at alpaca.markets)
- A Supabase project (or point at a local Postgres instead — see `docker-compose.yml`)

### 1. Clone

```bash
git clone https://github.com/pvk345/Polymarket-Trader
cd Polymarket-Trader
```

### 2. Configure

Create `backend/.env`:
```
DATABASE_URL=postgresql://...   # Supabase connection string, or local Postgres
REDIS_URL=redis://redis:6379
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_PAPER=true
JWT_SECRET=your_secret_key
```

### 3. Run

```bash
docker compose up --build
```

This starts the frontend, backend, and a local Redis cache. There's no local Postgres container by default — the backend connects straight to `DATABASE_URL`.

### 4. Open

Go to http://localhost:3000, create an account, and start building rules.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Login, returns JWT |
| GET | `/api/markets` | Live Polymarket data (paginated, up to 500 markets) |
| GET | `/api/rules` | List rules |
| POST | `/api/rules` | Create rule (keyword, exact-market, or multi-market AND) |
| PUT | `/api/rules/{id}` | Edit an existing rule |
| DELETE | `/api/rules/{id}` | Delete a rule |
| PATCH | `/api/rules/{id}/toggle` | Pause/resume a rule |
| GET | `/api/rules/performance` | Per-rule realized P&L |
| GET | `/api/pnl` | Portfolio P&L |
| GET | `/api/history` | Trade history |
| GET | `/api/backtest` | Run backtest (by keyword or exact market) |
| GET | `/api/watchlist` | Price watchlist |
| GET | `/api/settings` | App configuration |

## Deployment

| Service | Platform |
|---------|----------|
| Frontend | Vercel |
| Backend | Render |
| Always-on evaluator | AWS Lambda + EventBridge Scheduler |
| Container registry | AWS ECR |
| Database | Supabase (PostgreSQL) — shared by backend and Lambda |
| Cache | Render (managed Redis/Key-Value) |

## Built By
Prateek Komarla Class of 2028
