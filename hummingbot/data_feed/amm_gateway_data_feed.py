import asyncio
import logging
from decimal import Decimal
from typing import Dict, Optional, Set

from pydantic import BaseModel

from hummingbot.connector.gateway.common_types import Chain
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
    chain: str
    network: str
    swap_provider: str
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
        network: str,
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
        self.network = network
        self.trading_pairs = trading_pairs
        self.order_amount_in_base = order_amount_in_base

        # Gateway prices a swap against a network, and that network's config names the
        # swapProvider that quotes it. So the feed is configured with a network, not with
        # a dex: picking the dex is Gateway's job, and doing it here would let the feed
        # quote one venue while the connectors trade another.
        known_chains = tuple(c.chain for c in Chain)
        if not network.startswith(tuple(f"{chain}-" for chain in known_chains)):
            raise ValueError(
                f"Invalid network: {network}. Use Gateway's 'chain-network' format, "
                f"e.g. 'solana-mainnet-beta' or 'ethereum-mainnet' "
                f"(chains: {', '.join(known_chains)})"
            )
        self._chain = network.split("-", 1)[0]
        # Read from the network's config on the first price fetch. The lock is what makes
        # that first read single: every pair's buy and sell leg starts concurrently, so
        # without it they all miss the empty cache and read the config at once.
        self._swap_provider: Optional[str] = None
        self._swap_provider_lock = asyncio.Lock()

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.dex_logger is None:
            cls.dex_logger = logging.getLogger(__name__)
        return cls.dex_logger

    @property
    def name(self) -> str:
        return f"AmmDataFeed[{self.network}]"

    @property
    def chain(self) -> str:
        return self._chain

    @property
    def swap_provider(self) -> str:
        # The dex/trading_type quoting this network, once Gateway has been asked for it.
        return self._swap_provider or ""

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
                    chain=self._chain,
                    network=self.network,
                    swap_provider=self.swap_provider,
                    order_amount_in_base=self.order_amount_in_base,
                    buy_price=buy_price,
                    sell_price=sell_price,
                )
        except Exception as e:
            self.logger().warning(f"Failed to get price for {trading_pair}: {e}")

    async def _resolve_swap_provider(self) -> str:
        """
        The dex/trading_type the network config names as its swapProvider.

        Resolved once and kept: quote_swap resolves it the same way when it is not told
        one, but it does so per call, which would re-read the network config on every
        quote this feed takes.
        """
        async with self._swap_provider_lock:
            if self._swap_provider is None:
                swap_provider = await self.gateway_client.get_default_swap_provider(self.network)
                if not swap_provider:
                    raise ValueError(f"No swap provider configured for network {self.network}")
                if "/" not in swap_provider:
                    raise ValueError(
                        f"Invalid swap provider '{swap_provider}' for network {self.network} "
                        f"- expected 'dex/trading_type'"
                    )
                self._swap_provider = swap_provider
        return self._swap_provider

    async def _request_token_price(self, trading_pair: str, trade_type: TradeType) -> Optional[Decimal]:
        base, quote = split_hb_trading_pair(trading_pair)

        try:
            dex, trading_type = (await self._resolve_swap_provider()).split("/", 1)

            response = await self.gateway_client.quote_swap(
                network=self.network,
                dex=dex,
                trading_type=trading_type,
                base_asset=base,
                quote_asset=quote,
                amount=self.order_amount_in_base,
                side=trade_type,
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
