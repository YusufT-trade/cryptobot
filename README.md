# cryptobot

Here’s a concise, GitHub-ready explanation of main.py in English:

Purpose: CLI entrypoint for the multi-exchange crypto breakout scanner; orchestrates data fetch, scoring, optional AI validation, and output.
CLI args: -o/--output <path> saves JSON to a file (always also prints to stdout). python main.py --help shows usage.
Flow (asyncio.run(run_scan)):
Pulls market data from Binance, Bybit, and KuCoin via fetch_all_exchanges.
Filters out markets with low liquidity (quote_volume < MIN_LIQUIDITY_USD) or missing candles.
Computes BTC/ETH returns to gauge market regime.
Launches concurrent analyses per symbol (asyncio.as_completed); logs and skips failures.
Sorts by overall_score.
Optional AI check: if AI_VALIDATION_ENABLED, top N (AI_MAX_COINS) are sent to local Ollama (OLLAMA_URL, OLLAMA_MODEL); verdict can adjust score/action.
Drops entries below MIN_ALERT_SCORE, dumps remaining scores as JSON, writes to file if -o given, and prints a short “Immediate alerts” list.
Run example (for README):
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py -o breakout.json
Scope: main.py only handles CLI, orchestration, and I/O; all analytics and data fetching live in the scanner package.
