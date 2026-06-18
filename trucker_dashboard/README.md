# Road Warrior Options Dashboard

A free, self-hosted alternative to TradingView alerts. Scans a ~460-ticker
universe of liquid, optionable U.S. stocks and ETFs (not just a fixed
watchlist) and texts you a consolidated digest when new high-confluence call
or put setups show up - no TradingView paid plan needed, and no need to type
in a ticker.

See `Web_App_Deployment_Guide.pdf` (delivered alongside this folder) for full
non-technical setup instructions. Quick technical summary:

## How the market-wide scan works

Scanning all ~460 tickers every minute would blow past Finnhub's free
60-calls/minute limit (each ticker costs 2 calls). So the scan is split into
small rotating batches:

- `config.py` defines `UNIVERSE` (the ~460-ticker scan list) and `BATCH_SIZE`
  (25 tickers per batch = 50 API calls, well inside the free limit).
- Every call to `/api/scan-batch` scans the *next* batch in the rotation and
  merges the results into a running, cumulative picture of the whole market.
- With `BATCH_SIZE=25` and a 1-minute cron interval, a full pass over all
  ~460 tickers takes about 19 cron cycles - roughly **15-20 minutes** for a
  complete sweep. That's the realistic ceiling on free data; it is NOT
  instant, but it runs unattended and never needs a ticker typed in.
- The dashboard's "Top Picks" and "Full Scan Results" reflect whatever has
  been scanned so far in the current rotation, refreshed continuously.

## How option contracts are picked (Tradier)

Once a ticker qualifies (Lean CALLS / Lean PUTS), `contract_picker.py` turns
that stock-level lean into ONE specific, tradeable contract using a few
well-established options-buying heuristics:

- **Target delta ~0.65** (`TARGET_DELTA` in `config.py`) - the "stock
  replacement" zone. Contracts at this delta track the underlying closely
  and bleed less time value than far out-of-the-money strikes, while still
  costing a fraction of 100 shares.
- **7-35 days to expiration** (`MIN_/MAX_DAYS_TO_EXPIRATION`) - skips 0-3 DTE
  contracts (outsized gamma/theta risk for a signal that's only rechecked
  every 15-20 min) and skips far-dated contracts (extra premium/theta drag).
- **$100 budget cap** (`MAX_CONTRACT_COST`) - if the ideal-delta contract
  costs more than this, the picker walks toward cheaper, further
  out-of-the-money strikes in the same expiration before giving up.
- **Liquidity floor** (`MIN_CONTRACT_VOLUME` = 25, `MIN_OPEN_INTEREST` = 100)
  - a contract is skipped entirely unless EITHER today's volume or open
  interest clears its threshold. Thin contracts have wide bid/ask spreads
  and can be hard to exit, so this is checked before delta/budget, not
  after - an illiquid contract is never picked just because its delta or
  price looks ideal. Volume alone can legitimately be 0 early in the
  trading session, which is why open interest is accepted as an
  alternative signal. Both the text digest and dashboard card show
  whichever figure (volume or open interest) qualified the pick.

Contract data comes from `options_provider.py`, a thin wrapper around
Tradier's Market Data API. A free Tradier developer account's sandbox token
provides delayed strikes/expirations/bid/ask/greeks with no funded brokerage
account required - see `.env.example` for the two Tradier env vars. If no
contract fits the budget/window, the text alert and dashboard fall back to
just the stock-level lean with a "no contract found under budget" note.

## Local run
```
pip install -r requirements.txt
export FINNHUB_API_KEY=your_key
python app.py
```
Visit http://localhost:5000

## Routes
- `GET /` - dashboard page (auto-refreshes every 60s)
- `GET /api/signals` - JSON: cumulative scan results, top picks, and rotation
  progress (used by the dashboard)
- `GET /api/scan-batch?token=YOUR_CRON_TOKEN` - scans the next rotating batch
  and texts a digest of the top 3-5 setups if the ranked list changed. Call
  this from a free scheduler (cron-job.org) every 1 minute during market
  hours.
- `GET /healthz` - simple uptime check

## Environment variables
See `.env.example`.

## Editing the scan universe
Edit the `UNIVERSE` list in `config.py` - no other code changes needed.
Shrinking it (e.g. back down to a personal watchlist) makes full-rotation
scans finish faster; growing it makes them take longer, per the math above.

## Adjusting contract selection
Edit `TARGET_DELTA`, `MIN_DAYS_TO_EXPIRATION`, `MAX_DAYS_TO_EXPIRATION`,
`MAX_CONTRACT_COST`, `MIN_CONTRACT_VOLUME`, or `MIN_OPEN_INTEREST` in
`config.py` - no other code changes needed.
