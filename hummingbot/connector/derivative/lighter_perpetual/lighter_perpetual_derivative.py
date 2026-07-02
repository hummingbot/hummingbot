import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from lighter import SignerClient

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.lighter_perpetual import (
    lighter_perpetual_constants as CONSTANTS,
    lighter_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_api_order_book_data_source import (
    LighterPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_api_utils import (
    account_index_from_account,
    decimal_to_exchange_int,
    extract_account_snapshot,
    markets_by_exchange_symbol,
    markets_by_id,
    markets_by_trading_pair,
    normalize_timestamp_to_seconds,
    order_state_from_order_data,
    own_trade_details,
    perpetual_markets_from_exchange_info,
    trading_pair_symbol_map,
)
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_auth import LighterAuth
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_user_stream_data_source import (
    LighterPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_numeric_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_perpetual_trade_fee
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class LighterPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 60.0

    def __init__(
        self,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        lighter_perpetual_l1_address: str = None,
        lighter_perpetual_api_key_index: int = None,
        lighter_perpetual_api_public_key: str = None,
        lighter_perpetual_api_private_key: str = None,
        lighter_perpetual_account_limit: str = "Standard",
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._l1_address = lighter_perpetual_l1_address
        self._account_index = None
        self._api_key_index = (
            int(lighter_perpetual_api_key_index)
            if lighter_perpetual_api_key_index not in (None, "")
            else None
        )
        self._api_public_key = lighter_perpetual_api_public_key
        self._api_private_key = lighter_perpetual_api_private_key
        self._api_account_limit = lighter_perpetual_account_limit
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs or []
        self._domain = domain
        self._nonce_creator = NonceCreator.for_milliseconds()
        self._markets_by_id = {}
        self._markets_by_trading_pair = {}
        self._markets_by_exchange_symbol = {}
        self._tx_lock = asyncio.Lock()
        self._account_ready_lock = asyncio.Lock()
        # Single-flight task for WS-triggered balance refresh: Lighter's account_all_assets
        # event lacks `available_balance`, so we use the event as a trigger to refresh from REST.
        self._balance_refresh_task: Optional[asyncio.Task] = None
        self._real_time_balance_update = False
        self._signer_client = self._create_signer_client() if trading_required and self._account_index is not None else None
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def account_index(self) -> int:
        return self._account_index

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[LighterAuth]:
        if self._trading_required and self._signer_client is not None:
            return LighterAuth(self._signer_client, api_key_index=self._api_key_index, api_public_key=self._api_public_key)
        return None

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.generate_account_limit(self._api_account_limit)

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PING_PATH_URL

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

    async def _make_network_check_request(self):
        await self._api_get(path_url=self.check_network_request_path)

    async def start_network(self):
        if self.is_trading_required:
            await self._ensure_account_ready()
        await super().start_network()

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def supported_position_modes(self):
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def buy(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type=OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        order_id = self._new_client_order_id()
        position_action = kwargs.pop("position_action", PositionAction.OPEN)
        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.BUY,
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

    def sell(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        order_id = self._new_client_order_id()
        position_action = kwargs.pop("position_action", PositionAction.OPEN)
        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.SELL,
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

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        exchange_info = await self._api_get(
            path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL,
            params={"filter": "all"},
        )
        prices = []
        for market in perpetual_markets_from_exchange_info(exchange_info):
            prices.append({"symbol": market.exchange_symbol, "price": str(market.raw_info["last_trade_price"])})
        return prices

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(throttler=self._throttler, auth=self._auth)

    async def _make_trading_rules_request(self) -> Any:
        info = await self._api_get(
            path_url=self.trading_rules_request_path,
            params={"filter": "all"},
        )
        return info

    async def _make_trading_pairs_request(self) -> Any:
        return await self._make_trading_rules_request()

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return LighterPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return LighterPerpetualUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def _status_polling_loop_fetch_updates(self):
        await self._ensure_account_ready()
        await safe_gather(
            self._update_trade_history(),
            self._update_orders(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _update_order_status(self):
        await self._update_orders()

    async def _update_lost_orders_status(self):
        await self._update_lost_orders()

    def _integrator_order_params(self) -> Dict[str, int]:
        # Lighter's equivalent of a "builder code" (see hyperliquid PR #8265): orders can
        # credit the Hummingbot Foundation's integrator account for volume attribution.
        # These fields are part of the signed order transaction, so they are handed
        # straight to the SDK's create_order / create_market_order. Attribution is applied
        # on mainnet only and omitted when disabled or while the Foundation index is unset.
        if not CONSTANTS.INTEGRATOR_ENABLED:
            return {}
        if self._domain == CONSTANTS.TESTNET_DOMAIN:
            return {}
        if CONSTANTS.FOUNDATION_INTEGRATOR_ACCOUNT_INDEX <= 0:
            return {}
        return {
            "integrator_account_index": CONSTANTS.FOUNDATION_INTEGRATOR_ACCOUNT_INDEX,
            "integrator_taker_fee": CONSTANTS.FOUNDATION_INTEGRATOR_TAKER_FEE,
            "integrator_maker_fee": CONSTANTS.FOUNDATION_INTEGRATOR_MAKER_FEE,
        }

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
        await self._ensure_account_ready()
        market = self.market_info_for_trading_pair(trading_pair)
        price = self._effective_order_price(
            trading_pair=trading_pair,
            trade_type=trade_type,
            order_type=order_type,
            price=price,
        )
        base_amount = decimal_to_exchange_int(amount, market.size_decimals)
        price_int = decimal_to_exchange_int(price, market.price_decimals)
        client_order_index = int(order_id)
        reduce_only = position_action == PositionAction.CLOSE
        integrator_params = self._integrator_order_params()

        async with self._tx_lock:
            if order_type is OrderType.MARKET:
                _, tx_response, error = await self._signer_client.create_market_order(
                    market_index=market.market_id,
                    client_order_index=client_order_index,
                    base_amount=base_amount,
                    avg_execution_price=price_int,
                    is_ask=trade_type is TradeType.SELL,
                    reduce_only=reduce_only,
                    **integrator_params,
                )
            else:
                tif = self._signer_client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME
                if order_type is OrderType.LIMIT_MAKER:
                    tif = self._signer_client.ORDER_TIME_IN_FORCE_POST_ONLY
                _, tx_response, error = await self._signer_client.create_order(
                    market_index=market.market_id,
                    client_order_index=client_order_index,
                    base_amount=base_amount,
                    price=price_int,
                    is_ask=trade_type is TradeType.SELL,
                    order_type=self._signer_client.ORDER_TYPE_LIMIT,
                    time_in_force=tif,
                    reduce_only=reduce_only,
                    **integrator_params,
                )

        if error is not None:
            raise IOError(f"Error submitting Lighter order {order_id}: {error}")
        if not self._is_tx_response_success(tx_response):
            raise IOError(f"Error submitting Lighter order {order_id}: {tx_response}")
        return order_id, self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        await self._ensure_account_ready()
        market = self.market_info_for_trading_pair(tracked_order.trading_pair)
        order_data = await self._find_order(tracked_order=tracked_order, include_inactive=True)
        if order_data is None:
            raise IOError(f"{CONSTANTS.ORDER_NOT_EXIST_MESSAGE}: {order_id}")

        async with self._tx_lock:
            _, tx_response, error = await self._signer_client.cancel_order(
                market_index=market.market_id,
                order_index=int(order_data["order_id"]),
            )
        if error is not None:
            raise IOError(f"Error cancelling Lighter order {order_id}: {error}")
        if not self._is_tx_response_success(tx_response):
            raise IOError(f"Error cancelling Lighter order {order_id}: {tx_response}")
        return True

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
        return build_perpetual_trade_fee(
            exchange=self.name,
            is_maker=is_maker if is_maker is not None else order_type is OrderType.LIMIT_MAKER,
            position_action=position_action,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )

    async def _update_trading_fees(self):
        return

    async def _update_trade_history(self):
        if not self._order_tracker.all_fillable_orders:
            return
        if self._markets_by_exchange_symbol == {}:
            await self._update_trading_rules()

        market_ids = {
            self.market_info_for_trading_pair(order.trading_pair).market_id
            for order in self._order_tracker.all_fillable_orders.values()
        }
        for market_id in market_ids:
            response = await self._api_get(
                path_url=CONSTANTS.RECENT_TRADES_PATH_URL,
                params={
                    "market_id": market_id,
                    "limit": 100,
                },
            )
            for trade in response.get("trades", []):
                trade_update = self._trade_update_from_trade(trade)
                if trade_update is not None:
                    self._order_tracker.process_trade_update(trade_update)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        return []

    @staticmethod
    def _order_misc_updates(order_data: Dict[str, Any], state: OrderState) -> Optional[Dict[str, Any]]:
        if state != OrderState.FAILED:
            return None

        status = str(order_data.get("status", ""))
        # Kept both fields populated for compatibility with existing failure-event logging.
        return {
            "error_type": status,
            "error_message": f"Exchange order status: {status}",
        }

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        order_data = await self._find_order(tracked_order=tracked_order, include_inactive=True)
        if order_data is None:
            # Lighter's REST endpoints may not have indexed a just-submitted order yet.
            # Within the grace window, report it as still open rather than not-found, so the
            # order tracker doesn't escalate a live order to "lost".
            age = self.current_timestamp - tracked_order.creation_timestamp
            if age < CONSTANTS.ORDER_NOT_FOUND_GRACE_PERIOD:
                return OrderUpdate(
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=tracked_order.current_state,
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=tracked_order.exchange_order_id,
                )
            raise IOError(f"{CONSTANTS.ORDER_NOT_EXIST_MESSAGE}: {tracked_order.client_order_id}")
        new_state = order_state_from_order_data(order_data)
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=normalize_timestamp_to_seconds(
                order_data.get("updated_at", order_data.get("transaction_time"))
            ),
            new_state=new_state,
            client_order_id=str(order_data["client_order_id"]),
            exchange_order_id=str(order_data["order_id"]),
            misc_updates=self._order_misc_updates(order_data=order_data, state=new_state),
        )

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_response = await self._api_get(
            path_url=CONSTANTS.BALANCE_PATH_URL,
            params=self._account_lookup_params(),
        )
        account = extract_account_snapshot(
            account_response, account_index=self._account_index, l1_address=self._l1_address
        )
        self._set_account_index_from_account(account)
        available = self._safe_decimal(account.get("available_balance", "0"))

        for asset in account.get("assets", []):
            asset_name = str(asset["symbol"]).upper()
            # spot_balance = self._safe_decimal(asset.get("balance", "0"))
            locked_balance = self._safe_decimal(asset.get("locked_balance", "0"))
            total_balance = self._safe_decimal(asset.get("margin_balance", "0"))
            self._account_balances[asset_name] = total_balance
            self._account_available_balances[asset_name] = available if asset_name == CONSTANTS.COLLATERAL_TOKEN else total_balance - locked_balance
            remote_asset_names.add(asset_name)

        for asset_name in local_asset_names.difference(remote_asset_names):
            del self._account_balances[asset_name]
            del self._account_available_balances[asset_name]

    def _schedule_balance_refresh(self):
        # Trigger an out-of-band `_update_balances` REST call. Single-flight: if a
        # refresh is already in progress, this is a no-op (the running task will pick
        # up the latest state).
        if self._balance_refresh_task is None or self._balance_refresh_task.done():
            self._balance_refresh_task = safe_ensure_future(self._safe_update_balances())

    async def _safe_update_balances(self):
        try:
            await self._update_balances()
        except Exception:
            self.logger().exception("WS-triggered balance refresh failed.")

    async def _update_positions(self):
        account_response = await self._api_get(
            path_url=CONSTANTS.BALANCE_PATH_URL,
            params=self._account_lookup_params(),
        )
        account = extract_account_snapshot(
            account_response, account_index=self._account_index, l1_address=self._l1_address
        )
        self._set_account_index_from_account(account)

        active_position_keys = set()
        for raw_position in account.get("positions", []):
            position = self._parse_position(raw_position)
            if position is None:
                continue
            pos_key = self._perpetual_trading.position_key(position.trading_pair, position.position_side)
            active_position_keys.add(pos_key)
            self._perpetual_trading.set_position(pos_key, position)

        for position_key in list(self._perpetual_trading.account_positions.keys()):
            if position_key not in active_position_keys:
                self._perpetual_trading.remove_position(position_key)

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        if mode is PositionMode.ONEWAY:
            return True, ""
        return False, "Lighter only supports ONEWAY position mode."

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        await self._ensure_account_ready()
        if self._signer_client is None:
            return False, "Connector is not configured for trading."

        if not hasattr(self._signer_client, "update_leverage"):
            return False, "This lighter-sdk version does not support leverage updates."

        market = self.market_info_for_trading_pair(trading_pair)
        margin_mode = getattr(self._signer_client, "CROSS_MARGIN_MODE", 0)
        try:
            _, tx_response, error = await self._signer_client.update_leverage(
                market_index=market.market_id,
                margin_mode=margin_mode,
                leverage=int(leverage),
            )
        except Exception as e:
            return False, str(e)

        if error is not None:
            return False, f"Error updating leverage: {error}"

        if not self._is_tx_response_success(tx_response):
            return False, f"Unexpected leverage response: {tx_response}"

        return True, ""

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        if self._markets_by_exchange_symbol == {}:
            await self._update_trading_rules()
        market = self.market_info_for_trading_pair(trading_pair)
        response = await self._api_get(
            path_url=CONSTANTS.POSITION_FUNDING_PATH_URL,
            params={
                "account_index": self._account_index,
                "market_id": market.market_id,
                "limit": 1,
            },
            is_auth_required=True,
        )

        entries = response.get("position_fundings", response.get("fundings", []))
        if len(entries) == 0:
            return 0, Decimal("-1"), Decimal("-1")

        latest = entries[0]
        payment = self._safe_decimal(latest.get("change", "0"))
        if payment == Decimal("0"):
            return 0, Decimal("-1"), Decimal("-1")

        rate = self._safe_decimal(latest.get("rate", "-1"))
        timestamp_ms = int(latest.get("timestamp", 0))
        return timestamp_ms * 1e-3, rate, payment

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        if trading_pair not in self._markets_by_trading_pair:
            await self._update_trading_rules()
        if trading_pair not in self._markets_by_trading_pair:
            raise ValueError(f"Market info not available for {trading_pair}")
        market = self.market_info_for_trading_pair(trading_pair)
        response = await self._api_get(
            path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL,
            params={"market_id": market.market_id},
        )
        refreshed_markets = perpetual_markets_from_exchange_info(response)
        if len(refreshed_markets) == 0:
            return float(self._safe_decimal(market.raw_info.get("last_trade_price", "0")))
        return float(self._safe_decimal(refreshed_markets[0].raw_info["last_trade_price"]))

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                channel = str(event_message.get("channel", ""))
                if channel.startswith(f"{CONSTANTS.ACCOUNT_ALL_ORDERS_CHANNEL}:"):
                    self._process_order_events(event_message.get("orders", {}))
                elif channel.startswith(f"{CONSTANTS.ACCOUNT_ALL_TRADES_CHANNEL}:"):
                    self._process_trade_events(event_message.get("trades", {}))
                elif channel.startswith(f"{CONSTANTS.ACCOUNT_ALL_ASSETS_CHANNEL}:"):
                    # Lighter's assets event has no `available_balance` — use it as a
                    # signal to fetch the authoritative balance snapshot from REST.
                    self._schedule_balance_refresh()
                elif channel.startswith(f"{CONSTANTS.ACCOUNT_ALL_POSITIONS_CHANNEL}:"):
                    self._process_position_events(event_message.get("positions", {}))
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        markets = perpetual_markets_from_exchange_info(exchange_info_dict)
        self._markets_by_id = markets_by_id(markets)
        self._markets_by_trading_pair = markets_by_trading_pair(markets)
        self._markets_by_exchange_symbol = markets_by_exchange_symbol(markets)
        return [market.trading_rule(collateral_token=CONSTANTS.COLLATERAL_TOKEN) for market in markets]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        markets = perpetual_markets_from_exchange_info(exchange_info)
        self._markets_by_id = markets_by_id(markets)
        self._markets_by_trading_pair = markets_by_trading_pair(markets)
        self._markets_by_exchange_symbol = markets_by_exchange_symbol(markets)
        self._set_trading_pair_symbol_map(trading_pair_symbol_map(markets))

    def market_info_for_trading_pair(self, trading_pair: str):
        return self._markets_by_trading_pair[trading_pair]

    def market_info_for_market_id(self, market_id: int):
        return self._markets_by_id[int(market_id)]

    def _new_client_order_id(self) -> str:
        return str(
            get_new_numeric_client_order_id(
                nonce_creator=self._nonce_creator,
                max_id_bit_count=CONSTANTS.MAX_CLIENT_ORDER_ID_BIT_COUNT,
            )
        )

    def _effective_order_price(
        self,
        trading_pair: str,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
    ) -> Decimal:
        if order_type is not OrderType.MARKET:
            return price
        reference_price = self.get_mid_price(trading_pair) if price.is_nan() else price
        multiplier = Decimal("1") + CONSTANTS.MARKET_ORDER_SLIPPAGE
        if trade_type is TradeType.SELL:
            multiplier = Decimal("1") - CONSTANTS.MARKET_ORDER_SLIPPAGE
        return self.quantize_order_price(trading_pair, reference_price * multiplier)

    def _create_signer_client(self):
        if self._account_index is None or self._api_key_index is None or self._api_private_key is None:
            raise ValueError(
                "Lighter trading requires an L1 address or account index, plus API key index and API private key."
            )
        client = None
        try:
            client = SignerClient(
                url=web_utils.public_rest_url(domain=self._domain),
                account_index=self._account_index,
                api_private_keys={self._api_key_index: self._api_private_key},
            )
        except Exception as e:
            raise IOError(f"Error creating Lighter signer client: {e}")
        return client

    async def _find_order(self, tracked_order: InFlightOrder, include_inactive: bool) -> Optional[Dict[str, Any]]:
        await self._ensure_account_ready()
        market = self.market_info_for_trading_pair(tracked_order.trading_pair)
        active_orders = await self._api_get(
            path_url=CONSTANTS.ACCOUNT_ACTIVE_ORDERS_PATH_URL,
            params={
                "account_index": self._account_index,
                "market_id": market.market_id,
            },
            is_auth_required=True,
        )
        order = self._match_order(tracked_order=tracked_order, orders=active_orders.get("orders", []))
        if order is not None or not include_inactive:
            return order

        inactive_orders = await self._api_get(
            path_url=CONSTANTS.ACCOUNT_INACTIVE_ORDERS_PATH_URL,
            params={
                "account_index": self._account_index,
                "market_id": market.market_id,
                "limit": 100,
            },
            is_auth_required=True,
        )
        return self._match_order(tracked_order=tracked_order, orders=inactive_orders.get("orders", []))

    def _account_lookup_params(self) -> Dict[str, Any]:
        if self._account_index is not None:
            return {"by": CONSTANTS.ACCOUNT_LOOKUP_BY_INDEX, "value": self._account_index, "active_only": "true"}
        if self._l1_address is not None:
            return {"by": CONSTANTS.ACCOUNT_LOOKUP_BY_L1_ADDRESS, "value": self._l1_address, "active_only": "true"}
        raise ValueError("Lighter requires an L1 address or account index to look up account balances.")

    def _set_account_index_from_account(self, account: Dict[str, Any]):
        if self._account_index is None:
            self._account_index = account_index_from_account(account)

    async def _ensure_account_ready(self):
        if not self.is_trading_required:
            return
        async with self._account_ready_lock:
            if self._markets_by_exchange_symbol == {}:
                await self._update_trading_rules()
            if self._account_index is None:
                account_response = await self._api_get(
                    path_url=CONSTANTS.BALANCE_PATH_URL,
                    params=self._account_lookup_params(),
                )
                account = extract_account_snapshot(account_response, l1_address=self._l1_address)
                self._set_account_index_from_account(account)
            if self._signer_client is None:
                self._signer_client = self._create_signer_client()
                self._auth = self.authenticator
                self._web_assistants_factory = self._create_web_assistants_factory()
                self._user_stream_tracker = self._create_user_stream_tracker()

    @staticmethod
    def _match_order(tracked_order: InFlightOrder, orders: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for order in orders:
            if str(order.get("client_order_id", "")) == tracked_order.client_order_id:
                return order
            if (
                tracked_order.exchange_order_id is not None
                and str(order.get("order_id", "")) == tracked_order.exchange_order_id
            ):
                return order
        return None

    def _process_order_events(self, order_payload: Any):
        def iter_orders(payload: Any):
            if isinstance(payload, list):
                for item in payload:
                    yield from iter_orders(item)
            elif isinstance(payload, dict):
                if "client_order_id" in payload or "order_id" in payload:
                    yield payload
                    return
                for value in payload.values():
                    yield from iter_orders(value)

        for order in iter_orders(order_payload):
            client_order_id = str(order.get("client_order_id", ""))
            if client_order_id == "":
                continue
            tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
            if tracked_order is None:
                continue
            new_state = order_state_from_order_data(order)
            order_update = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=normalize_timestamp_to_seconds(
                    order.get("updated_at", order.get("transaction_time"))
                ),
                new_state=new_state,
                client_order_id=client_order_id,
                exchange_order_id=str(order.get("order_id")),
                misc_updates=self._order_misc_updates(order_data=order, state=new_state),
            )
            self._order_tracker.process_order_update(order_update)

    def _process_trade_events(self, trade_payload: Any):
        if isinstance(trade_payload, dict):
            groups = trade_payload.values()
        else:
            groups = [trade_payload]
        for trades in groups:
            if isinstance(trades, dict):
                trades = [trades]
            if not isinstance(trades, list):
                continue
            for trade in trades:
                trade_update = self._trade_update_from_trade(trade)
                if trade_update is not None:
                    self._order_tracker.process_trade_update(trade_update)

    def _process_position_events(self, position_payload: Any):
        # WS sends delta updates — only add/update positions present in the event.
        # Removing a position requires either size=0 in the event, or REST reconciliation
        # via _update_positions (which sees all positions and prunes closed ones).
        if isinstance(position_payload, dict):
            raw_positions = position_payload.values()
        elif isinstance(position_payload, list):
            raw_positions = position_payload
        else:
            return

        for raw_position in raw_positions:
            market_id = raw_position.get("market_id")
            size = self._safe_decimal(raw_position.get("position", "0"))
            position = self._parse_position(raw_position)
            if position is None:
                if market_id is not None and size == Decimal("0"):
                    market = self._markets_by_id.get(int(market_id))
                    if market is not None:
                        for side in (PositionSide.LONG, PositionSide.SHORT):
                            pos_key = self._perpetual_trading.position_key(market.trading_pair, side)
                            if pos_key in self._perpetual_trading.account_positions:
                                self._perpetual_trading.remove_position(pos_key)
                continue
            pos_key = self._perpetual_trading.position_key(position.trading_pair, position.position_side)
            self._perpetual_trading.set_position(pos_key, position)

    def _trade_update_from_trade(self, trade: Dict[str, Any]) -> Optional[TradeUpdate]:
        details = own_trade_details(trade, account_index=self._account_index)
        if details is None:
            return None

        trade_type, client_order_id, exchange_order_id, is_maker = details
        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
        if tracked_order is None and exchange_order_id:
            tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)
        if tracked_order is None:
            return None

        market = self.market_info_for_market_id(int(trade["market_id"]))
        position_action = (
            tracked_order.position
            if tracked_order.position in [PositionAction.OPEN, PositionAction.CLOSE]
            else PositionAction.OPEN
        )
        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_action,
            percent=market.maker_fee if is_maker else market.taker_fee,
        )
        price = self._safe_decimal(trade["price"])
        size = self._safe_decimal(trade["size"])
        return TradeUpdate(
            trade_id=str(trade["trade_id"]),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=normalize_timestamp_to_seconds(trade.get("transaction_time")),
            fill_price=price,
            fill_base_amount=size,
            fill_quote_amount=price * size,
            fee=fee,
            is_taker=not is_maker,
        )

    def _parse_position(self, raw_position: Dict[str, Any]) -> Optional[Position]:
        market_id = raw_position.get("market_id")
        symbol = str(raw_position.get("symbol", "")).upper()

        market = None
        if market_id is not None:
            market = self._markets_by_id.get(int(market_id))
        if market is None and symbol:
            market = self._markets_by_exchange_symbol.get(symbol)
        if market is None:
            return None

        sign = self._safe_decimal(raw_position.get("sign", "1"))
        size = self._safe_decimal(raw_position.get("position", "0"))
        amount = size * sign if sign in (Decimal("-1"), Decimal("1")) and size >= 0 else size

        if amount == Decimal("0"):
            return None

        position_side = PositionSide.LONG if amount > 0 else PositionSide.SHORT
        unrealized_pnl = self._safe_decimal(raw_position.get("unrealized_pnl", "0"))
        entry_price = self._safe_decimal(raw_position.get("avg_entry_price", "0"))

        leverage = Decimal("1")
        initial_margin_fraction = raw_position.get("initial_margin_fraction")
        if initial_margin_fraction not in (None, "", "0", 0):
            try:
                leverage = Decimal("1") / self._safe_decimal(initial_margin_fraction)
            except Exception:
                leverage = Decimal("1")

        return Position(
            trading_pair=market.trading_pair,
            position_side=position_side,
            unrealized_pnl=unrealized_pnl,
            entry_price=entry_price,
            amount=amount,
            leverage=leverage,
        )

    @staticmethod
    def _safe_decimal(value: Any) -> Decimal:
        if value is None or value == "":
            return Decimal("0")
        try:
            result = Decimal(str(value))
        except Exception:
            return Decimal("0")
        if result.is_nan() or result.is_infinite():
            return Decimal("0")
        return result

    @staticmethod
    def _extract_tx_code(tx_response: Any) -> Optional[int]:
        if tx_response is None:
            return None
        if isinstance(tx_response, dict):
            code = tx_response.get("code")
            if code is not None:
                try:
                    return int(code)
                except (TypeError, ValueError):
                    return None
        if hasattr(tx_response, "code"):
            try:
                return int(getattr(tx_response, "code"))
            except (TypeError, ValueError):
                return None
        return None

    def _is_tx_response_success(self, tx_response: Any) -> bool:
        code = self._extract_tx_code(tx_response)
        if code is None:
            return True
        return code == 200
