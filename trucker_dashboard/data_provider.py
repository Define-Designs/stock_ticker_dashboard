"""
Thin wrapper around yfinance (unofficial Yahoo Finance data) for OHLCV
candles - no signup, no API key needed.

This app originally pulled candles from Finnhub's free API, but Finnhub has
since moved its intraday /stock/candle endpoint behind a paid plan - free
keys now get a 403 Forbidden on every symbol, which is why a full day of
scanning could complete 19/19 batches while never actually checking a single
ticker. Yahoo's intraday history is the same kind of free, unofficial data
this app already relies on for option chains (see options_provider.py), so
candles were switched over to match it - one less paid dependency, and one
less thing that can silently break a whole day of scanning.

NOTE: yfinance only keeps a limited intraday history window (roughly 60 days
for 15m/60m bars), which is well within the lookbacks this app actually asks
for (config.py's ENTRY_LOOKBACK_SECONDS / CONFIRM_LOOKBACK_SECONDS are a few
days to a few weeks), so nothing here is cut short by that limit.

NOTE: candles are fetched with history(period=...), not history(start=...).
Passing a start/end date makes yfinance fire an extra "timezone lookup"
request before the real data request; when Yahoo throttles that lookup
(429), yfinance mishandles the response and raises a misleading
"Expecting value: line 1 column 1 (char 0)" JSON error on every single
ticker instead of a clear rate-limit error. Using period= skips that extra
request entirely and avoids the bug (see yfinance issue #2179 on GitHub).
"""
import time

import yfinance as yf

_cache = {}
CACHE_TTL = 55  # seconds


def _cached(key, fetch_fn):
    now = time.time()
    if key in _cache and now - _cache[key][0] < CACHE_TTL:
        return _cache[key][1]
    value = fetch_fn()
    _cache[key] = (now, value)
    return value


def _yf_interval(resolution):
    """Map this app's old Finnhub-style resolution strings ('15', '60', ...,
    still set in config.py as ENTRY_RESOLUTION/CONFIRM_RESOLUTION) to a
    yfinance interval string."""
    if resolution.isdigit():
        return f"{resolution}m"
    return {"D": "1d", "W": "1wk", "M": "1mo"}.get(resolution, resolution)


def _yf_period(lookback_seconds):
    """Map a lookback window to one of yfinance's fixed period= buckets
    (the strings it actually accepts), padded up generously so a
    holiday/weekend gap never leaves us short of bars. Deliberately coarse -
    Yahoo's own ~60-day cap on intraday history means there's no benefit to
    finer-grained buckets here."""
    days = lookback_seconds / 86400
    if days <= 5:
        return "5d"
    if days <= 30:
        return "1mo"
    if days <= 60:
        return "3mo"
    return "6mo"


def get_candles(symbol, resolution, lookback_seconds):
    """resolution: '15' or '60' (minutes), matching config.py.
    Returns a dict with keys 'o','h','l','c','v' (oldest -> newest lists)."""
    interval = _yf_interval(resolution)
    period = _yf_period(lookback_seconds)

    def fetch():
        hist = yf.Ticker(symbol).history(period=period, interval=interval)
        if hist is None or hist.empty:
            raise RuntimeError(f"No candle data for {symbol}")
        return {
            "o": hist["Open"].tolist(),
            "h": hist["High"].tolist(),
            "l": hist["Low"].tolist(),
            "c": hist["Close"].tolist(),
            "v": hist["Volume"].tolist(),
        }
    return _cached(f"candles|{symbol}|{resolution}|{lookback_seconds}", fetch)
