import logging
from typing import Any, Dict, List, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.pacifica_perpetual_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class PacificaPerpetualCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 150):
        super().__init__(trading_pair, interval, max_records)

    @property
    def name(self):
        return f"pacifica_perpetual_{self._trading_pair}"

    @property
    def rest_url(self):
        return CONSTANTS.REST_URL

    @property
    def wss_url(self):
        return CONSTANTS.WSS_URL

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

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(
            url=self.health_check_url,
            throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT
        )
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair: str) -> str:
        """
        Converts Hummingbot trading pair format to Pacifica format.
        Pacifica uses just the base asset (e.g., 'BTC' instead of 'BTC-USDC')
        """
        # Split the trading pair (e.g., "BTC-USDC" -> "BTC")
        return trading_pair.split("-")[0]

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

        API Documentation: https://docs.pacifica.fi/api-documentation/api/rest-api/markets/get-candle-data

        Example response:
        {
            "success": true,
            "data": [
                {
                    "t": 1748954160000,    # Start time (ms)
                    "T": 1748954220000,    # End time (ms)
                    "s": "BTC",            # Symbol
                    "i": "1m",             # Interval
                    "o": "105376",         # Open price
                    "c": "105376",         # Close price
                    "h": "105376",         # High price
                    "l": "105376",         # Low price
                    "v": "0.00022",        # Volume
                    "n": 2                 # Number of trades
                }
            ]
        }
        """
        params = {
            "symbol": self._ex_trading_pair,
            "interval": CONSTANTS.INTERVALS[self.interval],
        }

        if start_time is not None:
            params["start_time"] = int(start_time * 1000)  # Convert to milliseconds

        if end_time is not None:
            params["end_time"] = int(end_time * 1000)  # Convert to milliseconds

        if limit is not None:
            params["limit"] = limit

        return params

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        """
        Parse REST API response into standard candle format.

        Returns list of candles in format:
        [timestamp, open, high, low, close, volume, quote_asset_volume, n_trades, taker_buy_base_volume, taker_buy_quote_volume]
        """
        new_hb_candles = []

        if not data.get("success") or not data.get("data"):
            return new_hb_candles

        for candle in data["data"]:
            timestamp = self.ensure_timestamp_in_seconds(candle["t"])
            open_price = float(candle["o"])
            high = float(candle["h"])
            low = float(candle["l"])
            close = float(candle["c"])
            volume = float(candle["v"])
            # Pacifica doesn't provide quote_asset_volume, taker volumes
            # Setting these to 0 as per the pattern in other exchanges
            quote_asset_volume = 0
            n_trades = int(candle["n"])
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

        Documentation: https://docs.pacifica.fi/api-documentation/api/websocket/subscriptions/candle

        Example:
        {
            "method": "subscribe",
            "params": {
                "source": "candle",
                "symbol": "BTC",
                "interval": "1m"
            }
        }
        """
        return {
            "method": "subscribe",
            "params": {
                "source": CONSTANTS.WS_CANDLES_CHANNEL,
                "symbol": self._ex_trading_pair,
                "interval": CONSTANTS.INTERVALS[self.interval]
            }
        }

    def _parse_websocket_message(self, data: dict) -> Optional[Dict[str, Any]]:
        """
        Parse WebSocket candle update message.

        Documentation: https://docs.pacifica.fi/api-documentation/api/websocket/subscriptions/candle

        Example message:
        {
            "channel": "candle",
            "data": {
                "t": 1749052260000,
                "T": 1749052320000,
                "s": "SOL",
                "i": "1m",
                "o": "157.3",
                "c": "157.32",
                "h": "157.32",
                "l": "157.3",
                "v": "1.22",
                "n": 8
            }
        }
        """
        candles_row_dict = {}

        if data.get("channel") == CONSTANTS.WS_CANDLES_CHANNEL and data.get("data"):
            candle_data = data["data"]

            candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(candle_data["t"])
            candles_row_dict["open"] = float(candle_data["o"])
            candles_row_dict["high"] = float(candle_data["h"])
            candles_row_dict["low"] = float(candle_data["l"])
            candles_row_dict["close"] = float(candle_data["c"])
            candles_row_dict["volume"] = float(candle_data["v"])
            candles_row_dict["quote_asset_volume"] = 0  # Not provided by Pacifica
            candles_row_dict["n_trades"] = int(candle_data["n"])
            candles_row_dict["taker_buy_base_volume"] = 0  # Not provided by Pacifica
            candles_row_dict["taker_buy_quote_volume"] = 0  # Not provided by Pacifica

            return candles_row_dict

        return None
