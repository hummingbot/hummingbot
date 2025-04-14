import asyncio
import logging
from decimal import Decimal
from typing import Dict, Optional, Set

from pydantic import BaseModel

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.network_base import NetworkBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class TokenBuySellPrice(BaseModel):
    base: str
    quote: str
    connector: str
    chain: str
    network: str
    order_amount_in_base: Decimal
    buy_price: Decimal
    sell_price: Decimal


class AmmGatewayDataFeed(NetworkBase):
    dex_logger: Optional[HummingbotLogger] = None
    gateway_client = GatewayHttpClient.get_instance()

    def __init__(
        self,
        connector_chain_network: str,
        trading_pairs: Set[str],
        order_amount_in_base: Decimal,
        update_interval: float = 1.0,
    ) -> None:
        super().__init__()
        self._ev_loop = asyncio.get_event_loop()
        self._price_dict: Dict[str, TokenBuySellPrice] = {}
        self._update_interval = update_interval
        self.fetch_data_loop_task: Optional[asyncio.Task] = None
        # param required for DEX API request
        self.connector_chain_network = connector_chain_network
        self.trading_pairs = trading_pairs
        self.order_amount_in_base = order_amount_in_base

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.dex_logger is None:
            cls.dex_logger = logging.getLogger(__name__)
        return cls.dex_logger

    @property
    def name(self) -> str:
        return f"AmmDataFeed[{self.connector_chain_network}]"

    @property
    def connector(self) -> str:
        return self.connector_chain_network.split("_")[0]

    @property
    def chain(self) -> str:
        return self.connector_chain_network.split("_")[1]

    @property
    def network(self) -> str:
        return self.connector_chain_network.split("_")[2]

    @property
    def price_dict(self) -> Dict[str, TokenBuySellPrice]:
        return self._price_dict

    def is_ready(self) -> bool:
        return len(self._price_dict) == len(self.trading_pairs)

    async def check_network(self) -> NetworkStatus:
        is_gateway_online = await self.gateway_client.ping_gateway()
        if not is_gateway_online:
            self.logger().warning("Gateway is not online. Please check your gateway connection.")
        return NetworkStatus.CONNECTED if is_gateway_online else NetworkStatus.NOT_CONNECTED

    async def start_network(self) -> None:
        await self.stop_network()
        self.fetch_data_loop_task = safe_ensure_future(self._fetch_data_loop())

    async def stop_network(self) -> None:
        if self.fetch_data_loop_task is not None:
            self.fetch_data_loop_task.cancel()
            self.fetch_data_loop_task = None

    async def _fetch_data_loop(self) -> None:
        while True:
            try:
                await self._fetch_data()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Error getting data from {self.name}"
                    f"Check network connection. Error: {e}",
                )
            await self._async_sleep(self._update_interval)

    async def _fetch_data(self) -> None:
        token_price_tasks = [
            asyncio.create_task(self._register_token_buy_sell_price(trading_pair))
            for trading_pair in self.trading_pairs
        ]
        await asyncio.gather(*token_price_tasks)

    async def _register_token_buy_sell_price(self, trading_pair: str) -> None:
        base, quote = split_hb_trading_pair(trading_pair)
        token_buy_price_task = asyncio.create_task(self._request_token_price(trading_pair, TradeType.BUY))
        token_sell_price_task = asyncio.create_task(self._request_token_price(trading_pair, TradeType.SELL))
        self._price_dict[trading_pair] = TokenBuySellPrice(
            base=base,
            quote=quote,
            connector=self.connector,
            chain=self.chain,
            network=self.network,
            order_amount_in_base=self.order_amount_in_base,
            buy_price=await token_buy_price_task,
            sell_price=await token_sell_price_task,
        )

    async def _request_token_price(self, trading_pair: str, trade_type: TradeType) -> Decimal:
        base, quote = split_hb_trading_pair(trading_pair)
        connector, chain, network = self.connector_chain_network.split("_")
        token_price = await self.gateway_client.get_price(
            chain,
            network,
            connector,
            base,
            quote,
            self.order_amount_in_base,
            trade_type,
        )
        return Decimal(token_price["price"])

    @staticmethod
    async def _async_sleep(delay: float) -> None:
        """Used to mock in test cases."""
        await asyncio.sleep(delay)
