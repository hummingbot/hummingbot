import asyncio
import contextlib
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import aiohttp
from bidict import bidict

from hummingbot.connector.derivative.position import Position
from hummingbot.connector.derivative.reya_perpetual import (
    reya_perpetual_constants as CONSTANTS,
    reya_perpetual_utils,
    reya_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.reya_perpetual.reya_perpetual_api_order_book_data_source import (
    ReyaPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.reya_perpetual.reya_perpetual_api_user_stream_data_source import (
    ReyaPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.reya_perpetual.reya_perpetual_auth import ReyaPerpetualAuth, wire_client_id
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class ReyaAPIError(IOError):
    """An HTTP error response, with Reya's error code when the body carries one."""

    def __init__(self, status: int, code: Optional[str], message: str):
        super().__init__(f"HTTP {status} {code}: {message}")
        self.status = status
        self.code = code

    @property
    def outcome_unknown(self) -> bool:
        # The request may have reached the matching engine. SERVICE_UNAVAILABLE_ERROR
        # states the request was not accepted.
        return (self.code == CONSTANTS.ORDER_OUTCOME_UNKNOWN_ERROR
                or (self.status >= 500 and self.code != CONSTANTS.SERVICE_UNAVAILABLE_ERROR))


class ReyaOrderOutcomeUnknown(IOError):
    """The order request may have reached the matching engine; it is reconciled, not failed."""


class ReyaOrderNotFound(IOError):
    pass


class ReyaOrderHistoryTruncated(IOError):
    """The order is in neither the open orders nor the order-history pages read; older pages were not read."""


class ReyaPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils

    def __init__(
            self,
            balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
            rate_limits_share_pct: Decimal = Decimal("100"),
            reya_perpetual_private_key: Optional[str] = None,
            reya_perpetual_wallet_address: Optional[str] = None,
            reya_perpetual_account_id: Optional[str] = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self._private_key = reya_perpetual_private_key
        self._wallet = (reya_perpetual_wallet_address or "").lower()
        self._account_id = int(reya_perpetual_account_id or 0)
        self._trading_pairs = trading_pairs or []
        self._trading_required = trading_required
        self._domain = domain
        self._market_ids: Dict[str, int] = {}
        self._initial_margin: Dict[str, Decimal] = {}
        self._max_leverage: Dict[str, Decimal] = {}
        # Last trade sequence number applied to the account's position in each market, and a
        # counter of position changes so a REST snapshot does not undo a newer stream update.
        self._position_sequences: Dict[str, int] = {}
        self._position_changes: Dict[str, int] = {}
        # Markets whose position was removed at the sequence in _position_sequences; only a newer trade reopens it.
        self._closed_positions: Set[str] = set()
        self._position_change_count = 0
        self._signer_validated = False
        # Where reading a finished order's executions continues on the next poll, by client order id.
        self._fill_recovery_cursors: Dict[str, str] = {}
        self._maker_fee = reya_perpetual_utils.DEFAULT_FEES.maker_percent_fee_decimal
        self._taker_fee = reya_perpetual_utils.DEFAULT_FEES.taker_percent_fee_decimal
        # Reya rejects a nonce below the signer's last accepted one, so signed
        # requests are sent one at a time, in the order they were signed.
        self._signed_request_lock = asyncio.Lock()
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[ReyaPerpetualAuth]:
        if self._private_key is None:
            return None
        return ReyaPerpetualAuth(self._private_key, self._market_ids, self._domain)

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return 32

    @property
    def client_order_id_prefix(self) -> str:
        return "HBOT"

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.MARKETS_PATH

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.MARKETS_PATH

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.MARKETS_PATH

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def funding_fee_poll_interval(self) -> int:
        return 120

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        return CONSTANTS.COLLATERAL_TOKEN

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return CONSTANTS.COLLATERAL_TOKEN

    async def start_network(self):
        if self.is_trading_required:
            await self._validate_signer()
        await super().start_network()

    def get_available_balance(self, currency: str) -> Decimal:
        available = super().get_available_balance(currency)
        if currency != CONSTANTS.COLLATERAL_TOKEN:
            return available
        # Reya's free collateral reserves nothing for resting orders, so their initial
        # margin is reserved here to keep the budget checker from over-committing.
        for order in self.in_flight_orders.values():
            if order.price.is_finite():
                remaining = order.amount - order.executed_amount_base
                available -= remaining * order.price * self._initial_margin.get(order.trading_pair, Decimal("1"))
        return max(Decimal("0"), available)

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return isinstance(status_update_exception, ReyaOrderNotFound)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return (isinstance(cancelation_exception, ReyaAPIError)
                and cancelation_exception.code == CONSTANTS.ORDER_NOT_FOUND_ERROR)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(throttler=self._throttler, auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return ReyaPerpetualAPIOrderBookDataSource(
            self._trading_pairs, connector=self, api_factory=self._web_assistants_factory, domain=self._domain)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return ReyaPerpetualAPIUserStreamDataSource(
            self._wallet, api_factory=self._web_assistants_factory, domain=self._domain)

    async def _api_request(self, path_url: str, overwrite_url: Optional[str] = None,
                           method: RESTMethod = RESTMethod.GET, params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None, is_auth_required: bool = False,
                           return_err: bool = False, limit_id: Optional[str] = None,
                           headers: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = overwrite_url or await self._api_request_url(path_url=path_url, is_auth_required=is_auth_required)
        lock = self._signed_request_lock if method == RESTMethod.POST else contextlib.nullcontext()
        async with lock:
            response = await rest_assistant.execute_request_and_get_response(
                url=url, params=params, data=data, method=method, is_auth_required=is_auth_required,
                return_err=True, throttler_limit_id=limit_id or CONSTANTS.RATE_LIMIT_ID, headers=headers)
        if response.status < 400 or return_err:
            return await response.json()
        # Failures are classified by status and Reya's error code, never by message text.
        try:
            body = await response.json()
        except Exception:
            body = None
        body = body if isinstance(body, dict) else {}
        raise ReyaAPIError(response.status, body.get("error"), body.get("message", ""))

    def _wallet_path(self, resource: str) -> str:
        return CONSTANTS.WALLET_PATH.format(address=self._wallet, resource=resource)

    async def _validate_signer(self):
        # Reya's reads are public, so a successful balance read does not prove the key can trade.
        # The check runs when the connector connects and starts, and once it has passed it is not repeated.
        if self._signer_validated:
            return
        if self._auth is None:
            raise IOError("A Reya signer private key is required for trading")
        signer = self._auth.signer_address.lower()
        if signer != self._wallet:
            # A delegated signer must be an enabled API wallet of the owner.
            status = await self._api_get(path_url=CONSTANTS.API_WALLET_STATUS_PATH,
                                         overwrite_url=web_utils.api_wallet_status_url(self._wallet, self._domain))
            if signer not in {address.lower() for address in status.get("enabledApiWallets", [])}:
                raise IOError(f"Signer {signer} is not an enabled API wallet of {self._wallet} on Reya")
        self._signer_validated = True

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List[Dict[str, Any]]):
        mapping = bidict()
        for market in filter(web_utils.is_exchange_information_valid, exchange_info):
            symbol = market["symbol"]
            trading_pair = combine_to_hb_trading_pair(symbol.removesuffix(CONSTANTS.SYMBOL_SUFFIX),
                                                      CONSTANTS.COLLATERAL_TOKEN)
            mapping[symbol] = trading_pair
            self._market_ids[symbol] = int(market["marketId"])
            self._initial_margin[trading_pair] = Decimal(market["initialMarginParameter"])
            if market.get("maxLeverage") is not None:
                self._max_leverage[trading_pair] = Decimal(str(market["maxLeverage"]))
        self._set_trading_pair_symbol_map(mapping)

    async def _format_trading_rules(self, exchange_info_dict: List[Dict[str, Any]]) -> List[TradingRule]:
        rules = []
        for market in filter(web_utils.is_exchange_information_valid, exchange_info_dict):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(market["symbol"])
                rules.append(TradingRule(
                    trading_pair,
                    min_order_size=Decimal(market["minOrderQty"]),
                    min_price_increment=Decimal(market["tickSize"]),
                    min_base_amount_increment=Decimal(market["qtyStepSize"]),
                    buy_order_collateral_token=CONSTANTS.COLLATERAL_TOKEN,
                    sell_order_collateral_token=CONSTANTS.COLLATERAL_TOKEN,
                ))
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {market}. Skipping.")
        return rules

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        summary = await self._api_get(path_url=CONSTANTS.MARKET_SUMMARY_PATH.format(symbol=symbol))
        return float(summary["markPrice"])

    def _get_fee(self, base_currency: str, quote_currency: str, order_type: OrderType, order_side: TradeType,
                 position_action: PositionAction, amount: Decimal, price: Decimal = Decimal("NaN"),
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = order_type is OrderType.LIMIT_MAKER if is_maker is None else is_maker
        return TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent=self._maker_fee if is_maker else self._taker_fee,
            percent_token=CONSTANTS.COLLATERAL_TOKEN,
        )

    async def _update_trading_fees(self):
        configuration = await self._api_get(path_url=self._wallet_path("configuration"))
        tiers = await self._api_get(path_url=CONSTANTS.FEE_TIERS_PATH)
        tier = next(tier for tier in tiers if int(tier["tierId"]) == int(configuration["feeTierId"]))
        # Pre-trade estimates only; executions carry the fee actually charged.
        self._maker_fee = max(Decimal("0"), Decimal(tier["makerFee"]))
        self._taker_fee = max(Decimal("0"), Decimal(tier["takerFee"]))

    async def _place_order(self, order_id: str, trading_pair: str, amount: Decimal, trade_type: TradeType,
                           order_type: OrderType, price: Decimal, position_action: PositionAction = PositionAction.NIL,
                           **kwargs) -> Tuple[str, float]:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        is_buy = trade_type is TradeType.BUY
        if order_type is OrderType.MARKET:
            slippage = Decimal(CONSTANTS.MARKET_ORDER_SLIPPAGE)
            reference = self.get_price(trading_pair, is_buy)
            price = self.quantize_order_price(trading_pair, reference * (1 + slippage if is_buy else 1 - slippage))
        data = {
            "accountId": self._account_id,
            "exchangeId": CONSTANTS.EXCHANGE_ID,
            "symbol": symbol,
            "isBuy": is_buy,
            "orderType": "LIMIT",
            "qty": str(amount),
            "limitPx": str(price),
            "clientOrderId": wire_client_id(order_id),
            "timeInForce": "IOC" if order_type is OrderType.MARKET else "GTC",
        }
        if order_type is OrderType.MARKET:
            data["reduceOnly"] = position_action is PositionAction.CLOSE
        else:
            # Reya accepts reduce-only on IOC orders only, so a LIMIT close rests as a plain GTC order:
            # if the position is closed some other way first, it can open a reverse position.
            data["postOnly"] = order_type is OrderType.LIMIT_MAKER
        try:
            response = await self._api_post(path_url=CONSTANTS.CREATE_ORDER_PATH, data=data, is_auth_required=True)
        except ReyaAPIError as error:
            if error.outcome_unknown:
                raise ReyaOrderOutcomeUnknown(str(error)) from error
            raise
        except (asyncio.TimeoutError, aiohttp.ClientError) as error:
            raise ReyaOrderOutcomeUnknown(str(error)) from error
        return str(response["orderId"]), self.current_timestamp

    def _on_order_failure(self, order_id: str, trading_pair: str, amount: Decimal, trade_type: TradeType,
                          order_type: OrderType, price: Optional[Decimal], exception: Exception, **kwargs):
        if isinstance(exception, ReyaOrderOutcomeUnknown):
            # Status polling finds the order by client id, or reports it lost once it is not found.
            self.logger().warning(f"Order {order_id} may have reached Reya ({exception}); reconciling its status.")
            return
        super()._on_order_failure(order_id, trading_pair, amount, trade_type, order_type, price, exception, **kwargs)

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        symbol = await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair)
        data = {"accountId": self._account_id, "symbol": symbol, "clientOrderId": wire_client_id(order_id)}
        if tracked_order.exchange_order_id:
            data["orderId"] = tracked_order.exchange_order_id
        await self._api_post(path_url=CONSTANTS.CANCEL_ORDER_PATH, data=data, is_auth_required=True)
        return True

    async def _history(self, resource: str, since: float, until: Optional[float] = None,
                       max_pages: int = CONSTANTS.HISTORY_MAX_PAGES,
                       cursor: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Reads up to `max_pages` pages of a wallet history, newest first, from `cursor` when given.

        Also returns the cursor to continue from, or None once the history has been read to its end.
        """
        rows: List[Dict[str, Any]] = []
        params = {"limit": CONSTANTS.HISTORY_PAGE_LIMIT, "startTime": int(since * 1000)}
        if until is not None:
            params["endTime"] = int(until * 1000)
        if cursor is not None:
            params["cursor"] = cursor
        for _ in range(max_pages):
            page = await self._api_get(path_url=self._wallet_path(resource), params=params)
            rows += page["data"]
            cursor = page.get("meta", {}).get("nextCursor")
            if not cursor:
                return rows, None
            params = {**params, "cursor": cursor}
        return rows, cursor

    def _match_order(self, order: InFlightOrder, rows: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        client_id = wire_client_id(order.client_order_id)
        return next((row for row in rows
                     if int(row["accountId"]) == self._account_id
                     and (str(row["orderId"]) == order.exchange_order_id
                          or str(row.get("clientOrderId")) == client_id)), None)

    async def _order_rows(self, orders: List[InFlightOrder]) -> Tuple[List[Dict[str, Any]], bool]:
        """Current orders first, then retained history, newest first: the first match is the latest state.

        Also returns whether every row since the oldest order was read, so an order missing from a
        truncated read is not mistaken for one Reya never received.
        """
        rows = list(await self._api_get(path_url=self._wallet_path("openOrders")))
        cursor = None
        if any(self._match_order(order, rows) is None for order in orders):
            since = min(order.creation_timestamp for order in orders)
            history, cursor = await self._history("orderHistory", since)
            rows += history
        return rows, cursor is None

    def _order_update(self, order: InFlightOrder, row: Dict[str, Any]) -> OrderUpdate:
        state = CONSTANTS.ORDER_STATE.get(row["status"])
        new_state = OrderState[state] if state else order.current_state
        if new_state is OrderState.OPEN and Decimal(row.get("cumQty") or "0") > 0:
            new_state = OrderState.PARTIALLY_FILLED
        return OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=row["lastUpdateAt"] / 1000,
            new_state=new_state,
            client_order_id=order.client_order_id,
            exchange_order_id=str(row["orderId"]),
        )

    def _order_row(self, order: InFlightOrder, rows: List[Dict[str, Any]], complete: bool) -> Dict[str, Any]:
        row = self._match_order(order, rows)
        if row is None and complete:
            raise ReyaOrderNotFound(f"Order {order.client_order_id} is neither open nor in Reya's order history")
        if row is None:
            raise ReyaOrderHistoryTruncated(f"Order {order.client_order_id} is not in the most recent "
                                            f"{CONSTANTS.HISTORY_MAX_PAGES} pages of order history")
        return row

    async def _recover_fills(self, order: InFlightOrder, row: Dict[str, Any]) -> bool:
        """Prepares an order for a status that may complete it; returns whether the status can be applied.

        An order whose create had an unknown outcome learns its exchange id from the row; fills are
        matched by that id. When the row shows more filled than the connector has recorded, for
        example after a stream outage, the order's own executions are read, from its creation to
        its last update, before the status is applied. A finished order's window no longer changes,
        so if it holds more pages than one poll reads, reading continues from there on the next poll
        and the final status waits until its fills are found.
        """
        if not order.exchange_order_id:
            order.update_exchange_order_id(str(row["orderId"]))
        if Decimal(row.get("cumQty") or "0") <= order.executed_amount_base:
            self._fill_recovery_cursors.pop(order.client_order_id, None)
            return True
        finished = row["status"] in ("FILLED", "CANCELLED")
        cursor = self._fill_recovery_cursors.pop(order.client_order_id, None) if finished else None
        executions, cursor = await self._history(
            "perpExecutions", order.creation_timestamp,
            until=row["lastUpdateAt"] / 1000 + CONSTANTS.ORDER_FILLS_SETTLEMENT_WINDOW,
            max_pages=CONSTANTS.ORDER_FILLS_MAX_PAGES, cursor=cursor)
        for update in self._trade_updates(executions, [order]):
            self._order_tracker.process_trade_update(update)
        if finished and cursor is not None:
            self._fill_recovery_cursors[order.client_order_id] = cursor
            return False
        return True

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        rows, complete = await self._order_rows([tracked_order])
        row = self._order_row(tracked_order, rows, complete)
        if not await self._recover_fills(tracked_order, row):
            raise ReyaOrderHistoryTruncated(f"The fills of order {tracked_order.client_order_id} are still being read")
        return self._order_update(tracked_order, row)

    async def _update_orders_with_error_handler(self, orders: List[InFlightOrder], error_handler):
        # One open-orders read per cycle for all tracked orders, instead of one per order.
        if not orders:
            return
        try:
            rows, complete = await self._order_rows(orders)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            for order in orders:
                await error_handler(order, error)
            return
        for order in orders:
            # A lost order already failed its status checks; a miss in the pages read finalizes it as not found.
            lost = order.client_order_id in self._order_tracker.lost_orders
            try:
                row = self._order_row(order, rows, complete or lost)
            except ReyaOrderHistoryTruncated as error:
                # Missing from the newest pages only, so not evidence that Reya never received it; the
                # streams and the next status poll keep tracking it.
                self.logger().debug(f"{error}; its status is checked again on the next poll.")
                continue
            except ReyaOrderNotFound as error:
                await error_handler(order, error)
                continue
            try:
                ready = await self._recover_fills(order, row)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                # As the connector standard requires, a filled status is still applied when its fills cannot be read.
                self.logger().warning(f"Failed to read the fills of Reya order {order.client_order_id}: {error}")
                ready = True
            if ready:
                self._order_tracker.process_order_update(self._order_update(order, row))

    def _trade_updates(self, executions: Iterable[Dict[str, Any]], orders: Iterable[InFlightOrder]) -> List[TradeUpdate]:
        by_exchange_id = {order.exchange_order_id: order for order in orders if order.exchange_order_id}
        updates = []
        for execution in executions:
            for role in ("taker", "maker"):
                if str(execution.get(f"{role}AccountId")) != str(self._account_id):
                    continue
                order = by_exchange_id.get(str(execution.get(f"{role}OrderId")))
                if order is None:
                    continue
                price, amount = Decimal(execution["price"]), Decimal(execution["qty"])
                position_action = PositionAction.CLOSE if order.position is PositionAction.CLOSE else PositionAction.OPEN
                fee = TradeFeeBase.new_perpetual_fee(
                    fee_schema=self.trade_fee_schema(),
                    position_action=position_action,
                    percent_token=CONSTANTS.COLLATERAL_TOKEN,
                    flat_fees=[TokenAmount(CONSTANTS.COLLATERAL_TOKEN, Decimal(execution.get(f"{role}Fee") or "0"))],
                )
                updates.append(TradeUpdate(
                    trade_id=str(execution["sequenceNumber"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=order.exchange_order_id,
                    trading_pair=order.trading_pair,
                    fill_timestamp=execution["timestamp"] / 1000,
                    fill_price=price,
                    fill_base_amount=amount,
                    fill_quote_amount=price * amount,
                    fee=fee,
                    is_taker=role == "taker",
                ))
        return updates

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        if not order.exchange_order_id:
            return []
        executions, _ = await self._history("perpExecutions", order.creation_timestamp)
        return self._trade_updates(executions, [order])

    async def _update_fills(self, orders: List[InFlightOrder]):
        # Settled executions are the fills; one read covers every tracked order.
        orders = [order for order in orders if order.exchange_order_id]
        if not orders:
            return
        try:
            since = min(order.creation_timestamp for order in orders)
            executions, _ = await self._history("perpExecutions", since)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.logger().warning(f"Failed to fetch Reya executions. Error: {error}", exc_info=error)
            return
        for update in self._trade_updates(executions, orders):
            self._order_tracker.process_trade_update(update)

    async def _update_order_status(self):
        await self._update_fills(list(self._order_tracker.all_fillable_orders.values()))
        await self._update_orders()

    async def _update_lost_orders_status(self):
        await self._update_fills(list(self._order_tracker.lost_orders.values()))
        await self._update_lost_orders()

    def _apply_account_summaries(self, rows: Iterable[Dict[str, Any]]):
        for row in rows:
            if int(row["accountId"]) == self._account_id:
                self._account_balances[CONSTANTS.COLLATERAL_TOKEN] = Decimal(row["marginBalance"])
                self._account_available_balances[CONSTANTS.COLLATERAL_TOKEN] = Decimal(row["freeCollateral"])

    async def _update_balances(self):
        # `connect` reads the balance with trading not required, so the configured signer is checked here too.
        if self._private_key is not None:
            await self._validate_signer()
        try:
            rows = await self._api_get(path_url=self._wallet_path("accountSummaries"),
                                       params={"accountId": self._account_id})
        except ReyaAPIError as error:
            if error.status == 503:
                raise IOError("Reya cannot value the account right now (a price input is unavailable); "
                              "the balance is read again on the next update") from error
            raise
        if not any(int(row["accountId"]) == self._account_id for row in rows):
            raise IOError(f"Account {self._account_id} is not an open perpetual account of {self._wallet}")
        self._apply_account_summaries(rows)

    async def _apply_positions(self, rows: Iterable[Dict[str, Any]], complete: bool,
                               changes_before: Optional[int] = None):
        """Upserts position rows; a complete set also removes positions it does not contain.

        Positions arrive from REST, the positions channel and the positionRisk channel, which are
        not ordered with each other. A row whose lastTradeSequenceNumber is below the last one
        applied for its market is older than the position already tracked and is skipped. A
        complete REST set read when the change counter was `changes_before` does not remove a
        position that a stream changed after that.
        """
        symbols = await self.trading_pair_symbol_map()
        listed = set()
        for row in rows:
            symbol = row["symbol"]
            if int(row["accountId"]) != self._account_id or symbol not in symbols:
                continue
            listed.add(symbol)
            sequence = int(row["lastTradeSequenceNumber"])
            applied = self._position_sequences.get(symbol, 0)
            if sequence < applied or (symbol in self._closed_positions and sequence <= applied):
                continue
            self._position_sequences[symbol] = sequence
            self._position_change_count += 1
            self._position_changes[symbol] = self._position_change_count
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol)
            side = PositionSide.LONG if row["side"] == "B" else PositionSide.SHORT
            key = self._perpetual_trading.position_key(trading_pair, side)
            amount = Decimal(row["qty"])
            if amount == 0:
                self._perpetual_trading.remove_position(key)
                self._closed_positions.add(symbol)
                continue
            self._closed_positions.discard(symbol)
            previous = self._perpetual_trading.get_position(trading_pair, side)
            # Position records carry no valuation; the last known unrealized PnL is kept for them.
            if row.get("unrealizedPnl") is not None:
                unrealized_pnl = Decimal(row["unrealizedPnl"])
            else:
                unrealized_pnl = previous.unrealized_pnl if previous else Decimal("0")
            self._perpetual_trading.set_position(key, Position(
                trading_pair=trading_pair,
                position_side=side,
                unrealized_pnl=unrealized_pnl,
                entry_price=Decimal(row["avgEntryPrice"]),
                amount=amount if side is PositionSide.LONG else -amount,
                leverage=Decimal(self.get_leverage(trading_pair)),
            ))
        if complete:
            for key, position in list(self._perpetual_trading.account_positions.items()):
                symbol = symbols.inverse.get(position.trading_pair)
                if symbol in listed:
                    continue
                if changes_before is not None and self._position_changes.get(symbol, 0) > changes_before:
                    continue
                self._perpetual_trading.remove_position(key)
                self._closed_positions.add(symbol)

    async def _apply_position_valuations(self, rows: Iterable[Dict[str, Any]]):
        """Applies valued positions from the positionRisk channel.

        A valuation never removes a position: closes arrive on the positions channel. One computed
        before a fill or close the connector has already applied is skipped by its sequence number.
        """
        await self._apply_positions(rows, complete=False)

    async def _update_positions(self):
        changes_before = self._position_change_count
        try:
            rows = await self._api_get(path_url=self._wallet_path("positionRisk"),
                                       params={"accountId": self._account_id})
        except ReyaAPIError as error:
            if error.status != 503:
                raise
            # Reya cannot value the account right now (for example, a stale mark), but it still
            # serves the positions themselves; the last known unrealized PnL is kept.
            rows = await self._api_get(path_url=self._wallet_path("positions"))
        await self._apply_positions(rows, complete=True, changes_before=changes_before)

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        if mode is PositionMode.ONEWAY:
            return True, ""
        return False, "Reya supports one-way position mode only"

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        # Reya margins accounts cross-margin; leverage only sizes orders locally, up to the market's maximum.
        await self.trading_pair_symbol_map()
        maximum = self._max_leverage.get(trading_pair)
        if maximum is None:
            return False, f"{trading_pair} is not a Reya perpetual market"
        if 1 <= leverage <= maximum:
            return True, ""
        return False, f"Leverage for {trading_pair} must be between 1 and {maximum}"

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        # Funding accrues continuously into the account balance. Reya reports what each position
        # paid or received per UTC hour, newest first, once the hour has ended.
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        page = await self._api_get(path_url=self._wallet_path("fundingPayments"),
                                   params={"accountId": self._account_id, "symbol": symbol, "limit": 1})
        entries = page["data"]
        if not entries or Decimal(entries[0]["payment"]) == 0:
            return 0, Decimal("-1"), Decimal("-1")
        entry = entries[0]
        # The rate is an hourly percentage, omitted when none was recorded for the hour.
        rate = Decimal(entry.get("fundingRate", "0")) / 100
        timestamp = (entry["timestamp"] + CONSTANTS.FUNDING_PAYMENT_INTERVAL_MS) / 1000
        return timestamp, rate, Decimal(entry["payment"])

    @staticmethod
    def _event_rows(event: Dict[str, Any]) -> List[Dict[str, Any]]:
        payload = event.get("contents") if event.get("type") == "subscribed" else event.get("data")
        if isinstance(payload, dict):
            payload = payload.get("data")
        return payload or []

    def _process_order_rows(self, rows: List[Dict[str, Any]]):
        orders = self._order_tracker.all_updatable_orders
        by_client_id = {wire_client_id(order.client_order_id): order for order in orders.values()}
        for row in rows:
            if int(row["accountId"]) != self._account_id:
                continue
            if row.get("cancelReason") == CONSTANTS.FEED_RESET_CANCEL_REASON:
                # Not a cancellation on the exchange: poll now so REST rebuilds the order view.
                self._poll_notifier.set()
                continue
            order = (self._order_tracker.all_updatable_orders_by_exchange_order_id.get(str(row["orderId"]))
                     or by_client_id.get(str(row.get("clientOrderId"))))
            if order is not None:
                if not order.exchange_order_id:
                    # Recovered after a create with an unknown outcome: fills are matched by exchange id.
                    order.update_exchange_order_id(str(row["orderId"]))
                self._order_tracker.process_order_update(self._order_update(order, row))

    async def _user_stream_event_listener(self):
        async for event in self._iter_user_event_queue():
            try:
                channel = event.get("channel", "")
                if event.get("type") == "error":
                    self.logger().warning(f"Reya user stream error on {channel}: {event.get('message')}")
                    continue
                rows = self._event_rows(event)
                if channel.endswith("/orderChanges"):
                    self._process_order_rows(rows)
                elif channel.endswith("/perpExecutions"):
                    for update in self._trade_updates(rows, self._order_tracker.all_fillable_orders.values()):
                        self._order_tracker.process_trade_update(update)
                elif channel.endswith("/positions"):
                    await self._apply_positions(rows, complete=event.get("type") == "subscribed")
                elif channel.endswith("/positionRisk"):
                    await self._apply_position_valuations(rows)
                elif channel.endswith("/accountSummaries"):
                    self._apply_account_summaries(rows)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)
