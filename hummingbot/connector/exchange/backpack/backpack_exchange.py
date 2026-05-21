import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.backpack import (
    backpack_constants as CONSTANTS,
    backpack_utils as utils,
    backpack_web_utils as web_utils,
)
from hummingbot.connector.exchange.backpack.backpack_api_order_book_data_source import BackpackAPIOrderBookDataSource
from hummingbot.connector.exchange.backpack.backpack_api_user_stream_data_source import BackpackAPIUserStreamDataSource
from hummingbot.connector.exchange.backpack.backpack_auth import BackpackAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_numeric_client_order_id
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BackpackExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(self,
                 backpack_api_key: str,
                 backpack_api_secret: str,
                 balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
                 rate_limits_share_pct: Decimal = Decimal("100"),
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 ):
        self.api_key = backpack_api_key
        self.secret_key = backpack_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_backpack_timestamp = 1.0
        self._nonce_creator = NonceCreator.for_milliseconds()
        super().__init__(balance_asset_limit, rate_limits_share_pct)
        # Backpack does not provide balance updates through websocket, use REST polling instead
        self.real_time_balance_update = False

    @staticmethod
    def backpack_order_type(order_type: OrderType) -> str:
        return "Limit" if order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER] else "Market"

    @staticmethod
    def to_hb_order_type(backpack_type: str) -> OrderType:
        return OrderType[backpack_type]

    @property
    def authenticator(self):
        return BackpackAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        if self._domain == "exchange":
            return "backpack"
        else:
            return f"backpack_{self._domain}"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return self._domain

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.PING_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        # TODO
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.LIMIT, price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Override to use simple uint32 order IDs for Backpack
        """
        new_order_id = get_new_numeric_client_order_id(nonce_creator=self._nonce_creator,
                                                       max_id_bit_count=CONSTANTS.MAX_ORDER_ID_LEN)
        numeric_order_id = str(new_order_id)

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

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType = OrderType.LIMIT, price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Override to use simple uint32 order IDs for Backpack
        """
        new_order_id = get_new_numeric_client_order_id(nonce_creator=self._nonce_creator,
                                                       max_id_bit_count=CONSTANTS.MAX_ORDER_ID_LEN)
        numeric_order_id = str(new_order_id)
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

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pairs_prices = await self._api_get(path_url=CONSTANTS.TICKER_BOOK_PATH_URL)
        return pairs_prices

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        request_description = str(request_exception)

        is_time_synchronizer_related = (
            "INVALID_CLIENT_REQUEST" in request_description
            and (
                "timestamp" in request_description.lower()
                or "Invalid timestamp" in request_description
                or "Request has expired" in request_description
            )
        )
        return is_time_synchronizer_related

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return str(CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE) in str(
            status_update_exception
        ) and CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return str(CONSTANTS.UNKNOWN_ORDER_ERROR_CODE) in str(
            cancelation_exception
        ) and CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BackpackAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BackpackAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = order_type is OrderType.LIMIT_MAKER
        return AddedToCostTradeFee(percent=self.estimate_fee_pct(is_maker))

    def exchange_symbol_associated_to_pair(self, trading_pair: str) -> str:
        return trading_pair.replace("-", "_")

    def trading_pair_associated_to_exchange_symbol(self, symbol: str) -> str:
        return symbol.replace("_", "-")

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        order_result = None
        amount_str = f"{amount:f}"
        order_type_enum = BackpackExchange.backpack_order_type(order_type)
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        api_params = {
            "instruction": "orderExecute",
            "symbol": symbol,
            "side": side_str,
            "quantity": amount_str,
            "clientId": int(order_id),
            "orderType": order_type_enum,
        }
        if order_type_enum == "Limit":
            price_str = f"{price:f}"
            api_params["price"] = price_str
            api_params["postOnly"] = order_type == OrderType.LIMIT_MAKER
            api_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC
        try:
            order_result = await self._api_post(
                path_url=CONSTANTS.ORDER_PATH_URL,
                data=api_params,
                is_auth_required=True)
            o_id = str(order_result["id"])
            transact_time = order_result["createdAt"] * 1e-3
        except IOError as e:
            error_description = str(e)

            # Check for LIMIT_MAKER post-only rejection
            is_post_only_rejection = (
                order_type == OrderType.LIMIT_MAKER
                and "INVALID_ORDER" in error_description
                and "Order would immediately match and take" in error_description
            )

            if is_post_only_rejection:
                side = "BUY" if trade_type is TradeType.BUY else "SELL"
                self.logger().warning(
                    f"LIMIT_MAKER {side} order for {trading_pair} rejected: "
                    f"Order price {price} would immediately match and take liquidity. "
                    f"LIMIT_MAKER orders can only be placed as maker orders (post-only). "
                    f"Try adjusting your price to ensure the order is not immediately executable."
                )
                raise ValueError(
                    f"LIMIT_MAKER order would immediately match and take liquidity. "
                    f"Price {price} crosses the spread for {side} order on {trading_pair}."
                ) from e

            # Check for server overload
            is_server_overloaded = (
                "503" in error_description
                and "Unknown error, please check your request or try again later." in error_description
            )
            if is_server_overloaded:
                o_id = "UNKNOWN"
                transact_time = self._time_synchronizer.time()
            else:
                raise
        return o_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        symbol = self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        api_params = {
            "instruction": "orderCancel",
            "symbol": symbol,
            "clientId": int(order_id),
        }
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.ORDER_PATH_URL,
            data=api_params,
            is_auth_required=True)
        if cancel_result.get("status") == "Cancelled":
            return True
        return False

    async def _format_trading_rules(self, exchange_info_dict: List[Dict[str, Any]]) -> List[TradingRule]:
        """
        Signature type modified from dict to list due to the new exchange info format.
        """
        trading_pair_rules = exchange_info_dict.copy()
        retval = []
        for rule in trading_pair_rules:
            if not utils.is_exchange_information_valid(rule):
                continue
            try:
                trading_pair = self.trading_pair_associated_to_exchange_symbol(symbol=rule.get("symbol"))
                filters = rule.get("filters")

                min_order_size = Decimal(filters["quantity"]["minQuantity"])
                tick_size = Decimal(filters["price"]["tickSize"])
                step_size = Decimal(filters["quantity"]["stepSize"])
                min_notional = Decimal("0")  # min notional is not supported by Backpack
                retval.append(
                    TradingRule(trading_pair,
                                min_order_size=min_order_size,
                                min_price_increment=Decimal(tick_size),
                                min_base_amount_increment=Decimal(step_size),
                                min_notional_size=Decimal(min_notional)))
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    async def _status_polling_loop_fetch_updates(self):
        await super()._status_polling_loop_fetch_updates()

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            data = event_message.get("data")
            if not isinstance(data, dict):
                continue

            event_type = data.get("e")
            if event_type is None:
                continue

            try:
                if event_type in {
                    "orderAccepted",
                    "orderCancelled",
                    "orderExpired",
                    "orderFill",
                    "orderModified",
                    "triggerPlaced",
                    "triggerFailed",
                }:
                    # Get IDs, keeping None as None (not converting to string "None")
                    exchange_order_id = data.get("i")
                    if exchange_order_id is not None:
                        exchange_order_id = str(exchange_order_id)

                    client_order_id = data.get("c")
                    if client_order_id is not None:
                        client_order_id = str(client_order_id)

                    # 1) Resolve tracked order
                    tracked_order = None

                    if client_order_id is not None:
                        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)

                    # Fallback: sometimes 'c' is absent; match by exchange_order_id
                    if tracked_order is None and exchange_order_id is not None:
                        for o in self._order_tracker.all_updatable_orders.values():
                            if str(o.exchange_order_id) == exchange_order_id:
                                tracked_order = o
                                client_order_id = o.client_order_id  # recover internal id
                                break

                    # If still not found, nothing to update
                    if tracked_order is None or client_order_id is None:
                        continue

                    # 2) Trade fill event
                    if event_type == "orderFill":
                        # Trade fields are only present on orderFill events
                        fee_token = data.get("N")
                        fee_amount = data.get("n")

                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=tracked_order.trade_type,
                            percent_token=fee_token,
                            flat_fees=(
                                [TokenAmount(amount=Decimal(str(fee_amount)), token=str(fee_token))]
                                if fee_token is not None and fee_amount is not None
                                else []
                            ),
                        )

                        fill_qty = Decimal(str(data["l"]))
                        fill_price = Decimal(str(data["L"]))

                        trade_update = TradeUpdate(
                            trade_id=str(data["t"]),
                            client_order_id=client_order_id,
                            exchange_order_id=exchange_order_id,
                            trading_pair=tracked_order.trading_pair,
                            fee=fee,
                            fill_base_amount=fill_qty,
                            fill_quote_amount=fill_qty * fill_price,
                            fill_price=fill_price,
                            # Backpack timestamps are microseconds
                            fill_timestamp=data["T"] * 1e-6,
                        )
                        self._order_tracker.process_trade_update(trade_update)

                    # 3) Order state update
                    raw_state = data.get("X")
                    new_state = CONSTANTS.ORDER_STATE.get(raw_state, OrderState.FAILED)

                    order_update = OrderUpdate(
                        trading_pair=tracked_order.trading_pair,
                        # Backpack event time is microseconds
                        update_timestamp=data["E"] * 1e-6,
                        new_state=new_state,
                        client_order_id=client_order_id,
                        exchange_order_id=exchange_order_id,
                    )
                    self._order_tracker.process_order_update(order_update=order_update)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = order.exchange_order_id
            trading_pair = self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            try:
                params = {
                    "instruction": "fillHistoryQueryAll",
                    "symbol": trading_pair,
                    "orderId": exchange_order_id
                }
                all_fills_response = await self._api_get(
                    path_url=CONSTANTS.MY_TRADES_PATH_URL,
                    params=params,
                    is_auth_required=True)

                # Check for error responses from the exchange
                if isinstance(all_fills_response, dict) and "code" in all_fills_response:
                    code = all_fills_response["code"]
                    if code == "INVALID_ORDER":
                        # Order doesn't exist on exchange, mark as failed
                        order_update = OrderUpdate(
                            trading_pair=order.trading_pair,
                            new_state=OrderState.FAILED,
                            client_order_id=order.client_order_id,
                            exchange_order_id=order.exchange_order_id,
                            update_timestamp=self._time_synchronizer.time(),
                            misc_updates={
                                "error_type": "INVALID_ORDER",
                                "error_message": all_fills_response.get("msg", "Order does not exist on exchange")
                            }
                        )
                        self._order_tracker.process_order_update(order_update=order_update)
                        return trade_updates

                # Process trade fills
                for trade in all_fills_response:
                    exchange_order_id = str(trade["orderId"])
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=order.trade_type,
                        percent_token=trade["feeSymbol"],
                        flat_fees=[TokenAmount(amount=Decimal(trade["fee"]), token=trade["feeSymbol"])]
                    )
                    trade_update = TradeUpdate(
                        trade_id=str(trade["tradeId"]),
                        client_order_id=order.client_order_id,
                        exchange_order_id=exchange_order_id,
                        trading_pair=trading_pair,
                        fee=fee,
                        fill_base_amount=Decimal(trade["quantity"]),
                        fill_quote_amount=Decimal(trade["quantity"]) * Decimal(trade["price"]),
                        fill_price=Decimal(trade["price"]),
                        fill_timestamp=pd.Timestamp(trade["timestamp"]).timestamp(),
                    )
                    trade_updates.append(trade_update)
            except IOError as ex:
                if not self._is_request_exception_related_to_time_synchronizer(request_exception=ex):
                    raise
        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        trading_pair = self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        updated_order_data = await self._api_get(
            path_url=CONSTANTS.ORDER_PATH_URL,
            params={
                "instruction": "orderQuery",
                "symbol": trading_pair,
                "clientId": tracked_order.client_order_id},
            is_auth_required=True)

        new_state = CONSTANTS.ORDER_STATE[updated_order_data["status"]]

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data["id"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=updated_order_data["createdAt"] * 1e-3,
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_get(
            path_url=CONSTANTS.BALANCE_PATH_URL,
            params={"instruction": "balanceQuery"},
            is_auth_required=True)

        if account_info:
            for asset_name, balance_entry in account_info.items():
                free_balance = Decimal(balance_entry["available"])
                total_balance = Decimal(balance_entry["available"]) + Decimal(balance_entry["locked"])
                self._account_available_balances[asset_name] = free_balance
                self._account_balances[asset_name] = total_balance
                remote_asset_names.add(asset_name)

            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in exchange_info:
            if utils.is_exchange_information_valid(symbol_data):
                mapping[symbol_data["symbol"]] = combine_to_hb_trading_pair(base=symbol_data["baseSymbol"],
                                                                            quote=symbol_data["quoteSymbol"])
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {
            "symbol": self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        }

        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL,
            params=params
        )

        return float(resp_json["lastPrice"])
