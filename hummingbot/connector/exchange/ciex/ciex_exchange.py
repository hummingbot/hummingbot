import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from async_timeout import timeout
from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.ciex import ciex_constants as CONSTANTS, ciex_utils, ciex_web_utils as web_utils
from hummingbot.connector.exchange.ciex.ciex_api_order_book_data_source import CiexAPIOrderBookDataSource
from hummingbot.connector.exchange.ciex.ciex_auth import CiexAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class CiexExchange(ExchangePyBase):

    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        ciex_api_key: str,
        ciex_secret_key: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        shallow_order_book: bool = False,  # not supported yet
    ):

        self._api_key = ciex_api_key
        self._secret_key = ciex_secret_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        super().__init__(client_config_map=client_config_map)

        self._real_time_balance_update = False
        self._last_processed_trade_id_per_pair = {}

    @property
    def name(self) -> str:
        return "ciex"

    @property
    def authenticator(self) -> AuthBase:
        return CiexAuth(api_key=self._api_key, secret_key=self._secret_key, time_provider=self._time_synchronizer)

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return CONSTANTS.DEFAULT_DOMAIN

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.CIEX_SYMBOLS_PATH

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.CIEX_SYMBOLS_PATH

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.CIEX_PING_PATH

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        # Configured like this because the API documentation mentions a PENDING_CANCEL order status
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        Cancels all currently active orders. The cancelations are performed in parallel tasks.

        :param timeout_seconds: the maximum time (in seconds) the cancel logic should run

        :return: a list of CancellationResult instances, one for each of the orders to be canceled
        """
        order_id_set = set()
        incomplete_orders_by_trading_pair = defaultdict(list)
        for order in (o for o in self.in_flight_orders.values() if not o.is_done):
            incomplete_orders_by_trading_pair[order.trading_pair].append(order)
            order_id_set.add(order.client_order_id)
        tasks = []

        for incomplete_per_trading_pair in incomplete_orders_by_trading_pair.values():
            lower_bound = 0
            upper_bound = min(CONSTANTS.MAX_ORDERS_PER_BATCH_CANCEL, len(incomplete_per_trading_pair))
            while lower_bound < len(incomplete_per_trading_pair):
                orders = incomplete_per_trading_pair[lower_bound:upper_bound]
                tasks.append(asyncio.create_task(self._batch_cancel_orders(orders=orders)))
                lower_bound = lower_bound + CONSTANTS.MAX_ORDERS_PER_BATCH_CANCEL
                upper_bound = upper_bound + CONSTANTS.MAX_ORDERS_PER_BATCH_CANCEL

        successful_cancelations = []

        try:
            async with timeout(timeout_seconds):
                cancelation_results = await safe_gather(*tasks, return_exceptions=True)
                for cr in cancelation_results:
                    if isinstance(cr, Exception):
                        continue
                    for order in cr:
                        order_id_set.remove(order.client_order_id)
                        successful_cancelations.append(CancellationResult(order.client_order_id, True))

                        update_timestamp = (
                            self._time() if self.current_timestamp == float("nan") else self.current_timestamp
                        )
                        order_update: OrderUpdate = OrderUpdate(
                            client_order_id=order.client_order_id,
                            trading_pair=order.trading_pair,
                            update_timestamp=update_timestamp,
                            new_state=(
                                OrderState.CANCELED
                                if self.is_cancel_request_in_exchange_synchronous
                                else OrderState.PENDING_CANCEL
                            ),
                        )
                        self._order_tracker.process_order_update(order_update)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network(
                "Unexpected error canceling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order. Check API key and network connection.",
            )
        failed_cancelations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancelations + failed_cancelations

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = "HTTP status is 429" in error_description
        return is_time_synchronizer_related

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        # TODO: implement this method correctly for the connector
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_lost_order_removed_if_not_found_during_order_status_update
        # when replacing the dummy implementation
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        # TODO: implement this method correctly for the connector
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_cancel_order_not_found_in_the_exchange when replacing the
        # dummy implementation
        return False

    async def _batch_cancel_orders(self, orders: List[InFlightOrder]) -> List[InFlightOrder]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=orders[0].trading_pair)
        order_ids = [order.exchange_order_id for order in orders if order.exchange_order_id is not None]
        request_data = {
            "symbol": symbol,
            "orderIds": order_ids,
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CIEX_BATCH_CANCEL_ORDERS_PATH, data=request_data, is_auth_required=True
        )

        if "code" in cancel_result:
            raise IOError(
                f"Error canceling orders "
                f"{[order.client_order_id for order in orders if order.exchange_order_id is not None]} "
                f"(code: {cancel_result['code']} - description: {cancel_result['msg']}"
            )

        successfully_canceled = cancel_result.get("success", [])
        return [order for order in orders if int(order.exchange_order_id) in successfully_canceled]

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        request_data = {
            "symbol": symbol,
            "newClientOrderId": tracked_order.client_order_id,
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CIEX_CANCEL_ORDER_PATH, data=request_data, is_auth_required=True
        )

        if "code" in cancel_result:
            raise IOError(
                f"Error canceling order {order_id} "
                f"(code: {cancel_result['code']} - description: {cancel_result['msg']}"
            )

        return True

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
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        data = {
            "symbol": symbol,
            "volume": str(amount),
            "side": trade_type.name.upper(),
            "type": "LIMIT",
            "price": str(price),
            "newClientOrderId": order_id,
        }

        response = await self._api_post(
            path_url=CONSTANTS.CIEX_ORDER_PATH,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.CIEX_ORDER_CREATION_LIMIT_ID,
        )

        if "code" in response:
            raise IOError(
                f"Error submitting order {order_id} " f"(code: {response['code']} - description: {response['msg']}"
            )

        timestamp = response["transactTime"] * 1e-3 if "transactTime" in response else self.current_timestamp
        return str(response["orderId"]), timestamp

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
        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        fee = build_trade_fee(
            self.name,
            is_maker,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )
        return fee

    async def _update_trading_fees(self):
        pass

    async def _user_stream_event_listener(self):
        pass

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        trading_rules = []

        for info in exchange_info_dict.get("symbols", []):
            try:
                if ciex_utils.is_exchange_information_valid(exchange_info=info):
                    quantity_precision = info["quantityPrecision"]
                    price_precision = info["pricePrecision"]
                    min_order_size = Decimal(str(10**-quantity_precision))
                    min_quote_amount = Decimal(str(10**-price_precision))
                    trading_rules.append(
                        TradingRule(
                            trading_pair=await self.trading_pair_associated_to_exchange_symbol(symbol=info["symbol"]),
                            min_order_size=min_order_size,
                            min_order_value=min_order_size * min_quote_amount,
                            max_price_significant_digits=Decimal(str(price_precision)),
                            min_base_amount_increment=min_order_size,
                            min_quote_amount_increment=min_quote_amount,
                            min_price_increment=min_quote_amount,
                        )
                    )
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {info}. Skipping.")
        return trading_rules

    async def _update_balances(self):
        response = await self._api_get(path_url=CONSTANTS.CIEX_ACCOUNT_INFO_PATH, is_auth_required=True)

        if "code" in response:
            if not self._is_request_result_an_error_related_to_time_synchronizer(request_result=response):
                description = (
                    "Invalid API keys"
                    if response["code"] == CONSTANTS.INVALID_API_KEY_ERROR_CODE
                    else f"Error updating the balance information "
                    f"(code: {response['code']} - description: {response['msg']}"
                )
                raise IOError(description)
        else:
            self._account_available_balances.clear()
            self._account_balances.clear()

            for balance_details in response["balances"]:
                token = balance_details["asset"].upper()
                free_balance = Decimal(str(balance_details["free"]))
                locked_balance = Decimal(str(balance_details["locked"]))
                self._account_available_balances[token] = free_balance
                self._account_balances[token] = free_balance + locked_balance

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        # Not needed for CoinDCX since it reimplements _update_orders_fills
        raise NotImplementedError

    async def _request_order_fills(self):
        trade_responses = []
        for trading_pair in self.trading_pairs:
            try:
                parameters = {
                    "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
                    "limit": "1000",
                }
                starting_trade_id = self._last_processed_trade_id_per_pair.get(trading_pair)
                if starting_trade_id is None and self._order_tracker.all_fillable_orders:
                    any_fillable_order = list(self._order_tracker.all_fillable_orders.values())[0]
                    if any_fillable_order.order_fills:
                        starting_trade_id = list(any_fillable_order.order_fills.keys())[0]
                if starting_trade_id is not None:
                    parameters["fromId"] = int(starting_trade_id)

                results = await self._api_get(
                    path_url=CONSTANTS.CIEX_ORDER_FILLS_PATH,
                    params=parameters,
                    is_auth_required=True,
                )

                if results["list"]:
                    trade_responses.extend(results["list"])
                    # Latest trade always comes first
                    last_trade_id = int(results["list"][0]["id"])
                    self._last_processed_trade_id_per_pair[trading_pair] = max(
                        self._last_processed_trade_id_per_pair.get(trading_pair, 0), last_trade_id
                    )

            except asyncio.CancelledError:
                raise
            except Exception as request_error:
                self.logger().warning(f"Failed to fetch trade updates. Error: {request_error}")

        return trade_responses

    async def _update_orders_fills(self, orders: List[InFlightOrder]):
        orders_dict = {order.exchange_order_id: order for order in orders if order.exchange_order_id is not None}

        if orders_dict:

            trade_responses = await self._request_order_fills()

            for trade_response in trade_responses:
                exchange_order_ids = [str(trade_response["bidId"]), str(trade_response["askId"])]
                for exchange_order_id in exchange_order_ids:
                    order = orders_dict.get(exchange_order_id)
                    if order is not None:
                        try:
                            fee_token: str = trade_response["feeCoin"]
                            fee = TradeFeeBase.new_spot_fee(
                                fee_schema=self.trade_fee_schema(),
                                trade_type=order.trade_type,
                                percent_token=fee_token,
                                flat_fees=[TokenAmount(amount=Decimal(trade_response["fee"]), token=fee_token)],
                            )
                            trade_update = TradeUpdate(
                                trade_id=str(trade_response["id"]),
                                client_order_id=order.client_order_id,
                                exchange_order_id=exchange_order_id,
                                trading_pair=order.trading_pair,
                                fee=fee,
                                fill_price=Decimal(str(trade_response["price"])),
                                fill_base_amount=Decimal(str(trade_response["qty"])),
                                fill_quote_amount=Decimal(str(trade_response["qty"]))
                                * Decimal(str(trade_response["price"])),
                                fill_timestamp=float(trade_response["time"]) * 1e-3,
                            )
                            self._order_tracker.process_trade_update(trade_update)
                        except asyncio.CancelledError:
                            raise
                        except Exception as error:
                            self.logger().warning(
                                f"Failed to process trade update for order {order.client_order_id}. Error: {error}"
                            )

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        updated_order_data = await self._api_get(
            path_url=CONSTANTS.CIEX_ORDER_PATH,
            params={
                "orderId": await tracked_order.get_exchange_order_id(),
                "symbol": symbol,
            },
            is_auth_required=True,
            limit_id=CONSTANTS.CIEX_ORDER_STATUS_LIMIT_ID,
        )

        if "code" not in updated_order_data:
            new_state = CONSTANTS.ORDER_STATE[updated_order_data["status"]]
            exchange_order_id = str(updated_order_data["orderId"])
        elif updated_order_data["code"] == CONSTANTS.ORDER_DOES_NOT_EXIST_ERROR_CODE:
            new_state = OrderState.FAILED
            exchange_order_id = None
        else:
            raise IOError(
                f"Error updating status of order {tracked_order.client_order_id} "
                f"(code: {updated_order_data['code']} - description: {updated_order_data['msg']}"
            )

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=new_state,
        )

        return order_update

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler, time_synchronizer=self._time_synchronizer, auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return CiexAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs, connector=self, api_factory=self._web_assistants_factory
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        raise NotImplementedError

    def _is_user_stream_initialized(self):
        # CIEX does not have private websocket endpoints. Returning always True to allow the connector to start
        return True

    def _create_user_stream_tracker(self):
        # CIEX does not have private websocket endpoints.
        return None

    def _create_user_stream_tracker_task(self):
        # CIEX does not have private websocket endpoints.
        return None

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(ciex_utils.is_exchange_information_valid, exchange_info["symbols"]):
            mapping[symbol_data["symbol"]] = combine_to_hb_trading_pair(
                base=symbol_data["baseAsset"], quote=symbol_data["quoteAsset"]
            )
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {"symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)}

        resp_json = await self._api_get(path_url=CONSTANTS.CIEX_TICKER_PATH, params=params)

        return float(resp_json["last"])
