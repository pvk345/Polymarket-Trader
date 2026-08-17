from fastapi import APIRouter
import httpx

router = APIRouter()

@router.get("/health")
async def health_check():
    """Check that all services are reachable"""
    status = {
        "api": "ok",
        "polymarket": "unknown",
    }

    # Ping Polymarket API
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get("https://clob.polymarket.com/markets?limit=1")
            status["polymarket"] = "ok" if r.status_code == 200 else "error"
    except Exception:
        status["polymarket"] = "error"

    return status
