"""
Thin wrapper around yfinance (unofficial Yahoo Finance data) for options
chains - no signup, no API key, and no identity verification, which is why
this is the provider this app uses by default.

Yahoo doesn't publish greeks, so delta is computed locally with the
standard Black-Scholes formula, using the implied volatility yfinance does
provide along with bid/ask/volume/open interest. Black-Scholes delta is a
well-established approximation for liquid, near-term equity options - not a
perfect substitute for a broker's live greeks feed, but plenty accurate for
picking a delta-target strike on the names this scanner targets.

NOTE: yfinance scrapes Yahoo's public site rather than calling a documented,
supported API, so it can occasionally break or get rate-limited if hit too
hard. The short cache below (55s) keeps repeat lookups during a scan cycle
from hammering it. If Yahoo ever becomes unreliable, swap this file out for
a paid provider (Tradier, MarketData.app, etc.) - contract_picker.py and the
rest of the app don't need to change, since they only depend on
get_expirations()/get_chain() returning the same shape.
"""
import math
import time
from datetime import date, datetime

import pandas as pd
import yfinance as yf

from config import RISK_FREE_RATE

_cache = {}
CACHE_TTL = 55  # seconds


def _cached(key, fetch_fn):
    now = time.time()
    if key in _cache and now - _cache[key][0] < CACHE_TTL:
        return _cache[key][1]
    value = fetch_fn()
    _cache[key] = (now, value)
    return value


def _num(value):
    """yfinance hands back NaN (not None) for missing bid/ask/volume/etc on
    illiquid strikes - normalize that to None/0 so the rest of the app
    doesn't need to know about pandas NaN."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return value


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _bs_delta(option_type, underlying_price, strike, days_to_expiration, iv):
    """Black-Scholes delta. Returns None (rather than a misleading guess) if
    any input is unusable - e.g. iv of 0 from a stale/illiquid quote, or an
    expiration that's already today."""
    if not underlying_price or not strike or not iv or days_to_expiration <= 0:
        return None
    t = days_to_expiration / 365.0
    try:
        d1 = (
            math.log(underlying_price / strike) + (RISK_FREE_RATE + 0.5 * iv ** 2) * t
        ) / (iv * math.sqrt(t))
    except (ValueError, ZeroDivisionError):
        return None
    if option_type == "call":
        return _norm_cdf(d1)
    return _norm_cdf(d1) - 1.0


def _underlying_price(symbol, ticker):
    def fetch():
        try:
            price = ticker.fast_info.get("lastPrice") or ticker.fast_info.get("last_price")
            if price:
                return float(price)
        except Exception:
            pass
        hist = ticker.history(period="1d")
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1])
        return None
    return _cached(f"price|{symbol}", fetch)


def get_expirations(symbol):
    """Returns a sorted list of 'YYYY-MM-DD' expiration date strings."""
    def fetch():
        ticker = yf.Ticker(symbol)
        return sorted(ticker.options or [])
    return _cached(f"exp|{symbol}", fetch)


def get_chain(symbol, expiration):
    """Returns a list of option dicts (incl. computed greeks) for one
    expiration, in the same shape every provider in this app returns:
    option_type, strike, bid, ask, greeks.delta, volume, open_interest."""
    def fetch():
        ticker = yf.Ticker(symbol)
        underlying_price = _underlying_price(symbol, ticker)
        dte = (datetime.strptime(expiration, "%Y-%m-%d").date() - date.today()).days

        chain = ticker.option_chain(expiration)
        rows = []
        for option_type, df in (("call", chain.calls), ("put", chain.puts)):
            for _, row in df.iterrows():
                strike = _num(row.get("strike"))
                iv = _num(row.get("impliedVolatility"))
                delta = _bs_delta(option_type, underlying_price, strike, dte, iv)
                rows.append({
                    "option_type": option_type,
                    "strike": strike,
                    "bid": _num(row.get("bid")),
                    "ask": _num(row.get("ask")),
                    "greeks": {"delta": round(delta, 4) if delta is not None else None},
                    "volume": int(_num(row.get("volume")) or 0),
                    "open_interest": int(_num(row.get("openInterest")) or 0),
                })
        return rows
    return _cached(f"chain|{symbol}|{expiration}", fetch)
