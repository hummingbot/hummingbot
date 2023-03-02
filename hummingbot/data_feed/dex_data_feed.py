import asyncio
import logging
from typing import Dict, List, Optional, Set

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.script_strategy_base import Decimal


class DexDataFeed(DataFeedBase):
    dex_logger: Optional[HummingbotLogger] = None
    _dex_shared_instance: "DexDataFeed" = None

    def __init__(
        self,
        connector_chain_network: str,
        trading_pairs: Set[str],
        order_amount: Decimal,
        update_interval: float,
    ) -> None:
        super().__init__()
        self._ev_loop = asyncio.get_event_loop()
        self._price_dict: Dict[str, List[dict]] = {}
        self._update_interval = update_interval
        self.fetch_data_loop_task: Optional[asyncio.Task] = None
        # param required for DEX API request
        self.connector_chain_network = connector_chain_network
        self.trading_pairs = trading_pairs
        self.order_amount = order_amount

    @classmethod
    def get_instance(cls) -> "DexDataFeed":
        if cls._dex_shared_instance is None:
            cls._dex_shared_instance = DexDataFeed()
        return cls._dex_shared_instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.dex_logger is None:
            cls.dex_logger = logging.getLogger(__name__)
        return cls.dex_logger

    @property
    def name(self) -> str:
        return "DexDataFeed"

    @property
    def markets(self) -> Dict[str, Set]:
        return self._markets

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
            except Exception:
                self.logger().network(
                    f"Error getting data from {self.name}",
                    exc_info=True,
                    app_warning_msg="Couldn't fetch newest prices from DexDataFeed. "
                    "Check network connection.",
                )
            await self._async_sleep(self._update_interval)

    async def _fetch_data(self) -> None:
        await self._update_price_dict()
        self._ready_event.set()

    async def _update_price_dict(self) -> None:
        tasks = []
        for trading_pair in self.trading_pairs:
            self.logger().info(f"Appending task for {trading_pair}")
            tasks.append(
                asyncio.create_task(
                    self._request_token_price(trading_pair, TradeType.BUY)
                )
            )
            tasks.append(
                asyncio.create_task(
                    self._request_token_price(trading_pair, TradeType.SELL)
                )
            )
        responses = await asyncio.gather(*tasks)
        self._price_dict = responses

    async def _request_token_price(
        self, trading_pair: str, trade_type: TradeType
    ) -> dict:
        base, quote = trading_pair.split("-")
        connector, chain, network = self.connector_chain_network.split("_")
        return await GatewayHttpClient.get_instance().get_price(
            chain, network, connector, base, quote, self.order_amount, trade_type
        )

    @staticmethod
    async def _async_sleep(delay: float) -> None:
        """Used to mock in test cases."""
        await asyncio.sleep(delay)
