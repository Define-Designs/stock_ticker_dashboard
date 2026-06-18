"""
Smoke test using synthetic candle data - no live API key needed.
Run with: python3 test_app.py
"""
import os
import random
import sys

import signals
import contract_picker
import options_provider
import track_record


def make_uptrend_candles(n=120, start=100.0):
    closes, highs, lows, opens, vols = [], [], [], [], []
    price = start
    for i in range(n):
        price += random.uniform(0.05, 0.4)  # steady uptrend
        o = price - random.uniform(0, 0.1)
        c = price
        h = max(o, c) + random.uniform(0, 0.15)
        l = min(o, c) - random.uniform(0, 0.15)
        opens.append(o); closes.append(c); highs.append(h); lows.append(l)
        vols.append(random.uniform(1000, 5000))
    return {"o": opens, "h": highs, "l": lows, "c": closes, "v": vols}


def make_downtrend_candles(n=120, start=100.0):
    closes, highs, lows, opens, vols = [], [], [], [], []
    price = start
    for i in range(n):
        price -= random.uniform(0.05, 0.4)
        o = price + random.uniform(0, 0.1)
        c = price
        h = max(o, c) + random.uniform(0, 0.15)
        l = min(o, c) - random.uniform(0, 0.15)
        opens.append(o); closes.append(c); highs.append(h); lows.append(l)
        vols.append(random.uniform(1000, 5000))
    return {"o": opens, "h": highs, "l": lows, "c": closes, "v": vols}


def test_signal_math():
    random.seed(42)
    up = make_uptrend_candles()
    down = make_downtrend_candles()

    sig_up = signals.evaluate_timeframe(up)
    sig_down = signals.evaluate_timeframe(down)

    assert sig_up.direction == "bullish", f"expected bullish, got {sig_up.direction} score={sig_up.score}"
    assert sig_down.direction == "bearish", f"expected bearish, got {sig_down.direction} score={sig_down.score}"
    assert 0 <= sig_up.score <= 5
    assert 0 <= sig_down.score <= 5
    print(f"PASS test_signal_math  (up={sig_up.direction} {sig_up.score}/5, down={sig_down.direction} {sig_down.score}/5)")


def test_combine_signals_agree():
    random.seed(1)
    up = make_uptrend_candles()
    sig_a = signals.evaluate_timeframe(up)
    sig_b = signals.evaluate_timeframe(up)
    lean = signals.combine_signals(sig_a, sig_b, threshold=4)
    assert lean in ("Lean CALLS", "WAIT - Low Confluence"), lean
    print(f"PASS test_combine_signals_agree -> {lean}")


def test_combine_signals_conflict():
    random.seed(2)
    up = make_uptrend_candles()
    down = make_downtrend_candles()
    sig_a = signals.evaluate_timeframe(up)
    sig_b = signals.evaluate_timeframe(down)
    lean = signals.combine_signals(sig_a, sig_b, threshold=4)
    assert lean == "WAIT - Timeframes Conflict", lean
    print(f"PASS test_combine_signals_conflict -> {lean}")


def _fake_chain(specs, default_volume=100, default_open_interest=0):
    """specs: list of (delta, ask, strike) tuples, or (delta, ask, strike,
    volume, open_interest) tuples when a test needs to control liquidity
    explicitly. Defaults to a liquid volume so tests written before the
    liquidity filter existed keep working unchanged."""
    chain = []
    for spec in specs:
        if len(spec) == 3:
            delta, ask, strike = spec
            volume, open_interest = default_volume, default_open_interest
        else:
            delta, ask, strike, volume, open_interest = spec
        chain.append({
            "option_type": "call",
            "strike": strike,
            "bid": round(ask - 0.05, 2),
            "ask": ask,
            "greeks": {"delta": delta},
            "volume": volume,
            "open_interest": open_interest,
        })
    return chain


def test_contract_picker_targets_closest_delta():
    """Among several strikes, the one with delta closest to TARGET_DELTA
    (0.65) should win when all are within budget."""
    from datetime import date, timedelta
    today = date(2026, 1, 1)
    exp = (today + timedelta(days=14)).isoformat()

    contract_picker.options_provider.get_expirations = lambda symbol: [exp]
    contract_picker.options_provider.get_chain = lambda symbol, expiration: _fake_chain([
        (0.50, 0.40, 390),
        (0.65, 0.60, 395),
        (0.80, 0.90, 400),
    ])

    result = contract_picker.pick_contract("TEST", "bullish", today=today)
    assert result is not None
    assert result["delta"] == 0.65, result
    assert result["strike"] == 395, result
    assert result["option_type"] == "call"
    print(f"PASS test_contract_picker_targets_closest_delta -> picked {result['strike']}C delta={result['delta']}")


def test_contract_picker_budget_fallback():
    """If the closest-delta contract is over MAX_CONTRACT_COST ($100/contract,
    i.e. ask > $1.00), the picker should fall through to the next-closest
    delta candidate that fits the budget instead of giving up."""
    from datetime import date, timedelta
    today = date(2026, 1, 1)
    exp = (today + timedelta(days=14)).isoformat()

    contract_picker.options_provider.get_expirations = lambda symbol: [exp]
    contract_picker.options_provider.get_chain = lambda symbol, expiration: _fake_chain([
        (0.65, 5.00, 395),   # closest delta, but costs $500 - over budget
        (0.55, 0.90, 385),   # next-closest delta, costs $90 - fits
        (0.80, 0.50, 405),   # further delta, costs $50 - also fits
    ])

    result = contract_picker.pick_contract("TEST", "bullish", today=today)
    assert result is not None
    assert result["delta"] == 0.55, result
    assert result["cost"] == 90.0, result
    print(f"PASS test_contract_picker_budget_fallback -> skipped $500 contract, picked ${result['cost']} one")


def test_contract_picker_puts_use_negative_target_delta():
    from datetime import date, timedelta
    today = date(2026, 1, 1)
    exp = (today + timedelta(days=14)).isoformat()

    contract_picker.options_provider.get_expirations = lambda symbol: [exp]
    contract_picker.options_provider.get_chain = lambda symbol, expiration: [
        {"option_type": "put", "strike": 95, "bid": 0.85, "ask": 0.90, "greeks": {"delta": -0.65}, "volume": 50, "open_interest": 0},
        {"option_type": "put", "strike": 90, "bid": 0.45, "ask": 0.50, "greeks": {"delta": -0.45}, "volume": 50, "open_interest": 0},
    ]

    result = contract_picker.pick_contract("TEST", "bearish", today=today)
    assert result is not None
    assert result["option_type"] == "put"
    assert result["delta"] == -0.65, result
    print(f"PASS test_contract_picker_puts_use_negative_target_delta -> delta={result['delta']}")


def test_contract_picker_returns_none_with_no_chain_data():
    contract_picker.options_provider.get_expirations = lambda symbol: []
    result = contract_picker.pick_contract("NOCHAIN", "bullish")
    assert result is None
    print("PASS test_contract_picker_returns_none_with_no_chain_data")


def test_contract_picker_skips_illiquid_contract():
    """A contract with the closest delta but volume=0/open_interest=0 (below
    both MIN_CONTRACT_VOLUME and MIN_OPEN_INTEREST) should be skipped in
    favor of a liquid contract, even though the liquid one has a farther
    delta from target."""
    from datetime import date, timedelta
    today = date(2026, 1, 1)
    exp = (today + timedelta(days=14)).isoformat()

    contract_picker.options_provider.get_expirations = lambda symbol: [exp]
    contract_picker.options_provider.get_chain = lambda symbol, expiration: _fake_chain([
        (0.65, 0.60, 395, 0, 0),      # closest delta, but dead - no volume, no OI
        (0.55, 0.50, 385, 200, 0),    # farther delta, but plenty of volume
    ])

    result = contract_picker.pick_contract("TEST", "bullish", today=today)
    assert result is not None
    assert result["delta"] == 0.55, result
    assert result["strike"] == 385, result
    print(f"PASS test_contract_picker_skips_illiquid_contract -> picked liquid {result['strike']}C over illiquid 395C")


def test_contract_picker_open_interest_satisfies_floor_when_volume_zero():
    """Same-day volume of 0 shouldn't disqualify a contract if open interest
    alone clears MIN_OPEN_INTEREST - handles the early-trading-session case
    on an otherwise liquid name."""
    from datetime import date, timedelta
    today = date(2026, 1, 1)
    exp = (today + timedelta(days=14)).isoformat()

    contract_picker.options_provider.get_expirations = lambda symbol: [exp]
    contract_picker.options_provider.get_chain = lambda symbol, expiration: _fake_chain([
        (0.65, 0.60, 395, 0, 500),   # volume=0 but open_interest well above floor
    ])

    result = contract_picker.pick_contract("TEST", "bullish", today=today)
    assert result is not None
    assert result["open_interest"] == 500, result
    assert result["volume"] == 0, result
    print("PASS test_contract_picker_open_interest_satisfies_floor_when_volume_zero")


def test_contract_picker_all_illiquid_returns_none():
    """If every candidate fails the liquidity floor, the picker should
    return None for that expiration rather than handing back a dead
    contract."""
    from datetime import date, timedelta
    today = date(2026, 1, 1)
    exp = (today + timedelta(days=14)).isoformat()

    contract_picker.options_provider.get_expirations = lambda symbol: [exp]
    contract_picker.options_provider.get_chain = lambda symbol, expiration: _fake_chain([
        (0.65, 0.60, 395, 0, 0),
        (0.55, 0.50, 385, 5, 10),
    ])

    result = contract_picker.pick_contract("TEST", "bullish", today=today)
    assert result is None, result
    print("PASS test_contract_picker_all_illiquid_returns_none")


def test_attach_contract_skips_wait_leans():
    """attach_contract should never spend a Tradier lookup on a non-actionable
    (WAIT) lean - confirms the cost-saving short-circuit in app.py."""
    import app as flask_app_module

    calls = []

    def fake_pick_contract(symbol, direction):
        calls.append(symbol)
        return {"symbol": symbol, "option_type": "call", "strike": 1, "expiration": "2026-01-01",
                "expiration_display": "01/01/26", "ask": 1.0, "bid": 0.9, "delta": 0.65,
                "cost": 100.0, "dte": 10}

    flask_app_module.contract_picker.pick_contract = fake_pick_contract

    wait_result = flask_app_module.attach_contract({"symbol": "X", "lean": "WAIT - Low Confluence"})
    assert wait_result["contract"] is None
    assert calls == [], "should not call pick_contract for a WAIT lean"

    call_result = flask_app_module.attach_contract({"symbol": "Y", "lean": "Lean CALLS", "entry_direction": "bullish"})
    assert call_result["contract"] is not None
    assert calls == ["Y"]
    print("PASS test_attach_contract_skips_wait_leans")


def test_batch_rotation_and_alerts():
    """Exercises the market-wide rotating scanner end to end with a small
    fake universe (instead of the real ~460 tickers) so the test is fast and
    fully offline."""
    import app as flask_app_module

    # Shrink the universe + batch size so a "full rotation" only takes a
    # couple of calls in this test.
    flask_app_module.UNIVERSE = ["UP1", "UP2", "DN1", "DN2", "UP3"]
    flask_app_module.BATCH_SIZE = 2  # -> 3 batches: [UP1,UP2] [DN1,DN2] [UP3]

    random.seed(7)
    up_candles = make_uptrend_candles()
    down_candles = make_downtrend_candles()

    def fake_get_candles(symbol, resolution, lookback_seconds):
        return down_candles if symbol.startswith("DN") else up_candles

    flask_app_module.get_candles = fake_get_candles

    def fake_pick_contract(symbol, direction):
        return {"symbol": symbol, "option_type": "call" if direction == "bullish" else "put",
                "strike": 100, "expiration": "2026-02-01", "expiration_display": "02/01/26",
                "ask": 1.50, "bid": 1.40, "delta": 0.65 if direction == "bullish" else -0.65,
                "cost": 150.0, "dte": 14, "volume": 300, "open_interest": 1200}

    flask_app_module.contract_picker.pick_contract = fake_pick_contract

    sent_digests = []

    def fake_send_alert_digest(top_picks):
        sent_digests.append(top_picks)
        return True

    flask_app_module.send_alert_digest = fake_send_alert_digest

    # Fresh state for the test run.
    if os.path.exists(flask_app_module.STATE_FILE):
        os.remove(flask_app_module.STATE_FILE)
    _fresh_track_file()  # flask_app_module.track_record is the same module object

    client = flask_app_module.app.test_client()
    os.environ["CRON_TOKEN"] = "test123"

    # No token -> 401
    r = client.get("/api/scan-batch")
    assert r.status_code == 401
    print("PASS test_batch_rotation /api/scan-batch unauthorized -> 401")

    # Run 3 scan-batch calls = one full rotation through the fake universe.
    seen_batches = []
    for i in range(3):
        r = client.get("/api/scan-batch?token=test123")
        assert r.status_code == 200, (r.status_code, r.data)
        payload = r.get_json()
        seen_batches.append(payload["batch_index"])
    assert seen_batches == [0, 1, 2], seen_batches
    print(f"PASS test_batch_rotation rotated through batches {seen_batches}")

    # After a full rotation, /api/signals should show all 5 tickers scanned.
    r = client.get("/api/signals")
    assert r.status_code == 200
    payload = r.get_json()
    assert payload["tickers_scanned"] == 5, payload["tickers_scanned"]
    assert payload["universe_size"] == 5
    assert payload["last_full_rotation_completed_at"] is not None
    print(f"PASS test_batch_rotation /api/signals -> scanned {payload['tickers_scanned']}/5, "
          f"{len(payload['top_picks'])} top pick(s)")

    # A digest should have gone out at least once since uptrend tickers
    # should qualify for "Lean CALLS".
    assert len(sent_digests) >= 1, "expected at least one alert digest to be sent"
    print(f"PASS test_batch_rotation_and_alerts -> {len(sent_digests)} digest(s) sent")

    # Each qualifying pick scanned via /api/scan-batch should have a contract
    # attached (since we faked pick_contract above), and that contract data
    # should flow into the digest text Resend would actually send.
    first_digest_picks = sent_digests[0]
    actionable_picks = [p for p in first_digest_picks if p["lean"] in ("Lean CALLS", "Lean PUTS")]
    assert actionable_picks, "expected at least one actionable pick in the digest"
    for p in actionable_picks:
        assert p.get("contract") is not None, f"{p['symbol']} missing contract data"
    import notify
    digest_text = "\n".join(notify._line_for(p) for p in actionable_picks)
    assert "100C" in digest_text or "100P" in digest_text, digest_text
    assert "Ask $1.50" in digest_text, digest_text
    print("PASS test_batch_rotation_and_alerts -> contract details flow into digest text")

    # The scan-batch response and /api/signals should both surface a
    # track_record block, and the alert above should have started tracking
    # at least one trade (it may already show as closed rather than open,
    # since the fake contract's 2026-02-01 expiration is in the past
    # relative to whenever this test actually runs).
    def _tracked_total(tr):
        return tr["open"] + tr["wins"] + tr["losses"]

    assert "track_record" in payload, payload
    assert _tracked_total(payload["track_record"]) >= 1, payload["track_record"]
    r = client.get("/api/signals")
    assert _tracked_total(r.get_json()["track_record"]) >= 1
    print("PASS test_batch_rotation_and_alerts -> track_record wired into both endpoints")

    # Running the SAME rotation again with no change should NOT re-send an
    # identical top-N digest (dedupe by signature).
    digest_count_before = len(sent_digests)
    for i in range(3):
        client.get("/api/scan-batch?token=test123")
    assert len(sent_digests) == digest_count_before, "should not re-send an unchanged top-N digest"
    print("PASS test_batch_rotation_and_alerts -> no duplicate digest for unchanged top picks")

    os.remove(flask_app_module.STATE_FILE)


def _fresh_track_file():
    """Points track_record at a throwaway file so each test starts clean and
    tests don't clobber each other's records or the real /tmp file."""
    path = f"/tmp/test_track_record_{random.randint(0, 10**9)}.json"
    track_record.TRACK_FILE = path
    return path


def _fake_pick(symbol, option_type, strike, expiration, entry_price, entry_score=5):
    return {
        "symbol": symbol,
        "price": entry_price,
        "entry_score": entry_score,
        "contract": {
            "option_type": option_type,
            "strike": strike,
            "expiration": expiration,
            "expiration_display": expiration,
        },
    }


def test_track_record_call_win_by_reaching_strike():
    from datetime import date, timedelta
    _fresh_track_file()
    today = date(2026, 1, 1)
    exp = (today + timedelta(days=5)).isoformat()

    track_record.record_new_alert(_fake_pick("AVGO", "call", 395, exp, 392.90), now=0)
    track_record.update_with_prices({"AVGO": 396})  # crosses the strike
    track_record.finalize_expired(today=today + timedelta(days=6))

    summary = track_record.get_summary()
    assert summary["wins"] == 1 and summary["losses"] == 0, summary
    rec = summary["recent"][0]
    assert rec["status"] == "win" and rec["close_reason"] == "reached_strike", rec
    print("PASS test_track_record_call_win_by_reaching_strike")


def test_track_record_call_win_by_favorable_move_short_of_strike():
    from datetime import date, timedelta
    _fresh_track_file()
    today = date(2026, 1, 1)
    exp = (today + timedelta(days=5)).isoformat()

    # AVGO at 392.90, alert for the 395 call - price moves to 394 (toward the
    # strike, in profit on the contract) but never actually reaches 395.
    track_record.record_new_alert(_fake_pick("AVGO", "call", 395, exp, 392.90), now=0)
    track_record.update_with_prices({"AVGO": 394})
    track_record.finalize_expired(today=today + timedelta(days=6))

    summary = track_record.get_summary()
    assert summary["wins"] == 1 and summary["losses"] == 0, summary
    rec = summary["recent"][0]
    assert rec["status"] == "win" and rec["close_reason"] == "favorable_move", rec
    assert rec["reached_strike"] is False, rec
    print("PASS test_track_record_call_win_by_favorable_move_short_of_strike")


def test_track_record_call_loss_never_moves_favorably():
    from datetime import date, timedelta
    _fresh_track_file()
    today = date(2026, 1, 1)
    exp = (today + timedelta(days=5)).isoformat()

    track_record.record_new_alert(_fake_pick("AVGO", "call", 395, exp, 392.90), now=0)
    track_record.update_with_prices({"AVGO": 391.00})
    track_record.update_with_prices({"AVGO": 390.50})
    track_record.finalize_expired(today=today + timedelta(days=6))

    summary = track_record.get_summary()
    assert summary["wins"] == 0 and summary["losses"] == 1, summary
    rec = summary["recent"][0]
    assert rec["status"] == "loss" and rec["close_reason"] == "no_favorable_move_by_expiration", rec
    print("PASS test_track_record_call_loss_never_moves_favorably")


def test_track_record_put_direction():
    from datetime import date, timedelta
    _fresh_track_file()
    today = date(2026, 1, 1)
    exp = (today + timedelta(days=5)).isoformat()

    # Put: favorable = price going DOWN. Reaches the strike here.
    track_record.record_new_alert(_fake_pick("XYZ", "put", 45, exp, 50.00), now=0)
    track_record.update_with_prices({"XYZ": 44.00})
    track_record.finalize_expired(today=today + timedelta(days=6))

    summary = track_record.get_summary()
    assert summary["wins"] == 1, summary
    rec = summary["recent"][0]
    assert rec["status"] == "win" and rec["close_reason"] == "reached_strike", rec
    print("PASS test_track_record_put_direction")


def test_track_record_dedup_ignores_repeat_alert():
    from datetime import date, timedelta
    _fresh_track_file()
    today = date(2026, 1, 1)
    exp = (today + timedelta(days=5)).isoformat()

    track_record.record_new_alert(_fake_pick("AVGO", "call", 395, exp, 392.90), now=0)
    track_record.update_with_prices({"AVGO": 393.50})
    # Same symbol/strike/expiration/option_type re-fires on a later scan with
    # a different entry price - should be ignored, not overwrite progress.
    track_record.record_new_alert(_fake_pick("AVGO", "call", 395, exp, 100.00), now=100)

    summary = track_record.get_summary()
    assert summary["open"] == 1, summary
    print("PASS test_track_record_dedup_ignores_repeat_alert")


def test_track_record_open_not_counted_until_expired():
    from datetime import date, timedelta
    _fresh_track_file()
    today = date(2026, 1, 1)
    exp = (today + timedelta(days=5)).isoformat()

    track_record.record_new_alert(_fake_pick("AVGO", "call", 395, exp, 392.90), now=0)
    track_record.update_with_prices({"AVGO": 396})
    # Not yet past expiration - should still be open, not graded.
    track_record.finalize_expired(today=today)

    summary = track_record.get_summary()
    assert summary["open"] == 1, summary
    assert summary["wins"] == 0 and summary["losses"] == 0, summary
    assert summary["win_rate"] is None, summary
    print("PASS test_track_record_open_not_counted_until_expired")


def test_flask_basic_routes():
    import app as flask_app_module
    client = flask_app_module.app.test_client()

    r = client.get("/")
    assert r.status_code == 200, r.status_code
    assert b"Road Warrior" in r.data

    r = client.get("/healthz")
    assert r.status_code == 200 and r.data == b"ok"
    print("PASS test_flask_basic_routes")


if __name__ == "__main__":
    test_signal_math()
    test_combine_signals_agree()
    test_combine_signals_conflict()
    test_flask_basic_routes()
    test_contract_picker_targets_closest_delta()
    test_contract_picker_budget_fallback()
    test_contract_picker_puts_use_negative_target_delta()
    test_contract_picker_returns_none_with_no_chain_data()
    test_contract_picker_skips_illiquid_contract()
    test_contract_picker_open_interest_satisfies_floor_when_volume_zero()
    test_contract_picker_all_illiquid_returns_none()
    test_attach_contract_skips_wait_leans()
    test_batch_rotation_and_alerts()
    test_track_record_call_win_by_reaching_strike()
    test_track_record_call_win_by_favorable_move_short_of_strike()
    test_track_record_call_loss_never_moves_favorably()
    test_track_record_put_direction()
    test_track_record_dedup_ignores_repeat_alert()
    test_track_record_open_not_counted_until_expired()
    print("\nALL TESTS PASSED")
