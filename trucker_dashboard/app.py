import os
import json
import time
import math

from flask import Flask, render_template, jsonify, request

from config import (
    UNIVERSE,
    BATCH_SIZE,
    ENTRY_RESOLUTION,
    CONFIRM_RESOLUTION,
    ENTRY_LOOKBACK_SECONDS,
    CONFIRM_LOOKBACK_SECONDS,
    CONFLUENCE_THRESHOLD,
    TOP_N_ALERTS,
    MAX_CONTRACT_COST,
)
from data_provider import get_candles
from signals import evaluate_timeframe, combine_signals
from notify import send_alert_digest
import contract_picker
import track_record

app = Flask(__name__)

STATE_FILE = "/tmp/scan_state.json"

ACTIONABLE_LEANS = ("Lean CALLS", "Lean PUTS")


def get_batches():
    """Split the universe into fixed-size chunks. One chunk = one cron call."""
    return [UNIVERSE[i:i + BATCH_SIZE] for i in range(0, len(UNIVERSE), BATCH_SIZE)]


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "next_batch_index": 0,
        "results": {},
        "rotation_started_at": time.time(),
        "last_full_rotation_completed_at": None,
        "last_alert_signature": [],
        "last_alert_at": None,
    }


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def compute_ticker(symbol):
    entry_candles = get_candles(symbol, ENTRY_RESOLUTION, ENTRY_LOOKBACK_SECONDS)
    confirm_candles = get_candles(symbol, CONFIRM_RESOLUTION, CONFIRM_LOOKBACK_SECONDS)
    entry_sig = evaluate_timeframe(entry_candles)
    confirm_sig = evaluate_timeframe(confirm_candles)
    lean = combine_signals(entry_sig, confirm_sig, CONFLUENCE_THRESHOLD)
    return {
        "symbol": symbol,
        "price": round(entry_sig.price, 2),
        "lean": lean,
        "entry_direction": entry_sig.direction,
        "entry_score": entry_sig.score,
        "confirm_direction": confirm_sig.direction,
        "confirm_score": confirm_sig.score,
        "rsi": round(entry_sig.rsi, 1),
    }


def attach_contract(result):
    """Only spend an options-chain lookup on tickers that actually qualified -
    most of a 25-ticker batch will be WAIT, and there's no contract to pick
    for those."""
    if result.get("lean") not in ACTIONABLE_LEANS:
        result["contract"] = None
        return result
    try:
        result["contract"] = contract_picker.pick_contract(result["symbol"], result["entry_direction"])
    except Exception as e:
        result["contract"] = None
        result["contract_error"] = str(e)
    return result


def top_picks_from(results, top_n=TOP_N_ALERTS):
    actionable = [r for r in results.values() if r.get("lean") in ACTIONABLE_LEANS]
    actionable.sort(key=lambda r: (r["entry_score"], r["confirm_score"]), reverse=True)
    return actionable[:top_n]


def signature_for(picks):
    return sorted(f"{p['symbol']}:{p['lean']}:{p['entry_score']}" for p in picks)


@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        universe_size=len(UNIVERSE),
        batch_size=BATCH_SIZE,
        num_batches=len(get_batches()),
        max_contract_cost=MAX_CONTRACT_COST,
    )


@app.route("/api/signals")
def api_signals():
    """Cumulative results gathered across the ongoing rotation - fills in as
    /api/scan-batch progresses through the universe. Polled by the dashboard
    every 60s."""
    state = load_state()
    results = list(state["results"].values())
    results.sort(key=lambda r: (r.get("lean") in ACTIONABLE_LEANS, r.get("entry_score", 0)), reverse=True)
    picks = top_picks_from(state["results"])
    num_batches = len(get_batches())
    return jsonify({
        "results": results,
        "top_picks": picks,
        "tickers_scanned": len(results),
        "universe_size": len(UNIVERSE),
        "current_batch_index": state.get("next_batch_index", 0) % num_batches,
        "num_batches": num_batches,
        "last_full_rotation_completed_at": state.get("last_full_rotation_completed_at"),
        "track_record": track_record.get_summary(),
        "updated": int(time.time()),
    })


@app.route("/api/scan-batch")
def scan_batch():
    """Hit this endpoint from a free scheduler (cron-job.org) every minute
    during market hours. Each call scans ONE rotating slice of the full
    market universe (so it doesn't hammer yfinance all at once) and merges
    the results into a running, full-market picture. A text digest goes out
    only when the ranked top-N list actually changes."""
    cron_token = os.environ.get("CRON_TOKEN", "")
    token = request.args.get("token", "")
    if not cron_token or token != cron_token:
        return jsonify({"error": "unauthorized"}), 401

    state = load_state()
    batches = get_batches()
    num_batches = len(batches)
    batch_index = state.get("next_batch_index", 0) % num_batches
    batch_symbols = batches[batch_index]

    checked, errors = [], []
    now = time.time()
    for symbol in batch_symbols:
        try:
            result = compute_ticker(symbol)
            result = attach_contract(result)
            result["checked_at"] = now
            state["results"][symbol] = result
            checked.append(symbol)
        except Exception as e:
            errors.append({"symbol": symbol, "error": str(e)})

    if batch_index == 0:
        state["rotation_started_at"] = now
    if batch_index == num_batches - 1:
        state["last_full_rotation_completed_at"] = now

    state["next_batch_index"] = (batch_index + 1) % num_batches

    # Track record: feed this batch's freshly-checked prices to any open
    # tracked trades on those symbols, then close out anything whose
    # contract has expired (see track_record.py for the win/loss rule).
    price_map = {sym: state["results"][sym]["price"] for sym in checked if sym in state["results"]}
    track_record.update_with_prices(price_map)
    track_record.finalize_expired()

    picks = top_picks_from(state["results"])
    sig = signature_for(picks)
    alert_sent = False
    if picks and sig != state.get("last_alert_signature"):
        # A new/changed top-picks list is "a call being made" - start
        # tracking it regardless of whether the text itself goes out below,
        # so a Resend hiccup doesn't silently drop it from the track record.
        for p in picks:
            track_record.record_new_alert(p, now=now)
        ok = send_alert_digest(picks)
        if ok:
            alert_sent = True
            state["last_alert_signature"] = sig
            state["last_alert_at"] = now

    save_state(state)
    return jsonify({
        "batch_index": batch_index,
        "num_batches": num_batches,
        "checked": checked,
        "errors": errors,
        "top_picks": picks,
        "alert_sent": alert_sent,
        "track_record": track_record.get_summary(),
    })


@app.route("/healthz")
def healthz():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
