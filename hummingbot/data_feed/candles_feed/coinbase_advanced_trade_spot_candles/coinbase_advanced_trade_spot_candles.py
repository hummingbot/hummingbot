import logging
from typing import Dict, List, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class CoinbaseAdvancedTradeSpotCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 350):
        super().__init__(trading_pair, interval, max_records)

    @property
    def name(self):
        return f"coinbase_advanced_trade_{self._trading_pair}"

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
        return self.rest_url + CONSTANTS.CANDLES_ENDPOINT.format(product_id=self._ex_trading_pair)

    @property
    def candles_endpoint(self):
        return CONSTANTS.CANDLES_ENDPOINT_ID

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
        return trading_pair

    def _get_rest_candles_params(self,
                                 start_time: Optional[int] = None,
                                 end_time: Optional[int] = None,
                                 limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST) -> dict:
        return {
            "start": str(start_time),
            "end": str(end_time),
            "granularity": self.intervals[self.interval],
        }

    def _parse_rest_candles(self, data: Dict, end_time: Optional[int] = None) -> List[List[float]]:
        candles = data if isinstance(data, list) else data.get("candles", [])
        parsed_candles = [self._parse_candle(candle) for candle in candles]
        return sorted(parsed_candles, key=lambda candle: candle[0])

    def ws_subscription_payload(self):
        return {
            "type": "subscribe",
            "product_ids": [self._ex_trading_pair],
            "channel": CONSTANTS.WS_CANDLES_CHANNEL,
        }

    def _parse_websocket_message(self, data: dict):
        if data is None or data.get("channel") != CONSTANTS.WS_CANDLES_CHANNEL:
            return None

        for event in data.get("events", []):
            candles = event.get("candles", [])
            for candle in candles:
                if candle.get("product_id", self._ex_trading_pair) == self._ex_trading_pair:
                    return self._parse_candle(candle, as_dict=True)

        return None

    def _parse_candle(self, candle: Dict, as_dict: bool = False):
        timestamp = self.ensure_timestamp_in_seconds(float(candle["start"]))
        open_price = candle["open"]
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]
        volume = candle["volume"]
        quote_asset_volume = float(volume) * float(close)
        n_trades = 0
        taker_buy_base_volume = 0
        taker_buy_quote_volume = 0

        if as_dict:
            return {
                "timestamp": timestamp,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "quote_asset_volume": quote_asset_volume,
                "n_trades": n_trades,
                "taker_buy_base_volume": taker_buy_base_volume,
                "taker_buy_quote_volume": taker_buy_quote_volume,
            }

        return [
            timestamp, open_price, high, low, close, volume, quote_asset_volume, n_trades,
            taker_buy_base_volume, taker_buy_quote_volume
        ]
