import asyncio
import logging
from typing import Any, Dict, Optional, Set

from bidict import bidict

from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.data_feed.liquidations_feed.binance import constants as CONSTANTS
from hummingbot.data_feed.liquidations_feed.liquidations_base import Liquidation, LiquidationsBase, LiquidationSide
from hummingbot.logger import HummingbotLogger


class BinancePerpetualLiquidations(LiquidationsBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pairs: Set[str], max_retention_seconds: int):
        super().__init__(trading_pairs=trading_pairs, max_retention_seconds=max_retention_seconds)

    @property
    def name(self):
        return "binance_liquidations"

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
        return self._trading_pairs_map.inverse.get(trading_pair)

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the liquidations events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            force_order_streams = []

            if not self._trading_pairs or len(self._trading_pairs) == 0:
                # Subscribe to all forced orders on the exchange
                force_order_streams.append("!forceOrder@arr")
            else:
                # Subscribe to the selected orders of the given pairs
                for trading_pair in self._trading_pairs:
                    ex_trading_pair = self.get_exchange_trading_pair(trading_pair)
                    force_order_streams.append(f"{ex_trading_pair.lower()}@forceOrder")

            payload = {
                "method": "SUBSCRIBE",
                "params": force_order_streams,
                "id": 1
            }
            subscribe_liquidations_request: WSJSONRequest = WSJSONRequest(payload=payload)
            await ws.send(subscribe_liquidations_request)

            self.logger().info("Subscribed to public liquidations...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to public liquidations...",
                exc_info=True
            )
            raise

    async def _fetch_and_map_trading_pairs(self):
        rest_assistant = await self._api_factory.get_rest_assistant()
        exchange_info_url = f"{CONSTANTS.REST_URL}{CONSTANTS.EXCHANGE_INFO}"
        exchange_info = await rest_assistant.execute_request(
            url=exchange_info_url, throttler_limit_id=CONSTANTS.EXCHANGE_INFO
        )
        if exchange_info is not None:
            for symbol_data in exchange_info.get("symbols", []):
                exchange_symbol = symbol_data["pair"]
                base = symbol_data["baseAsset"]
                quote = symbol_data["quoteAsset"]
                trading_pair = combine_to_hb_trading_pair(base, quote)
                if trading_pair in self._trading_pairs_map.inverse:
                    self._resolve_trading_pair_symbols_duplicate(self._trading_pairs_map, exchange_symbol, base, quote)
                else:
                    self._trading_pairs_map[exchange_symbol] = trading_pair

            self.logger().info("Built trading-symbol pairs: %s", len(self._trading_pairs_map))
        else:
            raise RuntimeError("Exchange info was empty!")

    def _resolve_trading_pair_symbols_duplicate(self, mapping: bidict, new_exchange_symbol: str, base: str, quote: str):
        """Resolves name conflicts provoked by futures contracts.

        If the expected BASEQUOTE combination matches one of the exchange symbols, it is the one taken, otherwise,
        the trading pair is removed from the map and an error is logged.
        """
        expected_exchange_symbol = f"{base}{quote}"
        trading_pair = combine_to_hb_trading_pair(base, quote)
        current_exchange_symbol = mapping.inverse[trading_pair]
        if current_exchange_symbol == expected_exchange_symbol:
            pass
        elif new_exchange_symbol == expected_exchange_symbol:
            mapping.pop(current_exchange_symbol)
            mapping[new_exchange_symbol] = trading_pair
        else:
            self.logger().warning(
                f"Could not resolve the exchange symbols {new_exchange_symbol} and {current_exchange_symbol}")
            mapping.pop(current_exchange_symbol)

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
                "T":1568014460893,               // Order Trade Time
            }
        }
        """
        async for ws_response in websocket_assistant.iter_messages():
            data: Dict[str, Any] = ws_response.data
            if data.get("e") == "forceOrder":
                timestamp = int(data["o"]["T"])
                trading_pair = self._trading_pairs_map.get(data["o"]["s"])
                quantity = float(data["o"]["q"])
                price = float(data["o"]["ap"])
                side = data["o"]["S"]
                # SELL-Side means here, that a long position was forcefully liquidated and the other way round
                liquidation_side = LiquidationSide.LONG if side == "SELL" else LiquidationSide.SHORT

                if trading_pair not in self._liquidations:
                    self._liquidations[trading_pair] = []

                self._liquidations[trading_pair].append(Liquidation(
                    timestamp=timestamp,
                    trading_pair=trading_pair,
                    quantity=quantity,
                    price=price,
                    side=liquidation_side))
