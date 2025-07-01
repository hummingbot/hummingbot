import logging
from datetime import datetime, timezone
from typing import List, Optional

from dateutil.parser import parse as dateparse

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.btc_markets_spot_candles import constants as CONSTANTS
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.logger import HummingbotLogger


class BtcMarketsSpotCandles(CandlesBase):
    """
    BTC Markets implementation for fetching candlestick data.

    Note: BTC Markets doesn't support WebSocket for candles.
    """

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
        return f"btc_markets_{self._trading_pair}"

    @property
    def rest_url(self):
        return CONSTANTS.REST_URL

    @property
    def wss_url(self):
        # BTC Markets doesn't support WebSocket for candles
        return CONSTANTS.WSS_URL

    @property
    def health_check_url(self):
        return self.rest_url + CONSTANTS.HEALTH_CHECK_ENDPOINT

    @property
    def candles_url(self):
        market_id = self.get_exchange_trading_pair(self._trading_pair)
        return self.rest_url + CONSTANTS.CANDLES_ENDPOINT.format(market_id=market_id)

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
            url=self.health_check_url, throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT
        )
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        """
        Converts from the Hummingbot trading pair format to the exchange's trading pair format.
        BTC Markets uses the same format so no conversion is needed.
        """
        return trading_pair

    @property
    def _is_first_candle_not_included_in_rest_request(self):
        return False

    @property
    def _is_last_candle_not_included_in_rest_request(self):
        return False

    def _get_rest_candles_params(
        self, start_time: Optional[int] = None, end_time: Optional[int] = None, limit: Optional[int] = None
    ) -> dict:
        """
        Generates parameters for the REST API request to fetch candles.

        BTC Markets requires ISO 8601 format timestamps and supports both
        timestamp-based and pagination-based requests.

        For API documentation, please refer to:
        https://docs.btcmarkets.net/#tag/Market-Data-APIs/paths/~1v3~1markets~1{marketId}~1candles/get
        """
        params = {
            "timeWindow": self.intervals[self.interval],
            "limit": limit if limit is not None else self.candles_max_result_per_rest_request,
        }

        if start_time:
            # Convert Unix timestamp to ISO 8601 format
            start_iso = datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            params["from"] = start_iso

        if end_time:
            # Convert Unix timestamp to ISO 8601 format
            end_iso = datetime.fromtimestamp(end_time, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            params["to"] = end_iso

        return params

    def _parse_rest_candles(self, data: List[List[str]], end_time: Optional[int] = None) -> List[List[float]]:
        """
        Parse the REST API response into the standard candle format.

        BTC Markets response format:
        [
            [
                "2019-09-02T18:00:00.000000Z",  # timestamp
                "15100",                         # open
                "15200",                         # high
                "15100",                         # low
                "15199",                         # close
                "4.11970335"                     # volume
            ],
            ...
        ]

        We need to convert this to our standard format:
        [timestamp, open, high, low, close, volume, quote_asset_volume, n_trades, taker_buy_base_volume, taker_buy_quote_volume]
        """
        self.logger().debug(f"Parsing {len(data)} candles from REST API response")

        new_hb_candles = []
        for i in data:
            try:
                timestamp = self.ensure_timestamp_in_seconds(dateparse(i[0]).timestamp())
                open_price = float(i[1])
                high = float(i[2])
                low = float(i[3])
                close = float(i[4])
                volume = float(i[5])

                # BTC Markets doesn't provide these values, so we set them to 0
                quote_asset_volume = 0.0
                n_trades = 0.0
                taker_buy_base_volume = 0.0
                taker_buy_quote_volume = 0.0

                new_hb_candles.append(
                    [
                        timestamp,
                        open_price,
                        high,
                        low,
                        close,
                        volume,
                        quote_asset_volume,
                        n_trades,
                        taker_buy_base_volume,
                        taker_buy_quote_volume,
                    ]
                )

            except Exception as e:
                self.logger().error(f"Error parsing candle {i}: {e}")

        # Sort by timestamp in ascending order (oldest first, newest last)
        new_hb_candles.sort(key=lambda x: x[0])

        self.logger().debug(f"Parsed {len(new_hb_candles)} candles successfully")

        return new_hb_candles

    def ws_subscription_payload(self):
        """
        Not used for BTC Markets since WebSocket is not supported for candles.
        Implementing as required by the base class.
        """
        raise NotImplementedError

    def _parse_websocket_message(self, data):
        """
        Not used for BTC Markets since WebSocket is not supported for candles.
        Implementing as required by the base class.
        """
        raise NotImplementedError
