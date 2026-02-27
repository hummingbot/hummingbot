import asyncio
import hashlib
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_api_order_book_data_source import (
    GrvtPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GrvtPerpetualAuth, price_to_int, size_to_int
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_user_stream_data_source import (
    GrvtPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_utils import (
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
    get_new_client_order_id,
    get_order_type_and_tif,
    parse_trading_rule_from_instrument,
)
from hummingbot.connector.derivative.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger

s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal("0")


class GrvtPerpetualDerivative(PerpetualDerivativePyBase):
    """
    GRVT Perpetual Exchange connector for Hummingbot.
    GRVT is a hybrid DEX/CEX perpetual futures exchange built on ZKsync.
    Orders are signed with EIP-712 and submitted via REST; real-time updates via WebSocket.
    """

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger(__name__)
        return cls._logger

    def __init__(
        self,
        grvt_perpetual_api_key: str = "",
        grvt_perpetual_api_secret: str = "",
        grvt_perpetual_sub_account_id: str = "",
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._api_key = grvt_perpetual_api_key
        self._api_secret = grvt_perpetual_api_secret
        self._sub_account_id = grvt_perpetual_sub_account_id
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._last_trade_history_timestamp: Optional[float] = None
        # instrument hash map: exchange symbol -> instrument_hash (uint256 asset ID)
        self._instrument_hash_map: Dict[str, int] = {}
        # base decimals per instrument for size conversion
        self._instrument_base_decimals: Dict[str, int] = {}
        super().__init__()

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[GrvtPerpetualAuth]:
        if self._trading_required:
            return GrvtPerpetualAuth(
                api_key=self._api_key,
                api_secret=self._api_secret,
                sub_account_id=self._sub_account_id,
                domain=self._domain,
            )
        return None

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> Optional[int]:
        return None

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.GET_ALL_INSTRUMENTS_PATH

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.GET_ALL_INSTRUMENTS_PATH

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.GET_MINI_TICKER_PATH

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def funding_fee_poll_interval(self) -> int:
        return CONSTANTS.FUNDING_RATE_UPDATE_INTERVAL_SECOND

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.HEDGE]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        rule: TradingRule = self._trading_rules[trading_pair]
        return rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        rule: TradingRule = self._trading_rules[trading_pair]
        return rule.sell_order_collateral_token

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return "not found" in str(status_update_exception).lower()

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return "not found" in str(cancelation_exception).lower()

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth,
        )

    def _create_order_book_data_source(self) -> PerpetualAPIOrderBookDataSource:
        return GrvtPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return GrvtPerpetualUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    async def _make_network_check_request(self):
        await self._api_get(
            path_url=self.check_network_request_path,
            params={"instrument": "BTC_USDT_Perp"},
            is_auth_required=False,
        )

    async def _make_trading_rules_request(self) -> Any:
        return await self._api_get(
            path_url=self.trading_rules_request_path,
            is_auth_required=False,
        )

    async def _make_trading_pairs_request(self) -> Any:
        return await self._api_get(
            path_url=self.trading_pairs_request_path,
            is_auth_required=False,
        )

    async def _format_trading_rules(self, exchange_info_dict: Any) -> List[TradingRule]:
        rules = []
        instruments = exchange_info_dict.get("instruments", [])
        for inst in instruments:
            if not web_utils.is_exchange_information_valid(inst):
                continue
            try:
                parsed = parse_trading_rule_from_instrument(inst)
                rule = TradingRule(
                    trading_pair=parsed["trading_pair"],
                    min_order_size=parsed["min_order_size"],
                    max_order_size=parsed["max_order_size"],
                    min_price_increment=parsed["min_price_increment"],
                    min_base_amount_increment=parsed["min_base_amount_increment"],
                    min_notional_size=parsed["min_notional_size"],
                    buy_order_collateral_token=parsed["buy_order_collateral_token"],
                    sell_order_collateral_token=parsed["sell_order_collateral_token"],
                )
                rules.append(rule)
            except Exception:
                self.logger().exception(f"Error parsing trading rule for instrument: {inst}")
        return rules

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Any):
        mapping = bidict()
        instruments = exchange_info.get("instruments", [])
        for inst in instruments:
            if not web_utils.is_exchange_information_valid(inst):
                continue
            ex_symbol = inst.get("instrument", "")
            hb_pair = convert_from_exchange_trading_pair(ex_symbol)
            if ex_symbol and hb_pair:
                mapping[ex_symbol] = hb_pair
                # Store instrument hash and base decimals for order signing
                if "instrumentHash" in inst:
                    self._instrument_hash_map[ex_symbol] = int(inst["instrumentHash"], 16)
                self._instrument_base_decimals[ex_symbol] = inst.get("baseDecimals", 9)
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        ex_pair = convert_to_exchange_trading_pair(trading_pair)
        resp = await self._api_get(
            path_url=CONSTANTS.GET_MINI_TICKER_PATH,
            params={"instrument": ex_pair},
            is_auth_required=False,
        )
        tickers = resp.get("miniTickers", [])
        if tickers:
            return float(tickers[0].get("lastPrice", "0"))
        return 0.0

    async def _update_balances(self):
        resp = await self._api_get(
            path_url=CONSTANTS.GET_ACCOUNT_SUMMARY_PATH,
            params={"sub_account_id": self._sub_account_id},
            is_auth_required=True,
        )
        summary = resp.get("summary", {})
        quote = CONSTANTS.CURRENCY
        total = Decimal(str(summary.get("totalEquity", "0")))
        available = Decimal(str(summary.get("availableBalance", "0")))
        self._account_balances[quote] = total
        self._account_available_balances[quote] = available

    async def _update_positions(self):
        resp = await self._api_get(
            path_url=CONSTANTS.GET_POSITIONS_PATH,
            params={"sub_account_id": self._sub_account_id},
            is_auth_required=True,
        )
        positions = resp.get("positions", [])
        seen = set()
        for pos in positions:
            ex_symbol = pos.get("instrument", "")
            if ex_symbol in seen:
                continue
            seen.add(ex_symbol)
            try:
                hb_pair = await self.trading_pair_associated_to_exchange_symbol(ex_symbol)
            except KeyError:
                continue
            size = Decimal(str(pos.get("size", "0")))
            side = PositionSide.LONG if size > 0 else PositionSide.SHORT
            pos_key = self._perpetual_trading.position_key(hb_pair, side)
            if size != s_decimal_0:
                from hummingbot.core.event.events import Position
                _pos = Position(
                    trading_pair=hb_pair,
                    position_side=side,
                    unrealized_pnl=Decimal(str(pos.get("unrealizedPnl", "0"))),
                    entry_price=Decimal(str(pos.get("entryPrice", "0"))),
                    amount=abs(size),
                    leverage=Decimal(str(pos.get("leverage", "1"))),
                )
                self._perpetual_trading.set_position(pos_key, _pos)
            else:
                self._perpetual_trading.remove_position(pos_key)
        if not positions:
            for key in list(self._perpetual_trading.account_positions.keys()):
                self._perpetual_trading.remove_position(key)

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
        is_maker_order = is_maker or (order_type == OrderType.LIMIT_MAKER)
        return DeductedFromReturnsTradeFee(
            percent=self.estimate_fee_pct(is_maker_order)
        )

    def buy(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length,
        )
        if order_type is OrderType.MARKET:
            ref = self.get_mid_price(trading_pair) if price.is_nan() else price
            price = self.quantize_order_price(trading_pair, ref * Decimal("1.05"))
        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs,
        ))
        return order_id

    def sell(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length,
        )
        if order_type is OrderType.MARKET:
            ref = self.get_mid_price(trading_pair) if price.is_nan() else price
            price = self.quantize_order_price(trading_pair, ref * Decimal("0.95"))
        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs,
        ))
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
        ex_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        is_market, tif = get_order_type_and_tif(order_type)
        is_buying = trade_type == TradeType.BUY
        reduce_only = position_action == PositionAction.CLOSE
        post_only = order_type == OrderType.LIMIT_MAKER

        base_decimals = self._instrument_base_decimals.get(ex_symbol, 9)
        asset_id = self._instrument_hash_map.get(ex_symbol, 0)

        price_int = price_to_int(price)
        size_int = size_to_int(amount, base_decimals)

        nonce = self._auth.get_next_nonce()
        expiration = int(time.time()) + 3600

        legs = [{
            "assetID": asset_id,
            "contractSize": size_int,
            "limitPrice": price_int,
            "isBuyingContract": is_buying,
        }]

        signature = self._auth.sign_order(
            sub_account_id=int(self._sub_account_id),
            is_market=is_market,
            time_in_force=tif,
            post_only=post_only,
            reduce_only=reduce_only,
            legs=legs,
            nonce=nonce,
            expiration=expiration,
        )

        payload = {
            "subAccountID": int(self._sub_account_id),
            "isMarket": is_market,
            "timeInForce": tif,
            "postOnly": post_only,
            "reduceOnly": reduce_only,
            "legs": [{
                "instrument": ex_symbol,
                "isBuyingBase": is_buying,
                "limitPrice": str(price),
                "size": str(amount),
            }],
            "signature": signature,
        }

        resp = await self._api_post(
            path_url=CONSTANTS.CREATE_ORDER_PATH,
            data=payload,
            is_auth_required=True,
        )
        if resp.get("code", 0) != 0:
            raise IOError(f"Error placing order {order_id}: {resp.get('message', resp)}")

        order_data = resp.get("order", {})
        exchange_order_id = str(order_data.get("orderID", order_id))
        return exchange_order_id, self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        ex_symbol = await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair)
        exchange_order_id = tracked_order.exchange_order_id or order_id
        payload = {
            "subAccountID": int(self._sub_account_id),
            "orderID": exchange_order_id,
        }
        resp = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_PATH,
            data=payload,
            is_auth_required=True,
        )
        if resp.get("code", 0) != 0:
            raise IOError(f"Error cancelling order {order_id}: {resp.get('message', resp)}")
        return True

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        exchange_order_id = tracked_order.exchange_order_id
        if not exchange_order_id:
            exchange_order_id = await tracked_order.get_exchange_order_id()

        resp = await self._api_get(
            path_url=CONSTANTS.GET_ORDER_PATH,
            params={
                "sub_account_id": self._sub_account_id,
                "order_id": exchange_order_id,
            },
            is_auth_required=True,
        )
        order_data = resp.get("order", {})
        raw_status = order_data.get("status", "OPEN")
        new_state = CONSTANTS.ORDER_STATE.get(raw_status.upper(), OrderState.OPEN)
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=int(order_data.get("updatedTime", time.time() * 1e9)) * 1e-9,
            new_state=new_state,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(order_data.get("orderID", exchange_order_id)),
        )

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        if not order.exchange_order_id:
            return trade_updates
        resp = await self._api_get(
            path_url=CONSTANTS.GET_FILL_HISTORY_PATH,
            params={
                "sub_account_id": self._sub_account_id,
                "order_id": order.exchange_order_id,
            },
            is_auth_required=True,
        )
        fills = resp.get("fills", [])
        for fill in fills:
            fee_amount = Decimal(str(fill.get("fee", "0")))
            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=PositionAction.OPEN,
                percent_token=order.quote_asset,
                flat_fees=[TokenAmount(amount=fee_amount, token=order.quote_asset)],
            )
            fill_price = Decimal(str(fill.get("price", "0")))
            fill_size = Decimal(str(fill.get("size", "0")))
            trade_updates.append(TradeUpdate(
                trade_id=str(fill.get("fillID", "")),
                client_order_id=order.client_order_id,
                exchange_order_id=str(fill.get("orderID", order.exchange_order_id)),
                trading_pair=order.trading_pair,
                fill_timestamp=int(fill.get("eventTime", time.time() * 1e9)) * 1e-9,
                fill_price=fill_price,
                fill_base_amount=fill_size,
                fill_quote_amount=fill_price * fill_size,
                fee=fee,
            ))
        return trade_updates

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 second.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from GRVT. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _user_stream_event_listener(self):
        async for event in self._iter_user_event_queue():
            try:
                channel = event.get("channel", "")
                data = event.get("feed", event.get("data", {}))
                if channel == CONSTANTS.WS_ORDER:
                    self._process_order_message(data)
                elif channel == CONSTANTS.WS_FILL:
                    fills = data if isinstance(data, list) else [data]
                    for fill in fills:
                        await self._process_trade_message(fill)
                elif channel == CONSTANTS.WS_POSITION:
                    await self._update_positions()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener.", exc_info=True)
                await self._sleep(5.0)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        client_order_id = str(order_msg.get("clientOrderID", ""))
        tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
        if not tracked_order:
            return
        raw_status = order_msg.get("status", "OPEN")
        new_state = CONSTANTS.ORDER_STATE.get(raw_status.upper(), OrderState.OPEN)
        exchange_order_id = str(order_msg.get("orderID", ""))
        if exchange_order_id:
            tracked_order.update_exchange_order_id(exchange_order_id)
        order_update = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=int(order_msg.get("updatedTime", time.time() * 1e9)) * 1e-9,
            new_state=new_state,
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
        )
        self._order_tracker.process_order_update(order_update)

    async def _process_trade_message(self, fill: Dict[str, Any]):
        exchange_order_id = str(fill.get("orderID", ""))
        tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)
        if tracked_order is None:
            return
        fee_amount = Decimal(str(fill.get("fee", "0")))
        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=PositionAction.OPEN,
            percent_token=tracked_order.quote_asset,
            flat_fees=[TokenAmount(amount=fee_amount, token=tracked_order.quote_asset)],
        )
        fill_price = Decimal(str(fill.get("price", "0")))
        fill_size = Decimal(str(fill.get("size", "0")))
        trade_update = TradeUpdate(
            trade_id=str(fill.get("fillID", "")),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=int(fill.get("eventTime", time.time() * 1e9)) * 1e-9,
            fill_price=fill_price,
            fill_base_amount=fill_size,
            fill_quote_amount=fill_price * fill_size,
            fee=fee,
        )
        self._order_tracker.process_trade_update(trade_update)

    async def _get_position_mode(self) -> Optional[PositionMode]:
        return PositionMode.HEDGE

    async def _trading_pair_position_mode_set(
        self, mode: PositionMode, trading_pair: str
    ) -> Tuple[bool, str]:
        if mode != PositionMode.HEDGE:
            return False, "GRVT only supports HEDGE position mode."
        return True, ""

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        # GRVT does not expose a standalone set-leverage endpoint in v1;
        # leverage is embedded in the order margin type. Return success silently.
        return True, ""

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        ex_symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        start_time = int(((time.time() // 3600) - 1) * 3600 * 1e9)
        try:
            resp = await self._api_get(
                path_url=CONSTANTS.GET_FUNDING_PATH,
                params={
                    "sub_account_id": self._sub_account_id,
                    "instrument": ex_symbol,
                    "start_time": start_time,
                },
                is_auth_required=True,
            )
            payments = resp.get("fundingPayments", [])
            if not payments:
                return 0, Decimal("-1"), Decimal("-1")
            latest = payments[0]
            ts = int(latest.get("eventTime", 0)) * 1e-9
            rate = Decimal(str(latest.get("fundingRate", "0")))
            payment = Decimal(str(latest.get("payment", "0")))
            if payment == s_decimal_0:
                return 0, Decimal("-1"), Decimal("-1")
            return int(ts), rate, payment
        except Exception:
            return 0, Decimal("-1"), Decimal("-1")

    async def _update_trading_fees(self):
        pass  # GRVT fees are fixed; handled in _get_fee

    async def _status_polling_loop_fetch_updates(self):
        await self._update_order_status()
        await self._update_balances()
        await self._update_positions()
