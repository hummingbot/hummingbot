import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_0, s_decimal_NaN
from hummingbot.connector.exchange.whitebit import (
    whitebit_constants as CONSTANTS,
    whitebit_utils as utils,
    whitebit_web_utils as web_utils,
)
from hummingbot.connector.exchange.whitebit.whitebit_api_order_book_data_source import WhitebitAPIOrderBookDataSource
from hummingbot.connector.exchange.whitebit.whitebit_api_user_stream_data_source import WhitebitAPIUserStreamDataSource
from hummingbot.connector.exchange.whitebit.whitebit_auth import WhitebitAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class WhitebitExchange(ExchangePyBase):
    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        whitebit_api_key: str,
        whitebit_secret_key: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ):
        self._api_key = whitebit_api_key
        self._secret_key = whitebit_secret_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        super().__init__(client_config_map)

    @property
    def authenticator(self):
        return WhitebitAuth(api_key=self._api_key, secret_key=self._secret_key, time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "whitebit"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return CONSTANTS.DEFAULT_DOMAIN

    @property
    def client_order_id_max_length(self):
        return None

    @property
    def client_order_id_prefix(self):
        return "HBOT-"

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.WHITEBIT_INSTRUMENTS_PATH

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.WHITEBIT_INSTRUMENTS_PATH

    @property
    def check_network_request_path(self):
        return CONSTANTS.WHITEBIT_SERVER_STATUS_PATH

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        """
        Return a dictionary the trading_pair as key and the current price as value for each trading pair passed as
        parameter

        :param trading_pairs: list of trading pairs to get the prices for

        :return: Dictionary of associations between token pair and its latest price
        """
        last_prices = {}
        response = await self._api_get(path_url=CONSTANTS.WHITEBIT_TICKER_PATH)
        for market_symbol, ticker_info in response.items():
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=market_symbol)
            if trading_pair in trading_pairs:
                last_prices[trading_pair] = float(ticker_info["last_price"])

        return last_prices

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # Not required for this connectors
        return False

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        exchange_order_id = await tracked_order.get_exchange_order_id()

        params = {
            "market": await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair),
            "orderId": int(exchange_order_id),
        }

        cancel_result = await self._api_post(
            path_url=CONSTANTS.WHITEBIT_ORDER_CANCEL_PATH,
            data=params,
            is_auth_required=True,
        )

        if len(cancel_result.get("errors", {})) > 0:
            raise IOError(f"Error canceling order {order_id} ({cancel_result})")

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
        data = {
            "market": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "side": trade_type.name.lower(),
            "amount": str(amount),
            "price": str(price),
            "clientOrderId": order_id,
        }

        response = await self._api_post(
            path_url=CONSTANTS.WHITEBIT_ORDER_CREATION_PATH,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.WHITEBIT_ORDER_CREATION_PATH,
        )
        return str(response["orderId"]), response.get("timestamp", self.current_timestamp)

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> AddedToCostTradeFee:
        is_maker = is_maker or (order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER])
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
        async for stream_message in self._iter_user_event_queue():
            try:
                channel = stream_message.get("method")

                if channel == CONSTANTS.WHITEBIT_WS_PRIVATE_TRADES_CHANNEL:
                    event_message = {
                        "time": stream_message["params"][1],
                        "fee": stream_message["params"][6],
                        "price": stream_message["params"][4],
                        "amount": stream_message["params"][5],
                        "id": stream_message["params"][0],
                        "dealOrderId": stream_message["params"][3],
                        "clientOrderId": stream_message["params"][7],
                    }
                    event_message["deal"] = str(
                        Decimal(str(event_message["amount"])) * Decimal(str(event_message["price"]))
                    )

                    order = self._order_tracker.all_fillable_orders.get(event_message["clientOrderId"])
                    if order is not None:
                        trade_update = self._create_trade_update(trade_msg=event_message, order=order)
                        self._order_tracker.process_trade_update(trade_update)

                elif channel == CONSTANTS.WHITEBIT_WS_PRIVATE_ORDERS_CHANNEL:
                    update_event_id, event_message = stream_message["params"]
                    executed_amount = Decimal(str(event_message["deal_stock"]))

                    if update_event_id in [1, 2]:
                        order_state = OrderState.OPEN
                    elif update_event_id == 3 and executed_amount == s_decimal_0:
                        order_state = OrderState.CANCELED
                    else:
                        order_state = OrderState.FILLED

                    event_message["order_state"] = order_state
                    client_order_id = str(event_message.get("clientOrderId", event_message.get("client_order_id")))
                    order = self._order_tracker.all_updatable_orders.get(client_order_id)
                    if order is not None:
                        order_update = self._create_order_update(order_msg=event_message, order=order)
                        self._order_tracker.process_order_update(order_update)

                elif channel == CONSTANTS.WHITEBIT_WS_PRIVATE_BALANCE_CHANNEL:
                    for data in stream_message.get("params", []):
                        for token, balance_info in data.items():
                            available = Decimal(str(balance_info["available"]))
                            frozen = Decimal(str(balance_info["freeze"]))
                            self._account_balances[token] = available + frozen
                            self._account_available_balances[token] = available

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        trading_rules = []

        for info in exchange_info_dict.get("result", []):
            try:
                if utils.is_exchange_information_valid(exchange_info=info):
                    trading_rules.append(
                        TradingRule(
                            trading_pair=await self.trading_pair_associated_to_exchange_symbol(symbol=info["name"]),
                            min_order_size=Decimal(info["minAmount"]),
                            min_order_value=Decimal(info["minTotal"]),
                            max_price_significant_digits=Decimal(info["moneyPrec"]),
                            min_base_amount_increment=Decimal(1) / (Decimal(10) ** Decimal(str(info["stockPrec"]))),
                            min_quote_amount_increment=Decimal(1) / (Decimal(10) ** Decimal(str(info["moneyPrec"]))),
                            min_price_increment=Decimal(1) / (Decimal(10) ** Decimal(str(info["moneyPrec"]))),
                        )
                    )
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {info}. Skipping.")
        return trading_rules

    async def _request_order_fills(self, order: InFlightOrder):
        order_fills = []
        if order.exchange_order_id is not None:
            pagination_limit = 100
            pagination_offset = 0
            has_more_pages = True

            while has_more_pages:
                has_more_pages = False

                fills_result = await self._api_post(
                    path_url=CONSTANTS.WHITEBIT_ORDER_TRADES_PATH,
                    data={
                        "orderId": int(order.exchange_order_id),
                        "limit": pagination_limit,
                        "offset": pagination_offset,
                    },
                    is_auth_required=True,
                )

                is_invalid_order_id = (
                    fills_result.get("status") != CONSTANTS.ORDER_FILLS_REQUEST_INVALID_ORDER_ID_ERROR_CODE
                )
                has_warnings = f"Finished order id {order.exchange_order_id}" in fills_result.get("warning", "")
                if is_invalid_order_id and not has_warnings:
                    order_fills.extend(fills_result["records"])

                    if len(fills_result["records"]) == pagination_limit:
                        has_more_pages = True
                        pagination_offset += pagination_limit

        return order_fills

    async def _request_order_update(self, order: InFlightOrder) -> List[Dict[str, Any]]:
        result = []
        symbol = await self.exchange_symbol_associated_to_pair(order.trading_pair)
        active_order_result = await self._api_post(
            path_url=CONSTANTS.WHITEBIT_ACTIVE_ORDER_STATUS_PATH,
            data={"market": symbol, "clientOrderId": order.client_order_id},
            is_auth_required=True,
        )

        if type(active_order_result) == dict:
            active_order_result = [active_order_result]

        for active_order_status in active_order_result:
            active_order_status["order_state"] = OrderState.OPEN
            result.append(active_order_status)

        if order.exchange_order_id is not None:
            executed_order_result = await self._api_post(
                path_url=CONSTANTS.WHITEBIT_EXECUTED_ORDER_STATUS_PATH,
                data={"orderId": str(order.exchange_order_id)},
                is_auth_required=True,
            )
            if len(executed_order_result) > 0:
                # If the order is not executed, the result is an empty list. Otherwise, it is a dictionary
                for executed_order_status in executed_order_result[symbol]:
                    executed_order_status["order_state"] = OrderState.FILLED
                    result.append(executed_order_status)

        return result

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        try:
            if order.exchange_order_id is not None:
                all_fills_response = await self._request_order_fills(order=order)
                for trade_fill in all_fills_response:
                    trade_update = self._create_trade_update(trade_msg=trade_fill, order=order)
                    trade_updates.append(trade_update)
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            is_error_caused_by_unexistent_order = '"code":50005' in str(ex)
            if not is_error_caused_by_unexistent_order:
                raise

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        updated_order_data = await self._request_order_update(order=tracked_order)
        if len(updated_order_data) > 0:
            order_update = self._create_order_update(order_msg=updated_order_data[-1], order=tracked_order)
        else:
            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=tracked_order.current_state,
            )
        return order_update

    def _create_trade_update(self, trade_msg: Dict[str, Any], order: InFlightOrder):
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=order.trade_type,
            percent_token=order.quote_asset,
            flat_fees=[TokenAmount(amount=Decimal(trade_msg["fee"]), token=order.quote_asset)],
        )
        trade_update = TradeUpdate(
            trade_id=str(trade_msg["id"]),
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            fee=fee,
            fill_base_amount=Decimal(trade_msg["amount"]),
            fill_quote_amount=Decimal(trade_msg["amount"]) * Decimal(trade_msg["price"]),
            fill_price=Decimal(trade_msg["price"]),
            fill_timestamp=float(trade_msg["time"]),
        )
        return trade_update

    def _create_order_update(self, order_msg: Dict[str, Any], order: InFlightOrder):
        client_order_id = str(order_msg.get("clientOrderId", order_msg.get("client_order_id")))
        state = order_msg["order_state"]  # The state is added in the dict before calling this method
        if state == OrderState.OPEN and order.executed_amount_base > s_decimal_0:
            state = OrderState.PARTIALLY_FILLED
        order_update = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=float(
                order_msg.get("timestamp", order_msg.get("ftime", order_msg.get("mtime", self.current_timestamp)))
            ),
            new_state=state,
            client_order_id=client_order_id,
            exchange_order_id=str(order_msg.get("id", order_msg.get("orderId"))),
        )
        return order_update

    async def _update_balances(self):
        response = await self._api_post(path_url=CONSTANTS.WHITEBIT_BALANCE_PATH, is_auth_required=True)

        self._account_available_balances.clear()
        self._account_balances.clear()

        for token, balance_details in response.items():
            self._account_balances[token] = Decimal(balance_details["available"]) + Decimal(balance_details["freeze"])
            self._account_available_balances[token] = Decimal(balance_details["available"])

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler, time_synchronizer=self._time_synchronizer, auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return WhitebitAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs, connector=self, api_factory=self._web_assistants_factory
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return WhitebitAPIUserStreamDataSource(
            auth=self._auth, trading_pairs=self._trading_pairs, connector=self, api_factory=self._web_assistants_factory
        )

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(utils.is_exchange_information_valid, exchange_info["result"]):
            mapping[symbol_data["name"]] = combine_to_hb_trading_pair(
                base=symbol_data["stock"], quote=symbol_data["money"]
            )
        self._set_trading_pair_symbol_map(mapping)
