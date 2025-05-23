import logging
from typing import Any, Dict, List, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.bitmart_perpetual_candles import constants as CONSTANTS
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.logger import HummingbotLogger


class BitmartPerpetualCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 150):
        super().__init__(trading_pair, interval, max_records)
        self.contract_size = None
        self.ws_interval = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1H",
            "2h": "2H",
            "4h": "4H",
            "12h": "12H",
            "1d": "1D",
            "1w": "1W",
        }

    async def initialize_exchange_data(self):
        await self.get_exchange_trading_pair_contract_size()

    async def get_exchange_trading_pair_contract_size(self):
        contract_size = None
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=self.rest_url + CONSTANTS.CONTRACT_INFO_URL.format(contract=self._ex_trading_pair),
            throttler_limit_id=CONSTANTS.CONTRACT_INFO_URL
        )
        if response["code"] == 1000:
            symbols_data = response["data"].get("symbols")
            if len(symbols_data) > 0:
                contract_size = float(symbols_data[0]["contract_size"])
                self.contract_size = contract_size
        return contract_size

    @property
    def name(self):
        return f"bitmart_perpetual_{self._trading_pair}"

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

    @property
    def is_linear(self):
        return "USDT" in self._trading_pair

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(url=self.health_check_url,
                                             throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT)
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        return trading_pair.replace("-", "")

    @property
    def _is_first_candle_not_included_in_rest_request(self):
        return False

    @property
    def _is_last_candle_not_included_in_rest_request(self):
        return False

    def _get_rest_candles_params(self,
                                 start_time: Optional[int] = None,
                                 end_time: Optional[int] = None,
                                 limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST) -> dict:
        """
        For API documentation, please refer to:
        https://developer-pro.bitmart.com/en/futuresv2/#get-k-line

        start_time and end_time must be used at the same time.
        """
        params = {
            "symbol": self._ex_trading_pair,
            "step": CONSTANTS.INTERVALS[self.interval],
        }
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        return params

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        if data is not None and data.get("data") is not None:
            candles = data.get("data")
            if len(candles) > 0:
                return [[
                    self.ensure_timestamp_in_seconds(row["timestamp"]),
                    row["open_price"],
                    row["high_price"],
                    row["low_price"],
                    row["close_price"],
                    float(row["volume"]) * self.contract_size,
                    0.,
                    0.,
                    0.,
                    0.] for row in candles]
        return []

    def ws_subscription_payload(self):
        interval = self.ws_interval[self.interval]
        channel = f"futures/klineBin{interval}"
        args = [f"{channel}:{self._ex_trading_pair}"]
        payload = {
            "action": "subscribe",
            "args": args,
        }
        return payload

    def _parse_websocket_message(self, data):
        candles_row_dict: Dict[str, Any] = {}
        if data is not None and data.get("data") is not None:
            candle = data["data"]["items"][0]
            candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(candle["ts"])
            candles_row_dict["open"] = candle["o"]
            candles_row_dict["low"] = candle["l"]
            candles_row_dict["high"] = candle["h"]
            candles_row_dict["close"] = candle["c"]
            candles_row_dict["volume"] = float(candle["v"]) * self.contract_size
            candles_row_dict["quote_asset_volume"] = 0.
            candles_row_dict["n_trades"] = 0.
            candles_row_dict["taker_buy_base_volume"] = 0.
            candles_row_dict["taker_buy_quote_volume"] = 0.
            return candles_row_dict
