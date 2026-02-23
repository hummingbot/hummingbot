import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_api_order_book_data_source import (
    GRVTPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GRVTPerpetualAuth
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_user_stream_data_source import (
    GRVTPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_web_utils as web_utils
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource


PRICE_MULTIPLIER = 1_000_000_000


@dataclass
class _InstrumentInfo:
    instrument: str
    instrument_hash: str
    base: str
    quote: str
    base_decimals: int
    tick_size: Decimal
    min_size: Decimal


class GRVTPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils

    def __init__(
        self,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        grvt_perpetual_api_key: str = "",
        grvt_perpetual_api_secret: str = "",
        grvt_perpetual_sub_account_id: str = "",
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs or []

        self.grvt_perpetual_api_key = grvt_perpetual_api_key
        self.grvt_perpetual_api_secret = grvt_perpetual_api_secret
        self.grvt_perpetual_sub_account_id = grvt_perpetual_sub_account_id

        self._auth = GRVTPerpetualAuth(
            api_key=grvt_perpetual_api_key,
            api_secret=grvt_perpetual_api_secret,
            sub_account_id=grvt_perpetual_sub_account_id,
            domain=domain,
        )

        # Instrument cache
        self._instrument_by_exchange_symbol: Dict[str, _InstrumentInfo] = {}
        self._exchange_symbol_by_trading_pair: Dict[str, str] = {}

        super().__init__(balance_asset_limit=balance_asset_limit, rate_limits_share_pct=rate_limits_share_pct)

    def _create_web_assistants_factory(self):
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth,
        )

    async def _update_trading_fees(self):
        # No dedicated fee endpoint integrated yet.
        return

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> GRVTPerpetualAuth:
        return self._auth

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
        return "HBOT"

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.MARK_PRICE_URL

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]

    def supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        return self.quote_asset(trading_pair)

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        return self.quote_asset(trading_pair)

    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    def is_trading_required(self) -> bool:
        return self._trading_required

    def funding_fee_poll_interval(self) -> int:
        return 120

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return GRVTPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return GRVTPerpetualUserStreamDataSource(
            auth=self._auth,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def _ensure_instruments_loaded(self):
        if self._instrument_by_exchange_symbol:
            return
        exchange_info = await self._make_trading_rules_request()
        await self._format_trading_rules(exchange_info)
        # _update_trading_rules normally calls _initialize_trading_pair_symbols_from_exchange_info.
        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        instruments = exchange_info.get("result", [])
        for instrument in instruments:
            instrument_name = instrument.get("instrument")
            base = instrument.get("base")
            quote = instrument.get("quote")
            if not instrument_name or not base or not quote:
                continue
            hb_pair = combine_to_hb_trading_pair(base, quote)
            if hb_pair in mapping.inverse:
                # If duplicates exist, just skip; Hummingbot will log in other connectors,
                # but GRVT instrument names should be unique.
                continue
            mapping[instrument_name] = hb_pair
        self._set_trading_pair_symbol_map(mapping)

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        cancel_req: Dict[str, Any] = {
            "sub_account_id": str(self.grvt_perpetual_sub_account_id),
        }
        if tracked_order.exchange_order_id:
            cancel_req["order_id"] = tracked_order.exchange_order_id
        else:
            cancel_req["client_order_id"] = tracked_order.client_order_id
            cancel_req["time_to_live_ms"] = "0"

        return await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_URL,
            data=cancel_req,
            is_auth_required=True,
            limit_id=CONSTANTS.CANCEL_ORDER_URL,
        )

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
        await self._ensure_instruments_loaded()

        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        instrument_info = self._instrument_by_exchange_symbol.get(exchange_symbol)
        if instrument_info is None:
            raise ValueError(f"Instrument info not found for symbol {exchange_symbol}")

        nonce = int(self.current_timestamp * 1e3) % (2**32)
        expiration_ns = int(self.current_timestamp * 1e9) + 60_000_000_000  # 60s

        size_int = int(amount * (Decimal(10) ** instrument_info.base_decimals))
        price_int = int(price * Decimal(PRICE_MULTIPLIER)) if order_type == OrderType.LIMIT else 0

        # EIP-712 signable message uses different field casing and int-scaled fields
        signable_message_data: Dict[str, Any] = {
            "subAccountID": int(self.grvt_perpetual_sub_account_id),
            "isMarket": order_type == OrderType.MARKET,
            "timeInForce": 1 if order_type == OrderType.LIMIT else 3,  # GTT=1, IOC=3 (per sdk SignTimeInForce)
            "postOnly": bool(kwargs.get("post_only", False)),
            "reduceOnly": position_action == PositionAction.CLOSE,
            "legs": [
                {
                    "assetID": int(instrument_info.instrument_hash, 16),
                    "contractSize": size_int,
                    "limitPrice": price_int,
                    "isBuyingContract": trade_type == TradeType.BUY,
                }
            ],
            "nonce": nonce,
            "expiration": expiration_ns,
        }
        sig = self._auth.sign_order_payload(signable_message_data)

        # REST request uses official schema: ApiCreateOrderRequest{order: Order}
        order_payload: Dict[str, Any] = {
            "sub_account_id": str(self.grvt_perpetual_sub_account_id),
            "time_in_force": "GOOD_TILL_TIME" if order_type == OrderType.LIMIT else "IMMEDIATE_OR_CANCEL",
            "legs": [
                {
                    "instrument": instrument_info.instrument,
                    "size": str(amount),
                    "is_buying_asset": trade_type == TradeType.BUY,
                    "limit_price": str(price) if order_type == OrderType.LIMIT else None,
                }
            ],
            "signature": {
                "signer": sig["signer"],
                "r": sig["r"],
                "s": sig["s"],
                "v": sig["v"],
                "expiration": str(expiration_ns),
                "nonce": nonce,
            },
            "metadata": {
                "client_order_id": order_id,
            },
            "is_market": order_type == OrderType.MARKET,
            "post_only": bool(kwargs.get("post_only", False)),
            "reduce_only": position_action == PositionAction.CLOSE,
        }

        create_req = {"order": order_payload}

        resp = await self._api_post(
            path_url=CONSTANTS.CREATE_ORDER_URL,
            data=create_req,
            is_auth_required=True,
            limit_id=CONSTANTS.CREATE_ORDER_URL,
        )

        # SDK returns {result: {order_id: ...}} but be defensive
        result = resp.get("result", resp)
        exchange_order_id = result.get("order_id") or result.get("orderID") or result.get("id")
        if exchange_order_id is None:
            exchange_order_id = ""
        return str(exchange_order_id), self.current_timestamp

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = Decimal("0"),
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        # Placeholder fees until official fee endpoint is integrated
        is_maker = bool(is_maker) if is_maker is not None else order_type is OrderType.LIMIT
        fee_percent = Decimal("0.0001") if is_maker else Decimal("0.0005")
        return AddedToCostTradeFee(percent=fee_percent)

    async def _update_balances(self):
        resp = await self._api_post(
            path_url=CONSTANTS.ACCOUNT_SUMMARY_URL,
            data={"sub_account_id": str(self.grvt_perpetual_sub_account_id)},
            is_auth_required=True,
            limit_id=CONSTANTS.ACCOUNT_SUMMARY_URL,
        )
        result = resp.get("result", resp)
        self._account_available_balances.clear()
        self._account_balances.clear()
        for asset in result.get("assets", []):
            currency = asset.get("asset") or asset.get("currency")
            if currency is None:
                continue
            available = Decimal(str(asset.get("available", "0")))
            total = Decimal(str(asset.get("total", "0")))
            self._account_available_balances[currency] = available
            self._account_balances[currency] = total

    async def _update_positions(self):
        resp = await self._api_post(
            path_url=CONSTANTS.POSITIONS_URL,
            data={"sub_account_id": str(self.grvt_perpetual_sub_account_id)},
            is_auth_required=True,
            limit_id=CONSTANTS.POSITIONS_URL,
        )
        result = resp.get("result", resp)
        for pos in result.get("positions", []):
            symbol = pos.get("instrument")
            if not symbol:
                continue
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=symbol)
            size = Decimal(str(pos.get("size", "0")))
            if size == Decimal("0"):
                self._account_positions.pop(trading_pair, None)
                continue
            position_side = PositionSide.LONG if size > 0 else PositionSide.SHORT
            from hummingbot.connector.derivative.position import Position

            self._account_positions[trading_pair] = Position(
                trading_pair=trading_pair,
                position_side=position_side,
                unrealized_pnl=Decimal(str(pos.get("unrealized_pnl", pos.get("unrealizedPnl", "0")))),
                entry_price=Decimal(str(pos.get("entry_price", pos.get("entryPrice", "0")))),
                amount=abs(size),
                leverage=Decimal(str(pos.get("leverage", "1"))),
            )

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        instruments = exchange_info_dict.get("result", [])
        rules: List[TradingRule] = []

        for instrument in instruments:
            try:
                instrument_name = instrument["instrument"]
                base = instrument.get("base")
                quote = instrument.get("quote")
                instrument_hash = instrument.get("instrument_hash") or instrument.get("instrumentHash")
                base_decimals = instrument.get("base_decimals") or instrument.get("baseDecimals")

                tick_size = Decimal(str(instrument.get("tick_size") or instrument.get("tickSize") or "0"))
                min_size = Decimal(str(instrument.get("min_size") or instrument.get("minSize") or "0"))

                if instrument_hash is None or base_decimals is None or base is None or quote is None:
                    continue

                self._instrument_by_exchange_symbol[instrument_name] = _InstrumentInfo(
                    instrument=instrument_name,
                    instrument_hash=str(instrument_hash),
                    base=str(base),
                    quote=str(quote),
                    base_decimals=int(base_decimals),
                    tick_size=tick_size,
                    min_size=min_size,
                )

                trading_pair = combine_to_hb_trading_pair(str(base), str(quote))
                self._exchange_symbol_by_trading_pair[trading_pair] = instrument_name

                rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=min_size,
                        min_price_increment=tick_size,
                        min_base_amount_increment=min_size,
                        buy_order_collateral_token=str(quote),
                        sell_order_collateral_token=str(quote),
                    )
                )
            except Exception:
                self.logger().exception(f"Error parsing trading rule for instrument={instrument}")

        return rules

    async def _update_order_status(self):
        resp = await self._api_post(
            path_url=CONSTANTS.OPEN_ORDERS_URL,
            data={"sub_account_id": str(self.grvt_perpetual_sub_account_id)},
            is_auth_required=True,
            limit_id=CONSTANTS.OPEN_ORDERS_URL,
        )
        result = resp.get("result", resp)
        orders = result.get("result", result.get("orders", []))
        for order_info in orders:
            client_order_id = (
                order_info.get("metadata", {}) or {}
            ).get("client_order_id") or order_info.get("client_order_id") or order_info.get("clientOrderID")
            if not client_order_id:
                continue
            tracked_order = self.in_flight_orders.get(client_order_id)
            if tracked_order is None:
                continue
            status = order_info.get("state", {}).get("status") or order_info.get("status")
            new_state = CONSTANTS.ORDER_STATE.get(str(status), OrderState.OPEN)
            order_update = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=new_state,
                client_order_id=client_order_id,
                exchange_order_id=order_info.get("order_id") or order_info.get("orderID"),
            )
            self._order_tracker.process_order_update(order_update)

    async def _update_trade_history(self):
        pass

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        return []

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=tracked_order.current_state,
            client_order_id=tracked_order.client_order_id,
        )

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Error getting user event from queue. Retrying in 1s.")
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                channel = event_message.get("channel")
                data = event_message.get("data", {})
                if channel == "order":
                    for order_data in data:
                        client_order_id = order_data.get("client_order_id") or order_data.get("clientOrderID")
                        tracked_order = self.in_flight_orders.get(client_order_id)
                        if tracked_order:
                            status = order_data.get("status")
                            new_state = CONSTANTS.ORDER_STATE.get(str(status), OrderState.OPEN)
                            order_update = OrderUpdate(
                                trading_pair=tracked_order.trading_pair,
                                update_timestamp=float(order_data.get("time", 0)) * 1e-9,
                                new_state=new_state,
                                client_order_id=client_order_id,
                                exchange_order_id=order_data.get("order_id") or order_data.get("orderID"),
                            )
                            self._order_tracker.process_order_update(order_update)
                elif channel == "user_trade":
                    for trade_data in data:
                        client_order_id = trade_data.get("client_order_id") or trade_data.get("clientOrderID")
                        tracked_order = self.in_flight_orders.get(client_order_id)
                        if tracked_order:
                            fee = AddedToCostTradeFee(
                                flat_fees=[
                                    TokenAmount(
                                        token=tracked_order.quote_asset,
                                        amount=Decimal(str(trade_data.get("fee", "0"))),
                                    )
                                ]
                            )
                            fill_size = Decimal(str(trade_data.get("size")))
                            fill_price = Decimal(str(trade_data.get("price")))
                            trade_update = TradeUpdate(
                                trade_id=trade_data.get("id"),
                                client_order_id=client_order_id,
                                exchange_order_id=trade_data.get("order_id") or trade_data.get("orderID"),
                                trading_pair=tracked_order.trading_pair,
                                fee=fee,
                                fill_base_amount=fill_size,
                                fill_quote_amount=fill_size * fill_price,
                                fill_price=fill_price,
                                fill_timestamp=float(trade_data.get("time", 0)) * 1e-9,
                            )
                            self._order_tracker.process_trade_update(trade_update)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Error processing user stream event")

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return False

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        resp = await self._api_post(
            path_url=CONSTANTS.TICKER_URL,
            data={"instrument": exchange_symbol},
            is_auth_required=False,
            limit_id=CONSTANTS.TICKER_URL,
        )
        result = resp.get("result", resp)
        return float(result.get("last_price", result.get("lastPrice", 0)) or 0)

    async def _make_network_check_request(self):
        await self._api_post(
            path_url=CONSTANTS.MARK_PRICE_URL,
            data={},
            is_auth_required=False,
            limit_id=CONSTANTS.MARK_PRICE_URL,
        )

    async def _get_position_mode(self) -> Optional[PositionMode]:
        return PositionMode.ONEWAY

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        # GRVT currently only supports oneway at the API level (for now)
        return True, ""

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        return True, ""

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        return 0, Decimal("0"), Decimal("0")
