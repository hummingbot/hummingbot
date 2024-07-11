import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.kucoin import (
    kucoin_constants as CONSTANTS,
    kucoin_utils as utils,
    kucoin_web_utils as web_utils,
)
from hummingbot.connector.exchange.kucoin.kucoin_api_order_book_data_source import KucoinAPIOrderBookDataSource
from hummingbot.connector.exchange.kucoin.kucoin_api_user_stream_data_source import KucoinAPIUserStreamDataSource
from hummingbot.connector.exchange.kucoin.kucoin_auth import KucoinAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class KucoinExchange(ExchangePyBase):
    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 kucoin_api_key: str,
                 kucoin_passphrase: str,
                 kucoin_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        self.kucoin_api_key = kucoin_api_key
        self.kucoin_passphrase = kucoin_passphrase
        self.kucoin_secret_key = kucoin_secret_key
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_order_fill_ts_s: float = 0
        super().__init__(client_config_map=client_config_map)

    @property
    def authenticator(self):
        return KucoinAuth(
            api_key=self.kucoin_api_key,
            passphrase=self.kucoin_passphrase,
            secret_key=self.kucoin_secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "kucoin"

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
        return ""

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.SYMBOLS_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.SYMBOLS_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.SERVER_TIME_PATH_URL

    @property
    def orders_path_url(self):
        return CONSTANTS.ORDERS_PATH_URL_HFT if self._domain == "hft" else CONSTANTS.ORDERS_PATH_URL

    @property
    def fills_path_url(self):
        return CONSTANTS.FILLS_PATH_URL_HFT if self.domain == "hft" else CONSTANTS.FILLS_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pairs_prices = await self._api_get(path_url=CONSTANTS.ALL_TICKERS_PATH_URL)
        return pairs_prices

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        return CONSTANTS.RET_CODE_AUTH_TIMESTAMP_ERROR in error_description and CONSTANTS.RET_MSG_AUTH_TIMESTAMP_ERROR in error_description

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return (str(CONSTANTS.RET_CODE_RESOURCE_NOT_FOUND) in str(status_update_exception) and
                str(CONSTANTS.RET_MSG_RESOURCE_NOT_FOUND) in str(status_update_exception))

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return (str(CONSTANTS.RET_CODE_ORDER_NOT_EXIST_OR_NOT_ALLOW_TO_CANCEL) in str(cancelation_exception)
                and str(CONSTANTS.RET_MSG_ORDER_NOT_EXIST_OR_NOT_ALLOW_TO_CANCEL) in str(cancelation_exception))

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self.domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return KucoinAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return KucoinAPIUserStreamDataSource(
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
                 is_maker: Optional[bool] = None) -> AddedToCostTradeFee:

        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)
        if trading_pair in self._trading_fees:
            fees_data = self._trading_fees[trading_pair]
            fee_value = Decimal(fees_data["makerFeeRate"]) if is_maker else Decimal(fees_data["takerFeeRate"])
            fee = AddedToCostTradeFee(percent=fee_value)
        else:
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

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(utils.is_pair_information_valid, exchange_info.get("data", [])):
            mapping[symbol_data["symbol"]] = combine_to_hb_trading_pair(base=symbol_data["baseCurrency"],
                                                                        quote=symbol_data["quoteCurrency"])
        self._set_trading_pair_symbol_map(mapping)

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        side = trade_type.name.lower()
        order_type_str = "market" if order_type == OrderType.MARKET else "limit"
        data = {
            "size": str(amount),
            "clientOid": order_id,
            "side": side,
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "type": order_type_str,
        }
        if order_type is OrderType.LIMIT:
            data["price"] = str(price)
        elif order_type is OrderType.LIMIT_MAKER:
            data["price"] = str(price)
            data["postOnly"] = True
        exchange_order_id = await self._api_post(
            path_url=self.orders_path_url,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.POST_ORDER_LIMIT_ID,
        )
        if exchange_order_id.get("data") is None:
            raise IOError(f"Error placing order on Kucoin: {exchange_order_id}")
        return str(exchange_order_id["data"]["orderId"]), self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        This implementation specific function is called by _cancel, and returns True if successful
        """
        exchange_order_id = await tracked_order.get_exchange_order_id()
        params = {"symbol": tracked_order.trading_pair} if self.domain == "hft" else None
        cancel_result = await self._api_delete(
            f"{self.orders_path_url}/{exchange_order_id}",
            params=params,
            is_auth_required=True,
            limit_id=CONSTANTS.DELETE_ORDER_LIMIT_ID
        )
        response_param = "orderId" if self.domain == "hft" else "cancelledOrderIds"
        if cancel_result.get("data") is not None:
            return tracked_order.exchange_order_id in cancel_result["data"].get(response_param, [])
        else:
            raise IOError(f"Error cancelling order on Kucoin: {cancel_result}")

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("type")
                event_subject = event_message.get("subject")
                execution_data = event_message.get("data")

                # Refer to https://docs.kucoin.com/#private-order-change-events
                if event_type == "message" and event_subject == CONSTANTS.ORDER_CHANGE_EVENT_TYPE:
                    order_event_type = execution_data["type"]
                    client_order_id: Optional[str] = execution_data.get("clientOid")

                    fillable_order = self._order_tracker.all_fillable_orders.get(client_order_id)
                    updatable_order = self._order_tracker.all_updatable_orders.get(client_order_id)

                    event_timestamp = execution_data["ts"] * 1e-9

                    if fillable_order is not None and order_event_type == "match":
                        execute_amount_diff = Decimal(execution_data["matchSize"])
                        execute_price = Decimal(execution_data["matchPrice"])

                        fee = self.get_fee(
                            fillable_order.base_asset,
                            fillable_order.quote_asset,
                            fillable_order.order_type,
                            fillable_order.trade_type,
                            execute_price,
                            execute_amount_diff,
                        )

                        trade_update = TradeUpdate(
                            trade_id=execution_data["tradeId"],
                            client_order_id=client_order_id,
                            exchange_order_id=execution_data["orderId"],
                            trading_pair=updatable_order.trading_pair,
                            fee=fee,
                            fill_base_amount=execute_amount_diff,
                            fill_quote_amount=execute_amount_diff * execute_price,
                            fill_price=execute_price,
                            fill_timestamp=event_timestamp,
                        )
                        self._order_tracker.process_trade_update(trade_update)

                    if updatable_order is not None:
                        updated_status = updatable_order.current_state
                        if order_event_type == "open":
                            updated_status = OrderState.OPEN
                        elif order_event_type == "match":
                            updated_status = OrderState.PARTIALLY_FILLED
                        elif order_event_type == "filled":
                            updated_status = OrderState.FILLED
                        elif order_event_type == "canceled":
                            updated_status = OrderState.CANCELED

                        order_update = OrderUpdate(
                            trading_pair=updatable_order.trading_pair,
                            update_timestamp=event_timestamp,
                            new_state=updated_status,
                            client_order_id=client_order_id,
                            exchange_order_id=execution_data["orderId"],
                        )
                        self._order_tracker.process_order_update(order_update=order_update)

                elif event_type == "message" and event_subject == CONSTANTS.BALANCE_EVENT_TYPE:
                    currency = execution_data["currency"]
                    available_balance = Decimal(execution_data["available"])
                    total_balance = Decimal(execution_data["total"])
                    self._account_balances.update({currency: total_balance})
                    self._account_available_balances.update({currency: available_balance})

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        account_type = "trade_hf" if self.domain == "hft" else "trade"

        response = await self._api_get(
            path_url=CONSTANTS.ACCOUNTS_PATH_URL,
            params={"type": account_type},
            is_auth_required=True)

        if response:
            for balance_entry in response["data"]:
                asset_name = balance_entry["currency"]
                self._account_available_balances[asset_name] = Decimal(balance_entry["available"])
                self._account_balances[asset_name] = Decimal(balance_entry["balance"])
                remote_asset_names.add(asset_name)

            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]

    async def _format_trading_rules(self, raw_trading_pair_info: Dict[str, Any]) -> List[TradingRule]:
        trading_rules = []

        for info in raw_trading_pair_info["data"]:
            if utils.is_pair_information_valid(info):
                try:
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=info.get("symbol"))
                    trading_rules.append(
                        TradingRule(trading_pair=trading_pair,
                                    min_order_size=Decimal(info["baseMinSize"]),
                                    max_order_size=Decimal(info["baseMaxSize"]),
                                    min_price_increment=Decimal(info['priceIncrement']),
                                    min_base_amount_increment=Decimal(info['baseIncrement']),
                                    min_quote_amount_increment=Decimal(info['quoteIncrement']),
                                    min_notional_size=Decimal(info["quoteMinSize"]))
                    )
                except Exception:
                    self.logger().error(f"Error parsing the trading pair rule {info}. Skipping.", exc_info=True)
        return trading_rules

    async def _update_trading_fees(self):
        trading_symbols = [await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                           for trading_pair in self._trading_pairs]
        fees_json = []
        for idx in range(0, len(trading_symbols), CONSTANTS.TRADING_FEES_SYMBOL_LIMIT):
            sub_trading_symbols = trading_symbols[idx:idx + CONSTANTS.TRADING_FEES_SYMBOL_LIMIT]
            params = {"symbols": ",".join(sub_trading_symbols)}
            resp = await self._api_get(
                path_url=CONSTANTS.FEE_PATH_URL,
                params=params,
                is_auth_required=True,
            )
            fees_json.extend(resp["data"])

        for fee_json in fees_json:
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=fee_json["symbol"])
            self._trading_fees[trading_pair] = fee_json

    async def _update_orders_fills(self, orders: List[InFlightOrder]):
        # This method in the base ExchangePyBase, makes an API call for each order.
        # Given the rate limit of the API method and the breadth of info provided by the method
        # the mitigation proposal is to collect all orders in one shot, then parse them
        # Note that this is limited to 500 orders (pagination)
        # An alternative for Kucoin would be to use the limit/fills that returns 24hr updates, which should
        # be sufficient, the rate limit seems better suited
        all_trades_updates: List[TradeUpdate] = []
        if len(orders) > 0:
            try:
                all_trades_updates: List[TradeUpdate] = await self._all_trades_updates(orders)
            except asyncio.CancelledError:
                raise
            except Exception as request_error:
                self.logger().warning(
                    f"Failed to fetch trade updates. Error: {request_error}")

            for trade_update in all_trades_updates:
                self._order_tracker.process_trade_update(trade_update)

    async def _all_trades_updates(self, orders: List[InFlightOrder]) -> List[TradeUpdate]:
        trade_updates: List[TradeUpdate] = []
        if len(orders) > 0:
            exchange_to_client = {o.exchange_order_id: {"client_id": o.client_order_id, "trading_pair": o.trading_pair} for o in orders}

            # We request updates from either:
            #    - The earliest order creation_timestamp in the list (first couple requests)
            #    - The last time we got a fill
            self._last_order_fill_ts_s = int(max(self._last_order_fill_ts_s, min([o.creation_timestamp for o in orders])))

            # From Kucoin https://docs.kucoin.com/#list-fills:
            # "If you only specified the start time, the system will automatically
            #  calculate the end time (end time = start time + 7 * 24 hours)"
            all_fills_response = await self._api_get(
                path_url=self.fills_path_url,
                params={
                    "pageSize": 500,
                    "startAt": self._last_order_fill_ts_s * 1000,
                },
                is_auth_required=True)

            for trade in all_fills_response.get("items", []):
                if str(trade["orderId"]) in exchange_to_client:
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=TradeType.BUY if trade["side"] == "buy" else "sell",
                        percent_token=trade["feeCurrency"],
                        flat_fees=[TokenAmount(amount=Decimal(trade["fee"]), token=trade["feeCurrency"])]
                    )

                    client_info = exchange_to_client[str(trade["orderId"])]
                    trade_update = TradeUpdate(
                        trade_id=str(trade["tradeId"]),
                        client_order_id=client_info["client_id"],
                        trading_pair=client_info["trading_pair"],
                        exchange_order_id=str(trade["orderId"]),
                        fee=fee,
                        fill_base_amount=Decimal(trade["size"]),
                        fill_quote_amount=Decimal(trade["funds"]),
                        fill_price=Decimal(trade["price"]),
                        fill_timestamp=trade["createdAt"] * 1e-3,
                    )
                    trade_updates.append(trade_update)
                    # Update the last fill timestamp with the latest one
                    self._last_order_fill_ts_s = max(self._last_order_fill_ts_s, trade["createdAt"] * 1e-3)

        return trade_updates

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        raise Exception("Developer: This method should not be called, it is obsoleted for Kucoin")

        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = order.exchange_order_id
            all_fills_response = await self._api_get(
                path_url=self.fills_path_url,
                params={
                    "orderId": exchange_order_id,
                    "pageSize": 500,
                },
                is_auth_required=True)

            for trade in all_fills_response.get("items", []):
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=order.trade_type,
                    percent_token=trade["feeCurrency"],
                    flat_fees=[TokenAmount(amount=Decimal(trade["fee"]), token=trade["feeCurrency"])]
                )
                trade_update = TradeUpdate(
                    trade_id=str(trade["tradeId"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    trading_pair=order.trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(trade["size"]),
                    fill_quote_amount=Decimal(trade["funds"]),
                    fill_price=Decimal(trade["price"]),
                    fill_timestamp=trade["createdAt"] * 1e-3,
                )
                trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        exchange_order_id = await tracked_order.get_exchange_order_id()
        params = {"symbol": tracked_order.trading_pair} if self.domain == "hft" else None
        updated_order_data = await self._api_get(
            path_url=f"{self.orders_path_url}/{exchange_order_id}",
            is_auth_required=True,
            params=params,
            limit_id=CONSTANTS.GET_ORDER_LIMIT_ID)

        ordered_canceled = updated_order_data["data"]["cancelExist"]
        is_active = updated_order_data["data"]["active"] if self.domain == "hft" else updated_order_data["data"]["isActive"]
        op_type = updated_order_data["data"]["opType"]

        new_state = tracked_order.current_state
        if ordered_canceled or op_type == "CANCEL":
            new_state = OrderState.CANCELED
        elif not is_active:
            new_state = OrderState.FILLED

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=updated_order_data["data"]["id"],
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=new_state,
        )

        return order_update

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        }

        resp_json = await self._api_request(
            path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL,
            method=RESTMethod.GET,
            params=params
        )

        return float(resp_json["data"]["price"])
