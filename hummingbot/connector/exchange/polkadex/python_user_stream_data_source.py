import asyncio
from typing import List, TYPE_CHECKING

from dateutil.parser import parser
from gql import Client
from gql.transport.appsync_websockets import AppSyncWebsocketsTransport

from hummingbot.connector.exchange.polkadex import polkadex_constants as CONSTANTS
from hummingbot.connector.exchange.polkadex.graphql.user.streams import on_balance_update, on_order_update
from hummingbot.connector.exchange.polkadex.graphql.user.user import get_main_acc_from_proxy_acc
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.exchange.polkadex.polkadex_exchange import PolkadexExchange


class PolkadexUserStreamDataSource(UserStreamTrackerDataSource):

    def __init__(self, trading_pairs: List[str],
                 connector: 'PolkadexExchange',
                 api_factory: WebAssistantsFactory, ):
        super().__init__()
        self._api_factory = api_factory
        self._connector = connector
        self._trading_pairs = trading_pairs

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        print("Connecting to websocket user for user streams: ", self._connector.wss_url)
        await ws.connect(ws_url=self._connector.wss_url, ping_timeout=CONSTANTS.WS_PING_INTERVAL)
        return ws

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def listen_for_user_stream(self, output: asyncio.Queue):
        if self._connector.user_main_address is None:
            self._connector.user_main_address = await get_main_acc_from_proxy_acc(self._connector.user_proxy_address, self._connector.endpoint,
                                                                       self._connector.api_key)
        transport = AppSyncWebsocketsTransport(url=self._connector.endpoint, auth=self.auth)
        tasks = []
        async with Client(transport=transport, fetch_schema_from_transport=False) as session:
            tasks.append(
                asyncio.create_task(on_balance_update(self.user_main_address, session, self.balance_update_callback)))
            tasks.append(
                asyncio.create_task(on_order_update(self._connector.user_main_address, session, self.order_update_callback)))
            await asyncio.wait(tasks)

    def order_update_callback(self, message):
            """ Expected message structure

            {
      "data": {
        "onOrderUpdate": {
          "avg_filled_price": "0.10",
          "fee": "0.00000001",
          "filled_quantity": "0.01",
          "id": "1234567889",
          "m": "PDEX-100",
          "order_type": "LIMIT",
          "price": "0.10",
          "qty": "0.10",
          "side": "Bid",
          "status": "OPEN",
          "time": "2022-07-04T13:56:21.390508+00:00"
        }
      }
    }
            """
            message = message["data"]["onOrderUpdate"]
            print("trading pair split", message["m"])
            base_asset = message["m"].split("-")[0]
            quote_asset = message["m"].split("-")[1]

            ts = parser.parse(message["time"]).timestamp()
            tracked_order = self.in_flight_orders.get(message["id"])
            if tracked_order is not None:
                order_update = OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=ts,
                    new_state=CONSTANTS.ORDER_STATE[message["status"]],
                    client_order_id=message["id"],
                    exchange_order_id=str(message["id"]),
                )
                self._order_tracker.process_order_update(order_update=order_update)

                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=tracked_order.trade_type,
                    percent_token=message["fee"],
                    flat_fees=[TokenAmount(amount=Decimal(message["fee"]),
                                           token=fee_levied_asset(message["side"], base_asset, quote_asset))]
                )
                trade_update = TradeUpdate(
                    trade_id=str(ts),  # TODO: Add trade id to event
                    client_order_id=message["id"],
                    exchange_order_id=str(message["id"]),
                    trading_pair=tracked_order.trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(message["filled_quantity"]),
                    fill_quote_amount=Decimal(message["filled_quantity"]) * Decimal(message["avg_filled_price"]),
                    fill_price=Decimal(message["avg_filled_price"]),
                    fill_timestamp=ts,
                )
                self._order_tracker.process_trade_update(trade_update)
