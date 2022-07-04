import asyncio
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse
from dateutil import parser

from gql import Client
from gql.transport.appsync_auth import AppSyncApiKeyAuthentication
from gql.transport.appsync_websockets import AppSyncWebsocketsTransport

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.polkadex.graphql.market.market import get_recent_trades
from hummingbot.connector.exchange.polkadex.graphql.user.streams import on_balance_update, on_order_update
from hummingbot.connector.exchange.polkadex.graphql.user.user import get_all_balances_by_main_account, \
    get_main_acc_from_proxy_acc, find_order_by_main_account
from hummingbot.connector.exchange.polkadex.polkadex_constants import MIN_PRICE, MIN_QTY, POLKADEX_SS58_PREFIX, \
    UPDATE_ORDER_STATUS_MIN_INTERVAL
from hummingbot.connector.exchange.polkadex.polkadex_order_book_data_source import PolkadexOrderbookDataSource
from hummingbot.connector.exchange.polkadex import polkadex_constants as CONSTANTS
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TradeFeeBase, TokenAmount, \
    DeductedFromReturnsTradeFee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from substrateinterface import Keypair, KeypairType, SubstrateInterface


def fee_levied_asset(side, base, quote):
    if side == "Bid":
        return base
    else:
        return quote


class PolkadexExchange(ExchangePyBase):
    @property
    def authenticator(self):
        return None

    @property
    def domain(self):
        return None

    @property
    def client_order_id_max_length(self):
        return None

    @property
    def client_order_id_prefix(self):
        return None

    @property
    def trading_rules_request_path(self):
        return None

    @property
    def trading_pairs_request_path(self):
        return None

    @property
    def check_network_request_path(self):
        return None

    @property
    def is_trading_required(self) -> bool:
        return True

    def __init__(self, endpoint: str, api_key: str, seed_hex: str, trading_pairs: Optional[List[str]] = None):
        self.endpoint = endpoint
        self.api_key = api_key
        self._trading_pairs = trading_pairs
        self._last_trades_poll_binance_timestamp = 1.0
        self.host = str(urlparse(endpoint).netloc)
        self.auth = AppSyncApiKeyAuthentication(host=self.host, api_key=self.api_key)
        self.proxy_pair = Keypair.create_from_seed(seed_hex, POLKADEX_SS58_PREFIX, KeypairType.SR25519)
        self.user_proxy_address = self.proxy_pair.ss58_address
        self.user_main_address = await get_main_acc_from_proxy_acc(self.user_proxy_address, self.endpoint, self.api_key)
        custom_types = {
            "OrderPayload": {
                "user": "AccountId",
                "pair": "TradingPair",
                "side": "OrderSide",
                "order_type": "OrderType",
                "qty": "u128",
                "price": "u128",
                "nonce": "u32",
            },
            "CancelOrderPayload": {"id": "String"},
            "TradingPair": {
                "base_asset": "AssetId",
                "quote_asset": "AssetId",
            },
            "OrderSide": {
                "_enum": {
                    "Ask": None,
                    "Bid": None,
                },
            },
            "OrderType": {
                "_enum": {
                    "LIMIT": None,
                    "MARKET": None,
                },
            }
        }
        self.blockchain = SubstrateInterface(
            url="wss://blockchain.polkadex.trade",
            ss58_format=POLKADEX_SS58_PREFIX,
            type_registry=custom_types
        )
        super().__init__()

    @property
    def rate_limits_rules(self):
        return None

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    def name(self):
        return "polkadex"

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        pass

    async def _place_order(self, order_id: str, trading_pair: str, amount: Decimal, trade_type: TradeType,
                           order_type: OrderType, price: Decimal) -> Tuple[str, float]:


        pass

    def _get_fee(self, base_currency: str, quote_currency: str, order_type: OrderType, order_side: TradeType,
                 amount: Decimal, price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    def balance_update_callback(self, message):
        """ Expected message structure
        {
  "data": {
    "onBalanceUpdate": {
      "asset": "PDEX",
      "free": "0.10",
      "main_account": "eskmPnwDNLNCuZKa3aWuvNS6PshJoKsgBtwbdxyyipS2F2TR5",
      "pending_withdrawal": "0.00001",
      "reserved": "0.001"
                    }
            }
        }
        """

        message = message["data"]["onBalanceUpdate"]
        asset_name = message["asset"]
        free_balance = Decimal(message["free"])
        total_balance = Decimal(message["free"]) + Decimal(message["reserved"])
        self._account_available_balances[asset_name] = free_balance
        self._account_balances[asset_name] = total_balance

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

    async def _update_trading_fees(self):
        pass

    async def _user_stream_event_listener(self):
        transport = AppSyncWebsocketsTransport(url=self.endpoint, auth=self.auth)
        tasks = []
        async with Client(transport=transport, fetch_schema_from_transport=False) as session:
            tasks.append(
                asyncio.create_task(on_balance_update(self.user_main_address, session, self.balance_update_callback)))
            tasks.append(
                asyncio.create_task(on_order_update(self.user_main_address, session, self.order_update_callback)))
            await asyncio.wait(tasks)

    def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        rules = []
        for market in self.trading_pairs:
            # TODO: Update this with a real endpoint and config
            rules.append(TradingRule(market,
                                     min_order_size=MIN_QTY,
                                     min_price_increment=MIN_PRICE,
                                     min_base_amount_increment=MIN_QTY,
                                     min_notional_size=MIN_PRICE * MIN_QTY))
        return rules

    def _update_order_status(self):
        last_tick = self._last_poll_timestamp / UPDATE_ORDER_STATUS_MIN_INTERVAL
        current_tick = self.current_timestamp / UPDATE_ORDER_STATUS_MIN_INTERVAL

        tracked_orders: List[InFlightOrder] = list(self.in_flight_orders.values())
        if current_tick > last_tick and len(tracked_orders) > 0:

            for tracked_order in tracked_orders:
                result = await find_order_by_main_account(self.user_main_address, tracked_order.client_order_id,
                                                          tracked_order.trading_pair)

                if isinstance(result, Exception):
                    self.logger().network(
                        f"Error fetching status update for the order {tracked_order.client_order_id}: {result}.",
                        app_warning_msg=f"Failed to fetch status update for the order {tracked_order.client_order_id}."
                    )
                    # Wait until the order not found error have repeated a few times before actually treating
                    # it as failed. See: https://github.com/CoinAlpha/hummingbot/issues/601
                    await self._order_tracker.process_order_not_found(tracked_order.client_order_id)

                else:
                    # Update order execution status
                    new_state = CONSTANTS.ORDER_STATE[result["status"]]
                    ts = parser.parse(result["time"]).timestamp()
                    update = OrderUpdate(
                        client_order_id=tracked_order.client_order_id,
                        exchange_order_id=str(tracked_order.client_order_id),
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=ts,
                        new_state=new_state,
                    )
                    self._order_tracker.process_order_update(update)

    def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        balances = await get_all_balances_by_main_account(self.user_main_address, self.endpoint, self.api_key)
        """
      [
        {
          "asset": "PDEX",
          "free": "0.10",
          "pending_withdrawal": "0.00001",
          "reserved": "0.001"
        }
      ]
        """

        for balance_entry in balances:
            asset_name = balance_entry["asset"]
            free_balance = Decimal(balance_entry["free"])
            total_balance = Decimal(balance_entry["free"]) + Decimal(balance_entry["reserved"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        pass

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return PolkadexOrderbookDataSource(trading_pairs=self.trading_pairs,
                                           endpoint=self.endpoint,
                                           api_key=self.api_key)

    def _create_user_stream_data_source(self):
        pass

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        pass

    def c_stop_tracking_order(self, order_id):
        pass

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        recent_trade = await get_recent_trades(trading_pair, 1, None, self.endpoint, self.api_key)
        return float(recent_trade[0]["p"])
