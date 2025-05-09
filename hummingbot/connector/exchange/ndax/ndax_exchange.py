import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.exchange.ndax import ndax_constants as CONSTANTS, ndax_utils, ndax_web_utils as web_utils
from hummingbot.connector.exchange.ndax.ndax_api_order_book_data_source import NdaxAPIOrderBookDataSource
from hummingbot.connector.exchange.ndax.ndax_api_user_stream_data_source import NdaxAPIUserStreamDataSource
from hummingbot.connector.exchange.ndax.ndax_auth import NdaxAuth
from hummingbot.connector.exchange.ndax.ndax_websocket_adaptor import NdaxWebSocketAdaptor
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_numeric_client_order_id
from hummingbot.core.data_type.common import OpenOrder, OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)

RESOURCE_NOT_FOUND_ERR = "Resource Not Found"


class NdaxExchange(ExchangePyBase):
    """
    Class to onnect with NDAX exchange. Provides order book pricing, user account tracking and
    trading functionality.
    """

    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    UPDATE_TRADING_RULES_INTERVAL = 60.0

    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        ndax_uid: str,
        ndax_api_key: str,
        ndax_secret_key: str,
        ndax_account_name: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: Optional[str] = None,
    ):
        """
        :param ndax_uid: User ID of the account
        :param ndax_api_key: The API key to connect to private NDAX APIs.
        :param ndax_secret_key: The API secret.
        :param ndax_account_name: The name of the account associated to the user account.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        self._ndax_uid = ndax_uid
        self._ndax_api_key = ndax_api_key
        self._ndax_secret_key = ndax_secret_key
        self._ndax_account_name = ndax_account_name
        self._domain = domain

        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._nonce_creator = NonceCreator.for_milliseconds()
        self._authenticator = NdaxAuth(
            uid=self._ndax_uid,
            api_key=self._ndax_api_key,
            secret_key=self._ndax_secret_key,
            account_name=self._ndax_account_name,
        )
        super().__init__(client_config_map)
        self._product_id_map = {}

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self):
        return self._authenticator

    @property
    def domain(self):
        return self._domain

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def check_network_request_path(self):
        return CONSTANTS.PING_PATH_URL

    @property
    def client_order_id_max_length(self):
        return 32

    @property
    def client_order_id_prefix(self):
        return ""

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.MARKETS_URL

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.MARKETS_URL

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    async def initialized_account_id(self) -> int:
        if self.authenticator.account_id == 0:
            await self.authenticator.rest_authenticate(
                RESTRequest(method="POST", url="")
            )  # dummy request to trigger auth
        return self.authenticator.account_id

    def supported_order_types(self) -> List[OrderType]:
        """
        :return: a list of OrderType supported by this connector.
        Note that Market order type is no longer required and will not be used.
        """
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    def buy(
        self, trading_pair: str, amount: Decimal, order_type=OrderType.LIMIT, price: Decimal = s_decimal_NaN, **kwargs
    ) -> str:
        """
        Creates a promise to create a buy order using the parameters

        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price

        :return: the id assigned by the connector to the order (the client id)
        """
        prefix = self.client_order_id_prefix
        new_order_id = get_new_numeric_client_order_id(
            nonce_creator=self._nonce_creator, max_id_bit_count=self.client_order_id_max_length
        )
        numeric_order_id = f"{prefix}{new_order_id}"

        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.BUY,
                order_id=numeric_order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return numeric_order_id

    def sell(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        """
        Creates a promise to create a sell order using the parameters.
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        :return: the id assigned by the connector to the order (the client id)
        """
        prefix = self.client_order_id_prefix
        new_order_id = get_new_numeric_client_order_id(
            nonce_creator=self._nonce_creator, max_id_bit_count=self.client_order_id_max_length
        )
        numeric_order_id = f"{prefix}{new_order_id}"
        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.SELL,
                order_id=numeric_order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return numeric_order_id

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        **kwargs,
    ) -> Tuple[str, float]:
        params = {
            "InstrumentId": await self.exchange_symbol_associated_to_pair(trading_pair),
            "OMSId": 1,
            "AccountId": await self.initialized_account_id(),
            "ClientOrderId": int(order_id),
            "Side": 0 if trade_type == TradeType.BUY else 1,
            "Quantity": f"{amount:f}",
            "TimeInForce": 1,  # GTC
        }

        if order_type.is_limit_type():

            params.update(
                {
                    "OrderType": 2,  # Limit
                    "LimitPrice": f"{price:f}",
                }
            )
        else:
            params.update({"OrderType": 1})  # Market

        send_order_results = await self._api_post(
            path_url=CONSTANTS.SEND_ORDER_PATH_URL, data=params, is_auth_required=True
        )

        if send_order_results["status"] == "Rejected":
            raise ValueError(
                f"Order is rejected by the API. " f"Parameters: {params} Error Msg: {send_order_results['errormsg']}"
            )

        exchange_order_id = str(send_order_results["OrderId"])
        return exchange_order_id, self._time_synchronizer.time()

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        """
        To determine if an order is successfully canceled, we either call the
        GetOrderStatus/GetOpenOrders endpoint or wait for a OrderStateEvent/OrderTradeEvent from the WS.
        :param trading_pair: The market (e.g. BTC-CAD) the order is in.
        :param order_id: The client_order_id of the order to be cancelled.
        """
        body_params = {
            "OMSId": 1,
            "AccountId": await self.initialized_account_id(),
            "OrderId": await tracked_order.get_exchange_order_id(),
        }

        # The API response simply verifies that the API request have been received by the API servers.
        response = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_PATH_URL, data=body_params, is_auth_required=True
        )

        if response.get("errorcode", 1) != 0:
            raise IOError(response.get("errormsg"))

        return response.get("result", False)

    async def get_open_orders(self) -> List[OpenOrder]:
        query_params = {
            "OMSId": 1,
            "AccountId": await self.initialized_account_id(),
        }
        open_orders: List[Dict[str, Any]] = await self._api_request(
            path_url=CONSTANTS.GET_OPEN_ORDERS_PATH_URL, params=query_params, is_auth_required=True
        )

        return [
            OpenOrder(
                client_order_id=order["ClientOrderId"],
                trading_pair=await self.exchange_symbol_associated_to_pair(trading_pair=order["Instrument"]),
                price=Decimal(str(order["Price"])),
                amount=Decimal(str(order["Quantity"])),
                executed_amount=Decimal(str(order["QuantityExecuted"])),
                status=order["OrderState"],
                order_type=OrderType.LIMIT if order["OrderType"] == "Limit" else OrderType.MARKET,
                is_buy=True if order["Side"] == "Buy" else False,
                time=order["ReceiveTime"],
                exchange_order_id=order["OrderId"],
            )
            for order in open_orders
        ]

    def _format_trading_rules(self, instrument_info: List[Dict[str, Any]]) -> Dict[str, TradingRule]:
        """
        Converts JSON API response into a local dictionary of trading rules.
        :param instrument_info: The JSON API response.
        :returns: A dictionary of trading pair to its respective TradingRule.
        """
        result = {}
        for instrument in instrument_info:
            try:
                trading_pair = f"{instrument['Product1Symbol']}-{instrument['Product2Symbol']}"

                result[trading_pair] = TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=Decimal(str(instrument["MinimumQuantity"])),
                    min_price_increment=Decimal(str(instrument["PriceIncrement"])),
                    min_base_amount_increment=Decimal(str(instrument["QuantityIncrement"])),
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule: {instrument}. Skipping...", exc_info=True)
        return result

    async def _update_trading_rules(self):
        params = {"OMSId": 1}
        instrument_info: List[Dict[str, Any]] = await self._api_request(path_url=CONSTANTS.MARKETS_URL, params=params)
        self._trading_rules.clear()
        self._trading_rules = self._format_trading_rules(instrument_info)

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        params = {"OMSId": 1, "AccountId": await self.initialized_account_id()}
        account_positions: List[Dict[str, Any]] = await self._api_request(
            path_url=CONSTANTS.ACCOUNT_POSITION_PATH_URL, params=params, is_auth_required=True
        )
        for position in account_positions:
            asset_name = position["ProductSymbol"]
            self._account_balances[asset_name] = Decimal(str(position["Amount"]))
            self._account_available_balances[asset_name] = self._account_balances[asset_name] - Decimal(
                str(position["Hold"])
            )
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        Calls REST API to get order status
        """
        query_params = {
            "OMSId": 1,
            "AccountId": await self.initialized_account_id(),
            "OrderId": int(await tracked_order.get_exchange_order_id()),
        }

        updated_order_data = await self._api_get(
            path_url=CONSTANTS.GET_ORDER_STATUS_PATH_URL, params=query_params, is_auth_required=True
        )

        new_state = CONSTANTS.ORDER_STATE_STRINGS[updated_order_data["OrderState"]]

        if new_state == OrderState.OPEN and Decimal(str(updated_order_data["QuantityExecuted"])) > s_decimal_0:
            new_state = OrderState.PARTIALLY_FILLED

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data["OrderId"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self._time_synchronizer.time(),
            new_state=new_state,
        )
        return order_update

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                endpoint = NdaxWebSocketAdaptor.endpoint_from_message(event_message)
                payload = NdaxWebSocketAdaptor.payload_from_message(event_message)

                if endpoint == CONSTANTS.ACCOUNT_POSITION_EVENT_ENDPOINT_NAME:
                    self._process_account_position_event(payload)
                elif endpoint == CONSTANTS.ORDER_STATE_EVENT_ENDPOINT_NAME:
                    client_order_id = str(payload["ClientOrderId"])
                    tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                    if tracked_order is not None:
                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=payload["ReceiveTime"],
                            new_state=CONSTANTS.ORDER_STATE_STRINGS[payload["OrderState"]],
                            client_order_id=client_order_id,
                            exchange_order_id=str(payload["OrderId"]),
                        )
                        self._order_tracker.process_order_update(order_update=order_update)
                elif endpoint == CONSTANTS.ORDER_TRADE_EVENT_ENDPOINT_NAME:
                    self._process_trade_event_message(payload)
                else:
                    self.logger().debug(f"Unknown event received from the connector ({event_message})")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    def _process_account_position_event(self, account_position_event: Dict[str, Any]):
        token = account_position_event["ProductSymbol"]
        amount = Decimal(str(account_position_event["Amount"]))
        on_hold = Decimal(str(account_position_event["Hold"]))
        self._account_balances[token] = amount
        self._account_available_balances[token] = amount - on_hold

    def _process_trade_event_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        :param order_msg: The order event message payload
        """
        client_order_id = str(order_msg["ClientOrderId"])
        fillable_order = self._order_tracker.all_fillable_orders.get(client_order_id)
        if fillable_order is not None:
            trade_amount = Decimal(str(order_msg["Quantity"]))
            trade_price = Decimal(str(order_msg["Price"]))
            fee = self.get_fee(
                base_currency=fillable_order.base_asset,
                quote_currency=fillable_order.quote_asset,
                order_type=fillable_order.order_type,
                order_side=fillable_order.trade_type,
                amount=Decimal(order_msg["Quantity"]),
                price=Decimal(order_msg["Price"]),
            )
            self._order_tracker.process_trade_update(TradeUpdate(
                trade_id=str(order_msg["TradeId"]),
                client_order_id=fillable_order.client_order_id,
                exchange_order_id=fillable_order.exchange_order_id,
                trading_pair=fillable_order.trading_pair,
                fill_timestamp=self.current_timestamp,
                fill_price=trade_price,
                fill_base_amount=trade_amount,
                fill_quote_amount=trade_price * trade_amount,
                fee=fee,
            ))

    async def _make_trading_pairs_request(self) -> Any:
        exchange_info = await self._api_get(path_url=self.trading_pairs_request_path, params={"OMSId": 1})
        return exchange_info

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        body_params = {
            "OMSId": 1,
            "AccountId": await self.initialized_account_id(),
            "UserId": self._auth.uid,
            "InstrumentId": await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair),
            "orderId": await order.get_exchange_order_id(),
        }

        raw_responses: List[Dict[str, Any]] = await self._api_get(
            path_url=CONSTANTS.GET_TRADES_HISTORY_PATH_URL,
            params=body_params,
            is_auth_required=True,
            limit_id=CONSTANTS.GET_TRADES_HISTORY_PATH_URL,
        )

        for trade in raw_responses:

            fee = fee = self.get_fee(
                base_currency=order.base_asset,
                quote_currency=order.quote_asset,
                order_type=order.order_type,
                order_side=order.trade_type,
                amount=Decimal(trade["Quantity"]),
                price=Decimal(trade["Price"]),
            )
            trade_update = TradeUpdate(
                trade_id=str(trade["TradeId"]),
                client_order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
                trading_pair=order.trading_pair,
                fee=fee,
                fill_base_amount=Decimal(trade["Quantity"]),
                fill_quote_amount=Decimal(trade["Quantity"]) * Decimal(trade["Price"]),
                fill_price=Decimal(trade["Price"]),
                fill_timestamp=trade["TradeTime"],
            )
            trade_updates.append(trade_update)

        return trade_updates

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return NdaxAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return NdaxAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler, time_synchronizer=self._time_synchronizer, domain=self._domain, auth=self._auth
        )

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        # https://apidoc.ndax.io/?_gl=1*frgalf*_gcl_au*MTc2Mjc1NzIxOC4xNzQ0MTQ3Mzcy*_ga*ODQyNjI5MDczLjE3NDQxNDczNzI.*_ga_KBXHH6Z610*MTc0NTU0OTg5OC4xOS4xLjE3NDU1NTAyNTguMC4wLjA.#getorderfee
        is_maker = order_type is OrderType.LIMIT_MAKER
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(ndax_utils.is_exchange_information_valid, exchange_info):
            mapping[symbol_data["InstrumentId"]] = combine_to_hb_trading_pair(
                base=symbol_data["Product1Symbol"], quote=symbol_data["Product2Symbol"]
            )
            self._product_id_map[symbol_data["Product1Symbol"]] = symbol_data["Product1"]
            self._product_id_map[symbol_data["Product2Symbol"]] = symbol_data["Product2"]
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        ex_symbol = trading_pair.replace("-", "_")

        resp_json = await self._api_request(
            path_url=CONSTANTS.TICKER_PATH_URL
        )

        return float(resp_json.get(ex_symbol, {}).get("last_price", 0.0))

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return str(RESOURCE_NOT_FOUND_ERR) in str(cancelation_exception)

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return str(RESOURCE_NOT_FOUND_ERR) in str(status_update_exception)

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False
