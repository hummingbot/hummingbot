from decimal import Decimal

import pandas as pd
import pytest

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.strategy_v2.backtesting.executors_simulator.position_executor_simulator import PositionExecutorSimulator
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.executors import CloseType

TRADE_COST = 0.001
TIMESTAMPS = [1000.0, 1060.0, 1120.0, 1180.0]


def _simulate(side, open_, high, low, close, stop_loss=Decimal("0.05")):
    config = PositionExecutorConfig(
        timestamp=TIMESTAMPS[0],
        connector_name="binance",
        trading_pair="ETH-USDT",
        side=side,
        entry_price=Decimal("100"),
        amount=Decimal("1"),
        triple_barrier_config=TripleBarrierConfig(stop_loss=stop_loss, time_limit=180,
                                                  open_order_type=OrderType.MARKET),
    )
    df = pd.DataFrame({
        "timestamp": TIMESTAMPS,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
    }).set_index("timestamp", drop=False)
    return PositionExecutorSimulator().simulate(df, config, trade_cost=TRADE_COST)


def _final(simulation):
    return simulation.get_executor_info_at_timestamp(TIMESTAMPS[-1])


@pytest.mark.parametrize("side, high, low, close", [
    # entry at 100, stop at 95: bar 2 wicks to 90 and closes back above the entry at 101
    (TradeType.BUY, [100.0, 100.5, 101.5, 102.0], [100.0, 99.5, 90.0, 100.5], [100.0, 100.0, 101.0, 101.5]),
    # entry at 100, stop at 105: bar 2 wicks to 110 and closes back below the entry at 99
    (TradeType.SELL, [100.0, 100.5, 110.0, 99.5], [100.0, 99.5, 98.5, 98.0], [100.0, 100.0, 99.0, 98.5]),
])
def test_stop_loss_exit_is_priced_at_the_stop_not_at_the_close(side, high, low, close):
    simulation = _simulate(side, open_=[100.0, 100.0, 100.0, 100.0], high=high, low=low, close=close)

    assert simulation.close_type == CloseType.STOP_LOSS
    assert simulation.executor_simulation.index[-1] == TIMESTAMPS[2]
    info = _final(simulation)
    assert info.net_pnl_pct == pytest.approx(Decimal(-0.05 - 2 * TRADE_COST))
    assert info.net_pnl_quote == pytest.approx(Decimal((-0.05 - 2 * TRADE_COST) * 100))


@pytest.mark.parametrize("side, open_, high, low, close, gap_open", [
    # the stop bar opens at 92, below the 95 stop, so the stop fills at the open
    (TradeType.BUY, [100.0, 100.0, 92.0, 93.0], [100.0, 100.5, 94.0, 94.0], [100.0, 99.5, 91.0, 92.0],
     [100.0, 100.0, 93.0, 93.5], 92.0),
    # the stop bar opens at 108, above the 105 stop, so the stop fills at the open
    (TradeType.SELL, [100.0, 100.0, 108.0, 107.0], [100.0, 100.5, 109.0, 108.0], [100.0, 99.5, 106.0, 106.0],
     [100.0, 100.0, 107.0, 107.5], 108.0),
])
def test_stop_loss_exit_uses_the_open_when_the_bar_gaps_through_the_stop(side, open_, high, low, close, gap_open):
    simulation = _simulate(side, open_=open_, high=high, low=low, close=close)

    assert simulation.close_type == CloseType.STOP_LOSS
    side_multiplier = 1 if side == TradeType.BUY else -1
    expected = (gap_open / 100.0 - 1) * side_multiplier - 2 * TRADE_COST
    assert _final(simulation).net_pnl_pct == pytest.approx(Decimal(expected))


def test_exit_without_stop_loss_is_still_priced_at_the_close():
    simulation = _simulate(TradeType.BUY, open_=[100.0, 100.0, 100.0, 100.0], high=[100.0, 101.0, 102.0, 103.0],
                           low=[100.0, 99.0, 98.0, 97.0], close=[100.0, 100.5, 101.0, 102.0])

    assert simulation.close_type == CloseType.TIME_LIMIT
    assert _final(simulation).net_pnl_pct == pytest.approx(Decimal(102.0 / 100.0 - 1 - 2 * TRADE_COST))


def test_entry_bar_low_does_not_trigger_the_stop():
    # entry fills at the first bar's close (100); its dip to 90 happened before the entry
    simulation = _simulate(TradeType.BUY, open_=[100.0, 100.0, 100.0, 100.0], high=[101.0, 101.0, 101.0, 102.0],
                           low=[90.0, 99.0, 99.5, 100.0], close=[100.0, 100.5, 101.0, 101.5])

    assert simulation.close_type == CloseType.TIME_LIMIT
    assert _final(simulation).net_pnl_pct == pytest.approx(Decimal(101.5 / 100.0 - 1 - 2 * TRADE_COST))


@pytest.mark.parametrize("side, high, low, close", [
    (TradeType.BUY, [100.0, 100.5, 101.5, 102.0], [100.0, 99.5, 90.0, 100.5], [100.0, 100.0, 101.0, 101.5]),
    (TradeType.SELL, [100.0, 100.5, 110.0, 99.5], [100.0, 99.5, 98.5, 98.0], [100.0, 100.0, 99.0, 98.5]),
])
def test_stop_loss_reports_the_stop_price_as_the_close_price(side, high, low, close):
    simulation = _simulate(side, open_=[100.0, 100.0, 100.0, 100.0], high=high, low=low, close=close)

    expected_exit = 95.0 if side == TradeType.BUY else 105.0
    assert _final(simulation).custom_info["close_price"] == pytest.approx(expected_exit)


def test_close_price_is_the_bar_close_without_a_stop_loss():
    simulation = _simulate(TradeType.BUY, open_=[100.0, 100.0, 100.0, 100.0], high=[100.0, 101.0, 102.0, 103.0],
                           low=[100.0, 99.0, 98.0, 97.0], close=[100.0, 100.5, 101.0, 102.0])

    assert _final(simulation).custom_info["close_price"] == pytest.approx(102.0)
