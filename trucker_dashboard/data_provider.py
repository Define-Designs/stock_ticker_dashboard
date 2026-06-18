"""
Thin wrapper around the Finnhub free API, with a small in-memory cache so we
stay comfortably inside the free plan's 60-calls-per-minute limit even when
the dashboard auto-refreshes.
"""
import os
import time
import requests

FINNHUB_BASE = "https://finnhub.io/api/v1"

_cache = {}
CACHE_TTL = 55  # seconds


def _api_key():
    key = os.environ.get("FINNHUB_API_KEY", "")
    if not key:
        raise RuntimeError("FINNHUB_API_KEY environment variable is not set")
    return key


def _cached_get(url, params, ttl=CACHE_TTL):
    cache_key = url + "|" + str(sorted(params.items()))
    now = time.time()
    if cache_key in _cache and now - _cache[cache_key][0] < ttl:
        return _cache[cache_key][1]

    full_params = dict(params)
    full_params["token"] = _api_key()
    resp = requests.get(url, params=full_params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    _cache[cache_key] = (now, data)
    return data


def get_candles(symbol, resolution, lookback_seconds):
    """resolution: Finnhub resolution string, e.g. '15' or '60' (minutes)."""
    now = int(time.time())
    frm = now - lookback_seconds
    data = _cached_get(f"{FINNHUB_BASE}/stock/candle", {
        "symbol": symbol,
        "resolution": resolution,
        "from": frm,
        "to": now,
    })
    if data.get("s") != "ok":
        raise RuntimeError(f"No candle data for {symbol} (status={data.get('s')})")
    return {"o": data["o"], "h": data["h"], "l": data["l"], "c": data["c"], "v": data["v"], "t": data["t"]}
