"""HTTP client for stats.wnba.com JSON endpoints.

Phase 1: Database Schema & Historical Data Ingestion

Handles:
- Request headers (Host, User-Agent, Referer, Origin)
- Rate limiting (1.5s between calls)
- Timeouts (30s)
- Error handling
"""
import time
import logging
import requests

logger = logging.getLogger(__name__)

# Base URL and headers
BASE_URL = "https://stats.wnba.com/stats"
HEADERS = {
    "Host": "stats.wnba.com",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://stats.wnba.com/",
    "Origin": "https://stats.wnba.com",
}

# Rate limiting
RATE_LIMIT_DELAY = 1.5  # seconds between calls
last_request_time = 0


def fetch_endpoint(endpoint, params):
    """Fetch data from a stats.wnba.com endpoint.

    Args:
        endpoint: Endpoint name (e.g., "leaguedashteamstats")
        params: Dict of query parameters

    Returns:
        Parsed JSON response (or None on error)

    Raises:
        requests.RequestException on network/HTTP errors
        json.JSONDecodeError on invalid JSON
    """
    global last_request_time

    # Apply rate limiting
    elapsed = time.time() - last_request_time
    if elapsed < RATE_LIMIT_DELAY:
        delay = RATE_LIMIT_DELAY - elapsed
        logger.debug(f"Rate limiting: sleeping {delay:.2f}s")
        time.sleep(delay)

    url = f"{BASE_URL}/{endpoint}"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        last_request_time = time.time()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Request failed for {endpoint}: {e}")
        raise
