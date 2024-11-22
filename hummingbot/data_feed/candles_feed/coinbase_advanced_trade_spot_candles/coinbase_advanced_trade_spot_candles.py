import asyncio
import logging
from collections import deque
from typing import Dict, List, Optional

import hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils as web_utils
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_constants import (
    DEFAULT_DOMAIN,
    REST_URL,
    SERVER_TIME_EP,
    WSS_URL,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_exchange import (
    CoinbaseExchangeThrottler,
)
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles import constants as CONSTANTS
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.candle_data import CandleData
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.mixin_rest_operations import (
    MixinRestOperations,
)
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.mixin_ws_operations import MixinWSOperations
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.utils import update_deque_from_sequence
from hummingbot.logger import HummingbotLogger


class CoinbaseAdvancedTradeSpotCandles(
    MixinRestOperations,
    MixinWSOperations,
    CandlesBase,
):
    """Class for managing Coinbase Advanced Trade candle data.

    Handles fetching and processing of candle data from Coinbase Advanced Trade,
    supporting both REST and WebSocket connections.

    :param trading_pair: The trading pair to track (e.g. "BTC-USD")
    :param interval: Candle interval (e.g. "1m", "5m")
    :param max_records: Maximum number of candles to store
    """
    _logger: Optional[HummingbotLogger] = None
    web_utils = web_utils

    def __init__(
            self,
            trading_pair: str,
            interval: str = "1m",
            max_records: int = 150,
    ):
        super().__init__(trading_pair, interval, max_records)
        self._api_factory = WebAssistantsFactory(throttler=CoinbaseExchangeThrottler)

    @classmethod
    def logger(cls) -> HummingbotLogger | logging.Logger:
        """Get the logger for this class.

        :returns: Logger instance
        :rtype: HummingbotLogger
        """
        if cls._logger is None:
            cls._logger: HummingbotLogger | logging.Logger = logging.getLogger(__name__)
        return cls._logger

    @property
    def name(self) -> str:
        """Name of the exchange with candle pair tracked."""
        return f"coinbase_advanced_trade_{self._trading_pair}"

    @property
    def rest_url(self) -> str:
        """REST URL for the exchange."""
        return REST_URL.format(domain=DEFAULT_DOMAIN)

    @property
    def wss_url(self) -> str:
        """Websocket URL for the exchange."""
        return WSS_URL.format(domain=DEFAULT_DOMAIN)

    @property
    def candles_url(self) -> str:
        """Candles URL for the exchange."""
        return self.rest_url + CONSTANTS.CANDLES_ENDPOINT.format(product_id=self._ex_trading_pair)

    @property
    def health_check_url(self) -> str:
        """Candles URL for the exchange."""
        # This is correct: the SERVER_TIME_EP is not authenticated, but use the 'private' v3 URL
        # Changelog of Coinbase on Feb22nd 24
        return web_utils.private_rest_url(path_url=SERVER_TIME_EP)

    @property
    def candles_deque(self) -> deque:
        """Candles deque for the exchange."""
        return super()._candles

    @property
    def rate_limits(self) -> List[RateLimit]:
        """Rate limits for the exchange."""
        return []

    @property
    def intervals(self) -> Dict[str, int]:
        """Intervals supported by the exchange."""
        return CONSTANTS.INTERVALS

    @property
    def candles_endpoint(self):
        self.logger().debug(f"Getting candles endpoint for {self._ex_trading_pair}")
        raise CONSTANTS.CANDLES_ENDPOINT.format(product_id=self._ex_trading_pair)

    @property
    def _rest_throttler_limit_id(self):
        self.logger().debug(f"Getting rest throttler limit id for {CONSTANTS.CANDLES_ENDPOINT_ID}")
        return CONSTANTS.CANDLES_ENDPOINT_ID

    @property
    def candles_max_result_per_rest_request(self):
        return CONSTANTS.MAX_CANDLES_SIZE

    async def check_network(self) -> NetworkStatus:
        """Verifies the exchange status."""
        self.logger().debug("Checking network...")
        rest_assistant = await self._api_factory.get_rest_assistant()
        try:
            result = await rest_assistant.execute_request(
                url=web_utils.public_rest_url(path_url=SERVER_TIME_EP),
                throttler_limit_id=SERVER_TIME_EP,
            )
            if result is not None:
                return NetworkStatus.CONNECTED
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred when checking network status...")

        return NetworkStatus.NOT_CONNECTED

    def get_exchange_trading_pair(self, trading_pair) -> str:
        """Returns the trading pair in the format required by the exchange."""
        return trading_pair.replace("-", "-")

    async def listen_for_subscriptions(self):
        """
        Connects to the candlestick websocket endpoint and listens to the messages sent by the
        exchange.
        """
        if self.interval in CONSTANTS.WS_INTERVALS:
            await self._catsc_listen_for_websocket()
        else:
            await self._catsc_listen_to_fetch()

    async def _update_deque_set_historical(
            self,
            candles: tuple[CandleData, ...],
            *,
            extend_left: bool = False,
    ):
        call_history = len(self._candles) == 0
        update_deque_from_sequence(self._candles, candles, extend_left=extend_left)
        if call_history:
            self._ws_candle_available.set()
            await self._catsc_fill_historical_candles(self._ws_candle_available)

    def _get_first_candle_timestamp(self) -> int | None:
        return self._candles[0][0] if len(self._candles) > 0 else None

    def _get_last_candle_timestamp(self) -> int | None:
        return self._candles[-1][0] if len(self._candles) > 0 else None

    def _get_missing_timestamps(self) -> int:
        return self._candles.maxlen - len(self._candles)

    async def fill_historical_candles(self):
        return NotImplementedError

    async def _process_websocket_messages_task(self, websocket_assistant: WSAssistant):
        return NotImplementedError

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None):
        return NotImplementedError
