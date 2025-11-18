from decimal import Decimal

from services.indicators import IndicatorState


def test_indicator_state_updates():
    state = IndicatorState(fast_period=2, slow_period=4, atr_period=3)
    state.update(high=Decimal("11"), low=Decimal("9"), close=Decimal("10"), timestamp=1)
    snapshot = state.snapshot()
    assert snapshot is not None
    assert snapshot["ema_fast"] == 10.0
    assert snapshot["ema_slow"] == 10.0

    state.update(high=Decimal("12"), low=Decimal("10"), close=Decimal("11"), timestamp=2)
    snapshot = state.snapshot()
    assert snapshot is not None
    assert snapshot["ema_fast"] > 10
    assert snapshot["atr"] > 0
