"""
Lightweight win/loss tracker for the option calls this app actually sends.

A "call" is tracked the moment a setup first shows up in a sent digest - one
tracked trade per unique symbol/strike/expiration/option_type combination, so
the same setup re-appearing across scan cycles doesn't create duplicates.
Every tracked trade is graded automatically with no manual input, using a
two-part rule meant to match how an option buyer would actually judge the
trade:

  - WIN if the stock ever reaches the picked strike before expiration (the
    contract would have gone in-the-money), OR if the stock simply moves in
    the predicted direction at all relative to its price when the alert
    fired - even short of the strike, that still means the contract gained
    value at some point, since it's worth more the closer the stock gets to
    the strike.
  - LOSS only if, by expiration, the stock never once traded above (for a
    call) or below (for a put) its alert-time price.

This can't replicate minute-by-minute option pricing, but it matches the
plain-English standard this feature is meant to report against: did the
trade move the way it was supposed to before the contract expired.

NOTE: like scan_state.json, this file lives on local disk (/tmp), which is
fine for a single always-on Render instance but is NOT persisted across a
redeploy or a free-tier instance spinning down - history can reset. That's
an accepted tradeoff for keeping this app free and database-free.
"""
import json
import os
import time
from datetime import date, datetime

TRACK_FILE = "/tmp/track_record.json"


def _load():
    if os.path.exists(TRACK_FILE):
        try:
            with open(TRACK_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"records": {}}


def _save(data):
    with open(TRACK_FILE, "w") as f:
        json.dump(data, f)


def _key(symbol, option_type, strike, expiration):
    return f"{symbol}|{option_type}|{strike}|{expiration}"


def record_new_alert(pick, now=None):
    """pick: one item from top_picks (a result dict with 'contract' set).
    No-op if this exact symbol/strike/expiration/option_type combo is
    already being tracked (open OR closed), so a setup that keeps
    re-qualifying across scan cycles is only graded once."""
    contract = pick.get("contract")
    if not contract:
        return
    now = now if now is not None else time.time()
    data = _load()
    key = _key(pick["symbol"], contract["option_type"], contract["strike"], contract["expiration"])
    if key in data["records"]:
        return
    entry_price = pick["price"]
    data["records"][key] = {
        "symbol": pick["symbol"],
        "option_type": contract["option_type"],
        "strike": contract["strike"],
        "expiration": contract["expiration"],
        "expiration_display": contract.get("expiration_display"),
        "entry_price": entry_price,
        "entry_score": pick.get("entry_score"),
        "alert_at": now,
        "best_price": entry_price,
        "reached_strike": False,
        "status": "open",
        "close_reason": None,
        "closed_at": None,
    }
    _save(data)


def update_with_prices(price_map):
    """price_map: {symbol: latest_price} from whatever batch was just
    scanned. Updates the most-favorable price seen so far for every open
    record on those symbols, and flags it if the strike has been reached."""
    if not price_map:
        return
    data = _load()
    changed = False
    for rec in data["records"].values():
        if rec["status"] != "open":
            continue
        price = price_map.get(rec["symbol"])
        if price is None:
            continue
        changed = True
        if rec["option_type"] == "call":
            if price > rec["best_price"]:
                rec["best_price"] = price
            if price >= rec["strike"]:
                rec["reached_strike"] = True
        else:
            if price < rec["best_price"]:
                rec["best_price"] = price
            if price <= rec["strike"]:
                rec["reached_strike"] = True
    if changed:
        _save(data)


def finalize_expired(today=None, now=None):
    """Closes out any open record whose expiration date has passed, grading
    it win/loss off the best price seen during its life (see module
    docstring for the win/loss rule)."""
    today = today or date.today()
    now = now if now is not None else time.time()
    data = _load()
    changed = False
    for rec in data["records"].values():
        if rec["status"] != "open":
            continue
        exp = datetime.strptime(rec["expiration"], "%Y-%m-%d").date()
        if today <= exp:
            continue
        changed = True
        if rec["reached_strike"]:
            rec["status"], rec["close_reason"] = "win", "reached_strike"
        elif (rec["option_type"] == "call" and rec["best_price"] > rec["entry_price"]) or \
             (rec["option_type"] == "put" and rec["best_price"] < rec["entry_price"]):
            rec["status"], rec["close_reason"] = "win", "favorable_move"
        else:
            rec["status"], rec["close_reason"] = "loss", "no_favorable_move_by_expiration"
        rec["closed_at"] = now
    if changed:
        _save(data)


def get_summary(recent_limit=10):
    """Win-rate stats plus the most recently closed trades, newest first -
    what the dashboard's Track Record panel renders."""
    data = _load()
    records = list(data["records"].values())
    closed = [r for r in records if r["status"] != "open"]
    wins = [r for r in closed if r["status"] == "win"]
    losses = [r for r in closed if r["status"] == "loss"]
    win_rate = round(100 * len(wins) / len(closed), 1) if closed else None
    recent = sorted(closed, key=lambda r: r["closed_at"], reverse=True)[:recent_limit]
    return {
        "win_rate": win_rate,
        "wins": len(wins),
        "losses": len(losses),
        "open": len(records) - len(closed),
        "recent": recent,
    }
