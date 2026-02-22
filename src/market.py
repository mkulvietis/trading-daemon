"""
Market data access layer.
Centralises all communication with the data-service API.
"""
import logging
from datetime import datetime, time
import pytz
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

NY_TZ = pytz.timezone('America/New_York')
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)

DATA_SERVICE_BASE = "http://localhost:8000"

# Configure a session with retries and connection pooling
_session = requests.Session()
retries = Retry(total=3, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
_session.mount('http://', HTTPAdapter(max_retries=retries))


def is_market_open() -> bool:
    """Checks if the current NY time is within market hours (9:30 - 16:00 ET, Mon-Fri)."""
    now_ny = datetime.now(NY_TZ)
    if now_ny.weekday() > 4:
        return False
    return MARKET_OPEN <= now_ny.time() <= MARKET_CLOSE


def fetch_current_price(ticker: str = "@ES") -> float:
    """Fetches the latest close price from data-service."""
    try:
        url = f"{DATA_SERVICE_BASE}/bars/{ticker}"
        params = {"timeframe": 1, "bars_back": 1}
        
        response = _session.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if data and isinstance(data, list) and len(data) > 0:
            return float(data[-1]['close'])
    except Exception as e:
        logger.debug(f"Failed to fetch price: {e}")
    return 0.0


def fetch_trendlines(ticker: str = "@ES", timeframe: int = 5) -> dict:
    """Fetches trendlines and price relations from data-service."""
    try:
        url = f"{DATA_SERVICE_BASE}/trendlines"
        payload = {
            "ticker": ticker,
            "bars_back": 200,
            "timeframes": [timeframe],
            "only_final": False,
        }
        
        # Determine if GET or POST based on previous usage. 
        # Usually search endpoints with complex payloads are POST, but let's check.
        # Original code used data=... which implies POST.
        response = _session.post(url, json=payload, timeout=5)
        response.raise_for_status()
        
        return response.json()
    except Exception as e:
        logger.debug(f"Failed to fetch trendlines: {e}")
        return {}
