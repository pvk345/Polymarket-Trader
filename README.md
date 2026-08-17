# Polymarket Trader

A full-stack automated paper trading platform that correlates Polymarket prediction market probabilities with stock trades via the Alpaca API.

**Live Demo:** https://polymarket-trader-pied.vercel.app  
**Backend API:** https://polymarket-trader-backend.onrender.com/docs

## What It Does

Watches Polymarket prediction markets in real-time. When a market probability crosses a threshold you define, it automatically places a paper trade on a stock ticker via Alpaca.

**Example:** If the probability of a Fed rate cut rises above 70% → automatically buy TLT (20-year Treasury ETF)

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, Recharts |
| Backend | FastAPI (Python 3.11) |
| Database | PostgreSQL (Supabase) |
| Cache | Redis (Upstash) |
| Trading | Alpaca Paper Trading API |
| Markets | Polymarket Gamma API |
| Auth | JWT + bcrypt |
| Deployment | Vercel + Render |

## Features

- Live market watching — polls Polymarket every 30s, detects probability shifts
- Rule engine — keyword matching, probability thresholds, dynamic position sizing
- Exit strategies — take profit, stop loss, probability-based exits
- P&L tracking — realized/unrealized P&L, win rate, per-rule performance
- Backtesting — simulate rules against historical Polymarket and stock data
- Watchlist — track any ticker with price alerts and browser notifications
- Multi-user auth — register/login with bcrypt passwords and JWT tokens
- Market hours — live countdown to open/close, enforces no trades after hours

## How Rules Work

Each rule has three parts:

**Entry signal**
- Keyword to match against Polymarket market titles (e.g. "Fed", "recession", "tariff")
- Condition: probability above or below a threshold
- Action: buy or sell a stock ticker

**Position sizing**
- Fixed: same number of shares every time
- Dynamic: scales shares between a min and max based on confidence

**Exit strategy**
- Probability drops/rises past a threshold
- Take profit at X% gain
- Stop loss at X% loss
- No exit (hold indefinitely)

## Quick Start

### Prerequisites
- Docker Desktop
- Alpaca paper trading account (free at alpaca.markets)

### 1. Clone

```bash
git clone https://github.com/Keshav-08/polymarket-trader
cd polymarket-trader
```

### 2. Configure

Create `backend/.env`:
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_PAPER=true
JWT_SECRET=your_secret_key

### 3. Run

```bash
docker-compose up --build
```

### 4. Open

Go to http://localhost:3000, create an account, and start building rules.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Login, returns JWT |
| GET | `/api/markets` | Live Polymarket data |
| GET | `/api/rules` | List rules |
| POST | `/api/rules` | Create rule |
| GET | `/api/pnl` | Portfolio P&L |
| GET | `/api/history` | Trade history |
| GET | `/api/backtest` | Run backtest |
| GET | `/api/watchlist` | Price watchlist |
| GET | `/api/settings` | App configuration |

## Deployment

| Service | Platform |
|---------|----------|
| Frontend | Vercel |
| Backend | Render |
| Database | Supabase (PostgreSQL) |
| Cache | Upstash (Redis) |

## Built By

Keshav — Rutgers CS Class of 2027
