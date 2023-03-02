from typing import Dict

from pydantic import BaseModel

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.data_feed.dex_data_feed import DexDataFeed
from hummingbot.strategy.script_strategy_base import Decimal, ScriptStrategyBase


class DexResponse(BaseModel):
    network: str
    timestamp: int
    latency: float
    base: str
    quote: str
    amount: str
    rawAmount: str
    expectedAmount: str
    price: str
    gasPrice: int
    gasPriceToken: str
    gasLimit: int
    gasCost: str


class CrossDexArb(ScriptStrategyBase):
    connector_chain_network = "pancakeswap_binance-smart-chain_mainnet"
    trading_pairs = {"USDT-MATIC", "USDT-USDC"}
    markets = {connector_chain_network: trading_pairs}
    update_interval: float = 60.0
    order_amount: Decimal = Decimal("20")
    data_feed = DexDataFeed(
        connector_chain_network, trading_pairs, order_amount, update_interval
    )

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        # Is necessary to start the Candles Feed.
        super().__init__(connectors)
        self.data_feed.start()
        self.logger().info("DexDataFeed and CrossDexArb started...")

    def on_tick(self) -> None:
        # price_dict = self.data_feed.get_price_dict()
        # self.logger().info(f"price_dict: {price_dict}")
        price_dict = self.data_feed.get_price_dict()
        self.logger().info(f"price_dict: {price_dict}")

    async def async_task(self):
        base, quote = "USDT-MATIC".split("-")
        connector, chain, network = self.connector_chain_network.split("_")
        data = await GatewayHttpClient.get_instance().get_price(
            chain, network, connector, base, quote, self.order_amount, TradeType.BUY
        )
        self.logger().info(f"price: {data} (async)")

    def on_stop(self) -> None:
        """
        Without this functionality, the network iterator will continue running forever after stopping the strategy
        That's why is necessary to introduce this new feature to make a custom stop with the strategy.
        """
        self.data_feed.stop()
        self.logger().info("DexDataFeed and CrossDexArb ended...")
