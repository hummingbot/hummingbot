import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple, TypedDict

from pydantic import BaseModel

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.network_base import NetworkBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.script_strategy_base import Decimal, ScriptStrategyBase


class TokenPrice(BaseModel):
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


class TokenBuySellPrice(BaseModel):
    base: str
    quote: str
    connector: str
    chain: str
    network: str
    buy: TokenPrice
    sell: TokenPrice


class DexDataFeed(NetworkBase):
    dex_logger: Optional[HummingbotLogger] = None
    gateway_client = GatewayHttpClient.get_instance()

    def __init__(
        self,
        connector_chain_network: str,
        trading_pairs: Set[str],
        order_amount: Decimal,
        update_interval: float,
    ) -> None:
        super().__init__()
        self._ev_loop = asyncio.get_event_loop()
        self._price_dict: Dict[str, TokenBuySellPrice] = {}
        self._update_interval = update_interval
        self.fetch_data_loop_task: Optional[asyncio.Task] = None
        # param required for DEX API request
        self.connector_chain_network = connector_chain_network
        self.trading_pairs = trading_pairs
        self.order_amount = order_amount

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.dex_logger is None:
            cls.dex_logger = logging.getLogger(__name__)
        return cls.dex_logger

    @property
    def name(self) -> str:
        return f"DexDataFeed[{self.connector_chain_network}]"

    @property
    def connector(self) -> str:
        return self.connector_chain_network.split("_")[0]

    @property
    def chain(self) -> str:
        return self.connector_chain_network.split("_")[1]

    @property
    def network(self) -> str:
        return self.connector_chain_network.split("_")[2]

    async def check_network(self) -> NetworkStatus:
        is_gateway_online = await self.gateway_client.ping_gateway()
        return NetworkStatus.CONNECTED if is_gateway_online else NetworkStatus.NOT_CONNECTED

    async def start_network(self) -> None:
        await self.stop_network()
        self.fetch_data_loop_task = safe_ensure_future(self._fetch_data_loop())

    async def stop_network(self) -> None:
        if self.fetch_data_loop_task is not None:
            self.fetch_data_loop_task.cancel()
            self.fetch_data_loop_task = None

    def get_price_dict(self) -> Dict[str, List[dict]]:
        return self._price_dict

    async def _fetch_data_loop(self) -> None:
        while True:
            try:
                await self._fetch_data()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(
                    f"Error getting data from {self.name}",
                    exc_info=True,
                    app_warning_msg=f"Couldn't fetch newest prices from {self.name}. "
                    f"Check network connection. Error: {e}",
                )
            await self._async_sleep(self._update_interval)

    async def _fetch_data(self) -> None:
        await self._update_price_dict()

    async def _update_price_dict(self) -> None:
        token_price_tasks = [
            asyncio.create_task(self._register_token_buy_sell_price(trading_pair))
            for trading_pair in self.trading_pairs
        ]
        await asyncio.gather(*token_price_tasks)

    async def _register_token_buy_sell_price(self, trading_pair: str) -> None:
        base, quote = split_base_quote(trading_pair)
        token_buy_price_task = asyncio.create_task(self._request_token_price(trading_pair, TradeType.BUY))
        token_sell_price_task = asyncio.create_task(self._request_token_price(trading_pair, TradeType.SELL))
        self._price_dict[trading_pair] = TokenBuySellPrice(
            base=base,
            quote=quote,
            connector=self.connector,
            chain=self.chain,
            network=self.network,
            buy=await token_buy_price_task,
            sell=await token_sell_price_task,
        )

    async def _request_token_price(self, trading_pair: str, trade_type: TradeType) -> TokenPrice:
        base, quote = split_base_quote(trading_pair)
        connector, chain, network = self.connector_chain_network.split("_")
        token_price = await self.gateway_client.get_price(
            chain, network, connector, base, quote, self.order_amount, trade_type
        )
        return TokenPrice(**token_price)

    @staticmethod
    async def _async_sleep(delay: float) -> None:
        """Used to mock in test cases."""
        await asyncio.sleep(delay)


class CrossDexArb(ScriptStrategyBase):
    # define markets
    connector_chain_network_a = "pancakeswap_binance-smart-chain_mainnet"
    connector_chain_network_b = "sushiswap_binance-smart-chain_mainnet"
    trading_pairs = {"USDT-USDC"}
    markets = {
        connector_chain_network_a: trading_pairs,
        connector_chain_network_b: trading_pairs,
    }

    # set up data feed for 2 DEXs
    update_interval = 0.0
    order_amount: Decimal = Decimal("20")
    dex_data_feed_a = DexDataFeed(connector_chain_network_a, trading_pairs, order_amount, update_interval)
    dex_data_feed_b = DexDataFeed(connector_chain_network_b, trading_pairs, order_amount, update_interval)

    # for execute trade
    gateway_client = GatewayHttpClient.get_instance()

    def __init__(self, connectors: Dict[str, ConnectorBase]) -> None:
        # Is necessary to start the Candles Feed.
        super().__init__(connectors)
        self.dex_data_feed_a.start()
        self.dex_data_feed_b.start()
        self.logger().info(f"{self.dex_data_feed_a.name} and {self.dex_data_feed_b.name} started...")

    def on_stop(self) -> None:
        """
        Without this functionality, the network iterator will continue running forever after stopping the strategy
        That's why is necessary to introduce this new feature to make a custom stop with the strategy.
        """
        self.dex_data_feed_a.stop()
        self.dex_data_feed_b.stop()
        self.logger().info(f"{self.dex_data_feed_a.name} and {self.dex_data_feed_b.name} ended...")

    def on_tick(self) -> None:
        price_dict_a = self.dex_data_feed_a.get_price_dict()
        price_dict_b = self.dex_data_feed_b.get_price_dict()
        self.logger().info(f"price_dict_a: {price_dict_a}")
        self.logger().info(f"price_dict_b: {price_dict_b}")


def split_base_quote(trading_pair: str) -> Tuple[str, str]:
    base, quote = trading_pair.split("-")
    return base, quote
