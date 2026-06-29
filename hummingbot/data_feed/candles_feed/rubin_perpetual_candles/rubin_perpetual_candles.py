import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.rubin_perpetual_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class RubinPerpetualCandles(CandlesBase):
    """
    Candles feed for the Rubin perpetual DEX, sourced from the chain indexer.
    Mainnet by default; the testnet variant overrides ``_domain``.
    """
    _logger: Optional[HummingbotLogger] = None
    _domain: str = "rubin_perpetual"

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 150):
        super().__init__(trading_pair, interval, max_records)

    @property
    def name(self):
        return f"{self._domain}_{self._trading_pair}"

    @property
    def rest_url(self):
        return CONSTANTS.DOMAINS[self._domain]["rest"]

    @property
    def wss_url(self):
        return CONSTANTS.DOMAINS[self._domain]["wss"]

    @property
    def health_check_url(self):
        return self.rest_url + CONSTANTS.HEALTH_CHECK_ENDPOINT

    @property
    def candles_url(self):
        # The indexer carries the ticker in the path, not as a query param.
        return f"{self.rest_url}{CONSTANTS.CANDLES_ENDPOINT}/{self._ex_trading_pair}"

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
    def _is_first_candle_not_included_in_rest_request(self):
        return False

    @property
    def _is_last_candle_not_included_in_rest_request(self):
        return False

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(
            url=self.health_check_url,
            throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT,
        )
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair: str) -> str:
        # Rubin tickers match the Hummingbot format (e.g. "BTC-USD").
        return trading_pair

    @staticmethod
    def _iso_to_seconds(iso_ts: str) -> float:
        return datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).timestamp()

    @staticmethod
    def _seconds_to_iso(ts: Optional[float]) -> Optional[str]:
        if ts is None:
            return None
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def _get_rest_candles_params(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST,
    ) -> dict:
        params = {
            "resolution": CONSTANTS.INTERVALS[self.interval],
            "limit": limit or self.candles_max_result_per_rest_request,
        }
        from_iso = self._seconds_to_iso(start_time)
        to_iso = self._seconds_to_iso(end_time)
        if from_iso is not None:
            params["fromISO"] = from_iso
        if to_iso is not None:
            params["toISO"] = to_iso
        return params

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        candles = data.get("candles", []) if isinstance(data, dict) else []
        parsed = [self._candle_to_row(c) for c in candles if c and "close" in c]
        # The indexer returns newest-first; Hummingbot expects ascending by timestamp.
        parsed.sort(key=lambda row: row[0])
        return parsed

    def _candle_to_row(self, c: Dict[str, Any]) -> List[float]:
        return [
            self._iso_to_seconds(c["startedAt"]),
            float(c["open"]),
            float(c["high"]),
            float(c["low"]),
            float(c["close"]),
            float(c.get("baseTokenVolume", 0) or 0),   # volume (base)
            float(c.get("usdVolume", 0) or 0),          # quote_asset_volume
            float(c.get("trades", 0) or 0),             # n_trades
            0.0,                                        # taker_buy_base_volume (not provided)
            0.0,                                        # taker_buy_quote_volume (not provided)
        ]

    def ws_subscription_payload(self) -> Dict[str, Any]:
        return {
            "type": "subscribe",
            "channel": CONSTANTS.WS_CHANNEL,
            "id": f"{self._ex_trading_pair}/{CONSTANTS.INTERVALS[self.interval]}",
        }

    def _parse_websocket_message(self, data: dict) -> Optional[Dict[str, Any]]:
        if not isinstance(data, dict) or data.get("channel") != CONSTANTS.WS_CHANNEL:
            return None

        contents = data.get("contents")
        candle: Optional[Dict[str, Any]] = None
        msg_type = data.get("type")
        if msg_type == "channel_data" and isinstance(contents, dict):
            candle = contents
        elif msg_type == "subscribed" and isinstance(contents, dict):
            # Snapshot is newest-first; take the latest to bootstrap the feed.
            snapshot = contents.get("candles") or []
            candle = snapshot[0] if snapshot else None

        if not candle or "close" not in candle:
            return None

        row = self._candle_to_row(candle)
        return {
            "timestamp": row[0],
            "open": row[1],
            "high": row[2],
            "low": row[3],
            "close": row[4],
            "volume": row[5],
            "quote_asset_volume": row[6],
            "n_trades": row[7],
            "taker_buy_base_volume": row[8],
            "taker_buy_quote_volume": row[9],
        }


class RubinPerpetualTestnetCandles(RubinPerpetualCandles):
    """Testnet variant — same API, testnet indexer endpoints."""
    _domain: str = "rubin_perpetual_testnet"
