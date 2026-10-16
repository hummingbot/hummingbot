import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.lmex_perpetual import (
    lmex_perpetual_constants as CONSTANTS,
    lmex_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_api_order_book_data_source import (
    LmexPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_auth import LmexPerpetualAuth
from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_user_stream_data_source import (
    LmexPerpetualUserStreamDataSource,
    ORDERS_EVENT_KEY,
    POSITIONS_EVENT_KEY,
    TRADES_EVENT_KEY,
    WALLET_EVENT_KEY,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class LmexPerpetualDerivative(PerpetualDerivativePyBase):
    """
    LMEX Perpetual (Futures) connector.

    Connects to https://api.lmex.io/futures (or sandbox equivalent) using the
    LMEX Futures REST API v2.3.  There is no WebSocket feed; all data is
    obtained by periodic REST polling.

    Symbol mapping
    --------------
    LMEX uses ``BTC-PERP`` for perpetual contracts.
    Hummingbot represents the same market as ``BTC-USDT``.
    The ``_initialize_trading_pair_symbols_from_exchange_info`` method builds a
    bidict that maps between these representations.
    """

    DEFAULT_DOMAIN = CONSTANTS.DEFAULT_DOMAIN
    TICK_INTERVAL_LIMIT = 120.0

    web_utils = web_utils

    def __init__(
        self,
        lmex_perpetual_api_key: str,
        lmex_perpetual_secret_key: str,
        domain: str = DEFAULT_DOMAIN,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
    ):
        self._lmex_perpetual_api_key = lmex_perpetual_api_key
        self._lmex_perpetual_secret_key = lmex_perpetual_secret_key
        self._domain = domain
        self._trading_pairs = trading_pairs or []
        self._trading_required = trading_required
        self._position_mode: Optional[PositionMode] = None

        super().__init__(balance_asset_limit, rate_limits_share_pct)

        self._real_time_balance_update = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def authenticator(self) -> LmexPerpetualAuth:
        return LmexPerpetualAuth(
            api_key=self._lmex_perpetual_api_key,
            secret_key=self._lmex_perpetual_secret_key,
        )

    @property
    def name(self) -> str:
        return "lmex_perpetual"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.MARKET_SUMMARY_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.MARKET_SUMMARY_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.MARKET_SUMMARY_PATH_URL

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

    # ------------------------------------------------------------------
    # Supported order/position types
    # ------------------------------------------------------------------

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        return "USDT"

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return "USDT"

    # ------------------------------------------------------------------
    # Factory / lifecycle
    # ------------------------------------------------------------------

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth,
            domain=self._domain,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return LmexPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return LmexPerpetualUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def start(self, clock: Clock, timestamp: float):
        super().start(clock, timestamp)

    async def start_network(self):
        await self._update_trading_rules()
        await super().start_network()

    # ------------------------------------------------------------------
    # Network check
    # ------------------------------------------------------------------

    async def check_network(self) -> NetworkStatus:
        try:
            await self._api_request(
                method=RESTMethod.GET,
                path_url=CONSTANTS.MARKET_SUMMARY_PATH_URL,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    # ------------------------------------------------------------------
    # Error classification helpers
    # ------------------------------------------------------------------

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return False

    # ------------------------------------------------------------------
    # Trading rules
    # ------------------------------------------------------------------

    async def _format_trading_rules(self, raw_trading_pair_info: Any) -> List[TradingRule]:
        """
        Parse market_summary response into TradingRule objects.

        The market_summary endpoint returns a list of dicts.  Each dict has:
            symbol, minOrderSize, minPriceIncrement, minSizeIncrement,
            contractSize, active, ...
        """
        result: Dict[str, TradingRule] = {}

        items = raw_trading_pair_info if isinstance(raw_trading_pair_info, list) else [raw_trading_pair_info]

        for rule in items:
            try:
                if not rule.get("active", True):
                    continue

                ex_symbol = rule["symbol"]
                # Only handle perpetual contracts for now
                if not ex_symbol.endswith("-PERP"):
                    continue

                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=ex_symbol)

                min_order_size = Decimal(str(rule.get("minOrderSize", "1")))
                min_price_inc = Decimal(str(rule.get("minPriceIncrement", "0.01")))
                min_size_inc = Decimal(str(rule.get("minSizeIncrement", "1")))
                # contractSize tells us how much base asset one contract represents
                contract_size = Decimal(str(rule.get("contractSize", "1")))

                result[trading_pair] = TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=min_order_size,
                    min_price_increment=min_price_inc,
                    min_base_amount_increment=min_size_inc,
                    min_notional_size=Decimal("1"),
                    min_order_value=Decimal("1"),
                    buy_order_collateral_token="USDT",
                    sell_order_collateral_token="USDT",
                )

                # Store contract size so we can convert amount <-> contracts
                if not hasattr(self, "_contract_sizes"):
                    self._contract_sizes: Dict[str, Decimal] = {}
                self._contract_sizes[trading_pair] = contract_size

            except Exception:
                self.logger().error(
                    f"Error parsing trading rule for {rule}. Skipping.", exc_info=True
                )

        return list(result.values())

    # ------------------------------------------------------------------
    # Amount / contract size conversion
    # ------------------------------------------------------------------

    def _amount_to_contracts(self, trading_pair: str, amount: Decimal) -> int:
        """Convert base-asset amount to number of contracts (rounded down)."""
        contract_sizes = getattr(self, "_contract_sizes", {})
        contract_size = contract_sizes.get(trading_pair, Decimal("1"))
        return int(amount / contract_size)

    def _contracts_to_amount(self, trading_pair: str, contracts: int) -> Decimal:
        """Convert number of contracts to base-asset amount."""
        contract_sizes = getattr(self, "_contract_sizes", {})
        contract_size = contract_sizes.get(trading_pair, Decimal("1"))
        return Decimal(str(contracts)) * contract_size

    # ------------------------------------------------------------------
    # Order placement & cancellation
    # ------------------------------------------------------------------

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
        ex_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        num_contracts = self._amount_to_contracts(trading_pair, amount)
        if num_contracts < 1:
            num_contracts = 1

        side = "BUY" if trade_type is TradeType.BUY else "SELL"

        data: Dict[str, Any] = {
            "symbol": ex_symbol,
            "size": num_contracts,
            "side": side,
            "clOrderId": order_id,
        }

        if order_type is OrderType.MARKET:
            data["type"] = "MARKET"
        elif order_type is OrderType.LIMIT_MAKER:
            data["type"] = "LIMIT"
            data["price"] = str(price)
            data["time_in_force"] = "GTX"   # post-only
            data["postOnly"] = True
        else:
            # LIMIT
            data["type"] = "LIMIT"
            data["price"] = str(price)
            data["time_in_force"] = "GTC"

        reduce_only = kwargs.get("reduce_only", False)
        if reduce_only:
            data["reduceOnly"] = True

        order_result = await self._api_post(
            path_url=CONSTANTS.ORDER_PATH_URL,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_PATH_URL,
        )

        # Response is a list with one element
        if isinstance(order_result, list):
            order_result = order_result[0]

        status_code = order_result.get("status")
        if status_code in CONSTANTS.FAILED_STATUSES:
            raise IOError(
                {"label": "ORDER_REJECTED", "message": f"Order rejected with status {status_code}."}
            )

        exchange_order_id = str(order_result["orderID"])
        return exchange_order_id, self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        exchange_order_id = await tracked_order.get_exchange_order_id()
        ex_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)

        await self._api_delete(
            path_url=CONSTANTS.ORDER_PATH_URL,
            params={"symbol": ex_symbol, "orderID": exchange_order_id},
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_PATH_URL,
        )
        return True

    # ------------------------------------------------------------------
    # Balance updates
    # ------------------------------------------------------------------

    async def _update_balances(self):
        try:
            response = await self._api_get(
                path_url=CONSTANTS.USER_WALLET_PATH_URL,
                params={"wallet": "CROSS@"},
                is_auth_required=True,
                limit_id=CONSTANTS.USER_WALLET_PATH_URL,
            )
            self._process_balance_message(response)
        except Exception as e:
            self.logger().network(
                f"Unexpected error while fetching balance update - {e}",
                exc_info=True,
                app_warning_msg=f"Could not fetch balance update from {self.name_cap}",
            )
            raise

    def _process_balance_message(self, wallet_data: Any):
        """
        Parse the wallet response (list of currency entries) and update account balances.

        Response format:
            [{"currency": "USDT", "total": "1000.0", "available": "900.0", "wallet": "CROSS@"}, ...]
        """
        local_assets = set(self._account_balances.keys())
        remote_assets: set = set()

        items = wallet_data if isinstance(wallet_data, list) else [wallet_data]
        for entry in items:
            asset = entry.get("currency", "USDT")
            self._account_balances[asset] = Decimal(str(entry.get("total", "0")))
            self._account_available_balances[asset] = Decimal(str(entry.get("available", "0")))
            remote_assets.add(asset)

        for asset in local_assets - remote_assets:
            del self._account_balances[asset]
            del self._account_available_balances[asset]

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    async def _update_positions(self):
        """
        Fetch positions for all tracked trading pairs and update the
        in-memory position store.
        """
        for trading_pair in self._trading_pairs:
            try:
                ex_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                positions = await self._api_get(
                    path_url=CONSTANTS.POSITIONS_PATH_URL,
                    params={"symbol": ex_symbol},
                    is_auth_required=True,
                    limit_id=CONSTANTS.POSITIONS_PATH_URL,
                )
                for pos_data in (positions if isinstance(positions, list) else [positions]):
                    await self._process_position_data(pos_data)
            except Exception:
                self.logger().debug(
                    f"Error updating positions for {trading_pair}", exc_info=True
                )

    async def _process_position_data(self, position_data: Dict[str, Any]):
        ex_trading_pair = position_data.get("symbol")
        if not ex_trading_pair:
            return

        try:
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(ex_trading_pair)
        except Exception:
            return

        # "side" in LMEX position is BUY (long) or SELL (short)
        side_str = position_data.get("side", "BUY")
        position_side = PositionSide.LONG if side_str == "BUY" else PositionSide.SHORT

        total_contracts = int(position_data.get("total", 0))
        amount = self._contracts_to_amount(trading_pair, total_contracts)
        pos_key = self._perpetual_trading.position_key(trading_pair, position_side)

        if amount == Decimal("0"):
            self._perpetual_trading.remove_position(pos_key)
            return

        entry_price = Decimal(str(position_data.get("entryPrice", "0")))
        unrealized_pnl = Decimal(str(position_data.get("unrealizedPnl", "0")))
        leverage = Decimal(str(position_data.get("currentLeverage", "1")))

        position = Position(
            trading_pair=trading_pair,
            position_side=position_side,
            unrealized_pnl=unrealized_pnl,
            entry_price=entry_price,
            amount=amount,
            leverage=leverage,
        )
        self._perpetual_trading.set_position(pos_key, position)

    # ------------------------------------------------------------------
    # Order status
    # ------------------------------------------------------------------

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        try:
            exchange_order_id = await tracked_order.get_exchange_order_id()
            order_data = await self._api_get(
                path_url=CONSTANTS.ORDER_PATH_URL,
                params={"orderID": exchange_order_id},
                is_auth_required=True,
                limit_id=CONSTANTS.ORDER_PATH_URL,
            )
            # Response may be a list or dict
            if isinstance(order_data, list):
                order_data = order_data[0]

            order_update = self._create_order_update_from_data(order_data, tracked_order)
        except asyncio.TimeoutError:
            raise IOError(
                f"Skipped order status update for {tracked_order.client_order_id} "
                "- waiting for exchange order id."
            )
        return order_update

    def _create_order_update_from_data(
        self, order_data: Dict[str, Any], order: InFlightOrder
    ) -> OrderUpdate:
        new_state = self._order_state_from_status(order_data.get("status"))
        if new_state is None:
            new_state = order.current_state

        # LMEX timestamps are in milliseconds
        raw_ts = order_data.get("timestamp", order_data.get("orderID", 0))
        try:
            update_timestamp = float(raw_ts) * 1e-3
        except (TypeError, ValueError):
            update_timestamp = self.current_timestamp

        return OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=new_state,
            client_order_id=str(order_data.get("clOrderID", order.client_order_id)),
            exchange_order_id=str(order_data.get("orderID", order.exchange_order_id or "")),
        )

    def _order_state_from_status(self, status_code: Optional[int]) -> Optional[OrderState]:
        if status_code is None:
            return None
        if status_code in CONSTANTS.FILLED_STATUSES:
            return OrderState.FILLED
        if status_code in CONSTANTS.PARTIALLY_FILLED_STATUSES:
            return OrderState.PARTIALLY_FILLED
        if status_code in CONSTANTS.CANCELLED_STATUSES:
            return OrderState.CANCELED
        if status_code in CONSTANTS.FAILED_STATUSES:
            return OrderState.FAILED
        if status_code in CONSTANTS.OPEN_ORDER_STATUSES:
            return OrderState.OPEN
        return None

    # ------------------------------------------------------------------
    # Trade fills
    # ------------------------------------------------------------------

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates: List[TradeUpdate] = []
        try:
            exchange_order_id = await order.get_exchange_order_id()
            ex_symbol = await self.exchange_symbol_associated_to_pair(
                trading_pair=order.trading_pair
            )
            fills = await self._api_get(
                path_url=CONSTANTS.TRADE_HISTORY_PATH_URL,
                params={"symbol": ex_symbol, "orderID": exchange_order_id},
                is_auth_required=True,
                limit_id=CONSTANTS.TRADE_HISTORY_PATH_URL,
            )
            for fill in (fills if isinstance(fills, list) else [fills]):
                trade_updates.append(
                    self._create_trade_update_from_fill(fill, order)
                )
        except asyncio.TimeoutError:
            raise IOError(
                f"Skipped trade update for {order.client_order_id} "
                "- waiting for exchange order id."
            )
        return trade_updates

    def _create_trade_update_from_fill(
        self, fill: Dict[str, Any], order: InFlightOrder
    ) -> TradeUpdate:
        fee_asset = order.quote_asset
        fill_contracts = int(fill.get("size", 0))
        fill_amount = self._contracts_to_amount(order.trading_pair, fill_contracts)
        fill_price = Decimal(str(fill.get("price", "0")))

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=fill.get("orderAction", "OPEN"),
            percent_token=fee_asset,
            flat_fees=[TokenAmount(
                amount=Decimal(str(fill.get("feeAmount", "0"))),
                token=fee_asset,
            )],
        )

        # LMEX timestamp is in milliseconds
        raw_ts = fill.get("timestamp", 0)
        try:
            fill_ts = float(raw_ts) * 1e-3
        except (TypeError, ValueError):
            fill_ts = self.current_timestamp

        return TradeUpdate(
            trade_id=str(fill.get("tradeId", fill.get("serialId", ""))),
            client_order_id=order.client_order_id,
            exchange_order_id=str(fill.get("orderID", order.exchange_order_id or "")),
            trading_pair=order.trading_pair,
            fee=fee,
            fill_base_amount=abs(fill_amount),
            fill_quote_amount=abs(fill_amount * fill_price),
            fill_price=fill_price,
            fill_timestamp=fill_ts,
        )

    # ------------------------------------------------------------------
    # Funding fee
    # ------------------------------------------------------------------

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        """
        Fetch the most recent funding payment for *trading_pair*.

        Returns (timestamp, funding_rate, payment_amount).
        Returns (0, Decimal("0"), Decimal("0")) if no payment found.
        """
        try:
            ex_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            response = await self._api_request(
                method=RESTMethod.GET,
                path_url=CONSTANTS.FUNDING_HISTORY_PATH_URL,
                data={"symbol": ex_symbol, "count": 1},
                is_auth_required=False,
                limit_id=CONSTANTS.FUNDING_HISTORY_PATH_URL,
            )
            # Response: {symbol: [{time, rate, symbol}]}
            entries = response.get(ex_symbol, [])
            if not entries:
                return 0, Decimal("0"), Decimal("0")

            latest = entries[0]
            funding_rate = Decimal(str(latest.get("rate", "0")))
            # LMEX funding history does not return a payment amount directly;
            # payment = rate * mark_price * position_size would require more data.
            # Return 0 payment and let the framework handle it.
            raw_ts = latest.get("time", 0)
            try:
                timestamp = float(raw_ts) * 1e-3 if raw_ts > 1e10 else float(raw_ts)
            except (TypeError, ValueError):
                timestamp = 0.0

            return timestamp, funding_rate, Decimal("0")

        except Exception:
            self.logger().debug(
                f"Error fetching last fee payment for {trading_pair}", exc_info=True
            )
            return 0, Decimal("0"), Decimal("0")

    # ------------------------------------------------------------------
    # Leverage
    # ------------------------------------------------------------------

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        try:
            ex_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            resp = await self._api_post(
                path_url=CONSTANTS.LEVERAGE_PATH_URL,
                data={
                    "symbol": ex_symbol,
                    "leverage": leverage,
                    "marginMode": "CROSS",
                },
                is_auth_required=True,
                limit_id=CONSTANTS.LEVERAGE_PATH_URL,
            )
            if isinstance(resp, list):
                resp = resp[0]
            returned_leverage = int(resp.get("leverage", 0))
            if returned_leverage != leverage:
                return False, f"Exchange returned leverage {returned_leverage}, expected {leverage}"
            return True, ""
        except Exception as e:
            return False, str(e)

    # ------------------------------------------------------------------
    # Position mode
    # ------------------------------------------------------------------

    async def _get_position_mode(self) -> Optional[PositionMode]:
        # LMEX Perpetual currently supports ONE_WAY only
        return PositionMode.ONEWAY

    async def _execute_set_position_mode_for_pairs(
        self, mode: PositionMode, trading_pairs: List[str]
    ) -> Tuple[bool, List[str], str]:
        if mode is not PositionMode.ONEWAY:
            return False, [], "LMEX Perpetual only supports ONEWAY position mode."
        return True, trading_pairs, ""

    # ------------------------------------------------------------------
    # Trading pair symbol mapping
    # ------------------------------------------------------------------

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Any):
        """
        Build the exchange_symbol <-> hummingbot_trading_pair bidict.

        LMEX perpetual format: ``BTC-PERP``   → Hummingbot: ``BTC-USDT``
        LMEX quarterly format: ``BTC-20250328`` → Hummingbot: ``BTC-USDT`` (skipped for now)
        """
        mapping: bidict = bidict()
        items = exchange_info if isinstance(exchange_info, list) else [exchange_info]

        for item in items:
            ex_symbol: str = item.get("symbol", "")
            if not ex_symbol:
                continue
            if not item.get("active", True):
                continue
            # Handle perpetuals (BTC-PERP → BTC-USDT)
            if ex_symbol.endswith("-PERP"):
                base = ex_symbol.split("-")[0]
                hb_pair = f"{base}-USDT"
                if hb_pair not in mapping.inverse:
                    mapping[ex_symbol] = hb_pair
                continue
            # Skip quarterly / other formats for now
        self._set_trading_pair_symbol_map(mapping)

    # ------------------------------------------------------------------
    # Last traded price (for order book data source delegation)
    # ------------------------------------------------------------------

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        ex_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        response = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.MARKET_SUMMARY_PATH_URL,
            params={"symbol": ex_symbol},
        )
        items = response if isinstance(response, list) else [response]
        for item in items:
            if item.get("symbol") == ex_symbol:
                return float(item.get("last", "0"))
        return 0.0

    # ------------------------------------------------------------------
    # Fee estimation
    # ------------------------------------------------------------------

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        is_maker = is_maker or False
        return build_trade_fee(
            self.name,
            is_maker,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )

    async def _update_trading_fees(self):
        pass  # Not available via REST on LMEX; use DEFAULT_FEES from utils

    # ------------------------------------------------------------------
    # User stream event listener
    # ------------------------------------------------------------------

    async def _user_stream_event_listener(self):
        """
        Processes messages put into the user-stream queue by
        ``LmexPerpetualUserStreamDataSource``.

        Each message is a dict with keys:
            ``channel``: one of the *_EVENT_KEY constants
            ``data``:    raw API response (list or dict)
        """
        async for event_message in self._iter_user_event_queue():
            try:
                if isinstance(event_message, asyncio.CancelledError):
                    raise asyncio.CancelledError
                if not isinstance(event_message, dict):
                    raise Exception(event_message)

                channel: str = event_message.get("channel", "")
                data = event_message.get("data", [])

                if channel == WALLET_EVENT_KEY:
                    self._process_balance_message(data)

                elif channel == ORDERS_EVENT_KEY:
                    items = data if isinstance(data, list) else [data]
                    for order_msg in items:
                        self._process_order_message(order_msg)

                elif channel == TRADES_EVENT_KEY:
                    items = data if isinstance(data, list) else [data]
                    for trade_msg in items:
                        self._process_trade_message(trade_msg)

                elif channel == POSITIONS_EVENT_KEY:
                    items = data if isinstance(data, list) else [data]
                    for pos_msg in items:
                        await self._process_position_data(pos_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True
                )
                await self._sleep(5.0)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates the in-flight order tracker from an open-orders REST snapshot entry.
        """
        # LMEX open_orders entries use 'clOrderId' as client order id
        client_order_id = str(order_msg.get("clOrderId", order_msg.get("clOrderID", "")))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if not tracked_order:
            return

        order_update = self._create_order_update_from_data(order_msg, tracked_order)
        self._order_tracker.process_order_update(order_update=order_update)

    def _process_trade_message(self, trade_msg: Dict[str, Any]):
        """
        Updates in-flight order and fires fill events from a trade history entry.
        """
        client_order_id = str(trade_msg.get("clOrderId", trade_msg.get("clOrderID", "")))
        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
        if not tracked_order:
            return

        trade_update = self._create_trade_update_from_fill(trade_msg, tracked_order)
        self._order_tracker.process_trade_update(trade_update)
