import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.grvt_perpetual import (
    grvt_perpetual_constants as CONSTANTS,
    grvt_perpetual_utils as utils,
    grvt_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_api_order_book_data_source import (
    GrvtPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_api_user_stream_data_source import (
    GrvtPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GrvtPerpetualAuth
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_numeric_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import AccountEvent, PositionModeChangeEvent
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class GrvtPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils
    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    def __init__(
        self,
        grvt_perpetual_api_key: str = None,
        grvt_perpetual_private_key: str = None,
        grvt_perpetual_trading_account_id: str = None,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
    ):
        self.api_key = grvt_perpetual_api_key
        self.private_key = grvt_perpetual_private_key
        self.trading_account_id = grvt_perpetual_trading_account_id
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs or []
        self._position_mode = PositionMode.ONEWAY
        self._nonce_creator = NonceCreator.for_milliseconds()
        self._instrument_info_by_symbol: Dict[str, Dict[str, Any]] = {}
        self._leverage_by_trading_pair: Dict[str, Decimal] = {}
        self._symbol_map = bidict()
        self.real_time_balance_update = False
        super().__init__(balance_asset_limit=balance_asset_limit, rate_limits_share_pct=rate_limits_share_pct)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> GrvtPerpetualAuth:
        return GrvtPerpetualAuth(
            api_key=self.api_key,
            private_key=self.private_key,
            trading_account_id=self.trading_account_id,
            domain=self._domain,
        )

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return ""

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.INSTRUMENTS_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.INSTRUMENTS_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.INSTRUMENTS_PATH_URL

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
        return CONSTANTS.FUNDING_RATE_UPDATE_INTERVAL

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def supported_position_modes(self):
        return [PositionMode.ONEWAY]

    def buy(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        order_id = self._new_client_order_id()
        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
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
        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.SELL,
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            )
        )
        return order_id

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        return self._trading_rules[trading_pair].buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return self._trading_rules[trading_pair].sell_order_collateral_token

    async def _create_order(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        price: Optional[Decimal] = None,
        position_action: PositionAction = PositionAction.NIL,
        **kwargs,
    ):
        effective_position_action = await self._effective_position_action(
            trading_pair=trading_pair,
            trade_type=trade_type,
            amount=amount,
            position_action=position_action,
        )
        await super()._create_order(
            trade_type=trade_type,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            position_action=effective_position_action,
            **kwargs,
        )

    async def _make_network_check_request(self):
        await self._api_post(path_url=self.check_network_request_path, data={"kind": ["PERPETUAL"], "limit": 1})

    async def _make_trading_rules_request(self) -> Any:
        return await self._make_trading_pairs_request()

    async def _make_trading_pairs_request(self) -> Any:
        response = await self._api_post(
            path_url=self.trading_pairs_request_path,
            data={"kind": ["PERPETUAL"], "is_active": True, "limit": 1000},
        )
        return response.get("result", [])

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return GrvtPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return GrvtPerpetualAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
        position_action: PositionAction = PositionAction.NIL,
    ) -> TradeFeeBase:
        return build_trade_fee(
            self.name,
            is_maker=order_type in (OrderType.LIMIT, OrderType.LIMIT_MAKER) if is_maker is None else is_maker,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_FOUND_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_FOUND_MESSAGE in str(cancelation_exception)

    async def exchange_symbol_associated_to_pair(self, trading_pair: str) -> str:
        symbol_map = await self.trading_pair_symbol_map()
        return symbol_map.inverse[trading_pair]

    async def trading_pair_associated_to_exchange_symbol(self, symbol: str) -> str:
        symbol_map = await self.trading_pair_symbol_map()
        return symbol_map[symbol]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List[Dict[str, Any]]):
        mapping = bidict()
        info_by_symbol = {}
        for instrument_info in exchange_info:
            if utils.is_exchange_information_valid(instrument_info):
                exchange_symbol = instrument_info["instrument"]
                trading_pair = combine_to_hb_trading_pair(instrument_info["base"], instrument_info["quote"])
                mapping[exchange_symbol] = trading_pair
                info_by_symbol[exchange_symbol] = instrument_info
        self._symbol_map = mapping
        self._instrument_info_by_symbol = info_by_symbol
        self._set_trading_pair_symbol_map(mapping)

    async def _format_trading_rules(self, exchange_info_dict: List[Dict[str, Any]]) -> List[TradingRule]:
        trading_rules = []
        for instrument_info in exchange_info_dict:
            if not utils.is_exchange_information_valid(instrument_info):
                continue
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(instrument_info["instrument"])
                base_increment = max(
                    Decimal(str(instrument_info["min_size"])),
                    Decimal("1") / (Decimal("10") ** int(instrument_info["base_decimals"])),
                )
                trading_rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=Decimal(str(instrument_info["min_size"])),
                        max_order_size=Decimal(str(instrument_info["max_position_size"])),
                        min_price_increment=Decimal(str(instrument_info["tick_size"])),
                        min_base_amount_increment=base_increment,
                        min_notional_size=Decimal(str(instrument_info["min_notional"])),
                        buy_order_collateral_token=instrument_info["quote"],
                        sell_order_collateral_token=instrument_info["quote"],
                    )
                )
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {instrument_info}. Skipping.")
        return trading_rules

    async def _update_trading_fees(self):
        pass

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
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        instrument_info = self._instrument_info_by_symbol[exchange_symbol]
        payload = self._auth.get_order_payload(
            instrument=instrument_info,
            client_order_id=order_id,
            exchange_symbol=exchange_symbol,
            amount=amount,
            price=price,
            trade_type=trade_type,
            order_type=order_type,
            reduce_only=position_action == PositionAction.CLOSE,
        )
        response = await self._api_post(
            path_url=CONSTANTS.CREATE_ORDER_PATH_URL,
            data=payload,
            is_auth_required=True,
        )
        result = response.get("result")
        if result is None:
            raise IOError(f"GRVT create order failed: {response}")
        return str(result["order_id"]), self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        payload = {"sub_account_id": str(self.trading_account_id)}
        if self._is_active_exchange_order_id(tracked_order.exchange_order_id):
            payload["order_id"] = str(tracked_order.exchange_order_id)
        else:
            payload["client_order_id"] = tracked_order.client_order_id
        response = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_PATH_URL,
            data=payload,
            is_auth_required=True,
        )
        return bool(response.get("result", {}).get("ack"))

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(order.trading_pair)
        instrument_info = self._instrument_info_by_symbol[exchange_symbol]
        response = await self._api_post(
            path_url=CONSTANTS.FILL_HISTORY_PATH_URL,
            data={
                "sub_account_id": str(self.trading_account_id),
                "kind": ["PERPETUAL"],
                "base": [instrument_info["base"]],
                "quote": [instrument_info["quote"]],
                "limit": 1000,
            },
            is_auth_required=True,
        )
        fills = response.get("result", [])
        trade_updates = []
        for fill in fills:
            if (
                str(fill.get("client_order_id")) != order.client_order_id
                and str(fill.get("order_id")) != str(order.exchange_order_id)
            ):
                continue
            fee_token = fill.get("fee_currency") or self._instrument_info_by_symbol[exchange_symbol]["quote"]
            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=order.position,
                percent_token=fee_token,
                flat_fees=[TokenAmount(token=fee_token, amount=Decimal(str(fill["fee"])))],
            )
            fill_size = Decimal(str(fill["size"]))
            fill_price = Decimal(str(fill["price"]))
            trade_updates.append(
                TradeUpdate(
                    trade_id=str(fill["trade_id"]),
                    client_order_id=order.client_order_id,
                    exchange_order_id=str(fill["order_id"]),
                    trading_pair=order.trading_pair,
                    fee=fee,
                    fill_base_amount=fill_size,
                    fill_quote_amount=fill_size * fill_price,
                    fill_price=fill_price,
                    fill_timestamp=int(fill["event_time"]) * 1e-9,
                    is_taker=bool(fill.get("is_taker", True)),
                )
            )
        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        response = await self._api_post(
            path_url=CONSTANTS.ORDER_PATH_URL,
            data={
                "sub_account_id": str(self.trading_account_id),
                "client_order_id": tracked_order.client_order_id,
            },
            is_auth_required=True,
        )
        order_data = response.get("result")
        if order_data is None:
            raise IOError(f"Order not found for client_order_id={tracked_order.client_order_id}: {response}")
        return self._order_update_from_order_data(order_data=order_data, tracked_order=tracked_order)

    async def _update_balances(self):
        response = await self._api_post(
            path_url=CONSTANTS.ACCOUNT_SUMMARY_PATH_URL,
            data={"sub_account_id": str(self.trading_account_id)},
            is_auth_required=True,
        )
        account_summary = response.get("result", {})
        local_assets = set(self._account_balances.keys())
        remote_assets = set()
        available_balance = Decimal(str(account_summary.get("available_balance", "0")))
        settle_currency = account_summary.get("settle_currency")
        for spot_balance in account_summary.get("spot_balances", []):
            asset = spot_balance["currency"]
            total = Decimal(str(spot_balance["balance"]))
            free = available_balance if asset == settle_currency else total
            self._account_balances[asset] = total
            self._account_available_balances[asset] = free
            remote_assets.add(asset)
        for asset in local_assets.difference(remote_assets):
            self._account_balances.pop(asset, None)
            self._account_available_balances.pop(asset, None)

    async def _update_positions(self):
        response = await self._api_post(
            path_url=CONSTANTS.POSITIONS_PATH_URL,
            data={"sub_account_id": str(self.trading_account_id), "kind": ["PERPETUAL"]},
            is_auth_required=True,
        )
        remote_position_keys = set()
        for position_data in response.get("result", []):
            exchange_symbol = position_data["instrument"]
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(exchange_symbol)
            except KeyError:
                continue
            size = Decimal(str(position_data["size"]))
            side = PositionSide.SHORT if size < 0 else PositionSide.LONG
            pos_key = self._perpetual_trading.position_key(trading_pair, side)
            remote_position_keys.add(pos_key)
            if size == Decimal("0"):
                self._perpetual_trading.remove_position(pos_key)
                continue
            leverage = Decimal(str(position_data.get("leverage", self._leverage_by_trading_pair.get(trading_pair, 1))))
            position = Position(
                trading_pair=trading_pair,
                position_side=side,
                unrealized_pnl=Decimal(str(position_data["unrealized_pnl"])),
                entry_price=Decimal(str(position_data["entry_price"])),
                amount=size,
                leverage=leverage,
            )
            self._perpetual_trading.set_position(pos_key, position)
        for pos_key in list(self.account_positions.keys()):
            if pos_key not in remote_position_keys:
                self._perpetual_trading.remove_position(pos_key)

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        payment_response = await self._api_post(
            path_url=CONSTANTS.FUNDING_PAYMENT_HISTORY_PATH_URL,
            data={"sub_account_id": str(self.trading_account_id), "instrument": exchange_symbol, "limit": 1},
            is_auth_required=True,
        )
        payments = payment_response.get("result", [])
        if len(payments) == 0:
            return 0, Decimal("-1"), Decimal("-1")
        payment = payments[0]
        funding_response = await self._api_post(
            path_url=CONSTANTS.FUNDING_PATH_URL,
            data={"instrument": exchange_symbol, "end_time": payment["event_time"], "limit": 1},
        )
        funding_results = funding_response.get("result", [])
        funding_rate = Decimal(str(funding_results[0]["funding_rate"])) if funding_results else Decimal("-1")
        return int(payment["event_time"]) * 1e-9, funding_rate, Decimal(str(payment["amount"]))

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                stream = event_message.get("stream", "")
                feed = event_message.get("feed")
                if feed is None:
                    continue
                if stream == CONSTANTS.PRIVATE_WS_CHANNEL_FILL:
                    tracked_order = self._tracked_order_from_ids(
                        client_order_id=str(feed.get("client_order_id")),
                        exchange_order_id=str(feed.get("order_id")),
                    )
                    if tracked_order is None:
                        continue
                    exchange_symbol = await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair)
                    fee_token = feed.get("fee_currency") or self._instrument_info_by_symbol[exchange_symbol]["quote"]
                    fee = TradeFeeBase.new_perpetual_fee(
                        fee_schema=self.trade_fee_schema(),
                        position_action=tracked_order.position,
                        percent_token=fee_token,
                        flat_fees=[TokenAmount(token=fee_token, amount=Decimal(str(feed["fee"])))],
                    )
                    self._order_tracker.process_trade_update(
                        TradeUpdate(
                            trade_id=str(feed["trade_id"]),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=str(feed["order_id"]),
                            trading_pair=tracked_order.trading_pair,
                            fee=fee,
                            fill_base_amount=Decimal(str(feed["size"])),
                            fill_quote_amount=Decimal(str(feed["size"])) * Decimal(str(feed["price"])),
                            fill_price=Decimal(str(feed["price"])),
                            fill_timestamp=int(feed["event_time"]) * 1e-9,
                            is_taker=bool(feed.get("is_taker", True)),
                        )
                    )
                    safe_ensure_future(self._update_balances())
                    safe_ensure_future(self._update_positions())
                elif stream == CONSTANTS.PRIVATE_WS_CHANNEL_STATE:
                    tracked_order = self._tracked_order_from_ids(
                        client_order_id=str(feed.get("client_order_id")),
                        exchange_order_id=str(feed.get("order_id")),
                    )
                    if tracked_order is None:
                        continue
                    order_state = feed["order_state"]
                    self._order_tracker.process_order_update(
                        OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=int(order_state["update_time"]) * 1e-9,
                            new_state=self._grvt_order_state(order_state),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=str(feed["order_id"]),
                        )
                    )
                    safe_ensure_future(self._update_balances())
                    safe_ensure_future(self._update_positions())
                elif stream == CONSTANTS.PRIVATE_WS_CHANNEL_ORDER:
                    tracked_order = self._tracked_order_from_ids(
                        client_order_id=str(feed.get("metadata", {}).get("client_order_id")),
                        exchange_order_id=str(feed.get("order_id")),
                    )
                    if tracked_order is None:
                        continue
                    self._order_tracker.process_order_update(
                        self._order_update_from_order_data(order_data=feed, tracked_order=tracked_order)
                    )
                    safe_ensure_future(self._update_balances())
                    safe_ensure_future(self._update_positions())
                elif stream == CONSTANTS.PRIVATE_WS_CHANNEL_POSITION:
                    await self._process_position_stream_event(feed)
                    safe_ensure_future(self._update_balances())
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _process_position_stream_event(self, feed: Dict[str, Any]):
        exchange_symbol = feed["instrument"]
        if not self.trading_pair_symbol_map_ready():
            await self.trading_pair_symbol_map()
        if exchange_symbol not in self._symbol_map:
            return
        trading_pair = await self.trading_pair_associated_to_exchange_symbol(exchange_symbol)
        size = Decimal(str(feed["size"]))
        side = PositionSide.SHORT if size < 0 else PositionSide.LONG
        pos_key = self._perpetual_trading.position_key(trading_pair, side)
        if size == Decimal("0"):
            self._perpetual_trading.remove_position(pos_key)
            return
        leverage = Decimal(str(feed.get("leverage", self._leverage_by_trading_pair.get(trading_pair, 1))))
        self._perpetual_trading.set_position(
            pos_key,
            Position(
                trading_pair=trading_pair,
                position_side=side,
                unrealized_pnl=Decimal(str(feed["unrealized_pnl"])),
                entry_price=Decimal(str(feed["entry_price"])),
                amount=size,
                leverage=leverage,
            ),
        )

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        if mode != PositionMode.ONEWAY:
            error_msg = "GRVT only supports the ONEWAY position mode."
            self.trigger_event(
                AccountEvent.PositionModeChangeFailed,
                PositionModeChangeEvent(self.current_timestamp, trading_pair, mode, error_msg),
            )
            return False, error_msg
        self._position_mode = PositionMode.ONEWAY
        self.trigger_event(
            AccountEvent.PositionModeChangeSucceeded,
            PositionModeChangeEvent(self.current_timestamp, trading_pair, mode),
        )
        return True, ""

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        response = await self._api_post(
            path_url=CONSTANTS.SET_INITIAL_LEVERAGE_PATH_URL,
            data={
                "sub_account_id": str(self.trading_account_id),
                "instrument": exchange_symbol,
                "leverage": str(leverage),
            },
            is_auth_required=True,
        )
        success = bool(response.get("success", response.get("result", {}).get("success")))
        if success:
            self._leverage_by_trading_pair[trading_pair] = Decimal(str(leverage))
            return True, ""
        return False, f"Failed to set leverage for {trading_pair}: {response}"

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        response = await self._api_post(path_url=CONSTANTS.TICKER_PATH_URL, data={"instrument": exchange_symbol})
        return float(Decimal(str(response["result"]["last_price"])))

    def _new_client_order_id(self) -> str:
        raw_client_order_id = get_new_numeric_client_order_id(self._nonce_creator, max_id_bit_count=63)
        return str(raw_client_order_id | CONSTANTS.CLIENT_ORDER_ID_HIGH_BIT)

    async def _effective_position_action(
        self,
        trading_pair: str,
        trade_type: TradeType,
        amount: Decimal,
        position_action: PositionAction,
    ) -> PositionAction:
        if position_action != PositionAction.OPEN or self._position_mode != PositionMode.ONEWAY:
            return position_action
        current_position = self._active_position_for_trading_pair(trading_pair)
        if current_position is None:
            try:
                await self._update_positions()
            except Exception:
                self.logger().warning(
                    f"Failed to refresh positions before classifying {trade_type.name} {amount} {trading_pair}.",
                    exc_info=True,
                )
            current_position = self._active_position_for_trading_pair(trading_pair)
        if current_position is None:
            return position_action
        current_trade_side = TradeType.BUY if current_position.amount > 0 else TradeType.SELL
        if current_trade_side == trade_type:
            return position_action
        return PositionAction.CLOSE

    def _active_position_for_trading_pair(self, trading_pair: str) -> Optional[Position]:
        position = self.account_positions.get(trading_pair)
        if position is not None and position.amount != Decimal("0"):
            return position
        return None

    def _is_reduce_only_position_absent_error(self, exception: Exception) -> bool:
        return "Reduce only order with no position" in str(exception)

    def _on_order_failure(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Optional[Decimal],
        exception: Exception,
        **kwargs,
    ):
        position_action = kwargs.get("position_action")

        if position_action == PositionAction.CLOSE and self._is_reduce_only_position_absent_error(exception):
            self.logger().info(f"Treating rejected reduce-only close order {order_id} as canceled for {trading_pair}: {exception}")
            self._order_tracker.process_order_update(
                OrderUpdate(
                    trading_pair=trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=OrderState.CANCELED,
                    client_order_id=order_id,
                    misc_updates={
                        "error_message": str(exception),
                        "error_type": exception.__class__.__name__,
                    },
                )
            )
            safe_ensure_future(self._update_positions())
            safe_ensure_future(self._update_balances())
            return

        super()._on_order_failure(
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            trade_type=trade_type,
            order_type=order_type,
            price=price,
            exception=exception,
            **kwargs,
        )

    @staticmethod
    def _is_active_exchange_order_id(exchange_order_id: Optional[str]) -> bool:
        return exchange_order_id not in (None, "", "0x00", "0x0", "0")

    def _tracked_order_from_ids(self, client_order_id: Optional[str], exchange_order_id: Optional[str]) -> Optional[InFlightOrder]:
        tracked_order = None
        if client_order_id:
            tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id) or self._order_tracker.all_updatable_orders.get(client_order_id)
        if tracked_order is None and self._is_active_exchange_order_id(exchange_order_id):
            for order in self._order_tracker.all_fillable_orders.values():
                if str(order.exchange_order_id) == str(exchange_order_id):
                    tracked_order = order
                    break
        return tracked_order

    def _order_update_from_order_data(self, order_data: Dict[str, Any], tracked_order: InFlightOrder) -> OrderUpdate:
        state = order_data["state"]
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=int(state["update_time"]) * 1e-9,
            new_state=self._grvt_order_state(state),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(order_data["order_id"]),
        )

    def _grvt_order_state(self, state_data: Dict[str, Any]) -> OrderState:
        status = state_data["status"]
        if status == "OPEN":
            traded = Decimal(str((state_data.get("traded_size") or ["0"])[0]))
            return OrderState.PARTIALLY_FILLED if traded > 0 else OrderState.OPEN
        return CONSTANTS.ORDER_STATE[status]
