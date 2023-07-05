from decimal import Decimal

from hummingbot.smart_components.arbitrage_executor.arbitrage_executor import ArbitrageExecutor
from hummingbot.smart_components.arbitrage_executor.data_types import ArbitrageConfig, ExchangePair
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class ArbitrageWithSmartComponent(ScriptStrategyBase):
    exchange_A = "binance_paper_trade"
    exchange_B = "uniswap_polygon_mainnet"
    trading_pair = "USDC-USDT"
    markets = {exchange_A: {trading_pair},
               exchange_B: {trading_pair}}
    order_amount_usd = Decimal("15")
    active_arbitrages = []

    def on_tick(self):
        if len(self.active_arbitrages) < 1:
            self.create_arbitrage_executor()

    def get_arbitrage_config(self):
        price = self.connectors[self.exchange_A].get_mid_price(self.trading_pair)
        arbitrage_config = ArbitrageConfig(
            buying_market=ExchangePair(exchange=self.exchange_A, trading_pair=self.trading_pair),
            selling_market=ExchangePair(exchange=self.exchange_B, trading_pair=self.trading_pair),
            order_amount=self.order_amount_usd / price,
            min_profitability=Decimal("0.005"),
        )
        return arbitrage_config

    def on_stop(self):
        for arbitrage in self.active_arbitrages:
            arbitrage.terminate_control_loop()

    def create_arbitrage_executor(self):
        arbitrage_executor = ArbitrageExecutor(strategy=self,
                                               arbitrage_config=self.get_arbitrage_config())
        self.active_arbitrages.append(arbitrage_executor)
