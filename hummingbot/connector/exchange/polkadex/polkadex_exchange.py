import asyncio
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from bidict import bidict
from dateutil import parser
from gql import Client
from gql.transport.appsync_auth import AppSyncApiKeyAuthentication
from gql.transport.appsync_websockets import AppSyncWebsocketsTransport
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.network_iterator import NetworkStatus
from substrateinterface import Keypair, KeypairType, SubstrateInterface

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.polkadex import polkadex_constants as CONSTANTS
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
    MIN_PRICE,
    MIN_QTY,
    POLKADEX_SS58_PREFIX,
    UPDATE_ORDER_STATUS_MIN_INTERVAL, UNIT_BALANCE,
)
from hummingbot.connector.exchange.polkadex.polkadex_order_book_data_source import PolkadexOrderbookDataSource
from hummingbot.connector.exchange.polkadex.polkadex_payload import create_cancel_order_req, create_order
from hummingbot.connector.exchange.polkadex.polkadex_utils import convert_asset_to_ticker, convert_pair_to_market
from hummingbot.connector.exchange.polkadex.python_user_stream_data_source import PolkadexUserStreamDataSource
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def fee_levied_asset(side, base, quote):
    if side == "Bid":
        return base
    else:
        return quote


class PolkadexExchange(ExchangePyBase):
    def __init__(self, polkadex_seed_phrase: str,
                 trading_required: bool = True,
                 trading_pairs: Optional[List[str]] = None):

        self.endpoint = CONSTANTS.GRAPHQL_ENDPOINT
        self.wss_url = CONSTANTS.GRAPHQL_WSS_ENDPOINT
        self.api_key = CONSTANTS.GRAPHQL_API_KEY
        # Extract host from url
        host = str(urlparse(self.endpoint).netloc)
        self.auth = AppSyncApiKeyAuthentication(host=host, api_key=self.api_key)
        self._trading_pairs = trading_pairs

        self.is_trading_required_flag = trading_required
        if self.is_trading_required_flag:
            self.proxy_pair = Keypair.create_from_mnemonic(polkadex_seed_phrase,
                                                           POLKADEX_SS58_PREFIX,
                                                           KeypairType.SR25519)
            self.user_proxy_address = self.proxy_pair.ss58_address
            print("trading account: ", self.user_proxy_address)
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
                        ["user", "AccountId"],
                        ["pair", "TradingPair"],
                        ["side", "OrderSide"],
                        ["order_type", "OrderType"],
                        ["qty", "u128"],
                        ["price", "u128"],
                        ["nonce", "u32"],
                        ["client_order_id", "H256"]
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
                        ["polkadex", "Null"],
                        ["asset", "u128"],
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
        print("Connecting to blockchain")
        self.blockchain = SubstrateInterface(
            url="wss://blockchain.polkadex.trade",
            ss58_format=POLKADEX_SS58_PREFIX,
            type_registry=custom_types
        )
        print("Blockchain connected: ", self.blockchain.get_chain_head())
        super().__init__()

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        raise NotImplementedError

    @property
    def authenticator(self):
        return PolkadexAuth(api_key=self.api_key)

    @property
    def domain(self):
        return None

    @property
    def client_order_id_max_length(self):
        return 36

    @property
    def client_order_id_prefix(self):
        return "HBOT"

    @property
    def trading_rules_request_path(self):
        raise NotImplementedError

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
        trading_rules_list = self._format_trading_rules({})
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule
        await self._initialize_trading_pair_symbol_map()

    async def _update_time_synchronizer(self):
        print("Bypassing setting time from server, fix this later")
        pass

    async def check_network(self) -> NetworkStatus:
        return NetworkStatus.CONNECTED

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        # TODO; Convert client_order_id to enclave_order_id
        print("Cancelling orders...")
        encoded_cancel_req = create_cancel_order_req(self.blockchain, order_id)
        signature = self.proxy_pair.sign(encoded_cancel_req)
        params = [encoded_cancel_req, signature]
        await cancel_order(params)

    async def _place_order(self, order_id: str, trading_pair: str, amount: Decimal, trade_type: TradeType,
                           order_type: OrderType, price: Decimal) -> Tuple[str, float]:

        if self.user_main_address is None:
            self.user_main_address = await get_main_acc_from_proxy_acc(self.user_proxy_address,
                                                                       self.endpoint, self.api_key)
            print("Main account: ", self.user_main_address)
        encoded_order, order = create_order(self.blockchain, price, amount, order_type,
                                            trade_type, self.user_proxy_address,
                                            trading_pair.split("-")[0],
                                            trading_pair.split("-")[1],
                                            self.nonce)
        signature = self.proxy_pair.sign(encoded_order)
        params = [order, {"Sr25519": signature.hex()}]
        result = await place_order(params)
        return result["st"], result["cid"]

    def _get_fee(self, base_currency: str, quote_currency: str, order_type: OrderType, order_side: TradeType,
                 amount: Decimal, price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    def balance_update_callback(self, message):
        """ Expected message structure
        {"SetBalance":
            {
                "event_id":0,
                "user":"5C62Ck4UrFPiBtoCmeSrgF7x9yv9mn38446dhCpsi2mLHiFT",
                "asset":"polkadex",
                "free":0,
                "pending_withdrawal":0,
                "reserved":0
            }
        }
        """

        message = message["data"]["websocket_streams"]["data"]["SetBalance"]
        asset_name = convert_asset_to_ticker(message["asset"])
        free_balance = Decimal(message["free"])
        total_balance = Decimal(message["free"]) + Decimal(message["reserved"])
        self._account_available_balances[asset_name] = free_balance
        self._account_balances[asset_name] = total_balance

    def order_update_callback(self, message):
        """ Expected message structure
        {
            "SetOrder":{
                "event_id":10,
                "client_order_id":"0xb7be03c528a2eb771b2b076cf869c69b0d9f1f508b199ba601d6f043c40d994e",
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
                "nonce":100
            }
        }
        """
        # TODO: Update based on event id
        message = message["data"]["websocket_streams"]["data"]["SetOrder"]
        market, base_asset, quote_asset = convert_pair_to_market(message["pair"])
        print("trading pair", market)

        # ts = parser.parse(message["time"]).timestamp()
        ts = time.time()
        tracked_order = self.in_flight_orders.get(message["client_order_id"])
        if tracked_order is not None:
            order_update = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=ts,
                new_state=CONSTANTS.ORDER_STATE[message["status"]],
                client_order_id=message["client_order_id"],
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
                client_order_id=message["client_order_id"],
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
        raise NotImplementedError

    def handle_websocket_message(self, message: Dict):
        print("New websocket message: ", message)
        if "SetBalance" in message["data"]["websocket_streams"]["data"]:
            self.balance_update_callback(message)
        elif "SetOrder" in message["data"]["websocket_streams"]["data"]:
            self.order_update_callback(message)
        else:
            print("Unknown message from user websocket stream")

    async def _user_stream_event_listener(self):
        if self.user_main_address is None:
            self.user_main_address = await get_main_acc_from_proxy_acc(self.user_proxy_address, self.endpoint,
                                                                       self.api_key)
        transport = AppSyncWebsocketsTransport(url=self.endpoint, auth=self.auth)
        tasks = []
        async with Client(transport=transport, fetch_schema_from_transport=False) as session:
            tasks.append(
                asyncio.create_task(
                    websocket_streams_session_provided(self.user_main_address, session,
                                                       self.handle_websocket_message)))
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

    async def _update_order_status(self):
        if self.user_main_address is None:
            self.user_main_address = await get_main_acc_from_proxy_acc(self.user_proxy_address, self.endpoint,
                                                                       self.api_key)
        last_tick = self._last_poll_timestamp / UPDATE_ORDER_STATUS_MIN_INTERVAL
        current_tick = self.current_timestamp / UPDATE_ORDER_STATUS_MIN_INTERVAL

        tracked_orders: List[InFlightOrder] = list(self.in_flight_orders.values())
        if current_tick > last_tick and len(tracked_orders) > 0:

            for tracked_order in tracked_orders:
                result = await find_order_by_main_account(self.user_main_address, tracked_order.client_order_id,
                                                          tracked_order.trading_pair, self.endpoint, self.api_key)

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
                    new_state = CONSTANTS.ORDER_STATE[result["st"]]
                    ts = parser.parse(result["t"]).timestamp()
                    update = OrderUpdate(
                        client_order_id=tracked_order.client_order_id,
                        exchange_order_id=str(tracked_order.exchange_order_id),
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=ts,
                        new_state=new_state,
                    )
                    self._order_tracker.process_order_update(update)

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        if self.user_main_address is None:
            self.user_main_address = await get_main_acc_from_proxy_acc(self.user_proxy_address, self.endpoint,
                                                                       self.api_key)
        print("Checking balances for: ", self.user_main_address)
        balances = await get_all_balances_by_main_account(self.user_main_address, self.endpoint, self.api_key)
        print("Updating balances: {:?}", balances)
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
            free_balance = Decimal(balance_entry["f"]) / UNIT_BALANCE
            total_balance = Decimal(balance_entry["f"]) + Decimal(balance_entry["r"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance / UNIT_BALANCE
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

    # @property
    # def status_dict(self) -> Dict[str, bool]:
    #     return {
    #         # TODO: Fix this "symbols_mapping_initialized": self.trading_pair_symbol_map_ready(),
    #         "symbols_mapping_initialized": True,
    #         "order_books_initialized": self.order_book_tracker.ready,
    #         "account_balance": not self.is_trading_required or len(self._account_balances) > 0,
    #         "trading_rule_initialized": True,
    #         "user_stream_initialized": True,
    #         # "user_stream_initialized": TODO: Fix this   self._user_stream_tracker.data_source.last_recv_time > 0 if
    #         #  self.is_trading_required else True,
    #     }
    async def _initialize_trading_pair_symbol_map(self):
        markets = await get_all_markets(self.endpoint, self.api_key)
        mapping = bidict()
        for market in markets:
            base = market["m"].split("-")[0]
            quote = market["m"].split("-")[1]
            mapping[market["m"]] = combine_to_hb_trading_pair(base=base, quote=quote)
        self._set_trading_pair_symbol_map(mapping)

    def c_stop_tracking_order(self, order_id):
        raise NotImplementedError

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        recent_trade = await get_recent_trades(trading_pair, 1, None, self.endpoint, self.api_key)
        return float(recent_trade[0]["p"])
