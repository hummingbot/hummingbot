import asyncio
import math
from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, AsyncIterator, Dict, Iterable, List, Optional, Tuple

from neutronx_sdk import Network, OrderRequest, TimeInForce
from neutronx_sdk.indexer import (
    CHANNEL_FILLS,
    CHANNEL_ORDERS,
    CHANNEL_POSITIONS,
    AccountFundingV1,
    FillV1,
    OrderV1,
    PageV1,
    PositionV1,
    StatusV1,
    StreamFrame,
    TickerV1,
    compact_pair,
)
from neutronx_sdk.indexer.api import (
    PATH_STATUS,
    PATH_TICKERS,
    account_fills_path,
    account_funding_path,
    account_orders_path,
    max_subscriptions,
)
from neutronx_sdk.models import POSITION_STATUS_OPEN, FeeTier, Market, Order
from neutronx_sdk.orders import OrderStatus, snap_to_tick

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.neutronx_perpetual import (
    neutronx_perpetual_constants as CONSTANTS,
    neutronx_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.neutronx_perpetual.data_sources import translators
from hummingbot.connector.derivative.neutronx_perpetual.data_sources.neutronx_data_source import (
    NeutronxDataSource,
    build_wallet,
)
from hummingbot.connector.derivative.neutronx_perpetual.data_sources.tx_queue import CancelOutcome, PlacedOrder
from hummingbot.connector.derivative.neutronx_perpetual.neutronx_perpetual_api_order_book_data_source import (
    NeutronxPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.neutronx_perpetual.neutronx_perpetual_user_stream_data_source import (
    NeutronxPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_perpetual_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

FINAL_ORDER_STATES = frozenset({OrderState.FILLED, OrderState.CANCELED, OrderState.FAILED})


@dataclass
class _Settling:
    since: float
    backfilled_at: float = -math.inf


def _remember(cache: "OrderedDict[str, Any]", key: str, value: Any, capacity: int) -> None:
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > capacity:
        cache.popitem(last=False)


class NeutronxPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils

    def __init__(
        self,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        neutronx_perpetual_account_address: str = "",
        neutronx_perpetual_private_key: str = "",
        neutronx_perpetual_agent_key_id: int = 0,
        neutronx_perpetual_subaccount_id: int = 0,
        neutronx_perpetual_indexer_api_key: Optional[str] = None,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
        network: Optional[Network] = None,
        data_source: Optional[NeutronxDataSource] = None,
    ):
        self._domain = domain
        self._trading_pairs = trading_pairs or []
        self._trading_required = trading_required
        self._network = network or web_utils.network_for(domain)
        self._account_address = neutronx_perpetual_account_address.strip()
        self._api_key = str(neutronx_perpetual_indexer_api_key or "").strip() or None
        self._data_source = data_source or self._create_data_source(
            neutronx_perpetual_private_key,
            int(neutronx_perpetual_agent_key_id or 0),
            int(neutronx_perpetual_subaccount_id or 0),
        )
        self._markets: Dict[str, Market] = {}
        self._pairs_by_indexer: Dict[str, str] = {}
        self._fee_tier: Optional[FeeTier] = None
        self._seen_fills: "OrderedDict[str, None]" = OrderedDict()
        self._finished: "OrderedDict[str, OrderUpdate]" = OrderedDict()
        self._settling: Dict[str, _Settling] = {}
        self._indexer_backoff = web_utils.IndexerBackoff()
        self._network_failures = 0
        self._tickers = web_utils.SharedRequest(self._fetch_tickers, CONSTANTS.TICKERS_TTL)
        self._funding_payments = web_utils.SharedRequest(self._fetch_funding_payments)
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    def _create_data_source(self, private_key: str, agent_key_id: int, subaccount_id: int) -> NeutronxDataSource:
        wallet = None
        if self._trading_required:
            wallet = build_wallet(self._network, self._account_address, private_key, agent_key_id)
        return NeutronxDataSource(self._network, self._account_address, subaccount_id, wallet=wallet)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def network(self) -> Network:
        return self._network

    @property
    def account_address(self) -> str:
        return self._account_address

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key

    @property
    def max_subscriptions(self) -> int:
        return max_subscriptions(self._api_key)

    @property
    def authenticator(self) -> None:
        return None

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return web_utils.rate_limits(self._api_key)

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.CLIENT_ORDER_ID_MAX_LENGTH

    @property
    def client_order_id_prefix(self) -> str:
        return ""

    @property
    def trading_rules_request_path(self) -> str:
        return PATH_STATUS

    @property
    def trading_pairs_request_path(self) -> str:
        return PATH_STATUS

    @property
    def check_network_request_path(self) -> str:
        return PATH_STATUS

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def funding_fee_poll_interval(self) -> int:
        return CONSTANTS.FUNDING_FEE_POLL_INTERVAL

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        return self._trading_rules[trading_pair].buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return self._trading_rules[trading_pair].sell_order_collateral_token

    def trading_pair_for_indexer(self, indexer_pair: str) -> Optional[str]:
        return self._pairs_by_indexer.get(compact_pair(indexer_pair))

    async def request_indexer(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        limit_id: str = CONSTANTS.INDEXER_REST_LIMIT_ID,
    ) -> Any:
        return await self._api_get(path_url=path, params=params, limit_id=limit_id)

    async def tickers(self) -> Dict[str, TickerV1]:
        return await self._tickers.get()

    async def ticker(self, trading_pair: str) -> Optional[TickerV1]:
        return (await self.tickers()).get(compact_pair(trading_pair))

    async def _fetch_tickers(self) -> Dict[str, TickerV1]:
        raw = await self.request_indexer(PATH_TICKERS)
        tickers = [TickerV1.from_json(item) for item in raw] if isinstance(raw, list) else []
        return {compact_pair(ticker.pair): ticker for ticker in tickers}

    async def _api_request_url(self, path_url: str, is_auth_required: bool = False) -> str:
        return web_utils.indexer_rest_url(self._network, path_url)

    async def start_network(self):
        await super().start_network()
        if self.is_trading_required and not self._data_source.trading_ready:
            await self._data_source.start_trading()

    async def stop_network(self):
        await super().stop_network()
        if self.network_status is NetworkStatus.STOPPED:
            await self._data_source.stop()

    async def _update_time_synchronizer(self, pass_on_non_cancelled_error: bool = False):
        return

    async def check_network(self) -> NetworkStatus:
        try:
            await asyncio.wait_for(self._make_network_check_request(), timeout=CONSTANTS.NETWORK_CHECK_TIMEOUT)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._network_failures += 1
            if (
                self.network_status is NetworkStatus.CONNECTED
                and self._network_failures < CONSTANTS.NETWORK_FAILURES_TO_DISCONNECT
            ):
                self.logger().warning(f"The NeutronX network check failed, waiting for the next one: {error!r}")
                return NetworkStatus.CONNECTED
            return NetworkStatus.NOT_CONNECTED
        self._network_failures = 0
        return NetworkStatus.CONNECTED

    async def _make_network_check_request(self):
        try:
            raw = await self.request_indexer(PATH_STATUS, limit_id=CONSTANTS.INDEXER_STATUS_LIMIT_ID)
        except web_utils.IndexerRateLimitedError:
            raw = None
        lag_blocks = None if raw is None else StatusV1.from_json(raw).lag_blocks
        if lag_blocks is not None and lag_blocks > CONSTANTS.MAX_INDEXER_LAG_BLOCKS:
            raise IOError(f"the NeutronX indexer is {lag_blocks} blocks behind the chain")
        await self._data_source.check_node()

    async def _make_trading_rules_request(self) -> Dict[str, Any]:
        return await self._exchange_info()

    async def _make_trading_pairs_request(self) -> Dict[str, Any]:
        return await self._exchange_info()

    async def _exchange_info(self) -> Dict[str, Any]:
        markets, params = await safe_gather(self._data_source.markets(), self._data_source.orderbook_params())
        return {"markets": markets, "params": params}

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        markets = translators.active_markets(exchange_info_dict["markets"])
        self._markets = {translators.to_trading_pair(market.pair): market for market in markets}
        self._pairs_by_indexer = translators.compact_lookup(exchange_info_dict["markets"])
        min_notional = Decimal(exchange_info_dict["params"].min_order_notional)
        return [translators.trading_rule(market, min_notional) for market in markets]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        self._pairs_by_indexer = translators.compact_lookup(exchange_info["markets"])
        self._set_trading_pair_symbol_map(translators.symbol_map(exchange_info["markets"]))

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler, api_key=self._api_key, backoff=self._indexer_backoff
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return NeutronxPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return NeutronxPerpetualUserStreamDataSource(connector=self, api_factory=self._web_assistants_factory)

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_FOUND_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.CANCEL_REJECTED_MESSAGE in str(cancelation_exception)

    def buy(
        self, trading_pair: str, amount: Decimal, order_type=OrderType.LIMIT, price: Decimal = s_decimal_NaN, **kwargs
    ) -> str:
        return self._submit_order(TradeType.BUY, trading_pair, amount, order_type, price, **kwargs)

    def sell(
        self, trading_pair: str, amount: Decimal, order_type=OrderType.LIMIT, price: Decimal = s_decimal_NaN, **kwargs
    ) -> str:
        return self._submit_order(TradeType.SELL, trading_pair, amount, order_type, price, **kwargs)

    def _submit_order(
        self,
        trade_type: TradeType,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        price: Decimal,
        **kwargs,
    ) -> str:
        order_id = str(self._data_source.client_ids.allocate())
        position_action = kwargs.pop("position_action", PositionAction.OPEN)
        safe_ensure_future(
            self._create_order(
                trade_type=trade_type,
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                position_action=position_action,
                **kwargs,
            )
        )
        return order_id

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        position_action: PositionAction = PositionAction.NIL,
        **kwargs,
    ) -> Tuple[str, float]:
        request = self._order_request(order_id, trading_pair, amount, trade_type, order_type, price, position_action)
        placed = await self._send_order_request(request)
        return str(placed.order_id), self.current_timestamp

    async def _place_order_and_process_update(self, order: InFlightOrder, **kwargs) -> str:
        request = self._order_request(
            order.client_order_id,
            order.trading_pair,
            order.amount,
            order.trade_type,
            order.order_type,
            order.price,
            kwargs.get("position_action", order.position),
        )
        placed = await self._send_order_request(request)
        born_cancelled = placed.status == OrderStatus.CANCELLED and placed.filled == 0
        self._process_order_update(
            OrderUpdate(
                client_order_id=order.client_order_id,
                exchange_order_id=str(placed.order_id),
                trading_pair=order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.CANCELED if born_cancelled else OrderState.OPEN,
            )
        )
        return str(placed.order_id)

    async def _send_order_request(self, request: OrderRequest) -> PlacedOrder:
        if self.network_status is NetworkStatus.NOT_CONNECTED:
            raise IOError(CONSTANTS.NOT_CONNECTED_MESSAGE)
        return await self._data_source.place(request)

    def _order_request(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        position_action: PositionAction,
    ) -> OrderRequest:
        market = self._markets[trading_pair]
        side = translators.to_side(trade_type)
        time_in_force = TimeInForce.GTC
        if order_type is OrderType.MARKET:
            price = self._market_order_price(market, trading_pair, trade_type, price)
            time_in_force = TimeInForce.IOC
        return OrderRequest(
            pair=market.pair,
            side=side,
            price=snap_to_tick(Decimal(price), side, market.tick_size),
            quantity=Decimal(amount),
            leverage=self._order_leverage(trading_pair, market),
            time_in_force=time_in_force,
            post_only=order_type is OrderType.LIMIT_MAKER,
            reduce_only=translators.reduce_only(position_action),
            subaccount_id=self._data_source.subaccount_id,
            client_id=int(order_id),
        )

    def _market_order_price(self, market: Market, trading_pair: str, trade_type: TradeType, price: Decimal) -> Decimal:
        reference = Decimal(price) if price is not None and Decimal(price).is_finite() and price > 0 else None
        if reference is None:
            reference = self.get_mid_price(trading_pair)
        if reference is None or not reference.is_finite() or reference <= 0:
            raise ValueError(f"no reference price to place a market order on {trading_pair}")
        slippage = market.max_slippage if market.max_slippage > 0 else CONSTANTS.MARKET_ORDER_SLIPPAGE
        return reference * (1 + slippage) if trade_type is TradeType.BUY else reference * (1 - slippage)

    def _order_leverage(self, trading_pair: str, market: Market) -> Decimal:
        ceiling = max(1, int(market.effective_max_leverage))
        return Decimal(max(1, min(int(self.get_leverage(trading_pair)), ceiling)))

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        if order_id in self._settling:
            safe_ensure_future(self._refresh_orders([tracked_order]))
            return False
        exchange_order_id = await tracked_order.get_exchange_order_id()
        cancelled = await self._data_source.cancel(int(exchange_order_id))
        if cancelled.outcome is CancelOutcome.REJECTED:
            raise IOError(CONSTANTS.CANCEL_REJECTED_MESSAGE)
        self._settling.setdefault(order_id, _Settling(since=self._time()))
        if cancelled.outcome is CancelOutcome.GONE:
            safe_ensure_future(self._refresh_orders([tracked_order]))
            return False
        return await self._confirm_cancel(tracked_order)

    async def _confirm_cancel(self, order: InFlightOrder) -> bool:
        try:
            update = await self._request_order_status(order)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.logger().network(f"Error confirming the NeutronX cancel of {order.client_order_id}: {error}")
            return False
        if update.new_state is OrderState.CANCELED:
            self._release_client_id(order.client_order_id)
            return True
        if update.new_state in FINAL_ORDER_STATES:
            self._process_order_update(update)
        return False

    async def _cancel_lost_orders(self):
        lost = [order for order in self._order_tracker.lost_orders.values() if order.exchange_order_id]
        if not lost:
            return
        open_ids = {order.order_id for order in await self._data_source.open_orders()}
        for order in lost:
            if int(order.exchange_order_id) in open_ids:
                await self._execute_order_cancel(order)
            else:
                await self._refresh_orders([order])

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        position_action: PositionAction,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        maker = is_maker if is_maker is not None else order_type is OrderType.LIMIT_MAKER
        if self._fee_tier is None:
            return build_perpetual_trade_fee(
                self.name,
                maker,
                position_action=position_action,
                base_currency=base_currency,
                quote_currency=quote_currency,
                order_type=order_type,
                order_side=order_side,
                amount=amount,
                price=price,
            )
        rate = self._fee_tier.maker_fee_rate if maker else self._fee_tier.taker_fee_rate
        return TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent=rate,
            percent_token=quote_currency,
        )

    async def _update_trading_fees(self):
        if self.is_trading_required:
            self._fee_tier = await self._data_source.fee_tier()

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_balances(),
            self._update_positions(),
            self._update_order_status(),
            self._update_trade_history(),
        )

    async def _update_balances(self):
        balance = await self._data_source.balance()
        self._account_balances = {CONSTANTS.QUOTE_ASSET: balance.total}
        self._account_available_balances = {CONSTANTS.QUOTE_ASSET: balance.available}

    async def _update_positions(self):
        positions = {}
        for position in await self._data_source.positions():
            trading_pair = self.trading_pair_for_indexer(position.pair)
            if trading_pair is not None:
                positions[trading_pair] = translators.to_position(position, trading_pair)
        self._apply_positions(positions)

    def _apply_positions(self, positions: Dict[str, Position]):
        keys = set(self._perpetual_trading.account_positions) | {
            self._perpetual_trading.position_key(trading_pair) for trading_pair in positions
        }
        for key in keys:
            position = positions.get(key)
            if position is None or position.amount == 0:
                self._perpetual_trading.remove_position(key)
            else:
                self._perpetual_trading.set_position(key, position)

    async def _update_order_status(self):
        tracked = [order for order in self._order_tracker.active_orders.values() if order.exchange_order_id]
        if not tracked:
            return
        open_orders = {order.order_id: order for order in await self._data_source.open_orders()}
        missing = []
        for order in tracked:
            chain_order = open_orders.get(int(order.exchange_order_id))
            if chain_order is not None:
                self._process_order_update(translators.order_update(chain_order, order, self.current_timestamp))
            elif self._past_visibility_grace(order):
                missing.append(order)
        await self._refresh_orders(missing)

    def _past_visibility_grace(self, order: InFlightOrder) -> bool:
        return self.current_timestamp - order.creation_timestamp > CONSTANTS.ORDER_VISIBILITY_GRACE_SECONDS

    async def _refresh_orders(self, orders: Iterable[InFlightOrder]):
        for order in orders:
            try:
                self._process_order_update(await self._request_order_status(order))
            except asyncio.CancelledError:
                raise
            except Exception as error:
                if self._is_order_not_found_during_status_update_error(error):
                    await self._order_tracker.process_order_not_found(order.client_order_id)
                else:
                    self.logger().network(f"Error refreshing NeutronX order {order.client_order_id}: {error}")

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        exchange_order_id = await tracked_order.get_exchange_order_id()
        finished = self._finished.get(exchange_order_id)
        if finished is not None:
            return finished
        chain_order = await self._data_source.order(int(exchange_order_id))
        if chain_order is not None:
            return await self._settled_from_chain(tracked_order, chain_order)
        async for indexed in self._indexer_history(account_orders_path(self._account_address), tracked_order, OrderV1):
            if indexed.order_id == int(exchange_order_id):
                return await self._settled_from_indexer(tracked_order, indexed)
        raise IOError(CONSTANTS.ORDER_NOT_FOUND_MESSAGE)

    async def _settled_from_chain(self, order: InFlightOrder, chain_order: Order) -> OrderUpdate:
        update = translators.order_update(chain_order, order, self.current_timestamp)
        filled = translators.filled_amount(chain_order.status, chain_order.quantity, chain_order.filled_quantity)
        return await self._settled(order, update, filled)

    async def _settled_from_indexer(self, order: InFlightOrder, indexed: OrderV1) -> OrderUpdate:
        update = translators.order_update(indexed, order, indexed.updated_at.timestamp())
        filled = translators.filled_amount(indexed.status, indexed.quantity, indexed.filled)
        return await self._settled(order, update, filled)

    async def _settled(self, order: InFlightOrder, update: OrderUpdate, filled: Decimal) -> OrderUpdate:
        if update.new_state not in FINAL_ORDER_STATES:
            self._settling.pop(order.client_order_id, None)
            return update
        if self._fills_missing(order, filled):
            settling = self._settling.setdefault(order.client_order_id, _Settling(since=self._time()))
            if self._time() - settling.backfilled_at >= CONSTANTS.FILL_BACKFILL_INTERVAL:
                settling.backfilled_at = self._time()
                await self._backfill(order)
            if self._fills_missing(order, filled) and self._time() - settling.since < CONSTANTS.FILL_SETTLE_TIMEOUT:
                live = OrderState.PARTIALLY_FILLED if order.executed_amount_base > 0 else OrderState.OPEN
                return update._replace(new_state=live)
        if self._fills_missing(order, filled):
            self.logger().error(
                f"NeutronX order {order.client_order_id} finished with {filled} filled on chain, but the indexer "
                f"delivered fills for {order.executed_amount_base} within {CONSTANTS.FILL_SETTLE_TIMEOUT:.0f} s"
            )
        self._settling.pop(order.client_order_id, None)
        self._remember_finished(update)
        return update

    @staticmethod
    def _fills_missing(order: InFlightOrder, filled: Decimal) -> bool:
        return filled - order.executed_amount_base >= CONSTANTS.QUANTITY_INCREMENT

    async def _backfill(self, order: InFlightOrder):
        try:
            self._process_fills(await self._order_fills(order))
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.logger().network(f"Error fetching NeutronX fills of order {order.client_order_id}: {error}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        fills = await self._order_fills(order)
        return [translators.trade_update(fill, order, self.trade_fee_schema()) for fill in fills]

    async def _order_fills(self, order: InFlightOrder) -> List[FillV1]:
        exchange_order_id = int(await order.get_exchange_order_id())
        fills = self._indexer_history(account_fills_path(self._account_address), order, FillV1)
        return [fill async for fill in fills if fill.order_id == exchange_order_id]

    async def _update_trade_history(self):
        if not self._order_tracker.all_fillable_orders:
            return
        raw = await self.request_indexer(
            account_fills_path(self._account_address), params={"limit": CONSTANTS.HISTORY_PAGE_LIMIT}
        )
        self._process_fills(FillV1.from_json(item) for item in PageV1.from_json(raw).items)

    async def _indexer_history(self, path: str, order: InFlightOrder, model: Any) -> AsyncIterator[Any]:
        since = self._history_start(order)
        cursor = None
        for _ in range(CONSTANTS.HISTORY_MAX_PAGES):
            query = {"pair": translators.to_exchange_pair(order.trading_pair), "limit": CONSTANTS.HISTORY_PAGE_LIMIT}
            if cursor:
                query["cursor"] = cursor
            page = PageV1.from_json(await self.request_indexer(path, params=query))
            items = [model.from_json(item) for item in page.items]
            for item in items:
                yield item
            cursor = page.next_cursor
            if not cursor or not items or items[-1].time.timestamp() < since:
                return

    @staticmethod
    def _history_start(order: InFlightOrder) -> float:
        created = order.creation_timestamp
        if created is None or not math.isfinite(created) or created <= 0:
            return -math.inf
        return created - CONSTANTS.HISTORY_LOOKBACK_SECONDS

    async def _user_stream_event_listener(self):
        async for message in self._iter_user_event_queue():
            try:
                frame = StreamFrame.from_json(message)
                if frame.channel == CHANNEL_ORDERS:
                    self._process_orders_frame(frame)
                elif frame.channel == CHANNEL_FILLS:
                    self._process_fills(FillV1.from_json(row) for row in frame.rows())
                elif frame.channel == CHANNEL_POSITIONS:
                    self._apply_positions(self._indexer_positions(frame.rows()))
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")

    def _process_orders_frame(self, frame: StreamFrame):
        subaccount_id = self._data_source.subaccount_id
        orders = [OrderV1.from_json(row) for row in frame.rows()]
        orders = [order for order in orders if order.subaccount_id == subaccount_id]
        tracked = self._order_tracker.all_updatable_orders_by_exchange_order_id
        for order in orders:
            in_flight = tracked.get(str(order.order_id))
            if in_flight is None:
                continue
            update = translators.order_update(order, in_flight, order.updated_at.timestamp())
            if update.new_state in FINAL_ORDER_STATES:
                safe_ensure_future(self._finish_from_indexer(in_flight, order))
            else:
                self._process_order_update(update)
        if frame.is_snapshot:
            listed = {str(order.order_id) for order in orders}
            missing = [
                order for order in self._order_tracker.active_orders.values()
                if order.exchange_order_id
                and order.exchange_order_id not in listed
                and self._past_visibility_grace(order)
            ]
            if missing:
                safe_ensure_future(self._refresh_orders(missing))

    async def _finish_from_indexer(self, order: InFlightOrder, indexed: OrderV1):
        self._process_order_update(await self._settled_from_indexer(order, indexed))

    def _process_fills(self, fills: Iterable[FillV1]):
        subaccount_id = self._data_source.subaccount_id
        fillable = self._order_tracker.all_fillable_orders_by_exchange_order_id
        settling = {}
        for fill in fills:
            if fill.subaccount_id != subaccount_id or fill.fill_id in self._seen_fills:
                continue
            order = fillable.get(str(fill.order_id))
            if order is None:
                continue
            _remember(self._seen_fills, fill.fill_id, None, CONSTANTS.SEEN_FILLS_CAPACITY)
            self._order_tracker.process_trade_update(translators.trade_update(fill, order, self.trade_fee_schema()))
            if order.executed_amount_base >= order.amount:
                self._process_order_update(
                    OrderUpdate(
                        client_order_id=order.client_order_id,
                        exchange_order_id=order.exchange_order_id,
                        trading_pair=order.trading_pair,
                        update_timestamp=fill.time.timestamp(),
                        new_state=OrderState.FILLED,
                    )
                )
            elif order.client_order_id in self._settling:
                settling[order.client_order_id] = order
        if settling:
            safe_ensure_future(self._refresh_orders(settling.values()))

    def _process_order_update(self, update: OrderUpdate):
        self._order_tracker.process_order_update(update)
        if update.new_state not in FINAL_ORDER_STATES:
            return
        self._remember_finished(update)
        if update.client_order_id:
            self._settling.pop(update.client_order_id, None)
            self._release_client_id(update.client_order_id)

    def _remember_finished(self, update: OrderUpdate):
        if update.exchange_order_id:
            _remember(self._finished, update.exchange_order_id, update, CONSTANTS.FINISHED_ORDERS_CAPACITY)

    def _release_client_id(self, client_order_id: str):
        if client_order_id.isdigit():
            self._data_source.client_ids.release(int(client_order_id))

    def _indexer_positions(self, rows: Iterable[Dict[str, Any]]) -> Dict[str, Position]:
        positions = {}
        for row in rows:
            position = PositionV1.from_json(row)
            trading_pair = self.trading_pair_for_indexer(position.pair)
            if (
                trading_pair is not None
                and position.status == POSITION_STATUS_OPEN
                and position.subaccount_id == self._data_source.subaccount_id
            ):
                positions[trading_pair] = translators.to_position(position, trading_pair)
        return positions

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        ticker = await self.ticker(trading_pair)
        price = None if ticker is None else ticker.last_price or ticker.mark_price
        return float(price) if price is not None else float("nan")

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        if trading_pair not in self._markets:
            try:
                await self._update_trading_rules()
            except Exception as exception:
                return False, f"could not load NeutronX markets: {exception}"
        market = self._markets.get(trading_pair)
        if market is None:
            return False, f"{trading_pair} is not an active NeutronX market"
        if leverage < 1 or Decimal(leverage) > market.max_leverage:
            return False, f"leverage on {trading_pair} must be between 1 and {market.max_leverage}"
        if Decimal(leverage) > market.effective_max_leverage:
            allowed = format(market.effective_max_leverage.normalize(), "f")
            self.logger().warning(
                f"Open interest on {trading_pair} limits leverage to {allowed} for now; "
                f"orders go out with it until the market allows {leverage} again."
            )
        return True, ""

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        if mode is PositionMode.ONEWAY:
            return True, ""
        return False, "NeutronX nets positions per pair; only ONEWAY is supported"

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        pair = compact_pair(trading_pair)
        for payment in await self._funding_payments.get():
            if compact_pair(payment.pair) == pair:
                return payment.time.timestamp(), payment.rate or Decimal(0), payment.amount
        return 0, Decimal("-1"), Decimal("-1")

    async def _fetch_funding_payments(self) -> List[AccountFundingV1]:
        raw = await self.request_indexer(
            account_funding_path(self._account_address), params={"limit": CONSTANTS.HISTORY_PAGE_LIMIT}
        )
        payments = [AccountFundingV1.from_json(item) for item in PageV1.from_json(raw).items]
        return [payment for payment in payments if payment.subaccount_id == self._data_source.subaccount_id]
