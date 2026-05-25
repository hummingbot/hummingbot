import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS, gemini_web_utils as web_utils
from hummingbot.connector.exchange.gemini.gemini_api_order_book_data_source import GeminiAPIOrderBookDataSource
from hummingbot.connector.exchange.gemini.gemini_api_user_stream_data_source import GeminiAPIUserStreamDataSource
from hummingbot.connector.exchange.gemini.gemini_auth import GeminiAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
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
                 ):
        self.api_key = gemini_api_key
        self.secret_key = gemini_api_secret
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def authenticator(self):
        return GeminiAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return ""

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
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        # Gemini doesn't have a bulk ticker endpoint, so we return an empty list
        # and rely on individual ticker calls via _get_last_traded_price
        return []

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_str = str(request_exception)
        return "InvalidNonce" in error_str or "not within" in error_str

    async def _update_time_synchronizer(self, pass_on_non_cancelled_error: bool = False):
        # Clear stale offset samples before re-syncing so one fresh fetch replaces drifted values
        self._time_synchronizer.clear_time_offset_ms_samples()
        await super()._update_time_synchronizer(pass_on_non_cancelled_error=pass_on_non_cancelled_error)

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_FOUND_ERROR in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_FOUND_ERROR in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return GeminiAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return GeminiAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        # Honor caller-provided is_maker when given. Otherwise treat both LIMIT and
        # LIMIT_MAKER as maker orders (PMM uses LIMIT_MAKER) so we don't misclassify
        # post-only orders as takers.
        if is_maker is None:
            is_maker = order_type in (OrderType.LIMIT, OrderType.LIMIT_MAKER)
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        side = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL

        # Gemini REST API does not support "exchange market" order type.
        # All orders are placed as "exchange limit" with an explicit price.
        gemini_order_type = CONSTANTS.ORDER_TYPE_LIMIT

        api_params = {
            "request": CONSTANTS.NEW_ORDER_PATH_URL,
            "symbol": symbol,
            "amount": f"{amount:f}",
            "side": side,
            "type": gemini_order_type,
            "price": f"{price:f}",
            "client_order_id": order_id,
        }

        if order_type == OrderType.LIMIT_MAKER:
            api_params["options"] = ["maker-or-cancel"]

        order_result = await self._api_post(
            path_url=CONSTANTS.NEW_ORDER_PATH_URL,
            data=api_params,
            is_auth_required=True)

        o_id = str(order_result["order_id"])
        transact_time = order_result.get("timestampms", 0) * 1e-3

        return o_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        if tracked_order.exchange_order_id is None:
            await tracked_order.get_exchange_order_id()
        api_params = {
            "request": CONSTANTS.CANCEL_ORDER_PATH_URL,
            "order_id": int(tracked_order.exchange_order_id),
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_PATH_URL,
            data=api_params,
            is_auth_required=True)
        if cancel_result.get("is_cancelled", False):
            return True
        return False

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Gemini's /v1/symbols returns a list of symbol strings.
        We need to fetch details for each symbol individually.
        """
        retval = []
        # exchange_info_dict is the response from /v1/symbols, which is a list of symbol strings
        symbols = exchange_info_dict if isinstance(exchange_info_dict, list) else []

        for symbol in symbols:
            try:
                # Check if this symbol maps to one of our trading pairs
                try:
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=symbol)
                except KeyError:
                    continue

                rest_assistant = await self._web_assistants_factory.get_rest_assistant()
                details = await rest_assistant.execute_request(
                    url=web_utils.public_rest_url(
                        path_url=CONSTANTS.SYMBOL_DETAILS_PATH_URL.format(symbol)),
                    method=RESTMethod.GET,
                    throttler_limit_id=CONSTANTS.SYMBOL_DETAILS_PATH_URL,
                )

                min_order_size = Decimal(str(details.get("min_order_size", "0.00001")))
                tick_size = Decimal(str(details.get("tick_size", "1e-8")))
                quote_increment = Decimal(str(details.get("quote_increment", "0.01")))

                retval.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=min_order_size,
                        min_price_increment=quote_increment,
                        min_base_amount_increment=tick_size,
                        min_notional_size=min_order_size * quote_increment,
                    ))
            except Exception:
                self.logger().exception(f"Error parsing trading pair rule for {symbol}. Skipping.")
        return retval

    async def _status_polling_loop_fetch_updates(self):
        await super()._status_polling_loop_fetch_updates()

    async def _update_trading_fees(self):
        pass

    async def _user_stream_event_listener(self):
        """
        Processes events from the Gemini Fast API user stream.
        Handles order updates and balance updates.

        Gemini Fast API message formats:
        - Order events: {"E": <ns>, "s": "BTCUSD", "i": <id>, "c": <client_id>,
                         "S": "BUY", "o": "LIMIT", "X": "NEW", "p": "1.00",
                         "q": "0.001", "z": "0", "T": <ns>}
        - Balance updates: {"e": "balanceUpdate", "E": <ms>, "B": [{"a": "USD", "f": "207.39"}]}
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("e")

                if "X" in event_message:
                    # Order event — identified by presence of "X" (order status) field
                    order_status = event_message.get("X", "")
                    client_order_id = event_message.get("c", "")

                    # When a fill occurs, extract fill details from WS event fields.
                    # Per Gemini Fast API docs:
                    #   Z = CUMULATIVE executed base quantity for the order
                    #   L = price of the most recent execution (last fill price)
                    #   t = trade ID for the most recent execution
                    # Because `update_with_trade_update` accumulates `fill_base_amount`,
                    # we must convert the cumulative `Z` into a per-fill delta by
                    # subtracting what we've already tracked for this order. We also
                    # require a stable `t` to safely dedupe duplicate/stale events.
                    if order_status in ("PARTIALLY_FILLED", "FILLED"):
                        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
                        trade_id_raw = event_message.get("t")
                        if tracked_order is not None and trade_id_raw not in (None, ""):
                            cumulative_z = Decimal(str(event_message.get("Z", "0")))
                            prior_filled = tracked_order.executed_amount_base
                            fill_amount = max(Decimal("0"), cumulative_z - prior_filled)
                            if fill_amount > Decimal("0"):
                                fill_price = Decimal(str(event_message["L"]))
                                trade_id = str(trade_id_raw)
                                is_maker = tracked_order.order_type in (
                                    OrderType.LIMIT, OrderType.LIMIT_MAKER)
                                fee = DeductedFromReturnsTradeFee(
                                    percent=self.estimate_fee_pct(is_maker=is_maker))
                                trade_update = TradeUpdate(
                                    trade_id=trade_id,
                                    client_order_id=client_order_id,
                                    exchange_order_id=str(event_message.get("i", "")),
                                    trading_pair=tracked_order.trading_pair,
                                    fee=fee,
                                    fill_base_amount=fill_amount,
                                    fill_quote_amount=fill_amount * fill_price,
                                    fill_price=fill_price,
                                    fill_timestamp=CONSTANTS.convert_timestamp_to_seconds(
                                        event_message.get("E", 0)),
                                )
                                self._order_tracker.process_trade_update(trade_update)

                    # Process order status update
                    tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                    if tracked_order is not None and order_status in CONSTANTS.ORDER_STATE:
                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=CONSTANTS.convert_timestamp_to_seconds(
                                event_message.get("E", 0)),
                            new_state=CONSTANTS.ORDER_STATE[order_status],
                            client_order_id=client_order_id,
                            exchange_order_id=str(event_message.get("i", "")),
                        )
                        self._order_tracker.process_order_update(order_update=order_update)

                elif event_type == CONSTANTS.WS_EVENT_BALANCE_UPDATE:
                    # Balance update: {"e": "balanceUpdate", "B": [{"a": "USD", "f": "207.39"}]}
                    for balance_entry in event_message.get("B", []):
                        asset_name = balance_entry.get("a", "")
                        available = Decimal(str(balance_entry.get("f", "0")))
                        if asset_name:
                            self._account_available_balances[asset_name] = available
                            self._account_balances[asset_name] = available

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            symbol = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            try:
                all_fills_response = await self._api_post(
                    path_url=CONSTANTS.MY_TRADES_PATH_URL,
                    data={
                        "request": CONSTANTS.MY_TRADES_PATH_URL,
                        "symbol": symbol,
                        "limit_trades": 500,
                    },
                    is_auth_required=True,
                    limit_id=CONSTANTS.MY_TRADES_PATH_URL)

                for trade in all_fills_response:
                    if str(trade.get("order_id", "")) == order.exchange_order_id:
                        fee = TradeFeeBase.new_spot_fee(
                            fee_schema=self.trade_fee_schema(),
                            trade_type=order.trade_type,
                            percent_token=trade.get("fee_currency", ""),
                            flat_fees=[TokenAmount(
                                amount=Decimal(str(trade.get("fee_amount", "0"))),
                                token=trade.get("fee_currency", "")
                            )]
                        )
                        trade_update = TradeUpdate(
                            trade_id=str(trade["tid"]),
                            client_order_id=order.client_order_id,
                            exchange_order_id=str(trade["order_id"]),
                            trading_pair=order.trading_pair,
                            fee=fee,
                            fill_base_amount=Decimal(str(trade["amount"])),
                            fill_quote_amount=Decimal(str(trade["amount"])) * Decimal(str(trade["price"])),
                            fill_price=Decimal(str(trade["price"])),
                            fill_timestamp=trade["timestampms"] * 1e-3,
                        )
                        trade_updates.append(trade_update)
            except Exception:
                self.logger().exception(f"Error fetching trades for order {order.client_order_id}")

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        if tracked_order.exchange_order_id is None:
            await tracked_order.get_exchange_order_id()
        updated_order_data = await self._api_post(
            path_url=CONSTANTS.ORDER_STATUS_PATH_URL,
            data={
                "request": CONSTANTS.ORDER_STATUS_PATH_URL,
                "order_id": int(tracked_order.exchange_order_id),
            },
            is_auth_required=True)

        # Determine the order state from the response
        if updated_order_data.get("is_cancelled", False):
            new_state = CONSTANTS.ORDER_STATE["cancelled"]
        elif updated_order_data.get("is_live", False):
            new_state = CONSTANTS.ORDER_STATE["live"]
        elif Decimal(str(updated_order_data.get("remaining_amount", "0"))) == Decimal("0"):
            new_state = CONSTANTS.ORDER_STATE["closed"]
        else:
            new_state = CONSTANTS.ORDER_STATE.get("live")

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(updated_order_data["order_id"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=updated_order_data.get("timestampms", 0) * 1e-3,
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        try:
            account_info = await self._api_post(
                path_url=CONSTANTS.BALANCES_PATH_URL,
                data={
                    "request": CONSTANTS.BALANCES_PATH_URL,
                },
                is_auth_required=True)
        except Exception as e:
            self.logger().error(f"Error fetching Gemini balances: {e}", exc_info=True)
            raise

        for balance_entry in account_info:
            asset_name = balance_entry["currency"]
            # Skip derivative/contract currencies (e.g. "GEMI-BTC2602180800-HI70000")
            # as they contain hyphens that break hummingbot's trading pair parsing
            if "-" in asset_name:
                continue
            available_balance = Decimal(str(balance_entry["available"]))
            total_balance = Decimal(str(balance_entry["amount"]))
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        # exchange_info is the response from /v1/symbols — a list of symbol strings like ["btcusd", "ethusd"]
        symbols = exchange_info if isinstance(exchange_info, list) else []
        for symbol in symbols:
            try:
                # Gemini symbols are lowercase concatenated, e.g., "btcusd"
                # We need to split them into base and quote currencies
                base, quote = self._split_gemini_symbol(symbol)
                if base and quote:
                    hb_pair = combine_to_hb_trading_pair(base=base.upper(), quote=quote.upper())
                    mapping[symbol] = hb_pair
            except Exception:
                self.logger().debug(f"Could not parse symbol {symbol}, skipping.")
        self._set_trading_pair_symbol_map(mapping)

    @staticmethod
    def _split_gemini_symbol(symbol: str) -> Tuple[str, str]:
        """
        Splits a Gemini symbol like 'btcusd' into ('btc', 'usd').
        Gemini uses well-known currency codes. Common quote currencies are:
        usd, btc, eth, gbp, eur, sgd, gusd, dai, usdt
        """
        symbol = symbol.lower()
        # Try known quote currencies (longest first to avoid ambiguity)
        known_quotes = ["gusd", "usdt", "usdc", "dai", "sgd", "gbp", "eur", "usd", "btc", "eth"]
        for quote in known_quotes:
            if symbol.endswith(quote) and len(symbol) > len(quote):
                base = symbol[:-len(quote)]
                return base, quote
        return "", ""

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        resp_json = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.TICKER_PATH_URL.format(symbol),
        )

        return float(resp_json.get("close", resp_json.get("last", 0)))
