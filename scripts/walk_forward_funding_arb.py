#!/usr/bin/env python3
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hummingbot.strategy_v2.backtesting.funding_arbitrage import (  # noqa: E402
    FundingArbitrageCosts,
    FundingArbitrageParameters,
    simulate_funding_arbitrage,
)
from hummingbot.strategy_v2.backtesting.candidate_io import load_parameter_candidates  # noqa: E402
from hummingbot.strategy_v2.backtesting.walk_forward import (  # noqa: E402
    ValidationCriteria,
    generate_rolling_windows,
    summarize_out_of_sample,
    validation_score,
)


HOUR_MS = 3_600_000
DEFAULT_CANDIDATES = [
    FundingArbitrageParameters(0.001, 0.003, 24),
    FundingArbitrageParameters(0.002, 0.005, 48),
    FundingArbitrageParameters(0.003, 0.008, 72),
]


def request_json(url: str, payload: Dict = None, retries: int = 4):
    body = json.dumps(payload).encode() if payload else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "hummingbot-strategy-evolution/1.0",
        },
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except HTTPError as exc:
            if exc.code != 429 or attempt >= retries:
                raise
            retry_after = exc.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else min(60, 2 ** (attempt + 1))
        except URLError:
            if attempt >= retries:
                raise
            delay = min(30, 2 ** (attempt + 1))
        time.sleep(max(1.0, delay))
    raise RuntimeError("unreachable retry state")


def fetch_binance_funding(symbol: str, start_ms: int, end_ms: int) -> List[Dict]:
    params = urllib.parse.urlencode({"symbol": symbol, "startTime": start_ms, "endTime": end_ms, "limit": 1000})
    return request_json(f"https://fapi.binance.com/fapi/v1/fundingRate?{params}")


def fetch_binance_prices(symbol: str, start_ms: int, end_ms: int) -> List[Dict]:
    rows = []
    cursor = start_ms
    while cursor < end_ms:
        params = urllib.parse.urlencode({
            "symbol": symbol, "interval": "1h", "startTime": cursor, "endTime": end_ms, "limit": 1500,
        })
        batch = request_json(f"https://fapi.binance.com/fapi/v1/markPriceKlines?{params}")
        if not batch:
            break
        rows.extend({"timestamp": int(row[0]) // 1000, "price": float(row[4])} for row in batch)
        cursor = int(batch[-1][0]) + HOUR_MS
    return rows


def fetch_hyperliquid_funding(coin: str, start_ms: int, end_ms: int) -> List[Dict]:
    rows = []
    cursor = start_ms
    while cursor < end_ms:
        batch = request_json("https://api.hyperliquid.xyz/info", {
            "type": "fundingHistory", "coin": coin, "startTime": cursor, "endTime": end_ms,
        })
        if not batch:
            break
        rows.extend(batch)
        next_cursor = int(batch[-1]["time"]) + 1
        if next_cursor <= cursor:
            break
        cursor = next_cursor
    return rows


def fetch_hyperliquid_prices(coin: str, start_ms: int, end_ms: int) -> List[Dict]:
    rows = request_json("https://api.hyperliquid.xyz/info", {
        "type": "candleSnapshot",
        "req": {"coin": coin, "interval": "1h", "startTime": start_ms, "endTime": end_ms},
    })
    return [{"timestamp": int(row["t"]) // 1000, "price": float(row["c"])} for row in rows]


def build_snapshots(binance_funding, binance_prices, hyperliquid_funding, hyperliquid_prices) -> List[Dict]:
    binance_price_map = {row["timestamp"] // 3600 * 3600: row["price"] for row in binance_prices}
    hyperliquid_price_map = {row["timestamp"] // 3600 * 3600: row["price"] for row in hyperliquid_prices}
    binance_payment_map = {
        int(row["fundingTime"]) // HOUR_MS * 3600: float(row["fundingRate"]) for row in binance_funding
    }
    hyperliquid_payment_map = {
        int(row["time"]) // HOUR_MS * 3600: float(row["fundingRate"]) for row in hyperliquid_funding
    }
    timestamps = sorted(set(binance_price_map) & set(hyperliquid_price_map))
    latest_binance_rate = 0.0
    latest_hyperliquid_rate = 0.0
    binance_event_times = sorted(binance_payment_map)
    inferred_binance_interval_hours = 8.0
    snapshots = []
    for timestamp in timestamps:
        if timestamp in binance_payment_map:
            latest_binance_rate = binance_payment_map[timestamp]
            previous = [event for event in binance_event_times if event < timestamp]
            if previous:
                inferred_binance_interval_hours = max(1.0, (timestamp - previous[-1]) / 3600)
        if timestamp in hyperliquid_payment_map:
            latest_hyperliquid_rate = hyperliquid_payment_map[timestamp]
        snapshots.append({
            "timestamp": timestamp,
            "binance_price": binance_price_map[timestamp],
            "hyperliquid_price": hyperliquid_price_map[timestamp],
            "binance_funding_payment_rate": binance_payment_map.get(timestamp, 0.0),
            "hyperliquid_funding_payment_rate": hyperliquid_payment_map.get(timestamp, 0.0),
            "binance_forecast_daily_rate": latest_binance_rate * 24 / inferred_binance_interval_hours,
            "hyperliquid_forecast_daily_rate": latest_hyperliquid_rate * 24,
        })
    return snapshots


def run_walk_forward(args) -> Dict:
    end = args.end or int(time.time())
    start = args.start or end - int(args.days * 86_400)
    start_ms, end_ms = start * 1000, end * 1000
    binance_funding = fetch_binance_funding(args.binance_symbol, start_ms, end_ms)
    binance_prices = fetch_binance_prices(args.binance_symbol, start_ms, end_ms)
    hyperliquid_funding = fetch_hyperliquid_funding(args.coin, start_ms, end_ms)
    hyperliquid_prices = fetch_hyperliquid_prices(args.coin, start_ms, end_ms)
    snapshots = build_snapshots(binance_funding, binance_prices, hyperliquid_funding, hyperliquid_prices)
    windows = generate_rolling_windows(
        start, end, int(args.train_days * 86_400), int(args.test_days * 86_400), args.purge_hours * 3600,
    )
    costs = FundingArbitrageCosts(args.binance_taker_bps, args.hyperliquid_taker_bps, args.slippage_bps)
    criteria = ValidationCriteria(args.minimum_folds, args.minimum_profitable_fold_ratio,
                                  args.maximum_drawdown_pct, args.minimum_adjusted_net_quote)
    candidates = load_parameter_candidates(
        args.candidates_json, FundingArbitrageParameters, DEFAULT_CANDIDATES, args.candidate_count,
    )
    folds = []
    for window in windows:
        training_rows = [row for row in snapshots if window.train_start <= row["timestamp"] < window.train_end]
        test_rows = [row for row in snapshots if window.test_start <= row["timestamp"] < window.test_end]
        training_runs = []
        for candidate in candidates:
            metrics = simulate_funding_arbitrage(training_rows, candidate, costs, args.position_size)
            metrics["validation_score"] = validation_score(metrics)
            training_runs.append({"parameters": asdict(candidate), "metrics": metrics})
        selected = max(training_runs, key=lambda row: row["metrics"]["validation_score"])
        selected_parameters = FundingArbitrageParameters(**selected["parameters"])
        metrics = simulate_funding_arbitrage(test_rows, selected_parameters, costs, args.position_size)
        metrics["validation_score"] = validation_score(metrics)
        folds.append({
            "index": window.index, "status": "completed", "window": window.to_dict(),
            "selected_parameters": asdict(selected_parameters), "training_runs": training_runs, "metrics": metrics,
        })
    summary = summarize_out_of_sample(folds, criteria)
    return {
        "version": "1.0", "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": "funding_rate_arb", "strategy_label": "资金费率套利",
        "status": "completed" if len(folds) == len(windows) else "partial",
        "validation_passed": summary["passed"],
        "configuration": {
            "coin": args.coin, "binance_symbol": args.binance_symbol, "interval": "1h",
            "start": start, "end": end, "train_days": args.train_days, "test_days": args.test_days,
            "purge_hours": args.purge_hours, "position_size_quote_per_leg": args.position_size,
            "candidate_count": len(candidates), "snapshot_count": len(snapshots),
        },
        "cost_model": {**asdict(costs), "round_trip_pct": costs.round_trip_pct},
        "data_sources": {
            "binance_funding": "https://fapi.binance.com/fapi/v1/fundingRate",
            "binance_prices": "https://fapi.binance.com/fapi/v1/markPriceKlines",
            "hyperliquid": "https://api.hyperliquid.xyz/info",
        },
        "summary": summary, "folds": folds,
    }


def render_markdown(report: Dict) -> str:
    summary = report["summary"]
    config = report["configuration"]
    lines = [
        "# 资金费率套利滚动验证报告", "",
        f"- 生成时间：{report['generated_at']}",
        f"- 市场：Binance `{config['binance_symbol']}` / Hyperliquid `{config['coin']}`",
        f"- 验证结果：{'通过' if report['validation_passed'] else '未通过'}",
        f"- 历史快照：{config['snapshot_count']} 个小时",
        f"- 完成折数：{summary['completed_folds']}",
        f"- 盈利折数：{summary['profitable_folds']}（{summary['profitable_fold_ratio']:.1%}）",
        f"- 费用后样本外净收益：{summary['total_adjusted_net_quote']:.4f} USDT",
        f"- 最大回撤：{summary['maximum_drawdown_pct']:.2%}",
        f"- 套利持仓次数：{summary['total_positions']}", "", "## 成本模型", "",
        f"- Binance 吃单费：{report['cost_model']['binance_taker_bps']:.2f} 基点／腿／方向",
        f"- Hyperliquid 吃单费：{report['cost_model']['hyperliquid_taker_bps']:.2f} 基点／腿／方向",
        f"- 滑点：{report['cost_model']['slippage_bps_per_leg']:.2f} 基点／腿／方向",
        f"- 双腿完整往返成本：{report['cost_model']['round_trip_pct']:.2%}", "", "## 分折结果", "",
    ]
    for fold in report["folds"]:
        metrics = fold["metrics"]
        params = fold["selected_parameters"]
        lines.append(
            f"- 第 {fold['index']} 折：阈值={params['minimum_daily_rate_difference']:.2%}；"
            f"费用后净收益={metrics['adjusted_net_quote']:.4f} USDT；"
            f"最大回撤={metrics['max_drawdown_pct']:.2%}；持仓={metrics['total_positions']}"
        )
    lines.extend(["", "## 结论", "",
                  "历史模拟包含双腿费率现金流、基差变化、双边手续费和滑点，不包含盘口冲击与单腿成交失败。未通过门禁时必须保持影子状态。"])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="资金费率套利计费滚动验证")
    parser.add_argument("--coin", default="WIF")
    parser.add_argument("--binance-symbol", default="WIFUSDT")
    parser.add_argument("--days", type=float, default=60)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=0)
    parser.add_argument("--train-days", type=float, default=14)
    parser.add_argument("--test-days", type=float, default=7)
    parser.add_argument("--purge-hours", type=int, default=1)
    parser.add_argument("--candidate-count", type=int, choices=[1, 2, 3], default=3)
    parser.add_argument("--candidates-json", default="")
    parser.add_argument("--position-size", type=float, default=1_000)
    parser.add_argument("--binance-taker-bps", type=float, default=5.0)
    parser.add_argument("--hyperliquid-taker-bps", type=float, default=4.5)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--minimum-folds", type=int, default=3)
    parser.add_argument("--minimum-profitable-fold-ratio", type=float, default=0.5)
    parser.add_argument("--maximum-drawdown-pct", type=float, default=0.15)
    parser.add_argument("--minimum-adjusted-net-quote", type=float, default=0.0)
    parser.add_argument("--json-output", default=str(ROOT / "reports" / "funding_arb_walk_forward_latest.json"))
    parser.add_argument("--markdown-output", default=str(ROOT / "reports" / "funding_arb_walk_forward_latest.md"))
    args = parser.parse_args()
    args.start = args.start or None
    args.end = args.end or None
    report = run_walk_forward(args)
    json_path = Path(args.json_output).expanduser().resolve()
    markdown_path = Path(args.markdown_output).expanduser().resolve()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report) + "\n", encoding="utf-8")
    print(render_markdown(report))


if __name__ == "__main__":
    main()
