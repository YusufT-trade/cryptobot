import argparse
import asyncio
import json
from typing import List, Optional

import httpx

from scanner.analyzer import analyze_snapshot, top_alerts
from scanner.ai_validator import ai_validate
from scanner.config import (
    AI_MAX_COINS,
    AI_TIMEOUT,
    AI_VALIDATION_ENABLED,
    MIN_ALERT_SCORE,
    MIN_LIQUIDITY_USD,
    OLLAMA_MODEL,
    OLLAMA_URL,
)
from scanner.exchanges import fetch_all_exchanges
from scanner.models import CoinScore, MarketSnapshot


def returns_from_snapshot(symbol: str, snapshots: List[MarketSnapshot]) -> Optional[List[float]]:
    target = next((s for s in snapshots if s.symbol.startswith(symbol)), None)
    if not target:
        return None
    closes = [c.close for c in target.candles]
    if len(closes) < 3:
        return None
    return [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes))
        if closes[i - 1] != 0
    ]


async def run_scan(output_path: Optional[str]):
    print("Fetching market data ...", flush=True)
    snapshots = await fetch_all_exchanges()
    filtered = [s for s in snapshots if s.quote_volume >= MIN_LIQUIDITY_USD and s.candles]
    print(f"Fetched {len(snapshots)} markets; {len(filtered)} passed liquidity filter.", flush=True)

    btc_returns = returns_from_snapshot("BTCUSDT", filtered) or returns_from_snapshot("BTC-USDT", filtered)
    eth_returns = returns_from_snapshot("ETHUSDT", filtered) or returns_from_snapshot("ETH-USDT", filtered)

    scores: List[CoinScore] = []
    async with httpx.AsyncClient(timeout=20) as client:
        tasks = [analyze_snapshot(s, btc_returns, eth_returns, client) for s in filtered]
        for coro in asyncio.as_completed(tasks):
            try:
                score = await coro
                scores.append(score)
            except Exception as exc:  # noqa: BLE001
                print(f"Analysis failed: {exc}", flush=True)

    scores_sorted = sorted(scores, key=lambda x: x.overall_score, reverse=True)

    # Optional AI validation on top candidates
    if AI_VALIDATION_ENABLED and scores_sorted:
        async with httpx.AsyncClient(timeout=AI_TIMEOUT) as ai_client:
            for score in scores_sorted[:AI_MAX_COINS]:
                verdict, reason = await ai_validate(score, OLLAMA_MODEL, OLLAMA_URL, timeout=AI_TIMEOUT, client=ai_client)
                score.ai_verdict = verdict
                score.key_notes += f" | AI:{verdict} {reason[:60]}"
                if verdict == "reject":
                    score.recommended_action = "skip"
                    score.overall_score = max(0.0, score.overall_score - 10)

    # Filter by minimum alert score
    scores_sorted = [s for s in scores_sorted if s.overall_score >= MIN_ALERT_SCORE]

    data = [s.__dict__ for s in scores_sorted]
    json_output = json.dumps(data, ensure_ascii=False, indent=2)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_output)
        print(f"Saved results to {output_path}")

    print(json_output)

    alerts = top_alerts(scores_sorted)
    print("\nImmediate alerts:")
    for s in alerts:
        print(f"{s.coin_symbol} ({s.exchange}) -> {s.overall_score}")


def parse_args():
    parser = argparse.ArgumentParser(description="Multi-exchange crypto breakout scanner.")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to save JSON output (also printed to stdout).",
        default=None,
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_scan(args.output))
