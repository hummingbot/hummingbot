import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.decibel_perpetual_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    pass


class DecibelPerpetualCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
        self,
        trading_pair: str,
        interval: str = "1m",
        max_records: int = 150,
        domain: str = "decibel_perpetual",
        api_key: Optional[str] = None,
    ):
        super().__init__(trading_pair, interval, max_records)
        self._domain = domain
        self._api_key = api_key
        self._market_addr: Optional[str] = None
        self._perp_engine_global: Optional[str] = None

    @property
    def name(self):
        return f"decibel_perpetual_{self._trading_pair}"

    @property
    def rest_url(self):
        return self._get_rest_url()

    @property
    def wss_url(self):
        return self._get_wss_url()

    @property
    def health_check_url(self):
        return self.rest_url + CONSTANTS.HEALTH_CHECK_ENDPOINT

    @property
    def candles_url(self):
        return self.rest_url + CONSTANTS.CANDLES_ENDPOINT

    @property
    def candles_endpoint(self):
        return CONSTANTS.CANDLES_ENDPOINT

    @property
    def candles_max_result_per_rest_request(self):
        return CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST

    @property
    def rate_limits(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def intervals(self):
        return CONSTANTS.INTERVALS

    def _get_rest_url(self) -> str:
        """Get REST URL based on domain."""
        if self._domain == CONSTANTS.TESTNET_DOMAIN:
            return CONSTANTS.TESTNET_REST_URL
        elif hasattr(CONSTANTS, 'NETNA_DOMAIN') and self._domain == CONSTANTS.NETNA_DOMAIN:
            return CONSTANTS.NETNA_REST_URL
        return CONSTANTS.REST_URL

    def _get_wss_url(self) -> str:
        """Get WebSocket URL based on domain."""
        if self._domain == CONSTANTS.TESTNET_DOMAIN:
            return CONSTANTS.TESTNET_WSS_URL
        elif hasattr(CONSTANTS, 'NETNA_DOMAIN') and self._domain == CONSTANTS.NETNA_DOMAIN:
            return CONSTANTS.NETNA_WSS_URL
        return CONSTANTS.WSS_URL

    async def initialize_exchange_data(self):
        """
        Initialize market address and perp engine global address.
        These are needed for both REST and WebSocket candle subscriptions.
        """
        try:
            from decibel import get_market_addr, get_perp_engine_global_address

            # Get package address based on domain
            package_address = self._get_package_address()
            self._perp_engine_global = get_perp_engine_global_address(package_address)

            # Convert trading pair to Decibel market name
            exchange_symbol = self.get_exchange_trading_pair(self._trading_pair)
            self._market_addr = get_market_addr(exchange_symbol, self._perp_engine_global)

            self.logger().debug(
                f"Initialized Decibel candles: trading_pair={self._trading_pair}, "
                f"exchange_symbol={exchange_symbol}, market_addr={self._market_addr[:16]}..."
            )
        except Exception as e:
            self.logger().error(f"Failed to initialize Decibel candles market data: {e}")

    def _get_package_address(self) -> str:
        """Get package address based on domain."""
        from decibel import MAINNET_CONFIG, NETNA_CONFIG, TESTNET_CONFIG

        if self._domain == CONSTANTS.TESTNET_DOMAIN:
            return TESTNET_CONFIG.deployment.package
        elif hasattr(CONSTANTS, 'NETNA_DOMAIN') and self._domain == CONSTANTS.NETNA_DOMAIN:
            return NETNA_CONFIG.deployment.package
        return MAINNET_CONFIG.deployment.package

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(
            url=self.health_check_url,
            throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT,
        )
        return NetworkStatus.CONNECTED

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        await ws.connect(ws_url=self.wss_url, ping_timeout=self._ping_timeout, ws_headers=headers)
        return ws

    def get_exchange_trading_pair(self, trading_pair: str) -> str:
        """
        Converts Hummingbot trading pair format to Decibel format.
        Hummingbot: BTC-USD -> Decibel: BTC/USD
        """
        parts = trading_pair.split("-")
        if len(parts) == 2:
            return f"{parts[0]}/{parts[1]}"
        return trading_pair

    @property
    def _is_first_candle_not_included_in_rest_request(self):
        return False

    @property
    def _is_last_candle_not_included_in_rest_request(self):
        return False

    def _get_rest_candles_params(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST
    ) -> dict:
        """
        Build REST API parameters for fetching candles.

        Decibel API requires market address (not market name) for candlestick queries.
        Falls back to exchange trading pair when market address is not yet initialized
        (e.g., during unit tests without the decibel SDK).
        """
        market_param = self._market_addr if self._market_addr else self._ex_trading_pair
        params = {
            "market": market_param,
            "interval": CONSTANTS.INTERVALS[self.interval],
        }

        if start_time is not None:
            params["startTime"] = int(start_time * 1000)  # Convert to milliseconds

        if end_time is not None:
            params["endTime"] = int(end_time * 1000)  # Convert to milliseconds

        # Decibel API doesn't accept 'limit' parameter
        # It returns all candles in the time range

        return params

    def _get_rest_candles_headers(self) -> Optional[Dict[str, str]]:
        """
        Decibel candles endpoint requires API key authentication.
        """
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return None

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        """
        Parse REST API response into standard candle format.

        Returns list of candles in format:
        [timestamp, open, high, low, close, volume, quote_asset_volume, n_trades, taker_buy_base_volume, taker_buy_quote_volume]
        """
        new_hb_candles = []

        # Decibel response format may vary - handle both list and dict with data key
        candle_list = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(candle_list, dict):
            candle_list = [candle_list]

        for candle in candle_list:
            timestamp = self.ensure_timestamp_in_seconds(candle.get("timestamp", candle.get("t", 0)))
            open_price = float(candle.get("open", candle.get("o", 0)))
            high = float(candle.get("high", candle.get("h", 0)))
            low = float(candle.get("low", candle.get("l", 0)))
            close = float(candle.get("close", candle.get("c", 0)))
            volume = float(candle.get("volume", candle.get("v", 0)))
            # Decibel may not provide these fields - set to 0
            quote_asset_volume = float(candle.get("quote_volume", 0))
            n_trades = int(candle.get("n_trades", candle.get("n", 0)))
            taker_buy_base_volume = 0
            taker_buy_quote_volume = 0

            new_hb_candles.append([
                timestamp, open_price, high, low, close, volume,
                quote_asset_volume, n_trades, taker_buy_base_volume, taker_buy_quote_volume
            ])

        return new_hb_candles

    def ws_subscription_payload(self) -> Dict[str, Any]:
        """
        Build WebSocket subscription message.

        Decibel WebSocket topic format:
        market_candlestick:{market_addr}:{interval}
        Falls back to exchange trading pair when market address is not yet initialized.
        """
        market_param = self._market_addr if self._market_addr else self._ex_trading_pair
        return {
            "method": "subscribe",
            "topic": f"{CONSTANTS.WS_CANDLES_CHANNEL}:{market_param}:{CONSTANTS.INTERVALS[self.interval]}"
        }

    def _parse_websocket_message(self, data: dict) -> Optional[Dict[str, Any]]:
        """
        Parse WebSocket candle update message.
        """
        candles_row_dict = {}

        # Check if this is a candlestick message
        topic = data.get("topic", "")
        if CONSTANTS.WS_CANDLES_CHANNEL not in topic:
            return None

        candle_data = data.get("data", data)
        if not candle_data:
            return None

        candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(
            candle_data.get("timestamp", candle_data.get("t", 0))
        )
        candles_row_dict["open"] = float(candle_data.get("open", candle_data.get("o", 0)))
        candles_row_dict["high"] = float(candle_data.get("high", candle_data.get("h", 0)))
        candles_row_dict["low"] = float(candle_data.get("low", candle_data.get("l", 0)))
        candles_row_dict["close"] = float(candle_data.get("close", candle_data.get("c", 0)))
        candles_row_dict["volume"] = float(candle_data.get("volume", candle_data.get("v", 0)))
        candles_row_dict["quote_asset_volume"] = float(candle_data.get("quote_volume", 0))
        candles_row_dict["n_trades"] = int(candle_data.get("n_trades", candle_data.get("n", 0)))
        candles_row_dict["taker_buy_base_volume"] = 0
        candles_row_dict["taker_buy_quote_volume"] = 0

        return candles_row_dict
