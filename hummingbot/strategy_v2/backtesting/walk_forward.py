from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class WalkForwardWindow:
    index: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass(frozen=True)
class CostModel:
    fee_bps: float = 4.0
    slippage_bps: float = 2.0
    switch_bps: float = 1.0
    funding_rate_daily: float = 0.0001

    @property
    def fee_rate(self) -> float:
        return self.fee_bps / 10_000


@dataclass(frozen=True)
class ValidationCriteria:
    minimum_folds: int = 3
    minimum_profitable_fold_ratio: float = 0.5
    maximum_drawdown_pct: float = 0.15
    minimum_adjusted_net_quote: float = 0.0


def generate_rolling_windows(
    start: int,
    end: int,
    train_seconds: int,
    test_seconds: int,
    purge_seconds: int = 0,
) -> List[WalkForwardWindow]:
    if start >= end:
        raise ValueError("开始时间必须早于结束时间")
    if train_seconds <= 0 or test_seconds <= 0:
        raise ValueError("训练窗口和测试窗口必须大于零")
    if purge_seconds < 0:
        raise ValueError("隔离窗口不能为负数")

    windows: List[WalkForwardWindow] = []
    train_start = start
    index = 1
    while True:
        train_end = train_start + train_seconds
        test_start = train_end + purge_seconds
        test_end = test_start + test_seconds
        if test_end > end:
            break
        windows.append(WalkForwardWindow(index, train_start, train_end, test_start, test_end))
        train_start += test_seconds
        index += 1
    return windows


def apply_cost_model(
    raw_results: Dict,
    capital_quote: float,
    window_seconds: int,
    costs: CostModel,
) -> Dict:
    raw_net_quote = float(raw_results.get("net_pnl_quote", 0))
    engine_fees_quote = float(raw_results.get("total_fees_quote", 0))
    total_volume = float(raw_results.get("total_volume", 0))
    positions = int(raw_results.get("total_executors_with_position", 0))
    # Hummingbot reports round-trip filled volume, so apply one slippage rate to that full volume.
    slippage_quote = total_volume * costs.slippage_bps / 10_000
    switching_quote = positions * capital_quote * costs.switch_bps / 10_000
    funding_quote = capital_quote * abs(costs.funding_rate_daily) * window_seconds / 86_400
    adjusted_net_quote = raw_net_quote - slippage_quote - switching_quote - funding_quote
    adjusted_return = adjusted_net_quote / capital_quote if capital_quote else 0.0
    return {
        "raw_net_quote": raw_net_quote,
        "engine_fees_quote": engine_fees_quote,
        "slippage_quote": slippage_quote,
        "switching_quote": switching_quote,
        "funding_quote": funding_quote,
        "adjusted_net_quote": adjusted_net_quote,
        "adjusted_return": adjusted_return,
        "max_drawdown_pct": abs(float(raw_results.get("max_drawdown_pct", 0))),
        "sharpe_ratio": float(raw_results.get("sharpe_ratio", 0)),
        "profit_factor": float(raw_results.get("profit_factor", 0)),
        "total_positions": positions,
        "total_volume": total_volume,
        "turnover_ratio": total_volume / capital_quote if capital_quote else 0.0,
    }


def validation_score(metrics: Dict, drawdown_penalty: float = 1.0, turnover_penalty: float = 0.00002) -> float:
    return (
        float(metrics.get("adjusted_return", 0))
        - drawdown_penalty * float(metrics.get("max_drawdown_pct", 0))
        - turnover_penalty * float(metrics.get("turnover_ratio", 0))
    )


def summarize_out_of_sample(folds: Iterable[Dict], criteria: ValidationCriteria) -> Dict:
    completed = [fold for fold in folds if fold.get("status") == "completed"]
    adjusted_nets = [float(fold["metrics"]["adjusted_net_quote"]) for fold in completed]
    profitable = sum(value > 0 for value in adjusted_nets)
    profitable_ratio = profitable / len(completed) if completed else 0.0
    max_drawdown = max((float(fold["metrics"]["max_drawdown_pct"]) for fold in completed), default=0.0)
    total_adjusted_net = sum(adjusted_nets)
    passed = (
        len(completed) >= criteria.minimum_folds
        and profitable_ratio >= criteria.minimum_profitable_fold_ratio
        and max_drawdown <= criteria.maximum_drawdown_pct
        and total_adjusted_net > criteria.minimum_adjusted_net_quote
    )
    return {
        "completed_folds": len(completed),
        "profitable_folds": profitable,
        "profitable_fold_ratio": profitable_ratio,
        "total_adjusted_net_quote": total_adjusted_net,
        "maximum_drawdown_pct": max_drawdown,
        "total_positions": sum(int(fold["metrics"]["total_positions"]) for fold in completed),
        "passed": passed,
        "criteria": asdict(criteria),
    }
