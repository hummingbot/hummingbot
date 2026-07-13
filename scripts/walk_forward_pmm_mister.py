#!/usr/bin/env python3
import argparse
import asyncio
import json
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

from hummingbot.strategy_v2.backtesting.backtesting_engine_base import (  # noqa: E402
    BacktestingEngineBase,
)
from hummingbot.strategy_v2.backtesting.candidate_io import load_parameter_candidates  # noqa: E402
from hummingbot.strategy_v2.backtesting.walk_forward import (  # noqa: E402
    CostModel,
    ValidationCriteria,
    apply_cost_model,
    generate_rolling_windows,
    summarize_out_of_sample,
    validation_score,
)


@dataclass(frozen=True)
class PMMParameters:
    spread: float
    take_profit: float
    refresh_seconds: int


DEFAULT_CANDIDATES = [
    PMMParameters(0.0005, 0.001, 30),
    PMMParameters(0.001, 0.002, 60),
    PMMParameters(0.002, 0.003, 120),
]


def build_config(args, parameters: PMMParameters, suffix: str):
    data = {
        "id": f"walk_forward_pmm_{suffix}",
        "controller_type": "generic",
        "controller_name": "pmm_mister",
        "connector_name": args.connector,
        "trading_pair": args.trading_pair,
        "total_amount_quote": str(args.capital),
        "portfolio_allocation": str(args.portfolio_allocation),
        "target_base_pct": "0.5",
        "min_base_pct": "0.3",
        "max_base_pct": "0.7",
        "buy_spreads": str(parameters.spread),
        "sell_spreads": str(parameters.spread),
        "buy_amounts_pct": "1",
        "sell_amounts_pct": "1",
        "executor_refresh_time": parameters.refresh_seconds,
        "buy_cooldown_time": parameters.refresh_seconds,
        "sell_cooldown_time": parameters.refresh_seconds,
        "buy_position_effectivization_time": parameters.refresh_seconds * 2,
        "sell_position_effectivization_time": parameters.refresh_seconds * 2,
        "price_distance_tolerance": str(parameters.spread),
        "refresh_tolerance": str(parameters.spread),
        "leverage": args.leverage,
        "position_mode": "ONEWAY",
        "position_side": "BUY",
        "take_profit": str(parameters.take_profit),
        "open_order_type": "LIMIT_MAKER",
        "take_profit_order_type": "LIMIT_MAKER",
        "max_active_executors_by_level": 2,
        "position_profit_protection": True,
        "global_tp_enabled": False,
        "global_sl_enabled": True,
        "global_stop_loss": str(args.global_stop_loss),
    }
    return BacktestingEngineBase.get_controller_config_instance_from_dict(
        data, controllers_module="controllers"
    )


def normalize_engine_results(result: Dict) -> Dict:
    raw = dict(result["results"])
    executors = result["executors"]
    filled = [
        executor for executor in executors if float(executor.filled_amount_quote) > 0
    ]
    raw["net_pnl_quote"] = float(raw.get("net_pnl_quote", 0)) + float(
        raw.get("unrealized_pnl_quote", 0)
    )
    raw["total_volume"] = sum(
        float(executor.filled_amount_quote) for executor in filled
    )
    raw["total_executors_with_position"] = len(filled)
    return raw


async def run_period(
    args, parameters: PMMParameters, start: int, end: int, suffix: str, costs: CostModel
) -> Dict:
    engine = BacktestingEngineBase()
    result = await engine.run_backtesting(
        build_config(args, parameters, suffix),
        start,
        end,
        backtesting_resolution=args.interval,
        trade_cost=costs.fee_rate,
    )
    raw = normalize_engine_results(result)
    metrics = apply_cost_model(raw, args.capital, end - start, costs)
    metrics["validation_score"] = validation_score(metrics)
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
    costs = CostModel(args.fee_bps, args.slippage_bps, 0.0, args.funding_rate_daily)
    criteria = ValidationCriteria(
        args.minimum_folds,
        args.minimum_profitable_fold_ratio,
        args.maximum_drawdown_pct,
        args.minimum_adjusted_net_quote,
    )
    candidates = load_parameter_candidates(
        args.candidates_json,
        PMMParameters,
        DEFAULT_CANDIDATES,
        args.candidate_count,
    )
    folds: List[Dict] = []
    for window in windows:
        print(f"第 {window.index} 折：选择做市参数……")
        training_runs = []
        for candidate_index, candidate in enumerate(candidates, start=1):
            try:
                metrics = await run_period(
                    args,
                    candidate,
                    window.train_start,
                    window.train_end,
                    f"{window.index}_train_{candidate_index}",
                    costs,
                )
                training_runs.append(
                    {"parameters": asdict(candidate), "metrics": metrics}
                )
            except Exception as exc:
                training_runs.append(
                    {"parameters": asdict(candidate), "error": str(exc)}
                )
        successful = [run for run in training_runs if "metrics" in run]
        if not successful:
            folds.append(
                {
                    "index": window.index,
                    "status": "failed",
                    "window": window.to_dict(),
                    "training_runs": training_runs,
                    "error": "所有训练参数都运行失败",
                }
            )
            continue
        selected = max(successful, key=lambda run: run["metrics"]["validation_score"])
        parameters = PMMParameters(**selected["parameters"])
        candidate_test_runs = []
        for candidate_index, candidate in enumerate(candidates, start=1):
            try:
                test_metrics = await run_period(
                    args,
                    candidate,
                    window.test_start,
                    window.test_end,
                    f"{window.index}_test_{candidate_index}",
                    costs,
                )
                candidate_test_runs.append(
                    {"parameters": asdict(candidate), "metrics": test_metrics}
                )
            except Exception as exc:
                candidate_test_runs.append(
                    {"parameters": asdict(candidate), "error": str(exc)}
                )
        selected_test = next(
            (
                run
                for run in candidate_test_runs
                if run["parameters"] == asdict(parameters)
            ),
            {},
        )
        if "metrics" in selected_test:
            metrics = selected_test["metrics"]
            folds.append(
                {
                    "index": window.index,
                    "status": "completed",
                    "window": window.to_dict(),
                    "selected_parameters": asdict(parameters),
                    "training_runs": training_runs,
                    "candidate_test_runs": candidate_test_runs,
                    "metrics": metrics,
                }
            )
        else:
            folds.append(
                {
                    "index": window.index,
                    "status": "failed",
                    "window": window.to_dict(),
                    "selected_parameters": asdict(parameters),
                    "training_runs": training_runs,
                    "candidate_test_runs": candidate_test_runs,
                    "error": selected_test.get("error", "选中参数样本外运行失败"),
                }
            )
    summary = summarize_out_of_sample(folds, criteria)
    candidate_summaries = []
    for candidate in candidates:
        parameters = asdict(candidate)
        fixed_folds = []
        for fold in folds:
            run = next(
                (
                    row
                    for row in fold.get("candidate_test_runs") or []
                    if row.get("parameters") == parameters
                ),
                {},
            )
            fixed_folds.append(
                {
                    "status": "completed" if "metrics" in run else "failed",
                    "metrics": run.get("metrics", {}),
                }
            )
        candidate_summaries.append(
            {
                "parameters": parameters,
                "summary": summarize_out_of_sample(fixed_folds, criteria),
            }
        )
    fixed_candidate_passed = any(
        row["summary"]["passed"] for row in candidate_summaries
    )
    return {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": "pmm_mister",
        "strategy_label": "高级纯做市",
        "status": "completed"
        if summary["completed_folds"] == len(windows)
        else "partial",
        "validation_passed": summary["passed"] and fixed_candidate_passed,
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
            "portfolio_allocation": args.portfolio_allocation,
            "candidate_count": len(candidates),
        },
        "cost_model": asdict(costs),
        "summary": summary,
        "candidate_summaries": candidate_summaries,
        "folds": folds,
    }


def render_markdown(report: Dict) -> str:
    config, summary = report["configuration"], report["summary"]
    lines = [
        "# 高级纯做市滚动验证报告",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 市场：`{config['connector']}` / `{config['trading_pair']}` / `{config['interval']}`",
        f"- 验证结果：{'通过' if report['validation_passed'] else '未通过'}",
        f"- 完成折数：{summary['completed_folds']}",
        f"- 盈利折数：{summary['profitable_folds']}（{summary['profitable_fold_ratio']:.1%}）",
        f"- 费用后样本外净收益：{summary['total_adjusted_net_quote']:.4f} USDT",
        f"- 最大回撤：{summary['maximum_drawdown_pct']:.2%}",
        f"- 成交次数：{summary['total_positions']}",
        "",
        "## 分折结果",
        "",
    ]
    for fold in report["folds"]:
        if fold["status"] != "completed":
            lines.append(
                f"- 第 {fold['index']} 折：失败；{fold.get('error', '未知错误')}"
            )
            continue
        metrics, params = fold["metrics"], fold["selected_parameters"]
        lines.append(
            f"- 第 {fold['index']} 折：价差={params['spread']:.2%}；"
            f"费用后净收益={metrics['adjusted_net_quote']:.4f} USDT；"
            f"最大回撤={metrics['max_drawdown_pct']:.2%}；成交={metrics['total_positions']}"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "回测按全部成交额扣除手续费与滑点，并将窗口末持仓按市价计入。未通过门禁时必须保持影子状态。",
        ]
    )
    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="高级纯做市计费滚动验证")
    parser.add_argument("--connector", default="binance_perpetual")
    parser.add_argument("--trading-pair", default="ETH-USDT")
    parser.add_argument("--interval", default="3m")
    parser.add_argument("--days", type=float, default=7)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=0)
    parser.add_argument("--train-days", type=float, default=3)
    parser.add_argument("--test-days", type=float, default=1)
    parser.add_argument("--purge-minutes", type=int, default=3)
    parser.add_argument("--candidate-count", type=int, choices=[1, 2, 3], default=3)
    parser.add_argument("--candidates-json", default="")
    parser.add_argument("--capital", type=float, default=1_000)
    parser.add_argument("--portfolio-allocation", type=float, default=0.2)
    parser.add_argument("--leverage", type=int, default=1)
    parser.add_argument("--global-stop-loss", type=float, default=0.05)
    parser.add_argument("--fee-bps", type=float, default=4.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--funding-rate-daily", type=float, default=0.0001)
    parser.add_argument("--minimum-folds", type=int, default=3)
    parser.add_argument("--minimum-profitable-fold-ratio", type=float, default=0.5)
    parser.add_argument("--maximum-drawdown-pct", type=float, default=0.15)
    parser.add_argument("--minimum-adjusted-net-quote", type=float, default=0.0)
    parser.add_argument(
        "--json-output",
        default=str(ROOT / "reports" / "pmm_mister_walk_forward_latest.json"),
    )
    parser.add_argument(
        "--markdown-output",
        default=str(ROOT / "reports" / "pmm_mister_walk_forward_latest.md"),
    )
    args = parser.parse_args()
    args.start = args.start or None
    args.end = args.end or None
    report = await run_walk_forward(args)
    json_path = Path(args.json_output).expanduser().resolve()
    markdown_path = Path(args.markdown_output).expanduser().resolve()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_markdown(report) + "\n", encoding="utf-8")
    print(render_markdown(report))


if __name__ == "__main__":
    asyncio.run(main())
