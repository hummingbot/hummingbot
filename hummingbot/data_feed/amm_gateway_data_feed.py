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
    _gateway_client: Optional[GatewayHttpClient] = None

    @classmethod
    def get_gateway_client(cls) -> GatewayHttpClient:
        """Class method for lazy initialization of gateway client to avoid duplicate initialization during import"""
        if cls._gateway_client is None:
            cls._gateway_client = GatewayHttpClient.get_instance()
        return cls._gateway_client

    @property
    def gateway_client(self) -> GatewayHttpClient:
        """Instance property to access the gateway client"""
        return self.get_gateway_client()

    def __init__(
        self,
        connector: str,
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
        self.connector = connector
        self.trading_pairs = trading_pairs
        self.order_amount_in_base = order_amount_in_base

        # New format: connector/type (e.g., jupiter/router)
        if "/" not in connector:
            raise ValueError(f"Invalid connector format: {connector}. Use format like 'jupiter/router' or 'uniswap/amm'")
        self._connector_name = connector
        # We'll get chain and network from gateway during price fetching
        self._chain = None
        self._network = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.dex_logger is None:
            cls.dex_logger = logging.getLogger(__name__)
        return cls.dex_logger

    @property
    def name(self) -> str:
        return f"AmmDataFeed[{self.connector}]"

    @property
    def chain(self) -> str:
        # Chain is determined from gateway
        return self._chain or ""

    @property
    def network(self) -> str:
        # Network is determined from gateway
        return self._network or ""

    @property
    def price_dict(self) -> Dict[str, TokenBuySellPrice]:
        return self._price_dict

    def is_ready(self) -> bool:
        return len(self._price_dict) > 0

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
        await asyncio.gather(*token_price_tasks, return_exceptions=True)

    async def _register_token_buy_sell_price(self, trading_pair: str) -> None:
        try:
            base, quote = split_hb_trading_pair(trading_pair)
            token_buy_price_task = asyncio.create_task(self._request_token_price(trading_pair, TradeType.BUY))
            token_sell_price_task = asyncio.create_task(self._request_token_price(trading_pair, TradeType.SELL))
            buy_price = await token_buy_price_task
            sell_price = await token_sell_price_task

            if buy_price is not None and sell_price is not None:
                self._price_dict[trading_pair] = TokenBuySellPrice(
                    base=base,
                    quote=quote,
                    connector=self.connector,
                    chain=self._chain or "",
                    network=self._network or "",
                    order_amount_in_base=self.order_amount_in_base,
                    buy_price=buy_price,
                    sell_price=sell_price,
                )
        except Exception as e:
            self.logger().warning(f"Failed to get price for {trading_pair}: {e}")

    async def _request_token_price(self, trading_pair: str, trade_type: TradeType) -> Optional[Decimal]:
        base, quote = split_hb_trading_pair(trading_pair)

        # Use gateway's quote_swap which handles chain/network internally
        try:

            # Get chain and network from connector if not cached
            if not self._chain or not self._network:
                chain, network, error = await self.gateway_client.get_connector_chain_network(
                    self.connector
                )
                if not error:
                    self._chain = chain
                    self._network = network
                else:
                    self.logger().warning(f"Failed to get chain/network for {self.connector}: {error}")
                    return None

            # Use quote_swap which accepts the full connector name
            response = await self.gateway_client.quote_swap(
                network=self._network,
                connector=self.connector,
                base_asset=base,
                quote_asset=quote,
                amount=self.order_amount_in_base,
                side=trade_type,
                slippage_pct=None,
                pool_address=None
            )

            if response and "price" in response:
                return Decimal(str(response["price"]))
            return None
        except Exception as e:
            self.logger().warning(f"Failed to get price using quote_swap: {e}")
            return None

    @staticmethod
    async def _async_sleep(delay: float) -> None:
        """Used to mock in test cases."""
        await asyncio.sleep(delay)
