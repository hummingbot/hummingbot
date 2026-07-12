from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class FundingArbitrageParameters:
    minimum_daily_rate_difference: float
    take_profit_pct: float
    maximum_hold_hours: int
    reversal_stop_pct: float = -0.001
    maximum_entry_basis_pct: float = 0.02


@dataclass(frozen=True)
class FundingArbitrageCosts:
    binance_taker_bps: float = 5.0
    hyperliquid_taker_bps: float = 4.5
    slippage_bps_per_leg: float = 2.0

    @property
    def round_trip_pct(self) -> float:
        per_round_trip_bps = 2 * (
            self.binance_taker_bps
            + self.hyperliquid_taker_bps
            + 2 * self.slippage_bps_per_leg
        )
        return per_round_trip_bps / 10_000


def _basis_return(position: Dict, snapshot: Dict) -> float:
    if position["long_venue"] == "binance":
        long_return = snapshot["binance_price"] / position["binance_entry_price"] - 1
        short_return = 1 - snapshot["hyperliquid_price"] / position["hyperliquid_entry_price"]
    else:
        long_return = snapshot["hyperliquid_price"] / position["hyperliquid_entry_price"] - 1
        short_return = 1 - snapshot["binance_price"] / position["binance_entry_price"]
    return long_return + short_return


def _funding_cashflow(position: Dict, snapshot: Dict) -> float:
    binance_rate = float(snapshot.get("binance_funding_payment_rate", 0))
    hyperliquid_rate = float(snapshot.get("hyperliquid_funding_payment_rate", 0))
    if position["long_venue"] == "binance":
        return -binance_rate + hyperliquid_rate
    return binance_rate - hyperliquid_rate


def simulate_funding_arbitrage(
    snapshots: Iterable[Dict],
    parameters: FundingArbitrageParameters,
    costs: FundingArbitrageCosts,
    position_size_quote: float,
) -> Dict:
    rows = list(snapshots)
    if len(rows) < 2:
        return {
            "adjusted_net_quote": 0.0,
            "adjusted_return": 0.0,
            "max_drawdown_pct": 0.0,
            "total_positions": 0,
            "profitable_positions": 0,
            "costs_quote": 0.0,
            "funding_pnl_quote": 0.0,
            "basis_pnl_quote": 0.0,
            "turnover_ratio": 0.0,
            "parameters": asdict(parameters),
        }

    position = None
    realized_pct = 0.0
    equity_curve: List[float] = [0.0]
    trades: List[Dict] = []
    total_funding_pct = 0.0
    total_basis_pct = 0.0

    def close_position(snapshot: Dict, reason: str):
        nonlocal position, realized_pct, total_funding_pct, total_basis_pct
        basis_pct = _basis_return(position, snapshot)
        net_pct = position["funding_pct"] + basis_pct - costs.round_trip_pct
        realized_pct += net_pct
        total_funding_pct += position["funding_pct"]
        total_basis_pct += basis_pct
        trades.append({
            "entry_timestamp": position["entry_timestamp"],
            "exit_timestamp": snapshot["timestamp"],
            "long_venue": position["long_venue"],
            "funding_pct": position["funding_pct"],
            "basis_pct": basis_pct,
            "cost_pct": costs.round_trip_pct,
            "net_pct": net_pct,
            "exit_reason": reason,
        })
        position = None

    for snapshot in rows:
        binance_daily = float(snapshot["binance_forecast_daily_rate"])
        hyperliquid_daily = float(snapshot["hyperliquid_forecast_daily_rate"])
        daily_difference = abs(binance_daily - hyperliquid_daily)

        if position is not None:
            position["funding_pct"] += _funding_cashflow(position, snapshot)
            basis_pct = _basis_return(position, snapshot)
            current_pct = position["funding_pct"] + basis_pct - costs.round_trip_pct
            signed_advantage = (
                hyperliquid_daily - binance_daily
                if position["long_venue"] == "binance"
                else binance_daily - hyperliquid_daily
            )
            held_hours = (snapshot["timestamp"] - position["entry_timestamp"]) / 3_600
            if current_pct >= parameters.take_profit_pct:
                close_position(snapshot, "take_profit")
            elif signed_advantage <= parameters.reversal_stop_pct:
                close_position(snapshot, "funding_reversal")
            elif held_hours >= parameters.maximum_hold_hours:
                close_position(snapshot, "maximum_hold")

        if position is None and daily_difference >= parameters.minimum_daily_rate_difference:
            basis_pct = abs(snapshot["binance_price"] / snapshot["hyperliquid_price"] - 1)
            if basis_pct <= parameters.maximum_entry_basis_pct:
                position = {
                    "entry_timestamp": snapshot["timestamp"],
                    "long_venue": "binance" if binance_daily < hyperliquid_daily else "hyperliquid",
                    "binance_entry_price": snapshot["binance_price"],
                    "hyperliquid_entry_price": snapshot["hyperliquid_price"],
                    "funding_pct": 0.0,
                }

        unrealized_pct = 0.0
        if position is not None:
            unrealized_pct = position["funding_pct"] + _basis_return(position, snapshot) - costs.round_trip_pct
        equity_curve.append(realized_pct + unrealized_pct)

    if position is not None:
        close_position(rows[-1], "window_end")
        equity_curve.append(realized_pct)

    peak = equity_curve[0]
    max_drawdown = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    return {
        "adjusted_net_quote": realized_pct * position_size_quote,
        "adjusted_return": realized_pct,
        "max_drawdown_pct": max_drawdown,
        "total_positions": len(trades),
        "profitable_positions": sum(trade["net_pct"] > 0 for trade in trades),
        "costs_quote": len(trades) * costs.round_trip_pct * position_size_quote,
        "funding_pnl_quote": total_funding_pct * position_size_quote,
        "basis_pnl_quote": total_basis_pct * position_size_quote,
        "turnover_ratio": len(trades) * 4.0,
        "parameters": asdict(parameters),
        "trades": trades,
    }
