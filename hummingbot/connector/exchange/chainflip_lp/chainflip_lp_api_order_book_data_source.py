import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.chainflip_lp import chainflip_lp_constants as CONSTANTS
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_formatter import DataFormatter
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_source import ChainflipLPDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_exchange import ChainflipLpExchange


class ChainflipLPAPIOrderBookDataSource(OrderBookTrackerDataSource):
    def __init__(
        self,
        trading_pairs: List[str],
        connector: "ChainflipLpExchange",
        data_source: "ChainflipLPDataSource",
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs=trading_pairs)
        self._ev_loop = asyncio.get_event_loop()
        self._connector = connector
        self._data_source = data_source
        self._domain = domain
        # self._forwarders = []
        # self._configure_event_forwarders()

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self._data_source.order_book_snapshot(trading_pair=trading_pair)
        return snapshot

    async def listen_for_subscriptions(self):
        pass

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise NotImplementedError

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WS_RPC_URLS[self._domain], ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the
        """
        try:
            all_assets = self._data_source.assets_list()
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                asset = DataFormatter.format_trading_pair(symbol, all_assets)
                payload = {
                    "id": 1,
                    "jsonrpc": "2.0",
                    "method": CONSTANTS.SCHEDULED_SWAPS,
                    "params": {"base_asset": asset["base_asset"], "quote_asset": asset["quote_asset"]},
                }
                subscribe_scheduled_swaps: WSJSONRequest = WSJSONRequest(payload=payload)
                await ws.send(subscribe_scheduled_swaps)

                self.logger().info(f"Subscribed to scheduled for {trading_pair}")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...", exc_info=True
            )
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        #
        return ""
