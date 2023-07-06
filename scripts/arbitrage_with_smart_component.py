from decimal import Decimal

from hummingbot.core.data_type.common import OrderType
from hummingbot.smart_components.arbitrage_executor.arbitrage_executor import ArbitrageExecutor
from hummingbot.smart_components.arbitrage_executor.data_types import ArbitrageConfig, ExchangePair
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class ArbitrageWithSmartComponent(ScriptStrategyBase):
    exchange_A = "binance_paper_trade"
    exchange_B = "uniswap_polygon_mainnet"
    trading_pair = "USDC-USDT"
    markets = {exchange_A: {trading_pair},
               exchange_B: {trading_pair}}
    order_amount_usd = Decimal("12")
    active_arbitrages = []
    buy_order_id = None

    def on_tick(self):
        if len(self.active_arbitrages) < 1:
            self.create_arbitrage_executor()
        order_id = self.connectors[self.exchange_B].sell(
            trading_pair=self.trading_pair,
            amount=self.order_amount_usd,
            order_type=OrderType.MARKET,
            price=Decimal("0.99")
        )
        self.buy_order_id = order_id

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

    def format_status(self) -> str:
        status = []
        status.extend([f"Active Arbitrages: {len(self.active_arbitrages)}"])
        for arbitrage in self.active_arbitrages:
            status.extend(arbitrage.to_format_status())
        return "\n".join(status)
