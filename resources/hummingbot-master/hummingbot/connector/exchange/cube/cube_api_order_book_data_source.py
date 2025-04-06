import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.cube import cube_constants as CONSTANTS, cube_web_utils as web_utils
from hummingbot.connector.exchange.cube.cube_order_book import CubeOrderBook
from hummingbot.connector.exchange.cube.cube_ws_protobufs import market_data_pb2
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSBinaryRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.cube.cube_exchange import CubeExchange


class CubeAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'CubeExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._snapshot_messages_queue_key = CONSTANTS.SNAPSHOT_EVENT_TYPE
        self._domain = domain
        self._api_factory = api_factory

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        params = {
            "mbp": "true",
            "levels": 1000
        }

        try:
            market_id = await self._connector.exchange_market_id_associated_to_pair(trading_pair=trading_pair)
            rest_assistant = await self._api_factory.get_rest_assistant()
            data = await rest_assistant.execute_request(
                url=web_utils.public_rest_url(
                    path_url=CONSTANTS.MARKET_DATA_REQUEST_URL + f"/book/{market_id}/snapshot",
                    domain=self._domain),
                params=params,
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.SNAPSHOT_LM_ID,
            )
        except Exception as e:
            self.logger().error(f"Error fetching order book snapshot for {trading_pair}: {e}")
            return {}

        return data

    async def _subscribe_channels(self, ws: WSAssistant):
        pass

    async def _connected_websocket_assistant(self) -> WSAssistant:
        pass

    async def _connected_websocket_assistant_for_pair(self, trading_pair: str) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()

        market_id = await self._connector.exchange_market_id_associated_to_pair(trading_pair=trading_pair)

        await ws.connect(
            ws_url=f"{CONSTANTS.WSS_MARKET_DATA_URL.get(self._domain)}/book/{market_id}?mbp=true&trades=true",
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)

        self.logger().info(f"Subscribed to public order book for {trading_pair} and trade channels...")

        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = snapshot["result"]["lastTransactTime"]

        price_scaler = await self._connector.get_price_scaler(trading_pair)
        quantity_scaler = await self._connector.get_quantity_scaler(trading_pair)

        snapshot_msg: OrderBookMessage = CubeOrderBook.snapshot_message_from_exchange(
            msg=snapshot,
            timestamp=snapshot_timestamp,
            metadata={"trading_pair": trading_pair},
            price_scaler=price_scaler,
            quantity_scaler=quantity_scaler,
        )

        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = raw_message["trading_pair"]
        trades: market_data_pb2.Trades = raw_message["trades"]
        trade: market_data_pb2.Trades.Trade

        price_scaler = await self._connector.get_price_scaler(trading_pair)
        quantity_scaler = await self._connector.get_quantity_scaler(trading_pair)

        for trade in trades.trades:
            msg = {
                "trading_pair": trading_pair,
                "price": price_scaler * trade.price,
                "fill_quantity": quantity_scaler * trade.fill_quantity,
                "transact_time": trade.transact_time,
                "trade_id": trade.tradeId,
                "trade_type": float(
                    TradeType.SELL.value) if trade.aggressing_side == market_data_pb2.Side.ASK else float(
                    TradeType.BUY.value),
                "timestamp": time.time(),
            }

            trade_message = CubeOrderBook.trade_message_from_exchange(msg)
            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = raw_message["trading_pair"]
        diff_msg: market_data_pb2.MarketByPriceDiff = raw_message["mbp_diff"]
        # mbp_diff = market_data_pb2.MarketByPriceDiff().From
        # ParseDict(diff_msg, mbp_diff)
        diff: market_data_pb2.MarketByPriceDiff.Diff

        price_scaler = await self._connector.get_price_scaler(trading_pair)
        quantity_scaler = await self._connector.get_quantity_scaler(trading_pair)

        # Catch if diffs is not iterable
        if not hasattr(diff_msg, 'diffs'):
            self.logger().warning(f"Diff message does not contain diffs: {diff_msg}")
            return

        for diff in diff_msg.diffs:
            asks: List[OrderBookRow] = [OrderBookRow(0, 0, 0) for _ in range(0)]
            bids: List[OrderBookRow] = [OrderBookRow(0, 0, 0) for _ in range(0)]
            price = diff.price * price_scaler
            qty = diff.quantity * quantity_scaler
            update_id = int(time.time_ns())

            match diff.op:
                case market_data_pb2.MarketByPriceDiff.REMOVE:
                    if diff.side == market_data_pb2.ASK:
                        row = OrderBookRow(price, 0, update_id)
                        asks.append(row)
                    else:
                        row = OrderBookRow(price, 0, update_id)
                        bids.append(row)
                case market_data_pb2.MarketByPriceDiff.REPLACE:
                    if diff.side == market_data_pb2.ASK:
                        row = OrderBookRow(price, qty, update_id)
                        asks.append(row)
                    else:
                        row = OrderBookRow(price, qty, update_id)
                        bids.append(row)
            msg = {"trading_pair": trading_pair, "update_id": update_id, "bids": bids, "asks": asks}

            order_book_message: OrderBookMessage = CubeOrderBook.diff_message_from_exchange(
                msg, time.time())
            message_queue.put_nowait(order_book_message)

    async def _process_websocket_messages_for_pair(self, websocket_assistant: WSAssistant, trading_pair: str):
        async def handle_heartbeat():
            send_hb = True
            while send_hb:
                await asyncio.sleep(CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
                hb = market_data_pb2.Heartbeat(
                    request_id=0,
                    timestamp=time.time_ns(),
                )
                hb_request: WSBinaryRequest = WSBinaryRequest(
                    payload=market_data_pb2.ClientMessage(heartbeat=hb).SerializeToString())
                try:
                    await websocket_assistant.send(hb_request)
                except asyncio.CancelledError:
                    send_hb = False
                except ConnectionError:
                    send_hb = False
                except RuntimeError:
                    send_hb = False

        async def handle_messages():
            data: market_data_pb2.MdMessages
            async for ws_response in websocket_assistant.iter_messages():
                data = market_data_pb2.MdMessages().FromString(ws_response.data)
                if data is not None:  # data will be None when the websocket is disconnected
                    for md_msg in data.messages:
                        field = md_msg.WhichOneof('inner')
                        if field == CONSTANTS.DIFF_EVENT_TYPE:
                            diff_data = md_msg.mbp_diff
                            self._message_queue[CONSTANTS.DIFF_EVENT_TYPE].put_nowait(
                                {"trading_pair": trading_pair, "mbp_diff": diff_data})
                        elif field == CONSTANTS.TRADE_EVENT_TYPE:
                            trade_data = md_msg.trades
                            self._message_queue[CONSTANTS.TRADE_EVENT_TYPE].put_nowait(
                                {"trading_pair": trading_pair, "trades": trade_data})

        tasks = [handle_heartbeat(), handle_messages()]
        await safe_gather(*tasks)

    async def listen_for_subscriptions(self):
        """
        Connects to the trade events and order diffs websocket endpoints and listens to the messages sent by the
        exchange. Each message is stored in its own queue.
        """

        async def handle_subscription(trading_pair):
            ws: Optional[WSAssistant] = None
            while True:
                try:
                    ws: WSAssistant = await self._connected_websocket_assistant_for_pair(trading_pair=trading_pair)
                    await self._process_websocket_messages_for_pair(websocket_assistant=ws, trading_pair=trading_pair)
                except asyncio.CancelledError:
                    raise
                except ConnectionError as connection_exception:
                    self.logger().warning(
                        f"The websocket connection to {trading_pair} was closed ({connection_exception})")
                except Exception:
                    self.logger().exception(
                        "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds...",
                    )
                    await self._sleep(1.0)
                finally:
                    await self._on_order_stream_interruption(websocket_assistant=ws)

        tasks = [handle_subscription(trading_pair) for trading_pair in self._trading_pairs]
        await safe_gather(*tasks)
