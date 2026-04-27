import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.gemini import (
    gemini_constants as CONSTANTS,
    gemini_utils as utils,
    gemini_web_utils as web_utils,
)
from hummingbot.connector.exchange.gemini.gemini_api_order_book_data_source import GeminiAPIOrderBookDataSource
from hummingbot.connector.exchange.gemini.gemini_api_user_stream_data_source import GeminiAPIUserStreamDataSource
from hummingbot.connector.exchange.gemini.gemini_auth import GeminiAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class GeminiExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(self,
                 gemini_api_key: str,
                 gemini_api_secret: str,
                 balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
                 rate_limits_share_pct: Decimal = Decimal("100"),
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 ):
        self.api_key = gemini_api_key
        self.secret_key = gemini_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_gemini_timestamp = 1.0
        self._gemini_symbol_map: Optional[bidict] = None
        super().__init__(balance_asset_limit, rate_limits_share_pct)
        # Gemini does not provide balance updates through websocket
        self.real_time_balance_update = False

    @staticmethod
    def gemini_order_type(order_type: OrderType) -> str:
        if order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER]:
            return "exchange limit"
        return "exchange market"

    @property
    def authenticator(self):
        return GeminiAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        if self._domain == CONSTANTS.DEFAULT_DOMAIN:
            return "gemini"
        else:
            return f"gemini_{self._domain}"

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
        return CONSTANTS.SYMBOLS_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.SYMBOLS_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.SYMBOLS_PATH_URL

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
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        # Gemini uses nonce-based auth, not timestamp. Nonce errors look different.
        error_str = str(request_exception)
        return "InvalidNonce" in error_str or "nonce" in error_str.lower()

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_FOUND_ERROR in str(status_update_exception) or \
            CONSTANTS.ORDER_NOT_FOUND_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_FOUND_ERROR in str(cancelation_exception) or \
            CONSTANTS.ORDER_NOT_FOUND_MESSAGE in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return GeminiAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return GeminiAPIUserStreamDataSource(
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

    def _set_trading_pair_symbol_map(self, trading_pair_and_symbol_map):
        super()._set_trading_pair_symbol_map(trading_pair_and_symbol_map)
        self._gemini_symbol_map = bidict(trading_pair_and_symbol_map) if trading_pair_and_symbol_map is not None else None

    def exchange_symbol_associated_to_pair(self, trading_pair: str) -> str:
        if self._gemini_symbol_map is not None:
            inverse = self._gemini_symbol_map.inverse
            if trading_pair in inverse:
                return inverse[trading_pair]
        return trading_pair.replace("-", "").lower()

    def trading_pair_associated_to_exchange_symbol(self, symbol: str) -> str:
        if self._gemini_symbol_map is not None and symbol in self._gemini_symbol_map:
            return self._gemini_symbol_map[symbol]
        return symbol

    async def _make_trading_pairs_request(self) -> Any:
        return await self._make_trading_rules_request()

    async def _make_trading_rules_request(self) -> Any:
        symbols_response = await self._api_get(path_url=CONSTANTS.SYMBOLS_PATH_URL)
        # If the response is already a list of detail dicts (has "symbol" key), return directly
        if symbols_response and isinstance(symbols_response[0], dict):
            return symbols_response
        # Otherwise it's a list of symbol name strings — fetch details for each
        details = []
        for symbol in symbols_response:
            try:
                detail = await self._api_get(
                    path_url=CONSTANTS.SYMBOL_DETAILS_PATH_URL.format(symbol=symbol),
                    limit_id=CONSTANTS.SYMBOL_DETAILS_PATH_URL)
                details.append(detail)
            except Exception:
                self.logger().debug(f"Error fetching details for {symbol}, skipping.")
        return details

    async def _format_trading_rules(self, exchange_info_dict: List[Dict[str, Any]]) -> List[TradingRule]:
        retval = []
        for detail in exchange_info_dict:
            if not utils.is_exchange_information_valid(detail):
                continue
            try:
                symbol = detail["symbol"].lower()
                trading_pair = self.trading_pair_associated_to_exchange_symbol(symbol)
                tick_size = Decimal(str(detail["tick_size"]))
                min_order_size = Decimal(str(detail["min_order_size"]))
                quote_increment = Decimal(str(detail["quote_increment"]))
                retval.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=min_order_size,
                        min_price_increment=quote_increment,
                        min_base_amount_increment=tick_size,
                        min_notional_size=Decimal("0"),
                    ))
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {detail}. Skipping.")
        return retval

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List[Dict[str, Any]]):
        mapping = bidict()
        for detail in exchange_info:
            if utils.is_exchange_information_valid(detail):
                symbol = detail["symbol"].lower()
                base = detail["base_currency"].upper()
                quote = detail["quote_currency"].upper()
                mapping[symbol] = combine_to_hb_trading_pair(base=base, quote=quote)
        self._set_trading_pair_symbol_map(mapping)

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        symbol = self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        side = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        order_type_str = self.gemini_order_type(order_type)

        api_params = {
            "client_order_id": order_id,
            "symbol": symbol,
            "amount": f"{amount:f}",
            "price": f"{price:f}" if price != s_decimal_NaN else "1",
            "side": side,
            "type": order_type_str,
        }

        if order_type == OrderType.LIMIT_MAKER:
            api_params["options"] = ["maker-or-cancel"]

        try:
            order_result = await self._api_post(
                path_url=CONSTANTS.NEW_ORDER_PATH_URL,
                data=api_params,
                is_auth_required=True)
            o_id = str(order_result["order_id"])
            transact_time = float(order_result.get("timestampms", 0)) * 1e-3
        except IOError as e:
            error_description = str(e)
            is_post_only_rejection = (
                order_type == OrderType.LIMIT_MAKER
                and "MakerOrCancelWouldTake" in error_description
            )
            if is_post_only_rejection:
                raise ValueError(
                    f"LIMIT_MAKER order would immediately match and take liquidity. "
                    f"Price {price} crosses the spread for {side} order on {trading_pair}."
                ) from e
            raise

        return o_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        api_params = {
            "order_id": int(tracked_order.exchange_order_id),
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_PATH_URL,
            data=api_params,
            is_auth_required=True)
        return cancel_result.get("is_cancelled", False)

    async def _update_trading_fees(self):
        pass

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("type")
                if event_type is None:
                    continue

                if event_type in ("accepted", "booked", "cancelled", "rejected", "closed"):
                    client_order_id = event_message.get("client_order_id")
                    exchange_order_id = str(event_message.get("order_id", ""))

                    tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                    if tracked_order is None and exchange_order_id:
                        for o in self._order_tracker.all_updatable_orders.values():
                            if str(o.exchange_order_id) == exchange_order_id:
                                tracked_order = o
                                client_order_id = o.client_order_id
                                break

                    if tracked_order is None or client_order_id is None:
                        continue

                    new_state = CONSTANTS.ORDER_STATE.get(event_type, OrderState.FAILED)
                    order_update = OrderUpdate(
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=float(event_message.get("timestampms", 0)) * 1e-3,
                        new_state=new_state,
                        client_order_id=client_order_id,
                        exchange_order_id=exchange_order_id,
                    )
                    self._order_tracker.process_order_update(order_update=order_update)

                elif event_type == "fill":
                    client_order_id = event_message.get("client_order_id")
                    exchange_order_id = str(event_message.get("order_id", ""))

                    tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                    if tracked_order is None and exchange_order_id:
                        for o in self._order_tracker.all_updatable_orders.values():
                            if str(o.exchange_order_id) == exchange_order_id:
                                tracked_order = o
                                client_order_id = o.client_order_id
                                break

                    if tracked_order is None or client_order_id is None:
                        continue

                    fill_data = event_message.get("fill", {})
                    fee_currency = fill_data.get("fee_currency", "").upper()
                    fee_amount = Decimal(str(fill_data.get("fee", "0")))

                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=tracked_order.trade_type,
                        percent_token=fee_currency,
                        flat_fees=[TokenAmount(amount=fee_amount, token=fee_currency)] if fee_currency else [],
                    )

                    fill_price = Decimal(str(fill_data["price"]))
                    fill_amount = Decimal(str(fill_data["amount"]))

                    trade_update = TradeUpdate(
                        trade_id=str(fill_data["trade_id"]),
                        client_order_id=client_order_id,
                        exchange_order_id=exchange_order_id,
                        trading_pair=tracked_order.trading_pair,
                        fee=fee,
                        fill_base_amount=fill_amount,
                        fill_quote_amount=fill_amount * fill_price,
                        fill_price=fill_price,
                        fill_timestamp=float(event_message.get("timestampms", 0)) * 1e-3,
                    )
                    self._order_tracker.process_trade_update(trade_update)

                    # Also update order state based on remaining amount
                    remaining = Decimal(str(event_message.get("remaining_amount", "0")))
                    new_state = OrderState.FILLED if remaining == Decimal("0") else OrderState.PARTIALLY_FILLED
                    order_update = OrderUpdate(
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=float(event_message.get("timestampms", 0)) * 1e-3,
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
            trading_pair = order.trading_pair
            try:
                all_fills_response = await self._api_post(
                    path_url=CONSTANTS.MY_TRADES_PATH_URL,
                    data={"symbol": self.exchange_symbol_associated_to_pair(trading_pair)},
                    is_auth_required=True)

                for trade in all_fills_response:
                    if str(trade.get("order_id", "")) != str(order.exchange_order_id):
                        continue
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=order.trade_type,
                        percent_token=trade["fee_currency"],
                        flat_fees=[TokenAmount(
                            amount=Decimal(str(trade["fee_amount"])),
                            token=trade["fee_currency"]
                        )]
                    )
                    trade_update = TradeUpdate(
                        trade_id=str(trade["tid"]),
                        client_order_id=order.client_order_id,
                        exchange_order_id=str(trade["order_id"]),
                        trading_pair=trading_pair,
                        fee=fee,
                        fill_base_amount=Decimal(str(trade["amount"])),
                        fill_quote_amount=Decimal(str(trade["amount"])) * Decimal(str(trade["price"])),
                        fill_price=Decimal(str(trade["price"])),
                        fill_timestamp=float(trade.get("timestampms", 0)) * 1e-3,
                    )
                    trade_updates.append(trade_update)
            except IOError as ex:
                if not self._is_request_exception_related_to_time_synchronizer(request_exception=ex):
                    raise
        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        updated_order_data = await self._api_post(
            path_url=CONSTANTS.ORDER_STATUS_PATH_URL,
            data={"order_id": int(tracked_order.exchange_order_id)},
            is_auth_required=True)

        is_live = updated_order_data.get("is_live", False)
        is_cancelled = updated_order_data.get("is_cancelled", False)
        remaining = Decimal(str(updated_order_data.get("remaining_amount", "0")))
        executed = Decimal(str(updated_order_data.get("executed_amount", "0")))

        if is_cancelled:
            new_state = OrderState.CANCELED
        elif not is_live and remaining == Decimal("0") and executed > Decimal("0"):
            new_state = OrderState.FILLED
        elif is_live and executed > Decimal("0"):
            new_state = OrderState.PARTIALLY_FILLED
        elif is_live:
            new_state = OrderState.OPEN
        else:
            new_state = OrderState.FAILED

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data["order_id"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=float(updated_order_data.get("timestampms", 0)) * 1e-3,
            new_state=new_state,
        )
        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_post(
            path_url=CONSTANTS.BALANCES_PATH_URL,
            data={"account": CONSTANTS.DEFAULT_ACCOUNT},
            is_auth_required=True)

        if account_info:
            for balance in account_info:
                asset = balance["currency"].upper()
                available = Decimal(str(balance["available"]))
                total = Decimal(str(balance["amount"]))
                self._account_available_balances[asset] = available
                self._account_balances[asset] = total
                remote_asset_names.add(asset)

            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TICKER_V2_PATH_URL.format(symbol=symbol),
            limit_id=CONSTANTS.TICKER_V2_PATH_URL)
        return float(resp_json.get("close", resp_json.get("last", 0)))
