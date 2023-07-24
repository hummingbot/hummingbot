from decimal import Decimal

from hummingbot.smart_components.arbitrage_executor.arbitrage_executor import ArbitrageExecutor
from hummingbot.smart_components.arbitrage_executor.data_types import ArbitrageConfig, ExchangePair
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class ArbitrageWithSmartComponent(ScriptStrategyBase):
    # Parameters
    exchange_pair_1 = ExchangePair(exchange="kucoin", trading_pair="MATIC-USDT")
    exchange_pair_2 = ExchangePair(exchange="uniswap_polygon_mainnet", trading_pair="WMATIC-USDT")
    order_amount = Decimal("10")  # in base asset
    min_profitability = Decimal("0.004")

    markets = {exchange_pair_1.exchange: {exchange_pair_1.trading_pair},
               exchange_pair_2.exchange: {exchange_pair_2.trading_pair}}
    active_buy_arbitrages = []
    active_sell_arbitrages = []

    def on_tick(self):
        if len(self.active_buy_arbitrages) < 1:
            buy_arbitrage_executor = self.create_arbitrage_executor(
                buying_exchange_pair=self.exchange_pair_1,
                selling_exchange_pair=self.exchange_pair_2,
            )
            if buy_arbitrage_executor:
                self.active_buy_arbitrages.append(buy_arbitrage_executor)
        if len(self.active_sell_arbitrages) < 1:
            sell_arbitrage_executor = self.create_arbitrage_executor(
                buying_exchange_pair=self.exchange_pair_2,
                selling_exchange_pair=self.exchange_pair_1,
            )
            if sell_arbitrage_executor:
                self.active_sell_arbitrages.append(sell_arbitrage_executor)

    def on_stop(self):
        for arbitrage in self.active_buy_arbitrages:
            arbitrage.terminate_control_loop()
        for arbitrage in self.active_sell_arbitrages:
            arbitrage.terminate_control_loop()

    def create_arbitrage_executor(self, buying_exchange_pair: ExchangePair, selling_exchange_pair: ExchangePair):
        try:
            base_asset_for_selling_exchange = self.connectors[selling_exchange_pair.exchange].get_available_balance(
                selling_exchange_pair.trading_pair.split("-")[0])
            if self.order_amount > base_asset_for_selling_exchange:
                self.logger().info(f"Insufficient balance in exchange {selling_exchange_pair.exchange}"
                                   f"for sell {selling_exchange_pair.trading_pair.split('-')[0]} Actual: {base_asset_for_selling_exchange}")
                return

            quote_asset_for_buying_exchange = self.connectors[buying_exchange_pair.exchange].get_available_balance(
                buying_exchange_pair.trading_pair.split("-")[1])
            if self.order_amount > quote_asset_for_buying_exchange:
                self.logger().info(f"Insufficient balance in exchange {buying_exchange_pair.exchange} "
                                   f"for buy {buying_exchange_pair.trading_pair.split('-')[1]} Actual: {quote_asset_for_buying_exchange}")
                return

            arbitrage_config = ArbitrageConfig(
                buying_market=buying_exchange_pair,
                selling_market=selling_exchange_pair,
                order_amount=self.order_amount,
                min_profitability=self.min_profitability,
            )
            arbitrage_executor = ArbitrageExecutor(strategy=self,
                                                   arbitrage_config=arbitrage_config)
            return arbitrage_executor
        except Exception:
            self.logger().error(f"Error creating executor to buy on {buying_exchange_pair.exchange} and sell on {selling_exchange_pair.exchange}")

    def format_status(self) -> str:
        status = []
        status.extend([f"Active Arbitrages: {len(self.active_sell_arbitrages) + len(self.active_buy_arbitrages)}"])
        for arbitrage in self.active_sell_arbitrages:
            status.extend(arbitrage.to_format_status())
        for arbitrage in self.active_buy_arbitrages:
            status.extend(arbitrage.to_format_status())
        return "\n".join(status)
