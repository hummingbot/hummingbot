#!/usr/bin/env python3
import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from pyinjective.proto.injective.stream.v2 import query_pb2
    if not hasattr(query_pb2, "OrderFailuresFilter"):
        query_pb2.OrderFailuresFilter = type("OrderFailuresFilter", (), {})
except ImportError:
    pass

from hummingbot.strategy_v2.backtesting.backtesting_engine_base import BacktestingEngineBase  # noqa: E402
from hummingbot.strategy_v2.backtesting.walk_forward import (  # noqa: E402
    CostModel,
    ValidationCriteria,
    apply_cost_model,
    generate_rolling_windows,
    summarize_out_of_sample,
    validation_score,
)


@dataclass(frozen=True)
class SuperTrendParameters:
    length: int
    multiplier: float
    percentage_threshold: float


DEFAULT_CANDIDATES = [
    SuperTrendParameters(10, 3.0, 0.01),
    SuperTrendParameters(20, 4.0, 0.01),
    SuperTrendParameters(30, 4.5, 0.015),
]


def build_config(args, parameters: SuperTrendParameters, suffix: str):
    config_data = {
        "id": f"walk_forward_supertrend_{suffix}",
        "controller_name": "supertrend_v1",
        "controller_type": "directional_trading",
        "connector_name": args.connector,
        "trading_pair": args.trading_pair,
        "candles_connector": args.connector,
        "candles_trading_pair": args.trading_pair,
        "interval": args.interval,
        "length": parameters.length,
        "multiplier": parameters.multiplier,
        "percentage_threshold": parameters.percentage_threshold,
        "total_amount_quote": str(args.capital),
        "max_executors_per_side": 1,
        "cooldown_time": args.cooldown_seconds,
        "leverage": args.leverage,
        "position_mode": "HEDGE",
        "stop_loss": str(args.stop_loss),
        "take_profit": str(args.take_profit),
        "time_limit": args.time_limit_seconds,
        "take_profit_order_type": "MARKET",
    }
    return BacktestingEngineBase.get_controller_config_instance_from_dict(
        config_data, controllers_module="controllers"
    )


async def run_period(args, parameters: SuperTrendParameters, start: int, end: int, suffix: str, costs: CostModel) -> Dict:
    config = build_config(args, parameters, suffix)
    engine = BacktestingEngineBase()
    started = time.perf_counter()
    result = await engine.run_backtesting(
        config,
        start,
        end,
        backtesting_resolution=args.interval,
        trade_cost=costs.fee_rate,
    )
    metrics = apply_cost_model(result["results"], args.capital, end - start, costs)
    metrics["validation_score"] = validation_score(metrics)
    metrics["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    return metrics


async def run_walk_forward(args) -> Dict:
    end = args.end or int(time.time())
    start = args.start or end - int(args.days * 86_400)
    windows = generate_rolling_windows(
        start,
        end,
        int(args.train_days * 86_400),
        int(args.test_days * 86_400),
        args.purge_minutes * 60,
    )
    costs = CostModel(args.fee_bps, args.slippage_bps, args.switch_bps, args.funding_rate_daily)
    criteria = ValidationCriteria(
        minimum_folds=args.minimum_folds,
        minimum_profitable_fold_ratio=args.minimum_profitable_fold_ratio,
        maximum_drawdown_pct=args.maximum_drawdown_pct,
        minimum_adjusted_net_quote=args.minimum_adjusted_net_quote,
    )
    candidates = DEFAULT_CANDIDATES[:args.candidate_count]
    folds: List[Dict] = []

    for window in windows:
        print(f"第 {window.index} 折：选择训练参数……")
        training_runs = []
        for candidate_index, candidate in enumerate(candidates, start=1):
            try:
                metrics = await run_period(
                    args, candidate, window.train_start, window.train_end,
                    f"{window.index}_train_{candidate_index}", costs,
                )
                training_runs.append({"parameters": asdict(candidate), "metrics": metrics})
            except Exception as exc:
                training_runs.append({"parameters": asdict(candidate), "error": str(exc)})

        successful = [run for run in training_runs if "metrics" in run]
        if not successful:
            folds.append({
                "index": window.index,
                "status": "failed",
                "window": window.to_dict(),
                "training_runs": training_runs,
                "error": "所有训练参数都运行失败",
            })
            continue

        selected = max(successful, key=lambda run: run["metrics"]["validation_score"])
        parameters = SuperTrendParameters(**selected["parameters"])
        print(f"第 {window.index} 折：样本外验证参数 {parameters}")
        try:
            metrics = await run_period(
                args, parameters, window.test_start, window.test_end,
                f"{window.index}_test", costs,
            )
            folds.append({
                "index": window.index,
                "status": "completed",
                "window": window.to_dict(),
                "selected_parameters": asdict(parameters),
                "training_runs": training_runs,
                "metrics": metrics,
            })
        except Exception as exc:
            folds.append({
                "index": window.index,
                "status": "failed",
                "window": window.to_dict(),
                "selected_parameters": asdict(parameters),
                "training_runs": training_runs,
                "error": str(exc),
            })

    summary = summarize_out_of_sample(folds, criteria)
    return {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": "supertrend_v1",
        "strategy_label": "超级趋势",
        "status": "completed" if summary["completed_folds"] == len(windows) else "partial",
        "validation_passed": summary["passed"],
        "configuration": {
            "connector": args.connector,
            "trading_pair": args.trading_pair,
            "interval": args.interval,
            "start": start,
            "end": end,
            "train_days": args.train_days,
            "test_days": args.test_days,
            "purge_minutes": args.purge_minutes,
            "capital_quote": args.capital,
            "leverage": args.leverage,
            "candidate_count": len(candidates),
        },
        "cost_model": asdict(costs),
        "summary": summary,
        "folds": folds,
    }


def render_markdown(report: Dict) -> str:
    config = report["configuration"]
    summary = report["summary"]
    lines = [
        "# 超级趋势滚动验证报告",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 市场：`{config['connector']}` / `{config['trading_pair']}` / `{config['interval']}`",
        f"- 验证结果：{'通过' if report['validation_passed'] else '未通过'}",
        f"- 完成折数：{summary['completed_folds']}",
        f"- 盈利折数：{summary['profitable_folds']}（{summary['profitable_fold_ratio']:.1%}）",
        f"- 费用后样本外净收益：{summary['total_adjusted_net_quote']:.4f} USDT",
        f"- 最大回撤：{summary['maximum_drawdown_pct']:.2%}",
        f"- 总持仓次数：{summary['total_positions']}",
        "",
        "## 成本模型",
        "",
        f"- 手续费：{report['cost_model']['fee_bps']:.2f} 基点",
        f"- 滑点：{report['cost_model']['slippage_bps']:.2f} 基点／成交方向（按往返成交额计费）",
        f"- 切换成本：{report['cost_model']['switch_bps']:.2f} 基点／持仓",
        f"- 每日资金费率成本：{report['cost_model']['funding_rate_daily']:.4%}",
        "",
        "## 分折结果",
        "",
    ]
    for fold in report["folds"]:
        if fold["status"] != "completed":
            lines.append(f"- 第 {fold['index']} 折：失败；{fold.get('error', '未知错误')}")
            continue
        metrics = fold["metrics"]
        params = fold["selected_parameters"]
        lines.append(
            f"- 第 {fold['index']} 折：参数 length={params['length']}、multiplier={params['multiplier']}；"
            f"费用后净收益={metrics['adjusted_net_quote']:.4f} USDT；"
            f"最大回撤={metrics['max_drawdown_pct']:.2%}；持仓={metrics['total_positions']}"
        )
    lines.extend([
        "",
        "## 结论",
        "",
        "本报告只代表指定历史窗口的样本外模拟，不构成盈利承诺。只有满足门禁后，策略才可以进入纸面观察阶段。",
    ])
    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="超级趋势计费滚动验证")
    parser.add_argument("--connector", default="binance_perpetual")
    parser.add_argument("--trading-pair", default="BTC-USDT")
    parser.add_argument("--interval", default="3m")
    parser.add_argument("--days", type=float, default=30)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=0)
    parser.add_argument("--train-days", type=float, default=14)
    parser.add_argument("--test-days", type=float, default=3)
    parser.add_argument("--purge-minutes", type=int, default=3)
    parser.add_argument("--candidate-count", type=int, choices=[1, 2, 3], default=3)
    parser.add_argument("--capital", type=float, default=1_000)
    parser.add_argument("--leverage", type=int, default=1)
    parser.add_argument("--cooldown-seconds", type=int, default=300)
    parser.add_argument("--stop-loss", type=float, default=0.02)
    parser.add_argument("--take-profit", type=float, default=0.03)
    parser.add_argument("--time-limit-seconds", type=int, default=2_700)
    parser.add_argument("--fee-bps", type=float, default=4.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--switch-bps", type=float, default=1.0)
    parser.add_argument("--funding-rate-daily", type=float, default=0.0001)
    parser.add_argument("--minimum-folds", type=int, default=3)
    parser.add_argument("--minimum-profitable-fold-ratio", type=float, default=0.5)
    parser.add_argument("--maximum-drawdown-pct", type=float, default=0.15)
    parser.add_argument("--minimum-adjusted-net-quote", type=float, default=0.0)
    parser.add_argument("--json-output", default=str(ROOT / "reports" / "supertrend_walk_forward_latest.json"))
    parser.add_argument("--markdown-output", default=str(ROOT / "reports" / "supertrend_walk_forward_latest.md"))
    args = parser.parse_args()
    if args.start == 0:
        args.start = None
    if args.end == 0:
        args.end = None

    report = await run_walk_forward(args)
    json_output = Path(args.json_output).expanduser().resolve()
    markdown_output = Path(args.markdown_output).expanduser().resolve()
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + os.linesep, encoding="utf-8")
    markdown_output.write_text(render_markdown(report) + os.linesep, encoding="utf-8")
    print(render_markdown(report))


if __name__ == "__main__":
    asyncio.run(main())
