from __future__ import annotations
from typing import Optional
import logging
import httpx

from langchain_core.tools import tool
from app.settings import settings

logger = logging.getLogger(__name__)

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False


# ==================================================
# 1) Calculator
# ==================================================
@tool
async def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """Perform basic arithmetic. operation must be one of: add, sub, mul, div."""
    try:
        if operation == "add":
            result = first_num + second_num
        elif operation == "sub":
            result = first_num - second_num
        elif operation == "mul":
            result = first_num * second_num
        elif operation == "div":
            if second_num == 0:
                return {"error": "Division by zero"}
            result = first_num / second_num
        else:
            return {"error": f"Invalid operation '{operation}'. Use add, sub, mul, or div."}
        return {"operation": operation, "result": result}
    except Exception as e:
        logger.exception("Calculator failed")
        return {"error": str(e)}


# ==================================================
# 2) Stock Price (Alpha Vantage)
# ==================================================
@tool
async def get_stock_price(symbol: str) -> dict:
    """Fetch the latest stock price for a ticker symbol (e.g. AAPL, TCS.BSE) using Alpha Vantage."""
    if not settings.ALPHAVANTAGE_API_KEY:
        return {"error": "Stock price lookup is not configured (missing API key)."}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://www.alphavantage.co/query",
                params={"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": settings.ALPHAVANTAGE_API_KEY},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.exception("Stock fetch failed")
        return {"error": str(e)}


# ==================================================
# 3) Web Search (DuckDuckGo — free, no API key)
# ==================================================
@tool
async def web_search(query: str, max_results: int = 5) -> dict:
    """Search the web for current/real-time information not available in the documents."""
    try:
        if DDGS_AVAILABLE:
            with DDGS() as ddg:
                results = list(ddg.text(query, max_results=max_results))
            return {"query": query, "results": results}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://duckduckgo.com/html/", params={"q": query})
            return {"query": query, "html": resp.text[:2000]}
    except Exception as e:
        logger.exception("Web search failed")
        return {"error": str(e)}


# ==================================================
# 4) RAG re-query tool (adapted to new schema)
# ==================================================
@tool
async def rag_lookup(query: str, document_ids_csv: Optional[str] = None) -> dict:
    """
    Re-query the user's uploaded documents mid-conversation if the agent needs
    additional/different information than what was already retrieved.
    document_ids_csv: optional comma-separated document IDs to restrict search to.
    """
    try:
        from app.db.session import AsyncSessionLocal
        from app.core.rag import retrieve

        document_ids = document_ids_csv.split(",") if document_ids_csv else None

        async with AsyncSessionLocal() as db:
            chunks = await retrieve(db, query, document_ids=document_ids)

        return {
            "query": query,
            "results": [{"text": c["content"], "document_id": c["document_id"], "page_number": c.get("page_number")} for c in chunks],
        }
    except Exception as e:
        logger.exception("RAG lookup tool failed")
        return {"error": str(e)}


def get_custom_tools() -> list:
    return [calculator, get_stock_price, web_search, rag_lookup]