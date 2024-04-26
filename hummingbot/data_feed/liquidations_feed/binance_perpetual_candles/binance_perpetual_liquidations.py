import asyncio
import logging
from typing import Any, Dict, Optional

from bidict import bidict

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.data_feed.candles_feed.binance_perpetual_candles import constants as CONSTANTS
from hummingbot.data_feed.liquidations_feed.liquidations_base import LiquidationsBase
from hummingbot.logger import HummingbotLogger


class BinancePerpetualLiquidations(LiquidationsBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pairs: list, max_records: int = 100):
        super().__init__(trading_pairs=trading_pairs, max_records=max_records)
        self.trading_pairs_map = bidict({tp: self.get_exchange_trading_pair(tp) for tp in trading_pairs})

    @property
    def name(self):
        return f"binance_perpetual_{self._liquidations.keys()}"

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
    def rate_limits(self):
        return CONSTANTS.RATE_LIMITS

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(url=self.health_check_url,
                                             throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT)
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        return trading_pair.replace("-", "")

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the candles events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            for trading_pair in self._trading_pairs:
                ex_trading_pair = self.get_exchange_trading_pair(trading_pair)
                liquidations_params = [f"{ex_trading_pair.lower()}@forceOrder"]
                payload = {
                    "method": "SUBSCRIBE",
                    "params": liquidations_params,
                    "id": 1
                }
                subscribe_liquidations_request: WSJSONRequest = WSJSONRequest(payload=payload)
                await ws.send(subscribe_liquidations_request)
            self.logger().info("Subscribed to public liquidations...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to public klines...",
                exc_info=True
            )
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        """
        Example response:
        {
            "e":"forceOrder",                   // Event Type
            "E":1568014460893,                  // Event Time
            "o":{

                "s":"BTCUSDT",                   // Symbol
                "S":"SELL",                      // Side
                "o":"LIMIT",                     // Order Type
                "f":"IOC",                       // Time in Force
                "q":"0.014",                     // Original Quantity
                "p":"9910",                      // Price
                "ap":"9910",                     // Average Price
                "X":"FILLED",                    // Order Status
                "l":"0.014",                     // Order Last Filled Quantity
                "z":"0.014",                     // Order Filled Accumulated Quantity
                "T":1568014460893,              // Order Trade Time

            }

        }
        """
        async for ws_response in websocket_assistant.iter_messages():
            data: Dict[str, Any] = ws_response.data
            if data.get("e") == "forceOrder":
                trading_pair = self.trading_pairs_map.inverse.get(data["o"]["s"])
                processed_data = [data.get("E")] + list(data.get("o").values())
                self._liquidations[trading_pair].append(processed_data)
