from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.api import health, markets, portfolio, rules, trades, history, backtest, pnl, settings, watchlist
from app.api.auth import router as auth_router, get_current_user, create_users_table
from app.core.database import create_tables

app = FastAPI(title="Polymarket Trader API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    create_tables()
    create_users_table()
    print("✅ Database tables ready")

# Public routes
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(health.router, prefix="/api", tags=["health"])

# Protected routes
protected = {"dependencies": [Depends(get_current_user)]}
app.include_router(markets.router, prefix="/api", tags=["markets"], **protected)
app.include_router(portfolio.router, prefix="/api", tags=["portfolio"], **protected)
app.include_router(rules.router, prefix="/api", tags=["rules"], **protected)
app.include_router(trades.router, prefix="/api", tags=["trades"], **protected)
app.include_router(history.router, prefix="/api", tags=["history"], **protected)
app.include_router(backtest.router, prefix="/api", tags=["backtest"], **protected)
app.include_router(pnl.router, prefix="/api", tags=["pnl"], **protected)
app.include_router(settings.router, prefix="/api", tags=["settings"], **protected)
app.include_router(watchlist.router, prefix="/api", tags=["watchlist"], **protected)

@app.get("/")
def root():
    return {"message": "Polymarket Trader API v1.0.0 running"}
