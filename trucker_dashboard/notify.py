"""
Sends text-message alerts by emailing the client's phone carrier's
email-to-SMS gateway (e.g. 5551234567@vtext.com for Verizon), using Resend's
HTTPS email API. This is free and works on Render's free tier, which blocks
the raw SMTP ports (25/465/587) that a normal Gmail-SMTP approach would need.
"""
import os
import requests

RESEND_API_URL = "https://api.resend.com/emails"


def send_text_alert(subject, body):
    api_key = os.environ.get("RESEND_API_KEY", "")
    to_address = os.environ.get("ALERT_EMAIL_TO", "")
    from_address = os.environ.get("ALERT_FROM_ADDRESS", "onboarding@resend.dev")

    if not api_key or not to_address:
        print("Notify skipped - missing RESEND_API_KEY or ALERT_EMAIL_TO")
        return False

    resp = requests.post(
        RESEND_API_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "from": from_address,
            "to": [to_address],
            "subject": subject,
            "text": body,
        },
        timeout=10,
    )
    if resp.status_code not in (200, 201):
        print("Resend error:", resp.status_code, resp.text)
        return False
    return True


def _line_for(p):
    """One pick -> one text line. If a Tradier contract was found, show the
    actual tradeable contract (strike/expiration/ask/delta/volume) instead of
    just the stock-level lean - e.g.
    "AVGO $395C 06/18/26 Ask $4.20 (D0.65) Vol312 5/5". The contract has
    already passed the liquidity floor (MIN_CONTRACT_VOLUME/MIN_OPEN_INTEREST
    in config.py) by the time it gets here, so the volume shown is for
    transparency, not a re-check."""
    contract = p.get("contract")
    if contract:
        letter = "C" if contract["option_type"] == "call" else "P"
        strike = contract["strike"]
        strike_str = f"{strike:g}"
        liquidity = contract.get("volume") or contract.get("open_interest") or 0
        return (
            f"{p['symbol']} ${strike_str}{letter} {contract['expiration_display']} "
            f"Ask ${contract['ask']:.2f} (D{contract['delta']}) Vol{liquidity} {p['entry_score']}/5"
        )
    # Lean qualified but no contract fit the budget/window (or Tradier lookup
    # failed) - fall back to the stock-level line so the setup still gets
    # surfaced, just without contract specifics.
    return f"{p['symbol']} {p['lean'].replace('Lean ', '')} {p['entry_score']}/5 @ ${p['price']} (no contract under budget)"


def send_alert_digest(top_picks):
    """top_picks: list of result dicts (symbol, price, lean, entry_score,
    contract, ...), already sorted best-first. Sends ONE text listing all of
    them, so a busy market-wide scan doesn't flood the client's phone with
    one text per ticker."""
    if not top_picks:
        return False

    lines = [_line_for(p) for p in top_picks]
    body = "Top setups right now:\n" + "\n".join(lines)
    subject = f"{len(top_picks)} option setup(s): " + ", ".join(p["symbol"] for p in top_picks)
    return send_text_alert(subject=subject, body=body)
