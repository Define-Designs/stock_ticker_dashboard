"""
Thin wrapper around the Tradier Market Data API for live options chains.

A free Tradier developer account gives you a sandbox token with delayed
(not real-time, no funded brokerage account needed) options chain data -
strikes, expirations, bid/ask, and greeks (delta/gamma/theta/vega/IV via
ORATS). That's plenty for a system that already only rescans every
15-20 minutes. For true real-time chain data you'd need to be an actual
funded Tradier Brokerage customer and point TRADIER_BASE_URL at the
production host instead - see the deployment guide.
"""
import os
import time
import requests

_cache = {}
CACHE_TTL = 55  # seconds


def _base_url():
    return os.environ.get("TRADIER_BASE_URL", "https://sandbox.tradier.com/v1")


def _api_key():
    key = os.environ.get("TRADIER_API_KEY", "")
    if not key:
        raise RuntimeError("TRADIER_API_KEY environment variable is not set")
    return key


def _cached_get(path, params):
    cache_key = path + "|" + str(sorted(params.items()))
    now = time.time()
    if cache_key in _cache and now - _cache[cache_key][0] < CACHE_TTL:
        return _cache[cache_key][1]

    resp = requests.get(
        _base_url() + path,
        params=params,
        headers={"Authorization": f"Bearer {_api_key()}", "Accept": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    _cache[cache_key] = (now, data)
    return data


def get_expirations(symbol):
    """Returns a sorted list of 'YYYY-MM-DD' expiration date strings."""
    data = _cached_get("/markets/options/expirations", {
        "symbol": symbol,
        "includeAllRoots": "true",
        "strikes": "false",
    })
    dates = (data.get("expirations") or {}).get("date")
    if dates is None:
        return []
    if isinstance(dates, str):
        return [dates]
    return list(dates)


def get_chain(symbol, expiration):
    """Returns a list of option dicts (incl. greeks) for one expiration."""
    data = _cached_get("/markets/options/chains", {
        "symbol": symbol,
        "expiration": expiration,
        "greeks": "true",
    })
    options = (data.get("options") or {}).get("option")
    if options is None:
        return []
    if isinstance(options, dict):
        return [options]
    return list(options)
