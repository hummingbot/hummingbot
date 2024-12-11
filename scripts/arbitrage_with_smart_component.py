from decimal import Decimal
from typing import Dict, Optional

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.executors.arbitrage_executor.arbitrage_executor import ArbitrageExecutor
from hummingbot.strategy_v2.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig
from hummingbot.strategy_v2.executors.data_types import ConnectorPair


class ArbitrageConfig(StrategyV2ConfigBase):
    exchange_pair_1: ConnectorPair = ConnectorPair(connector_name="mexc", trading_pair="BAI-USDT")
    exchange_pair_2: ConnectorPair = ConnectorPair(connector_name="uniswap_ethereum_base", trading_pair="BAI-USDC")
    gas_price_conversion: Decimal = Decimal("0.000134513521")
    order_amount: Decimal = Decimal("10")  # in base asset
    min_profitability: Decimal = Decimal("0.01")
    delay_between_executors: int = 10  # in seconds


class ArbitrageWithSmartComponent(StrategyV2Base):
    @classmethod
    def init_markets(cls, config: ArbitrageConfig):
        """
        Initialize the markets that the strategy is going to use. This method is called when the strategy is created in
        the start command. Can be overridden to implement custom behavior.
        """
        markets = {config.exchange_pair_1.connector_name: {config.exchange_pair_1.trading_pair},
                   config.exchange_pair_2.connector_name: {config.exchange_pair_2.trading_pair}}
        controllers_configs = config.load_controller_configs()
        for controller_config in controllers_configs:
            markets = controller_config.update_markets(markets)
        cls.markets = markets

    def __init__(self, connectors: Dict[str, ConnectorBase], config: Optional[ArbitrageConfig] = None):
        super().__init__(connectors, config)
        self.config = config
        self.gateway_client = GatewayHttpClient.get_instance()
        self.active_buy_arbitrages = []
        self.active_sell_arbitrages = []
        self.closed_buy_arbitrages = []
        self.closed_sell_arbitrages = []
        self.failed_buy_arbitrages = []
        self.failed_sell_arbitrages = []
        self.fetch_gateway_prices_task = None

    def on_tick(self):
        if self.fetch_gateway_prices_task is None or self.fetch_gateway_prices_task.done():
            self.fetch_gateway_prices_task = safe_ensure_future(self.update_rate_oracle_custom_prices())
        self.cleanup_arbitrages()
        last_buy, last_sell = self.last_closed_timestamp_arbitrage_by_side()
        if len(self.active_buy_arbitrages) < 1 and last_buy + self.config.delay_between_executors < self.current_timestamp:
            buy_arbitrage_executor = self.create_arbitrage_executor(
                buying_exchange_pair=self.config.exchange_pair_1,
                selling_exchange_pair=self.config.exchange_pair_2,
            )
            if buy_arbitrage_executor:
                self.active_buy_arbitrages.append(buy_arbitrage_executor)
        if len(self.active_sell_arbitrages) < 1 and last_sell + self.config.delay_between_executors < self.current_timestamp:
            sell_arbitrage_executor = self.create_arbitrage_executor(
                buying_exchange_pair=self.config.exchange_pair_2,
                selling_exchange_pair=self.config.exchange_pair_1,
            )
            if sell_arbitrage_executor:
                self.active_sell_arbitrages.append(sell_arbitrage_executor)

    async def update_rate_oracle_custom_prices(self):
        exchange_1_price = self.market_data_provider.get_price_by_type(self.config.exchange_pair_1.connector_name,
                                                                       self.config.exchange_pair_1.trading_pair, TradeType.BUY)
        connector_2, chain_2, network_2 = self.config.exchange_pair_2.connector_name.split("_")
        base_2, quote_2 = self.config.exchange_pair_2.trading_pair.split("-")
        exchange_2_price = await self.gateway_client.get_price(chain=chain_2, network=network_2, connector=connector_2,
                                                               base_asset=base_2, quote_asset=quote_2,
                                                               amount=self.config.order_amount, side=TradeType.BUY)
        rate_oracle = RateOracle.get_instance()
        rate_oracle.set_price(self.config.exchange_pair_1.trading_pair, exchange_1_price)
        rate_oracle.set_price(self.config.exchange_pair_2.trading_pair, exchange_2_price)

    async def on_stop(self):
        for arbitrage in self.active_buy_arbitrages:
            arbitrage.stop()
        for arbitrage in self.active_sell_arbitrages:
            arbitrage.stop()

    def last_closed_timestamp_arbitrage_by_side(self):
        last_buy = max([arbitrage.close_timestamp for arbitrage in self.closed_buy_arbitrages
                        if arbitrage.config.buying_market == self.config.exchange_pair_1]) if len(
            self.closed_buy_arbitrages) > 0 else 0
        last_sell = max([arbitrage.close_timestamp for arbitrage in self.closed_sell_arbitrages
                         if arbitrage.config.buying_market == self.config.exchange_pair_2]) if len(
            self.closed_sell_arbitrages) > 0 else 0
        return last_buy, last_sell

    def create_arbitrage_executor(self, buying_exchange_pair: ConnectorPair, selling_exchange_pair: ConnectorPair):
        try:
            arbitrage_config = ArbitrageExecutorConfig(
                timestamp=self.current_timestamp,
                buying_market=buying_exchange_pair,
                selling_market=selling_exchange_pair,
                order_amount=self.config.order_amount,
                min_profitability=self.config.min_profitability,
                gas_conversion_price=self.config.gas_price_conversion,
            )
            arbitrage_executor = ArbitrageExecutor(strategy=self,
                                                   config=arbitrage_config)
            arbitrage_executor.start()
            return arbitrage_executor
        except Exception:
            self.logger().error(
                f"Error creating executor to buy on {buying_exchange_pair.connector_name} and sell on {selling_exchange_pair.connector_name}")

    def format_status(self) -> str:
        status = []
        status.extend([f"Closed buy arbitrages: {len(self.closed_buy_arbitrages)}"])
        status.extend([f"Closed sell arbitrages: {len(self.closed_sell_arbitrages)}"])
        status.extend([f"Failed buy arbitrages: {len(self.failed_buy_arbitrages)}"])
        status.extend([f"Failed sell arbitrages: {len(self.failed_sell_arbitrages)}"])
        status.extend([f"Active Arbitrages: {len(self.active_sell_arbitrages) + len(self.active_buy_arbitrages)}"])
        for arbitrage in self.active_sell_arbitrages:
            status.extend(arbitrage.to_format_status())
        for arbitrage in self.active_buy_arbitrages:
            status.extend(arbitrage.to_format_status())
        return "\n".join(status)

    def cleanup_arbitrages(self):
        for arbitrage in self.active_buy_arbitrages:
            if arbitrage.is_closed:
                self.closed_buy_arbitrages.append(arbitrage)
                self.active_buy_arbitrages.remove(arbitrage)
        for arbitrage in self.active_sell_arbitrages:
            if arbitrage.is_closed:
                self.closed_sell_arbitrages.append(arbitrage)
                self.active_sell_arbitrages.remove(arbitrage)
