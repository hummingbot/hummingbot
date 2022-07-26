import asyncio
import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.bittrex import (
    bittrex_constants as CONSTANTS,
    bittrex_utils,
    bittrex_web_utils as web_utils,
)
from hummingbot.connector.exchange.bittrex.bittrex_api_order_book_data_source import BittrexAPIOrderBookDataSource
from hummingbot.connector.exchange.bittrex.bittrex_api_user_stream_data_source import BittrexAPIUserStreamDataSource
from hummingbot.connector.exchange.bittrex.bittrex_auth import BittrexAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BittrexExchange(ExchangePyBase):

    UPDATE_ORDERS_INTERVAL = 10.0
    web_utils = web_utils

    def __init__(self,
                 bittrex_api_key: str,
                 bittrex_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        self.api_key = bittrex_api_key
        self.secret_key = bittrex_secret_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        super().__init__()

    @property
    def name(self) -> str:
        return "bittrex"

    @property
    def authenticator(self) -> BittrexAuth:
        return BittrexAuth(self.api_key, self. secret_key)

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return None

    @property
    def client_order_id_max_length(self):
        return 40

    @property
    def client_order_id_prefix(self):
        return ""

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.SERVER_TIME_URL

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
        return [OrderType.LIMIT, OrderType.MARKET]

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return BittrexAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return BittrexAPIUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory)

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal
                           ) -> Tuple[str, float]:

        path_url = CONSTANTS.ORDER_CREATION_URL
        body = {
            "marketSymbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "direction": "BUY" if trade_type is TradeType.BUY else "SELL",
            "type": "LIMIT" if order_type is OrderType.LIMIT else "MARKET",
            "quantity": float(amount),
            "clientOrderId": order_id
        }
        if order_type is OrderType.LIMIT:
            body.update({
                "limit": float(price),
                "timeInForce": "GOOD_TIL_CANCELLED"
                # Available options [GOOD_TIL_CANCELLED, IMMEDIATE_OR_CANCEL,
                # FILL_OR_KILL, POST_ONLY_GOOD_TIL_CANCELLED]
            })
        elif order_type is OrderType.MARKET:
            body.update({
                "timeInForce": "IMMEDIATE_OR_CANCEL"
            })
        order_result = await self._api_post(
            path_url=path_url,
            params=body,
            data=body,
            is_auth_required=True)
        o_id = order_result["id"]
        transact_time = self._get_timestamp(order_result["createdAt"])
        return o_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        exchange_id = await tracked_order.get_exchange_order_id()
        api_params = {
            "id": exchange_id
        }
        cancel_result = await self._api_delete(
            path_url=CONSTANTS.ORDER_DETAIL_URL.format(exchange_id),
            params=api_params,
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_DETAIL_LIMIT_ID)
        if cancel_result["status"] == "CLOSED":
            return True
        return False

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        account_balances = await self._api_get(path_url=CONSTANTS.BALANCES_URL, is_auth_required=True)
        for balance_entry in account_balances:
            asset_name = balance_entry["currencySymbol"]
            available_balance = balance_entry["available"]
            total_balance = balance_entry["total"]
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)
        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _format_trading_rules(self, markets: List) -> List[TradingRule]:
        retval = []
        for market in markets:
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(market.get("symbol"))
                min_trade_size = market.get("minTradeSize")
                precision = market.get("precision")
                retval.append(TradingRule(trading_pair,
                                          min_order_size=min_trade_size,
                                          min_price_increment=Decimal(precision),
                                          min_base_amount_increment=Decimal(precision),
                                          min_notional_size=Decimal(precision)
                                          ))
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {market}. Skipping.", exc_info=True)
        return retval

    async def _update_trading_fees(self):
        resp = await self._api_get(
            path_url=CONSTANTS.FEES_URL,
            is_auth_required=True,
        )
        for fees in resp:
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=fees["marketSymbol"])
            self._trading_fees[trading_pair] = fees

    async def _update_order_status(self):
        tracked_orders = list(self.in_flight_orders.values())
        for tracked_order in tracked_orders:
            try:
                client_order_id = tracked_order.client_order_id
                exchange_order_id = await tracked_order.get_exchange_order_id()
                params = {
                    "orderId": exchange_order_id
                }
                order = None
                if exchange_order_id:
                    order = await self._api_get(path_url=CONSTANTS.ORDER_DETAIL_URL.format(exchange_order_id),
                                                params=params,
                                                is_auth_required=True,
                                                limit_id=CONSTANTS.ORDER_DETAIL_LIMIT_ID)
            except Exception:
                self.logger().network(
                    f"Error fetching status update for the order {client_order_id}",
                    app_warning_msg=f"Failed to fetch status update for the order {client_order_id}."
                )
                await self._order_tracker.process_order_not_found(client_order_id)
                continue
            if order is None:
                continue
            if "code" in order:
                self.logger().network(
                    f"Error fetching status update for the order {client_order_id}",
                    app_warning_msg=f"No matching orders found for {client_order_id}."
                )
                await self._order_tracker.process_order_not_found(client_order_id)
                continue
            new_state = self._get_order_status(order)
            update_time = self._get_timestamp(order["updatedAt"])
            update = OrderUpdate(
                client_order_id=client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=update_time,
                new_state=new_state,
            )
            self._order_tracker.process_order_update(update)

    async def _user_stream_event_listener(self):
        async for stream_message in self._iter_user_event_queue():
            try:
                content = stream_message.get("delta") or stream_message.get("deltas")
                if "marketSymbol" not in content:  # Updates total balance and available balance of specified currency
                    asset_name = content["currencySymbol"]
                    total_balance = content["total"]
                    available_balance = content["available"]
                    self._account_available_balances[asset_name] = available_balance
                    self._account_balances[asset_name] = total_balance
                elif "executedAt" in content:  # Updates track order status
                    safe_ensure_future(self._process_execution_event(content))
                else:
                    safe_ensure_future(self._process_order_update_event(content))

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _process_order_update_event(self, msg: Dict[str, Any]):
        order_id = msg["id"]
        update_time = self._get_timestamp(msg["updatedAt"])
        order_state = self._get_order_status(msg)
        tracked_order = self.in_flight_orders.get(msg["clientOrderId"])
        if tracked_order is not None:
            order_update = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=update_time,
                new_state=order_state,
                client_order_id=msg["clientOrderId"],
                exchange_order_id=order_id,
            )
            self._order_tracker.process_order_update(order_update=order_update)

    async def _process_execution_event(self, events: Dict[str, Any]):
        for execution_event in events:
            order_id = execution_event["orderId"]
            tracked_order = None
            for order in self.in_flight_orders.values():
                exchange_order_id = await order.get_exchange_order_id()
                if exchange_order_id == order_id:
                    tracked_order = order
                    break
            if tracked_order is not None:
                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=tracked_order.trade_type,
                    percent_token=tracked_order.trading_pair.split("-")[-1],
                    flat_fees=[TokenAmount(amount=execution_event["rate"],
                                           token=tracked_order.trading_pair.split("-")[-1])]
                )
                trade_update = TradeUpdate(
                    trade_id=execution_event["id"],
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=order_id,
                    trading_pair=tracked_order.trading_pair,
                    fee=fee,
                    fill_base_amount=execution_event["quantity"],
                    fill_quote_amount=execution_event["quantity"] * execution_event["rate"],
                    fill_price=execution_event["rate"],
                    fill_timestamp=await self._get_timestamp(execution_event["executedAt"]),
                )
                self._order_tracker.process_trade_update(trade_update)

    def _get_fee(self,
                 base_currency,
                 quote_currency,
                 order_type,
                 order_side,
                 amount,
                 price = s_decimal_NaN,
                 is_maker = None) -> AddedToCostTradeFee:
        is_maker = order_type is OrderType.LIMIT_MAKER
        return AddedToCostTradeFee(percent=self.estimate_fee_pct(is_maker))

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List):
        mapping = bidict()
        for symbol_data in filter(bittrex_utils.is_exchange_information_valid, exchange_info):
            mapping[symbol_data["symbol"]] = combine_to_hb_trading_pair(base=symbol_data["baseCurrencySymbol"],
                                                                        quote=symbol_data["quoteCurrencySymbol"])
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {
            "marketSymbol": exchange_symbol
        }
        resp = await self._api_get(
            path_url=CONSTANTS.SYMBOL_TICKER_PATH.format(exchange_symbol),
            params=params,
            limit_id=CONSTANTS.SYMBOL_TICKER_LIMIT_ID
        )
        return resp["lastTradeRate"]

    @staticmethod
    def _get_timestamp(transact_info):
        transact_time_info = datetime.datetime.strptime(transact_info, '%Y-%m-%d %H:%M:%S.%f')
        return datetime.datetime.timestamp(transact_time_info)

    @staticmethod
    def _get_order_status(order):
        order_state = order["status"]
        new_state = ""
        if order_state == "OPEN":
            new_state = CONSTANTS.ORDER_STATE[order_state]
        else:
            if order["fillQuantity"] == order["quantity"]:
                new_state = CONSTANTS.ORDER_STATE[order_state + "-FILLED"]
            else:
                new_state = CONSTANTS.ORDER_STATE[order_state + "-CANCELLED"]
        return new_state
