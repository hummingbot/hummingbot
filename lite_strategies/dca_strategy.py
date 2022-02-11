import time
from hummingbot.strategy.lite_strategy_base import LiteStrategyBase, Decimal, OrderType


class DCAStrategy(LiteStrategyBase):
    markets = {"binance_paper_trade": {"BTC-USDT"}}
    last_ordered_ts = 0.
    buy_interval = 60. * 24

    async def on_tick(self):
        if self.last_ordered_ts < time.time() - self.buy_interval:
            price = self.connectors["binance_paper_trade"].get_price("BTC-USDT", False) * Decimal("0.9")
            self.buy("binance_paper_trade", "BTC-USDT", Decimal("100") / price, OrderType.LIMIT, price)
            self.last_ordered_ts = time.time()
