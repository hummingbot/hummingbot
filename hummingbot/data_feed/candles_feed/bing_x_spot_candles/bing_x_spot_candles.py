import logging
import uuid
from typing import List, Optional

from hummingbot.connector.exchange.bing_x.bing_x_utils import decompress_ws_message
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.bing_x_spot_candles import constants as CONSTANTS
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.logger import HummingbotLogger


class BingXSpotCandles(CandlesBase):
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
        return f"bing_x_{self._trading_pair}"

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
        await rest_assistant.execute_request(url=self.health_check_url,
                                             throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT)
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        # BingX spot uses the dashed BASE-QUOTE notation natively, both on REST and WS.
        return trading_pair

    def _get_rest_candles_params(self,
                                 start_time: Optional[int] = None,
                                 end_time: Optional[int] = None,
                                 limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST) -> dict:
        # The REST kline endpoint accepts the Hummingbot interval strings verbatim; both
        # timestamps are millisecond epoch values (live-verified).
        return {
            "symbol": self._ex_trading_pair,
            "interval": self.interval,
            "startTime": start_time * 1000,
            "endTime": end_time * 1000,
            "limit": limit,
        }

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        # Live rows are [openTimeMs, open, high, low, close, volume, closeTimeMs, quoteVolume]
        # and arrive newest-first; the feed contract wants ascending ten-column rows with
        # second timestamps and zero-filled n_trades/taker fields (BingX does not report them).
        rows = (data or {}).get("data") or []
        return [
            [self.ensure_timestamp_in_seconds(row[0]), row[1], row[2], row[3], row[4], row[5],
             row[7], 0.0, 0.0, 0.0]
            for row in reversed(rows)
        ]

    def ws_subscription_payload(self):
        payload = {
            "id": str(uuid.uuid4()),
            "reqType": "sub",
            "dataType": f"{self._ex_trading_pair}@kline_{CONSTANTS.INTERVALS[self.interval]}",
        }
        return payload

    def _parse_websocket_message(self, data):
        # WS frames are gzip-compressed JSON; text frames carry no candle data. The kline push
        # wraps the candle under {"code": 0, "data": {"e": "kline", "K": {...}}} (live-verified);
        # subscription acks have no "data" object and are ignored.
        if isinstance(data, (bytes, bytearray)):
            data = decompress_ws_message(data)
        if not isinstance(data, dict):
            return None
        payload = data.get("data")
        if not isinstance(payload, dict) or payload.get("e") != "kline":
            return None
        kline = payload["K"]
        return {
            "timestamp": self.ensure_timestamp_in_seconds(kline["t"]),
            "open": kline["o"],
            "high": kline["h"],
            "low": kline["l"],
            "close": kline["c"],
            "volume": kline["v"],
            "quote_asset_volume": kline["q"],
            "n_trades": kline["n"],
            "taker_buy_base_volume": 0.0,
            "taker_buy_quote_volume": 0.0,
        }
