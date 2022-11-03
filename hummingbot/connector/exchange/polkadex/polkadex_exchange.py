import asyncio
import json
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from bidict import bidict
from gql import Client
from gql.transport.appsync_auth import AppSyncJWTAuthentication
from gql.transport.appsync_websockets import AppSyncWebsocketsTransport
from gql.transport.exceptions import TransportQueryError
from substrateinterface import Keypair, KeypairType, SubstrateInterface

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.polkadex import polkadex_constants as CONSTANTS, polkadex_utils as p_utils
from hummingbot.connector.exchange.polkadex.graphql.general.streams import websocket_streams_session_provided
from hummingbot.connector.exchange.polkadex.graphql.market.market import get_all_markets, get_recent_trades
from hummingbot.connector.exchange.polkadex.graphql.user.user import (
    cancel_order,
    find_order_by_main_account,
    get_all_balances_by_main_account,
    get_main_acc_from_proxy_acc,
    place_order,
)
from hummingbot.connector.exchange.polkadex.polkadex_auth import PolkadexAuth
from hummingbot.connector.exchange.polkadex.polkadex_constants import (
    POLKADEX_SS58_PREFIX,
    UPDATE_ORDER_STATUS_MIN_INTERVAL,
)
from hummingbot.connector.exchange.polkadex.polkadex_order_book_data_source import PolkadexOrderbookDataSource
from hummingbot.connector.exchange.polkadex.polkadex_payload import create_cancel_order_req, create_order
from hummingbot.connector.exchange.polkadex.polkadex_user_stream_data_source import PolkadexUserStreamDataSource
from hummingbot.connector.exchange.polkadex.polkadex_utils import convert_asset_to_ticker
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TradeFeeBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


def fee_levied_asset(side, base, quote):
    if side == "Bid":
        return base
    else:
        return quote


class PolkadexExchange(ExchangePyBase):
    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 polkadex_seed_phrase: str,
                 trading_required: bool = True,
                 trading_pairs: Optional[List[str]] = None):

        self.endpoint = CONSTANTS.GRAPHQL_ENDPOINT
        self.wss_url = CONSTANTS.GRAPHQL_WSS_ENDPOINT
        self.api_key = CONSTANTS.GRAPHQL_API_KEY
        host = str(urlparse(self.endpoint).netloc)
        self.host = host

        self._trading_pairs = trading_pairs
        self.is_trading_required_flag = trading_required
        if self.is_trading_required_flag:
            self.proxy_pair = Keypair.create_from_mnemonic(polkadex_seed_phrase,
                                                           POLKADEX_SS58_PREFIX,
                                                           KeypairType.SR25519)
            self.user_proxy_address = self.proxy_pair.ss58_address
            self.auth = AppSyncJWTAuthentication(host, self.user_proxy_address)

        self.user_main_address = None
        self.nonce = 0  # TODO: We need to fetch the nonce from enclave
        self.event_id = 0  # Tracks the event_id from websocket messages
        custom_types = {
            "runtime_id": 1,
            "versioning": [
            ],
            "types": {
                "OrderPayload": {
                    "type": "struct",
                    "type_mapping": [
                        ["client_order_id", "H256"],
                        ["user", "AccountId"],
                        ["main_account", "AccountId"],
                        ["pair", "String"],
                        ["side", "OrderSide"],
                        ["order_type", "OrderType"],
                        ["quote_order_quantity", "String"],
                        ["qty", "String"],
                        ["price", "String"],
                        ["timestamp", "i64"],
                    ]
                },
                "CancelOrderPayload": {
                    "type": "struct",
                    "type_mapping": [
                        ["id", "String"]
                    ]},
                "TradingPair": {
                    "type": "struct",
                    "type_mapping": [
                        ["base_asset", "AssetId"],
                        ["quote_asset", "AssetId"],
                    ]
                },
                "OrderSide": {
                    "type": "enum",
                    "type_mapping": [
                        ["Ask", "Null"],
                        ["Bid", "Null"],
                    ],
                },
                "AssetId": {
                    "type": "enum",
                    "type_mapping": [
                        ["asset", "u128"],
                        ["polkadex", "Null"],
                    ],
                },
                "OrderType": {
                    "type": "enum",
                    "type_mapping": [
                        ["LIMIT", "Null"],
                        ["MARKET", "Null"],
                    ],
                },
                "EcdsaSignature": "[u8; 65]",
                "Ed25519Signature": "H512",
                "Sr25519Signature": "H512",
                "AnySignature": "H512",
                "MultiSignature": {
                    "type": "enum",
                    "type_mapping": [
                        [
                            "Ed25519",
                            "Ed25519Signature"
                        ],
                        [
                            "Sr25519",
                            "Sr25519Signature"
                        ],
                        [
                            "Ecdsa",
                            "EcdsaSignature"
                        ]
                    ]
                },
            }
        }
        self.blockchain = SubstrateInterface(
            url="wss://blockchain.polkadex.trade",
            ss58_format=POLKADEX_SS58_PREFIX,
            type_registry=custom_types
        )
        super().__init__(client_config_map)

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        raise NotImplementedError

    def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        raise NotImplementedError

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        raise NotImplementedError

    def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        raise NotImplementedError

    @property
    def authenticator(self):
        return PolkadexAuth(api_key=self.api_key)

    @property
    def domain(self):
        return None

    @property
    def client_order_id_max_length(self):
        return 32

    @property
    def client_order_id_prefix(self):
        return "HBOT"

    # we don't need it as we will do it in _format_trading_rules
    @property
    def trading_rules_request_path(self):
        return None

    @property
    def trading_pairs_request_path(self):
        raise NotImplementedError

    @property
    def check_network_request_path(self):
        raise NotImplementedError

    @property
    def is_trading_required(self) -> bool:
        return self.is_trading_required_flag

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def name(self) -> str:
        return "polkadex"

    async def _update_trading_rules(self):
        trading_rules_list = await self._format_trading_rules({})
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule
        await self._initialize_trading_pair_symbol_map()

    async def _update_time_synchronizer(self):
        pass

    async def check_network(self) -> NetworkStatus:
        return NetworkStatus.CONNECTED

    # TODO Define these Exceptions
    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        # TODO; Convert client_order_id to enclave_order_id
        if tracked_order.exchange_order_id is not None:
            try:
                encoded_cancel_req = create_cancel_order_req(self.blockchain, tracked_order.exchange_order_id)
            except Exception:
                return False
            try:
                signature = self.proxy_pair.sign(encoded_cancel_req)
                params = [tracked_order.exchange_order_id, self.user_proxy_address, tracked_order.trading_pair,
                          {"Sr25519": signature.hex()}]
            except Exception:
                return False
            try:
                await cancel_order(params, self.user_proxy_address)
            except Exception:
                return False
            return True
        else:
            return False

    async def _place_order(self, order_id: str, trading_pair: str, amount: Decimal, trade_type: TradeType,
                           order_type: OrderType, price: Decimal, **kwargs) -> Tuple[str, float]:
        try:
            try:
                if self.user_main_address is None:
                    self.user_main_address = await get_main_acc_from_proxy_acc(self.user_proxy_address,
                                                                               self.user_proxy_address)
            except Exception:
                raise Exception("Main account not found")

            ts = int(time.time())
            try:
                # converting to type GQL can understand
                encoded_order, order = create_order(self.blockchain, price, amount, order_type, order_id,
                                                    trade_type, self.user_proxy_address, self.user_main_address,
                                                    trading_pair.split("-")[0],
                                                    trading_pair.split("-")[1],
                                                    int(time.time()))
            except Exception:
                raise Exception("Unable to create encoded order")
            try:
                signature = self.proxy_pair.sign(encoded_order)
                params = [order, {"Sr25519": signature.hex()}]
            except Exception:
                raise Exception("Unable to create signature")
            try:
                result = await place_order(params, self.user_proxy_address)
                if result is not None:
                    return result, ts
                else:
                    raise Exception("Exchange result none")
            except TransportQueryError:
                self.logger().error("TransportQuery Error for id: ", order_id)
                raise Exception("Transport Query Error")
        except Exception as e:
            print("Inside Main Exception : ", e)

    def _get_fee(self, base_currency: str, quote_currency: str, order_type: OrderType, order_side: TradeType,
                 amount: Decimal, price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    # ToDo: Need to change balance parsing
    def balance_update_callback(self, message):
        """ Expected message structure
            {
                "type": "SetBalance"
                "event_id":0,
                "user":"5C62Ck4UrFPiBtoCmeSrgF7x9yv9mn38446dhCpsi2mLHiFT",
                "asset":"polkadex",
                "free":0,
                "pending_withdrawal":0,
                "reserved":0
            }

        """
        # print("Balance Update call: ",message)
        asset_name = convert_asset_to_ticker(message["asset"])
        free_balance = p_utils.parse_price_or_qty(message["free"])
        total_balance = p_utils.parse_price_or_qty(message["free"]) + p_utils.parse_price_or_qty(message["reserved"])
        self._account_available_balances[asset_name] = free_balance
        self._account_balances[asset_name] = total_balance

    def order_update_callback(self, message):
        """ Expected message structure
        {
                "type": "Order"
                "event_id":10,
                "client_order_id":"",
                "avg_filled_price":10,
                "fee":100,
                "filled_quantity":100,
                "status":"OPEN",
                "id":0,
                "user":"5C62Ck4UrFPiBtoCmeSrgF7x9yv9mn38446dhCpsi2mLHiFT",
                "pair":{"base_asset":"polkadex","quote_asset":{"asset":1}},
                "side":"Ask",
                "order_type":"LIMIT",
                "qty":10,
                "price":10,
                "quote_order_qty":0,
                "timestamp": 11
        }
        """
        encoded_client_order_id = message["client_order_id"]
        encoded_client_order_id = encoded_client_order_id[2:]
        encoded_client_order_id = bytes.fromhex(encoded_client_order_id)
        encoded_client_order_id = encoded_client_order_id.decode()

        ts = time.time()
        tracked_order = self.in_flight_orders.get(encoded_client_order_id)
        if tracked_order is not None:
            order_update = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=ts,
                new_state=CONSTANTS.ORDER_STATE[message["status"]],
                client_order_id=encoded_client_order_id,
                exchange_order_id=str(message["id"]),
            )
            self._order_tracker.process_order_update(order_update=order_update)
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=self.trade_fee_schema(),
                trade_type=TradeType.SELL,
            )
            trade_update = TradeUpdate(
                trade_id=str(ts),  # TODO: Add trade id to event
                client_order_id=encoded_client_order_id,
                exchange_order_id=str(message["id"]),
                trading_pair=tracked_order.trading_pair,
                fee=fee,
                fill_base_amount=Decimal(message["filled_quantity"]),
                fill_quote_amount=(Decimal(message["filled_quantity"])) * (
                    Decimal(message["avg_filled_price"])),
                fill_price=Decimal(message["avg_filled_price"]),
                fill_timestamp=ts,
            )
            self._order_tracker.process_trade_update(trade_update)

    async def _update_trading_fees(self):
        pass

    # ToDo: If above two functions (balance/update) are change here
    def handle_websocket_message(self, message, _value):
        """
        {
            'websocket_streams': {
            'data': {'type': 'SetBalance',
            'event_id': 0, 'user': '5C62Ck4UrFPiBtoCmeSrgF7x9yv9mn38446dhCpsi2mLHiFT',
             'asset': 'polkadex', 'free': 0, 'pending_withdrawal': 0, 'reserved': 0}
             }

        }
        """
        message = message["websocket_streams"]["data"]
        message = json.loads(message)

        if "SetBalance" in message["type"]:
            self.balance_update_callback(message)
        elif "Order" in message["type"]:
            self.order_update_callback(message)
        else:
            pass

    async def _user_stream_event_listener(self):
        if self.user_main_address is None:
            self.user_main_address = await get_main_acc_from_proxy_acc(self.user_proxy_address,
                                                                       self.user_proxy_address)
        transport = AppSyncWebsocketsTransport(url=self.endpoint, auth=self.auth)
        tasks = []
        try:
            async with Client(transport=transport, fetch_schema_from_transport=False) as session:
                tasks.append(
                    asyncio.create_task(
                        websocket_streams_session_provided(self.user_main_address, session,
                                                           self.handle_websocket_message
                                                           )
                    ))
                tasks.append(
                    asyncio.create_task(
                        websocket_streams_session_provided(self.user_proxy_address, session,
                                                           self.handle_websocket_message
                                                           )
                    ))

                await asyncio.wait(tasks)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error in user stream listener loop.", exc_info=True)

    # ToDo: Trading rules parsing also needs to be change
    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
        "data": {
            "getAllMarkets": {
            "items": [
                {
                "market": "PDEX-1",
                "max_order_qty": "1000000000000000",
                "max_price": "1000000000000000",
                "min_order_qty": "1000000000000",
                "min_price": "1000000000000",
                "price_tick_size": "1",
                "qty_step_size": "1",
                "quote_asset_precision": "8"
                },
                {
                "market": "PDEX-2",
                "max_order_qty": "1000000000000000",
                "max_price": "1000000000000000",
                "min_order_qty": "1000000000000",
                "min_price": "1000000000000",
                "price_tick_size": "1",
                "qty_step_size": "1",
                "quote_asset_precision": "8"
                }
            ]
            }
        }
        }
        """
        markets_data = await get_all_markets("RandomString")
        rules = []
        for market in markets_data:
            # TODO: Update this with a real endpoint and config
            rules.append(TradingRule(market["market"],
                                     min_order_size=Decimal(market["min_order_qty"]),  # ToDo: Fix this
                                     max_order_size=Decimal(market["max_order_qty"]),
                                     min_price_increment=Decimal(market["price_tick_size"]),
                                     min_base_amount_increment=Decimal(market["qty_step_size"]),
                                     min_quote_amount_increment=Decimal(market["price_tick_size"]) * Decimal(
                                         market["qty_step_size"]),
                                     max_price_significant_digits=Decimal(8)
                                     ))
        return rules

    async def _update_order_status(self):
        if self.user_main_address is None:
            self.user_main_address = await get_main_acc_from_proxy_acc(self.user_proxy_address,
                                                                       self.user_proxy_address)
        last_tick = self._last_poll_timestamp / UPDATE_ORDER_STATUS_MIN_INTERVAL
        current_tick = self.current_timestamp / UPDATE_ORDER_STATUS_MIN_INTERVAL

        tracked_orders: List[InFlightOrder] = list(self.in_flight_orders.values())
        if current_tick > last_tick and len(tracked_orders) > 0:

            for tracked_order in tracked_orders:
                if tracked_order.exchange_order_id is not None:
                    result = await find_order_by_main_account(self.user_proxy_address, tracked_order.exchange_order_id,
                                                              tracked_order.trading_pair,
                                                              self.user_proxy_address)
                    # TODO: Fix order update
                    if result is None:
                        self.logger().network(
                            f"Error fetching status update for the order {tracked_order.exchange_order_id}: {result}.",
                            app_warning_msg=f"Failed to fetch status update for the order {tracked_order.exchange_order_id}."
                        )
                        # Wait until the order not found error have repeated a few times before actually treating
                        # it as failed. See: https://github.com/CoinAlpha/hummingbot/issues/601
                        await self._order_tracker.process_order_not_found(tracked_order.client_order_id)

                    else:
                        new_state = CONSTANTS.ORDER_STATE[result["st"]]
                        ts = result["t"]
                        update = OrderUpdate(
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=str(tracked_order.exchange_order_id),
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=ts,
                            new_state=new_state,
                        )
                        self._order_tracker.process_order_update(update)
                else:
                    try:
                        tracked_order.exchange_order_id = await tracked_order.get_exchange_order_id()
                    except asyncio.TimeoutError:
                        self.logger().debug(
                            f"Tracked order {tracked_order.client_order_id} does not have an exchange id. "
                            f"Attempting fetch in next polling interval."
                        )
                        await self._order_tracker.process_order_not_found(tracked_order.client_order_id)

    # ToDo: Balances parsing also needs to be change
    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        if self.user_main_address is None:
            self.user_main_address = await get_main_acc_from_proxy_acc(self.user_proxy_address,
                                                                       self.user_proxy_address)
        balances = await get_all_balances_by_main_account(self.user_main_address, self.user_proxy_address)

        """
      [
        {
          "a": "PDEX",
          "f": "0.10",
          "r": "0.001"
        }
      ]
        """

        for balance_entry in balances:
            asset_name = balance_entry["a"]
            free_balance = p_utils.parse_price_or_qty(balance_entry["f"])
            total_balance = p_utils.parse_price_or_qty(balance_entry["f"]) + p_utils.parse_price_or_qty(
                balance_entry["r"])

            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        api_factory = WebAssistantsFactory(throttler=self._throttler, auth=self._auth)
        return api_factory

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return PolkadexOrderbookDataSource(trading_pairs=self.trading_pairs,
                                           connector=self,
                                           api_factory=self._web_assistants_factory,
                                           api_key=self.api_key)

    def _create_user_stream_data_source(self):
        return PolkadexUserStreamDataSource(trading_pairs=self.trading_pairs,
                                            connector=self,
                                            api_factory=self._web_assistants_factory)

    async def _initialize_trading_pair_symbol_map(self):
        # We are using Random Token for general GQL queries such as get_all_markets
        markets = await get_all_markets("Random Token")
        mapping = bidict()
        for market in markets:
            base = market["market"].split("-")[0]
            quote = market["market"].split("-")[1]
            mapping[market["market"]] = combine_to_hb_trading_pair(base=base, quote=quote)
        self._set_trading_pair_symbol_map(mapping)

    def c_stop_tracking_order(self, order_id):
        raise NotImplementedError

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        recent_trade = await get_recent_trades(trading_pair, 1, None, self.user_proxy_address)
        return p_utils.parse_price_or_qty(recent_trade[0]["p"])
