import asyncio
import contextlib
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, Iterable, List, Optional, Tuple

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
        if self._auth is None:
            raise IOError("A Reya signer private key is required for trading")
        signer = self._auth.signer_address.lower()
        if signer == self._wallet:
            return
        # A delegated signer must be an enabled API wallet of the owner.
        status = await self._api_get(path_url=CONSTANTS.API_WALLET_STATUS_PATH,
                                     overwrite_url=web_utils.api_wallet_status_url(self._wallet, self._domain))
        if signer not in {address.lower() for address in status.get("enabledApiWallets", [])}:
            raise IOError(f"Signer {signer} is not an enabled API wallet of {self._wallet} on Reya")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List[Dict[str, Any]]):
        mapping = bidict()
        for market in filter(web_utils.is_exchange_information_valid, exchange_info):
            symbol = market["symbol"]
            trading_pair = combine_to_hb_trading_pair(symbol.removesuffix(CONSTANTS.SYMBOL_SUFFIX),
                                                      CONSTANTS.COLLATERAL_TOKEN)
            mapping[symbol] = trading_pair
            self._market_ids[symbol] = int(market["marketId"])
            self._initial_margin[trading_pair] = Decimal(market["initialMarginParameter"])
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
        if position_action is PositionAction.CLOSE and order_type is not OrderType.MARKET:
            # Reya accepts reduce-only on IOC orders only. A resting close could open a
            # reverse position if the position is closed some other way first.
            raise ValueError("Reya accepts orders that close a position only as MARKET orders")
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

    async def _history(self, resource: str, since: float) -> AsyncIterable[Dict[str, Any]]:
        params = {"limit": CONSTANTS.HISTORY_PAGE_LIMIT, "startTime": int(since * 1000)}
        for _ in range(CONSTANTS.HISTORY_MAX_PAGES):
            page = await self._api_get(path_url=self._wallet_path(resource), params=params)
            for row in page["data"]:
                yield row
            cursor = page.get("meta", {}).get("nextCursor")
            if not cursor:
                return
            params = {**params, "cursor": cursor}

    def _match_order(self, order: InFlightOrder, rows: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        client_id = wire_client_id(order.client_order_id)
        return next((row for row in rows
                     if int(row["accountId"]) == self._account_id
                     and (str(row["orderId"]) == order.exchange_order_id
                          or str(row.get("clientOrderId")) == client_id)), None)

    async def _order_rows(self, orders: List[InFlightOrder]) -> List[Dict[str, Any]]:
        # Current orders first, then retained history, newest first: the first match is the latest state.
        rows = list(await self._api_get(path_url=self._wallet_path("openOrders")))
        if any(self._match_order(order, rows) is None for order in orders):
            since = min(order.creation_timestamp for order in orders)
            rows += [row async for row in self._history("orderHistory", since)]
        return rows

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

    def _order_update_from_rows(self, order: InFlightOrder, rows: List[Dict[str, Any]]) -> OrderUpdate:
        row = self._match_order(order, rows)
        if row is None:
            raise ReyaOrderNotFound(f"Order {order.client_order_id} is neither open nor in Reya's order history")
        return self._order_update(order, row)

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        return self._order_update_from_rows(tracked_order, await self._order_rows([tracked_order]))

    async def _update_orders_with_error_handler(self, orders: List[InFlightOrder], error_handler):
        # One open-orders read per cycle for all tracked orders, instead of one per order.
        if not orders:
            return
        try:
            rows = await self._order_rows(orders)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            for order in orders:
                await error_handler(order, error)
            return
        for order in orders:
            try:
                self._order_tracker.process_order_update(self._order_update_from_rows(order, rows))
            except ReyaOrderNotFound as error:
                await error_handler(order, error)

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
        executions = [row async for row in self._history("perpExecutions", order.creation_timestamp)]
        return self._trade_updates(executions, [order])

    async def _update_fills(self, orders: List[InFlightOrder]):
        # Settled executions are the fills; one read covers every tracked order.
        orders = [order for order in orders if order.exchange_order_id]
        if not orders:
            return
        try:
            since = min(order.creation_timestamp for order in orders)
            executions = [row async for row in self._history("perpExecutions", since)]
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
        rows = await self._api_get(path_url=self._wallet_path("accountSummaries"),
                                   params={"accountId": self._account_id})
        if not any(int(row["accountId"]) == self._account_id for row in rows):
            raise IOError(f"Account {self._account_id} is not an open perpetual account of {self._wallet}")
        self._apply_account_summaries(rows)

    async def _apply_positions(self, rows: Iterable[Dict[str, Any]], complete: bool):
        """Upserts position rows; a complete set also removes positions it does not contain."""
        symbols = await self.trading_pair_symbol_map()
        current = set()
        for row in rows:
            if int(row["accountId"]) != self._account_id or row["symbol"] not in symbols:
                continue
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(row["symbol"])
            side = PositionSide.LONG if row["side"] == "B" else PositionSide.SHORT
            key = self._perpetual_trading.position_key(trading_pair, side)
            amount = Decimal(row["qty"])
            if amount == 0:
                self._perpetual_trading.remove_position(key)
                continue
            current.add(key)
            previous = self._perpetual_trading.get_position(trading_pair, side)
            # Valuation fields are omitted while Reya cannot value the account.
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
            for key in list(self._perpetual_trading.account_positions):
                if key not in current:
                    self._perpetual_trading.remove_position(key)

    async def _update_positions(self):
        await self._apply_positions(await self._api_get(path_url=self._wallet_path("positions")), complete=True)

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        if mode is PositionMode.ONEWAY:
            return True, ""
        return False, "Reya supports one-way position mode only"

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        # Reya margins accounts cross-margin; leverage only sizes orders locally, up to the market's maximum.
        maximum = Decimal("1") / self._initial_margin[trading_pair]
        if 1 <= leverage <= maximum:
            return True, ""
        return False, f"Leverage for {trading_pair} must be between 1 and {maximum}"

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        # Funding accrues continuously into the account balance; there are no discrete payments.
        return 0, Decimal("-1"), Decimal("-1")

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
            order = (self._order_tracker.all_updatable_orders_by_exchange_order_id.get(str(row["orderId"]))
                     or by_client_id.get(str(row.get("clientOrderId"))))
            if order is not None:
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
                elif channel.endswith("/accountSummaries"):
                    self._apply_account_summaries(rows)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)
