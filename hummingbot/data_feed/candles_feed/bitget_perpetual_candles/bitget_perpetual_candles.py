import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.connections.data_types import WSPlainTextRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.data_feed.candles_feed.bitget_perpetual_candles import constants as CONSTANTS
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.logger import HummingbotLogger


class BitgetPerpetualCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 150):
        super().__init__(trading_pair, interval, max_records)

        self._ping_task: Optional[asyncio.Task] = None

    @property
    def name(self):
        return f"bitget_{self._trading_pair}"

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
    def _is_last_candle_not_included_in_rest_request(self):
        return True

    @property
    def _is_first_candle_not_included_in_rest_request(self):
        return True

    @staticmethod
    def product_type_associated_to_trading_pair(trading_pair: str) -> str:
        """
        Returns the product type associated with the trading pair
        """
        _, quote = split_hb_trading_pair(trading_pair)

        if quote == "USDT":
            return CONSTANTS.USDT_PRODUCT_TYPE
        if quote == "USDC":
            return CONSTANTS.USDC_PRODUCT_TYPE
        if quote == "USD":
            return CONSTANTS.USD_PRODUCT_TYPE

        raise ValueError(f"No product type associated to {trading_pair} tranding pair")

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(
            url=self.health_check_url,
            throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT
        )

        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        return trading_pair.replace("-", "")

    def _get_rest_candles_params(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST
    ) -> dict:

        params = {
            "symbol": self._ex_trading_pair,
            "productType": self.product_type_associated_to_trading_pair(self._trading_pair),
            "granularity": CONSTANTS.INTERVALS[self.interval],
            "limit": limit
        }

        if start_time is not None and end_time is not None:
            now = int(time.time())
            max_days = CONSTANTS.INTERVAL_LIMITS_DAYS.get(self.interval)

            if max_days is not None:
                allowed_seconds = max_days * 24 * 60 * 60
                earliest_allowed = now - allowed_seconds

                if start_time < earliest_allowed:
                    self.logger().error(
                        f"[Bitget API] Invalid start time for interval '{self.interval}': "
                        f"the earliest allowed start time is {earliest_allowed} "
                        f"({max_days} days before now), but requested {start_time}."
                    )
                    raise ValueError('Invalid start time for current interval. See logs for more details.')

        if start_time is not None:
            params["startTime"] = start_time * 1000
        if end_time is not None:
            params["endTime"] = end_time * 1000

        return params

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        """
        Rest response example:
        {
            "code": "00000",
            "msg": "success",
            "requestTime": 1695865615662,
            "data": [
                [
                    "1695835800000",  # Timestamp ms
                    "26210.5",        # Entry
                    "26210.5",        # Highest
                    "26194.5",        # Lowest
                    "26194.5",        # Exit
                    "26.26",          # Volume base
                    "687897.63"       # Volume quote
                ]
            ]
        }
        """
        if data and data.get("data"):
            candles = data["data"]

            return [
                [
                    self.ensure_timestamp_in_seconds(int(row[0])),
                    float(row[1]), float(row[2]), float(row[3]),
                    float(row[4]), float(row[5]), float(row[6]),
                    0., 0., 0.
                ]
                for row in candles
            ]

        return []

    def ws_subscription_payload(self):
        interval = CONSTANTS.INTERVALS[self.interval]
        channel = f"{CONSTANTS.WS_CANDLES_ENDPOINT}{interval}"
        payload = {
            "op": "subscribe",
            "args": [
                {
                    "instType": self.product_type_associated_to_trading_pair(self._trading_pair),
                    "channel": channel,
                    "instId": self._ex_trading_pair
                }
            ]
        }

        return payload

    def _parse_websocket_message(self, data: dict) -> Optional[Dict[str, Any]]:
        """
        WS response example:
        {
            "action": "snapshot",  # or "update"
            "arg": {
                "instType": "USDT-FUTURES",
                "channel": "candle1m",
                "instId": "BTCUSDT"
            },
            "data": [
                [
                    "1695835800000",  # Timestamp ms
                    "26210.5",        # Opening
                    "26210.5",        # Highest
                    "26194.5",        # Lowest
                    "26194.5",        # Closing
                    "26.26",          # Volume coin
                    "687897.63"       # Volume quote
                    "687897.63"       # Volume USDT
                ]
            ],
            "ts": 1695702747821
            }
        """
        if data == "pong":
            return

        candles_row_dict: Dict[str, Any] = {}

        if data and data.get("data") and data["action"] == "update":
            candle = data["data"][0]
            candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(int(candle[0]))
            candles_row_dict["open"] = float(candle[1])
            candles_row_dict["high"] = float(candle[2])
            candles_row_dict["low"] = float(candle[3])
            candles_row_dict["close"] = float(candle[4])
            candles_row_dict["volume"] = float(candle[5])
            candles_row_dict["quote_asset_volume"] = float(candle[6])
            candles_row_dict["n_trades"] = 0.
            candles_row_dict["taker_buy_base_volume"] = 0.
            candles_row_dict["taker_buy_quote_volume"] = 0.

            return candles_row_dict

    async def _send_ping(self, websocket_assistant: WSAssistant) -> None:
        ping_request = WSPlainTextRequest(CONSTANTS.PUBLIC_WS_PING_REQUEST)

        await websocket_assistant.send(ping_request)

    async def send_interval_ping(self, websocket_assistant: WSAssistant) -> None:
        """
        Coroutine to send PING messages periodically.

        :param websocket_assistant: The websocket assistant to use to send the PING message.
        """
        try:
            while True:
                await self._send_ping(websocket_assistant)
                await asyncio.sleep(CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        except asyncio.CancelledError:
            self.logger().info("Interval PING task cancelled")
            raise
        except Exception:
            self.logger().exception("Error sending interval PING")

    async def listen_for_subscriptions(self):
        """
        Connects to the candlestick websocket endpoint and listens to the messages sent by the
        exchange.
        """
        ws: Optional[WSAssistant] = None
        while True:
            try:
                ws: WSAssistant = await self._connected_websocket_assistant()
                await self._subscribe_channels(ws)
                self._ping_task = asyncio.create_task(self.send_interval_ping(ws))
                await self._process_websocket_messages(websocket_assistant=ws)
            except asyncio.CancelledError:
                raise
            except ConnectionError as connection_exception:
                self.logger().warning(f"The websocket connection was closed ({connection_exception})")
            except Exception:
                self.logger().exception(
                    "Unexpected error occurred when listening to public klines. Retrying in 1 seconds...",
                )
                await self._sleep(1.0)
            finally:
                if self._ping_task is not None:
                    self._ping_task.cancel()
                    try:
                        await self._ping_task
                    except asyncio.CancelledError:
                        pass
                    self._ping_task = None
                await self._on_order_stream_interruption(websocket_assistant=ws)
