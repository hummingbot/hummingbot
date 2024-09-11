from decimal import Decimal

from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.arbitrage_executor.arbitrage_executor import ArbitrageExecutor
from hummingbot.strategy_v2.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig
from hummingbot.strategy_v2.executors.data_types import ConnectorPair


class ArbitrageWithSmartComponent(ScriptStrategyBase):
    # Parameters
    exchange_pair_1 = ConnectorPair(connector_name="binance", trading_pair="MATIC-USDT")
    exchange_pair_2 = ConnectorPair(connector_name="uniswap_polygon_mainnet", trading_pair="WMATIC-USDT")
    order_amount = Decimal("50")  # in base asset
    min_profitability = Decimal("0.004")

    markets = {exchange_pair_1.connector_name: {exchange_pair_1.trading_pair},
               exchange_pair_2.connector_name: {exchange_pair_2.trading_pair}}
    active_buy_arbitrages = []
    active_sell_arbitrages = []
    closed_arbitrage_executors = []

    def on_tick(self):
        self.cleanup_arbitrages()
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

    async def on_stop(self):
        for arbitrage in self.active_buy_arbitrages:
            arbitrage.stop()
        for arbitrage in self.active_sell_arbitrages:
            arbitrage.stop()

    def create_arbitrage_executor(self, buying_exchange_pair: ConnectorPair, selling_exchange_pair: ConnectorPair):
        try:
            base_asset_for_selling_exchange = self.connectors[selling_exchange_pair.connector_name].get_available_balance(
                selling_exchange_pair.trading_pair.split("-")[0])
            if self.order_amount > base_asset_for_selling_exchange:
                self.logger().info(f"Insufficient balance in exchange {selling_exchange_pair.connector_name} "
                                   f"to sell {selling_exchange_pair.trading_pair.split('-')[0]} "
                                   f"Actual: {base_asset_for_selling_exchange} --> Needed: {self.order_amount}")
                return

            # Harcoded for now since we don't have a price oracle for WMATIC (CoinMarketCap rate source is requested and coming)
            pair_conversion = selling_exchange_pair.trading_pair.replace("W", "")
            price = RateOracle.get_instance().get_pair_rate(pair_conversion)
            quote_asset_for_buying_exchange = self.connectors[buying_exchange_pair.connector_name].get_available_balance(
                buying_exchange_pair.trading_pair.split("-")[1])
            if self.order_amount * price > quote_asset_for_buying_exchange:
                self.logger().info(f"Insufficient balance in exchange {buying_exchange_pair.connector_name} "
                                   f"to buy {buying_exchange_pair.trading_pair.split('-')[1]} "
                                   f"Actual: {quote_asset_for_buying_exchange} --> Needed: {self.order_amount * price}")
                return

            arbitrage_config = ArbitrageExecutorConfig(
                buying_market=buying_exchange_pair,
                selling_market=selling_exchange_pair,
                order_amount=self.order_amount,
                min_profitability=self.min_profitability,
            )
            arbitrage_executor = ArbitrageExecutor(strategy=self,
                                                   config=arbitrage_config)
            arbitrage_executor.start()
            return arbitrage_executor
        except Exception:
            self.logger().error(f"Error creating executor to buy on {buying_exchange_pair.connector_name} and sell on {selling_exchange_pair.connector_name}")

    def format_status(self) -> str:
        status = []
        status.extend([f"Closed Arbtriages: {len(self.closed_arbitrage_executors)}"])
        for arbitrage in self.closed_arbitrage_executors:
            status.extend(arbitrage.to_format_status())
        status.extend([f"Active Arbitrages: {len(self.active_sell_arbitrages) + len(self.active_buy_arbitrages)}"])
        for arbitrage in self.active_sell_arbitrages:
            status.extend(arbitrage.to_format_status())
        for arbitrage in self.active_buy_arbitrages:
            status.extend(arbitrage.to_format_status())
        return "\n".join(status)

    def cleanup_arbitrages(self):
        for arbitrage in self.active_buy_arbitrages:
            if arbitrage.is_closed:
                self.closed_arbitrage_executors.append(arbitrage)
                self.active_buy_arbitrages.remove(arbitrage)
        for arbitrage in self.active_sell_arbitrages:
            if arbitrage.is_closed:
                self.closed_arbitrage_executors.append(arbitrage)
                self.active_sell_arbitrages.remove(arbitrage)
