import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.evedex_perpetual_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class EvedexPerpetualCandles(CandlesBase):
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
        ws_access_token: Optional[str] = None,
    ):
        self._message_id = 0
        self._ping_task: Optional[asyncio.Task] = None
        self._ws_assistant: Optional[WSAssistant] = None
        self._instrument_resolved = False
        self._ws_access_token: Optional[str] = ws_access_token
        super().__init__(trading_pair, interval, max_records)

    @property
    def name(self):
        return f"evedex_perpetual_{self._trading_pair}"

    @property
    def rest_url(self):
        return CONSTANTS.MARKET_DATA_REST_URL

    @property
    def wss_url(self):
        return CONSTANTS.WSS_URL

    @property
    def health_check_url(self):
        return f"{CONSTANTS.EXCHANGE_REST_URL}{CONSTANTS.HEALTH_CHECK_ENDPOINT}"

    @property
    def candles_url(self):
        return f"{CONSTANTS.MARKET_DATA_REST_URL}{CONSTANTS.CANDLES_ENDPOINT.format(instrument=self._ex_trading_pair)}"

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
        base, quote = trading_pair.split("-")
        if quote == "USDT":
            quote = "USD"
        return f"{base}{quote}"

    async def initialize_exchange_data(self):
        if self._instrument_resolved:
            return

        base, quote = self._trading_pair.split("-")
        rest_assistant = await self._api_factory.get_rest_assistant()
        try:
            instruments = await rest_assistant.execute_request(
                url=f"{CONSTANTS.EXCHANGE_REST_URL}{CONSTANTS.INSTRUMENTS_ENDPOINT}",
                throttler_limit_id=CONSTANTS.INSTRUMENTS_ENDPOINT,
            )
        except Exception:
            self.logger().warning("Failed to resolve Evedex instrument name from exchange info. "
                                  "Using derived symbol.")
            self._instrument_resolved = True
            return

        instruments_list = instruments if isinstance(instruments, list) else instruments.get("list", [])
        for instrument in instruments_list:
            from_coin = instrument.get("from") or {}
            to_coin = instrument.get("to") or {}
            inst_base = from_coin.get("symbol")
            inst_quote = to_coin.get("symbol")
            if inst_base != base:
                continue
            if inst_quote == quote or (quote == "USDT" and inst_quote == "USD"):
                resolved = instrument.get("name")
                if resolved:
                    self._ex_trading_pair = resolved
                break

        self._instrument_resolved = True

    def _format_iso_timestamp(self, timestamp: int) -> str:
        ts = float(timestamp)
        if ts >= 1e17:
            ts = ts / 1e9
        else:
            ts = self.ensure_timestamp_in_seconds(ts)
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def _get_rest_candles_params(self,
                                 start_time: Optional[int] = None,
                                 end_time: Optional[int] = None,
                                 limit: Optional[int] = None) -> dict:
        params = {
            "group": CONSTANTS.INTERVALS[self.interval],
        }
        if start_time is not None:
            params["after"] = self._format_iso_timestamp(start_time)
        if end_time is not None:
            params["before"] = self._format_iso_timestamp(end_time)
        return params

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        if data is None:
            return []

        raw = data
        if isinstance(data, dict):
            raw = data.get("data") or data.get("result") or data.get("candles") or []

        if not isinstance(raw, list):
            return []

        parsed: List[List[float]] = []
        for row in raw:
            if isinstance(row, list):
                parsed_row = self._parse_candle_row(row)
            elif isinstance(row, dict):
                parsed_row = self._parse_candle_dict(row)
            else:
                continue
            if parsed_row is not None:
                parsed.append(parsed_row)

        parsed.sort(key=lambda r: r[0])
        return parsed

    def _normalize_timestamp(self, timestamp: Any) -> float:
        ts = self.ensure_timestamp_in_seconds(timestamp)
        return self._round_timestamp_to_interval_multiple(int(ts))

    def _parse_candle_row(self, row: List[Any]) -> Optional[List[float]]:
        if len(row) < 6:
            return None
        timestamp = self._normalize_timestamp(row[0])
        open_price = row[1]
        close_price = row[2]
        high_price = row[3]
        low_price = row[4]
        if len(row) >= 7:
            volume_usd = row[5]
            volume = row[6]
        else:
            volume_usd = 0
            volume = row[5]
        return [
            timestamp,
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
            volume_usd,
            0.,
            0.,
            0.,
        ]

    def _parse_candle_dict(self, data: Dict[str, Any]) -> Optional[List[float]]:
        timestamp = data.get("timestamp") or data.get("t") or data.get("time")
        if timestamp is None:
            return None
        open_price = data["open"] if "open" in data else data.get("o")
        close_price = data["close"] if "close" in data else data.get("c")
        high_price = data["high"] if "high" in data else data.get("h")
        low_price = data["low"] if "low" in data else data.get("l")
        volume = data["volume"] if "volume" in data else data.get("v", 0)
        if "volumeUsd" in data:
            quote_volume = data["volumeUsd"]
        elif "quoteVolume" in data:
            quote_volume = data["quoteVolume"]
        else:
            quote_volume = data.get("q", 0)
        return [
            self._normalize_timestamp(timestamp),
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
            quote_volume,
            0.,
            0.,
            0.,
        ]

    def _next_message_id(self) -> int:
        self._message_id += 1
        return self._message_id

    def _subscription_channels(self) -> List[str]:
        interval = CONSTANTS.INTERVALS[self.interval]
        channels = [f"market-data:last-candlestick-{self._ex_trading_pair}-{interval}"]
        if "-" in self._ex_trading_pair:
            channels.append(f"market-data:last-candlestick-{self._ex_trading_pair.replace('-', '')}-{interval}")
        return list(dict.fromkeys(channels))

    def ws_subscription_payload(self):
        interval = CONSTANTS.INTERVALS[self.interval]
        channel = f"market-data:last-candlestick-{self._ex_trading_pair}-{interval}"
        payload = {
            "subscribe": {
                "channel": channel,
                "recoverable": True,
                "flag": 1,
            },
            "id": self._next_message_id(),
        }
        access_token = self._ws_access_token
        if access_token:
            payload["subscribe"]["data"] = {"accessToken": access_token}
        return payload

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            access_token = self._ws_access_token
            for channel in self._subscription_channels():
                subscribe_payload = {
                    "subscribe": {
                        "channel": channel,
                        "recoverable": True,
                        "flag": 1,
                    },
                    "id": self._next_message_id(),
                }
                if access_token:
                    subscribe_payload["subscribe"]["data"] = {"accessToken": access_token}
                subscribe_request = WSJSONRequest(payload=subscribe_payload)
                await ws.send(subscribe_request)
            self.logger().info("Subscribed to public klines...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to public klines...",
                exc_info=True
            )
            raise

    async def _ping_loop(self, websocket_assistant: WSAssistant):
        try:
            while True:
                await asyncio.sleep(CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
                ping_request = WSJSONRequest(payload={"ping": {}})
                await websocket_assistant.send(ping_request)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().debug(f"Ping loop error: {e}")

    async def _connected_websocket_assistant(self) -> WSAssistant:
        if self._ping_task is not None and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None

        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=self.wss_url,
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL + CONSTANTS.WS_PING_TIMEOUT,
        )

        connect_request = WSJSONRequest(payload={
            "connect": {"name": "js"},
            "id": self._next_message_id(),
        })
        await ws.send(connect_request)

        # Centrifugo server sends pings; respond with pong in message handler.
        self._ws_assistant = ws
        return ws

    def _parse_websocket_message(self, data):
        if data is None:
            return None
        if data == {}:
            return WSJSONRequest(payload={})
        if isinstance(data, dict) and "ping" in data:
            self.logger().debug("Received Centrifugo ping on candles stream; sending pong.")
            return WSJSONRequest(payload={"pong": {}})

        payload = None
        if isinstance(data, dict) and "push" in data:
            payload = data.get("push", {}).get("pub", {}).get("data")
        elif isinstance(data, dict) and "data" in data:
            payload = data.get("data")

        if payload is None:
            return None

        if isinstance(payload, list):
            parsed = self._parse_candle_row(payload)
        elif isinstance(payload, dict):
            if isinstance(payload.get("data"), list):
                parsed = self._parse_candle_row(payload.get("data"))
            else:
                parsed = self._parse_candle_dict(payload)
        else:
            parsed = None

        if parsed is None:
            return None

        return {
            "timestamp": parsed[0],
            "open": parsed[1],
            "high": parsed[2],
            "low": parsed[3],
            "close": parsed[4],
            "volume": parsed[5],
            "quote_asset_volume": parsed[6],
            "n_trades": parsed[7],
            "taker_buy_base_volume": parsed[8],
            "taker_buy_quote_volume": parsed[9],
        }

    async def _on_order_stream_interruption(self, websocket_assistant: Optional[WSAssistant] = None):
        if self._ping_task is not None:
            self._ping_task.cancel()
            self._ping_task = None
        await super()._on_order_stream_interruption(websocket_assistant)
