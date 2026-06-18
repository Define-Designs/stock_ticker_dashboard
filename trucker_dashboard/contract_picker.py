"""
Turns a directional stock signal (Lean CALLS / Lean PUTS) into ONE specific,
budget-respecting option contract - e.g. "AVGO $395 Call 06/18/26, ask
$4.20" - instead of just "AVGO calls". Strike/expiration selection follows
a few well-established options-buying heuristics (see config.py for the
full rationale on each constant):

  1. Target a delta around 0.60-0.70 ("stock replacement" zone) so the
     contract tracks the stock closely and isn't bleeding heavy time value.
  2. Only consider expirations inside a sane days-to-expiration window -
     skip 0-3 DTE (gamma/theta risk) and skip anything too far out (extra
     premium/theta drag for a swing-style signal).
  3. Require real liquidity (volume or open interest above a floor) - a
     contract that's cheap and at the right delta is still a bad pick if
     nobody's trading it, since that means a wide bid/ask spread and
     difficulty exiting the position.
  4. If the ideal-delta contract is over budget or too illiquid, walk
     toward the next-closest-delta strike in the same expiration before
     giving up on that expiration entirely.
"""
from datetime import date, datetime

from config import (
    TARGET_DELTA,
    MIN_DAYS_TO_EXPIRATION,
    MAX_DAYS_TO_EXPIRATION,
    MAX_CONTRACT_COST,
    MIN_CONTRACT_VOLUME,
    MIN_OPEN_INTEREST,
)
import options_provider


def _dte(expiration_str, today=None):
    today = today or date.today()
    exp = datetime.strptime(expiration_str, "%Y-%m-%d").date()
    return (exp - today).days


def _fmt_display_date(expiration_str):
    return datetime.strptime(expiration_str, "%Y-%m-%d").strftime("%m/%d/%y")


def _is_liquid(o):
    """Volume can legitimately be 0 early in the trading session even on a
    liquid name, so a contract passes if EITHER today's volume or open
    interest clears its floor."""
    volume = o.get("volume") or 0
    open_interest = o.get("open_interest") or 0
    return volume >= MIN_CONTRACT_VOLUME or open_interest >= MIN_OPEN_INTEREST


def _eligible_expirations(symbol, today=None):
    all_exps = sorted(options_provider.get_expirations(symbol))
    in_window = [e for e in all_exps if MIN_DAYS_TO_EXPIRATION <= _dte(e, today) <= MAX_DAYS_TO_EXPIRATION]
    if in_window:
        return in_window
    # Fallback: nearest expiration that's at least MIN_DAYS_TO_EXPIRATION out,
    # so we still avoid 0-3 DTE risk even if nothing fits the ideal window.
    far_enough = [e for e in all_exps if _dte(e, today) >= MIN_DAYS_TO_EXPIRATION]
    if far_enough:
        return far_enough[:1]
    return all_exps[:1] if all_exps else []


def pick_contract(symbol, direction, today=None):
    """direction: 'bullish' -> call, 'bearish' -> put.
    Returns a contract dict, or None if no usable chain data / nothing fit
    the budget."""
    option_type = "call" if direction == "bullish" else "put"
    target_delta = TARGET_DELTA if option_type == "call" else -TARGET_DELTA

    for expiration in _eligible_expirations(symbol, today):
        chain = options_provider.get_chain(symbol, expiration)
        candidates = [
            o for o in chain
            if o.get("option_type") == option_type
            and o.get("greeks") and o["greeks"].get("delta") is not None
            and o.get("ask") not in (None, 0)
            and _is_liquid(o)
        ]
        if not candidates:
            continue

        candidates.sort(key=lambda o: abs(o["greeks"]["delta"] - target_delta))

        for o in candidates:
            cost = round(o["ask"] * 100, 2)
            if cost <= MAX_CONTRACT_COST:
                return {
                    "symbol": symbol,
                    "option_type": option_type,
                    "strike": o["strike"],
                    "expiration": expiration,
                    "expiration_display": _fmt_display_date(expiration),
                    "ask": o["ask"],
                    "bid": o.get("bid"),
                    "delta": round(o["greeks"]["delta"], 2),
                    "cost": cost,
                    "dte": _dte(expiration, today),
                    "volume": o.get("volume") or 0,
                    "open_interest": o.get("open_interest") or 0,
                }
    return None
