# Market-wide scan universe: ~460 liquid, optionable U.S. stocks/ETFs
# (S&P 500 names plus popular high-volume optionable extras like SOFI, PLTR,
# RIVN, meme/momentum names, and major index ETFs). This is intentionally
# NOT all 8,000+ listed tickers - most of those have no options or are too
# illiquid to matter, and a free-tier data plan can't cycle through that many
# names fast enough to be useful anyway. Edit this list any time - no other
# code changes needed.
UNIVERSE = [
    "A", "AAL", "AAP", "AAPL", "ABBV", "ABNB", "ABT", "ACN", "ADBE", "ADI", "ADM", "ADP",
    "ADSK", "AEE", "AEP", "AFL", "AFRM", "AIG", "AKAM", "ALB", "ALGN", "ALL", "AMAT", "AMC",
    "AMCR", "AMD", "AME", "AMG", "AMGN", "AMP", "AMT", "AMZN", "ANET", "ANF", "AON", "APA",
    "APD", "APH", "ARE", "ARKK", "ASTS", "ATO", "AVB", "AVGO", "AVY", "AWK", "AXON", "AXP",
    "AZO", "BA", "BABA", "BAC", "BALL", "BAX", "BB", "BBY", "BDX", "BEN", "BIDU", "BIIB",
    "BK", "BKNG", "BKR", "BLK", "BMY", "BSX", "BXP", "C", "CAG", "CAH", "CARR", "CAT", "CB",
    "CBOE", "CCL", "CDNS", "CE", "CF", "CFG", "CHD", "CHPT", "CHRW", "CHTR", "CI", "CL",
    "CLX", "CMA", "CMCSA", "CME", "CMG", "CMI", "CMS", "CNP", "COF", "COIN", "COP", "COR",
    "COST", "CPB", "CPRI", "CPT", "CRL", "CRM", "CRWD", "CSCO", "CSX", "CTLT", "CTRA",
    "CTSH", "CTVA", "CVNA", "CVS", "CVX", "D", "DASH", "DD", "DDOG", "DE", "DECK", "DELL",
    "DFS", "DG", "DHR", "DIA", "DIS", "DKNG", "DLR", "DLTR", "DOCU", "DOV", "DOW", "DPZ",
    "DRI", "DTE", "DUK", "DVN", "DXCM", "EA", "EBAY", "ECL", "ED", "EIX", "EL", "ELV", "EMN",
    "EMR", "EOG", "EQIX", "EQR", "EQT", "ES", "ESS", "ETN", "ETSY", "EVRG", "EW", "EXC",
    "EXPD", "EXPE", "EXR", "F", "FANG", "FAST", "FCX", "FDX", "FE", "FFIV", "FIS", "FITB",
    "FOUR", "FOX", "FOXA", "FRT", "FTNT", "FUBO", "GD", "GE", "GEHC", "GEN", "GILD", "GIS",
    "GL", "GLW", "GM", "GME", "GOOG", "GOOGL", "GPC", "GPN", "GPS", "GRAB", "GS", "GWW",
    "HAL", "HBAN", "HCA", "HD", "HES", "HII", "HLT", "HOLX", "HON", "HOOD", "HPE", "HPQ",
    "HRL", "HST", "HSY", "HUM", "HWM", "IAC", "IBM", "ICE", "IDXX", "IFF", "INCY", "INTC",
    "INTU", "IP", "IPG", "IQV", "IR", "IRM", "ISRG", "ITW", "IVZ", "IWM", "JBHT", "JCI",
    "JD", "JNJ", "JNPR", "JPM", "K", "KDP", "KEY", "KEYS", "KHC", "KIM", "KLAC", "KMB",
    "KMI", "KMX", "KO", "KR", "LCID", "LHX", "LI", "LIN", "LLY", "LMT", "LNT", "LOW", "LRCX",
    "LULU", "LVS", "LYB", "LYV", "MA", "MAA", "MAR", "MARA", "MCD", "MCHP", "MCK", "MCO",
    "MDB", "MDLZ", "MDT", "MELI", "MET", "META", "MGM", "MKC", "MKTX", "MLM", "MMC", "MMM",
    "MNST", "MO", "MOS", "MPC", "MRK", "MRNA", "MRO", "MRVL", "MS", "MSFT", "MTB", "MTCH",
    "MTD", "MU", "NCLH", "NDAQ", "NEE", "NEM", "NET", "NFLX", "NI", "NIO", "NKE", "NKLA",
    "NOC", "NOW", "NSC", "NTAP", "NTRS", "NU", "NUE", "NVDA", "NWS", "NWSA", "NXPI", "O",
    "ODFL", "OKE", "OKTA", "OMC", "ON", "ORCL", "ORLY", "OTIS", "OXY", "PANW", "PARA",
    "PAYX", "PCAR", "PDD", "PEG", "PEP", "PFE", "PG", "PGR", "PH", "PINS", "PKG", "PLD",
    "PLTR", "PM", "PNC", "PNW", "PODD", "PPG", "PPL", "PRU", "PSA", "PSX", "PVH", "PYPL",
    "QCOM", "QQQ", "RBLX", "RCL", "REG", "REGN", "RF", "RIOT", "RIVN", "RJF", "RKLB", "RL",
    "RMD", "ROK", "ROP", "ROST", "RTX", "SBUX", "SCHW", "SE", "SHOP", "SHW", "SIRI", "SJM",
    "SLB", "SNA", "SNAP", "SNOW", "SNPS", "SO", "SOFI", "SPCE", "SPG", "SPGI", "SPY", "SQ",
    "SRE", "STT", "STX", "STZ", "SWKS", "SYF", "SYK", "SYY", "T", "TAP", "TDG", "TEAM",
    "TECH", "TEL", "TER", "TFC", "TGT", "TJX", "TME", "TMO", "TMUS", "TPR", "TRGP", "TROW",
    "TRV", "TSLA", "TSN", "TT", "TTWO", "TWLO", "TXN", "TXT", "U", "UDR", "ULTA", "UNH",
    "UNP", "UPS", "UPST", "URBN", "USB", "V", "VALE", "VICI", "VLO", "VMC", "VRTX", "VTR",
    "VTRS", "VZ", "WAB", "WAT", "WBD", "WDAY", "WDC", "WEC", "WELL", "WFC", "WMB", "WMT",
    "WST", "WTW", "WYNN", "XEL", "XLE", "XLF", "XLK", "XOM", "XPEV", "XPO", "YUM", "ZBH",
    "ZBRA", "ZG", "ZION", "ZS", "ZTS",
]

# How many tickers to fetch+score per cron-triggered scan call. Kept small on
# purpose: each ticker costs 2 Finnhub API calls (entry TF + confirm TF), and
# Finnhub's free tier caps out at 60 calls/minute. 25 tickers = 50 calls,
# leaving headroom and finishing well inside a single web request.
BATCH_SIZE = 25

# Finnhub candle resolutions (minutes)
ENTRY_RESOLUTION = "15"      # entry timeframe
CONFIRM_RESOLUTION = "60"    # confirmation timeframe

ENTRY_LOOKBACK_SECONDS = 60 * 60 * 24 * 5        # ~5 days of 15m bars
CONFIRM_LOOKBACK_SECONDS = 60 * 60 * 24 * 20     # ~20 days of 1H bars

# Minimum confluence score (out of 5) required on the entry timeframe before
# a lean is shown. Matches the indicator's recommended options threshold.
CONFLUENCE_THRESHOLD = 4

# How many of the best current setups to text and to highlight on the
# dashboard's "Top Picks" section.
TOP_N_ALERTS = 5

# Don't re-send a text for the exact same top-N list/scores. This still lets
# a new alert through whenever the ranked list changes (new ticker enters
# top N, one drops out, or the lean flips).

# --- Options contract selection (Tradier) ---
# Once a ticker qualifies (Lean CALLS / Lean PUTS), these rules pick ONE
# actual option contract - not just "buy AVGO calls" but "AVGO $395 Call
# 06/18/26" with a live ask price.
#
# Target delta ~0.60-0.70 ("stock replacement" zone). Contracts in this
# range track the stock much more closely and lose less value to time decay
# than far-out-of-the-money strikes, while still costing a fraction of
# buying 100 shares. Calls target +TARGET_DELTA, puts target -TARGET_DELTA.
TARGET_DELTA = 0.65

# Skip expirations closer than this many days out - very short-dated
# contracts (0-3 DTE) carry outsized gamma/theta risk that this signal
# (checked every 15-20 min, not tick-by-tick) isn't built to manage. Skip
# expirations further out than the max too, to keep premium and theta drag
# reasonable for the swing-style horizon the indicator measures.
MIN_DAYS_TO_EXPIRATION = 7
MAX_DAYS_TO_EXPIRATION = 35

# Hard cap on contract cost (ask price x 100), matching the original
# "options under $100" brief. If the ideal target-delta contract costs more
# than this, the picker walks toward cheaper, further out-of-the-money
# strikes in the same expiration until it finds one that fits.
MAX_CONTRACT_COST = 100.00

# Liquidity floor. A contract qualifies if EITHER its same-day volume or its
# open interest clears its threshold (volume alone can be 0 early in the
# trading day even on a liquid name, so open interest is checked as a
# fallback signal of how actively that strike is traded overall). Contracts
# that fail both are skipped - thin volume means a wide bid/ask spread and
# the risk of not being able to exit the position quickly, which matters
# more here than chasing the single "best" delta on an illiquid strike.
MIN_CONTRACT_VOLUME = 25
MIN_OPEN_INTEREST = 100
