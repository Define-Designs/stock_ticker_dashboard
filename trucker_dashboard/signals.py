"""
Python port of the SFX Algo Toolkit's 5-factor confluence logic.

This is a simplified re-implementation of the same ideas used in the Pine
Script indicator (EMA trend, MACD momentum, RSI, VWAP position, and a
support/resistance check), so the web dashboard can compute its own signals
without needing TradingView at all.
"""
from dataclasses import dataclass
import numpy as np


@dataclass
class TFSignal:
    direction: str   # "bullish" or "bearish"
    score: int        # confluence score (0-5) in favor of `direction`
    trend_up: bool
    macd_bull: bool
    rsi_bull: bool
    vwap_bull: bool
    htf_sr_bull: bool
    price: float
    rsi: float
    vwap: float


def ema(values, length):
    values = np.asarray(values, dtype=float)
    alpha = 2 / (length + 1)
    out = np.zeros_like(values)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def rsi(values, length=14):
    values = np.asarray(values, dtype=float)
    n = len(values)
    out = np.full(n, 50.0)
    if n <= length:
        return out

    deltas = np.diff(values)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = gains[:length].mean()
    avg_loss = losses[:length].mean()

    for i in range(length, n):
        if i > length:
            g = gains[i - 1]
            l = losses[i - 1]
            avg_gain = (avg_gain * (length - 1) + g) / length
            avg_loss = (avg_loss * (length - 1) + l) / length
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100 - (100 / (1 + rs))
    return out


def macd(values, fast=12, slow=26, signal=9):
    values = np.asarray(values, dtype=float)
    macd_line = ema(values, fast) - ema(values, slow)
    signal_line = ema(macd_line, signal)
    return macd_line, signal_line


def session_vwap(highs, lows, closes, volumes):
    """Cumulative VWAP across the supplied candle window (acts as a rolling
    session proxy - good enough for a glance-at-a-stop dashboard)."""
    typ = (np.asarray(highs) + np.asarray(lows) + np.asarray(closes)) / 3.0
    vol = np.asarray(volumes, dtype=float)
    cum_pv = np.cumsum(typ * vol)
    cum_v = np.cumsum(vol)
    with np.errstate(divide="ignore", invalid="ignore"):
        vwap = np.where(cum_v > 0, cum_pv / np.where(cum_v == 0, 1, cum_v), closes)
    return vwap


def recent_pivot_levels(highs, lows, lookback=20):
    highs = np.asarray(highs)[-lookback:]
    lows = np.asarray(lows)[-lookback:]
    return float(highs.max()), float(lows.min())


def evaluate_timeframe(candles):
    """
    candles: dict with keys 'o','h','l','c','v' (oldest -> newest lists)
    Returns a TFSignal evaluated on the most recent bar.
    """
    closes = candles["c"]
    highs = candles["h"]
    lows = candles["l"]
    vols = candles["v"]

    if len(closes) < 35:
        raise ValueError("Not enough candles to compute indicators (need 35+)")

    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    macd_line, signal_line = macd(closes)
    rsi_vals = rsi(closes, 14)
    vwap_vals = session_vwap(highs, lows, closes, vols)
    swing_high, swing_low = recent_pivot_levels(highs, lows, lookback=20)

    price = float(closes[-1])
    trend_up = bool(ema9[-1] > ema21[-1])
    macd_bull = bool(macd_line[-1] > signal_line[-1])
    rsi_bull = bool(rsi_vals[-1] > 50)
    vwap_bull = bool(price > vwap_vals[-1])
    mid = swing_low + (swing_high - swing_low) * 0.25
    htf_sr_bull = bool(price > swing_low and price >= mid)

    bull_score = sum([trend_up, macd_bull, rsi_bull, vwap_bull, htf_sr_bull])
    bear_score = 5 - bull_score

    if bull_score >= bear_score:
        direction, score = "bullish", bull_score
    else:
        direction, score = "bearish", bear_score

    return TFSignal(
        direction=direction,
        score=score,
        trend_up=trend_up,
        macd_bull=macd_bull,
        rsi_bull=rsi_bull,
        vwap_bull=vwap_bull,
        htf_sr_bull=htf_sr_bull,
        price=price,
        rsi=float(rsi_vals[-1]),
        vwap=float(vwap_vals[-1]),
    )


def combine_signals(entry: TFSignal, confirm: TFSignal, threshold=4):
    """
    Mirrors the indicator's multi-timeframe rule: both timeframes must agree
    on direction, AND the entry timeframe must hit the confluence threshold.
    """
    if entry.direction != confirm.direction:
        return "WAIT - Timeframes Conflict"
    if entry.score < threshold:
        return "WAIT - Low Confluence"
    return "Lean CALLS" if entry.direction == "bullish" else "Lean PUTS"
