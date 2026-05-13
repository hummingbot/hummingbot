import asyncio
import random
import time
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.aevo_perpetual import (
    aevo_perpetual_constants as CONSTANTS,
    aevo_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_api_order_book_data_source import (
    AevoPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_api_user_stream_data_source import (
    AevoPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_auth import AevoPerpetualAuth
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, PriceType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class AevoPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0

    def __init__(
            self,
            balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
            rate_limits_share_pct: Decimal = Decimal("100"),
            aevo_perpetual_api_key: str = None,
            aevo_perpetual_api_secret: str = None,
            aevo_perpetual_signing_key: str = None,
            aevo_perpetual_account_address: str = None,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self._api_key = aevo_perpetual_api_key
        self._api_secret = aevo_perpetual_api_secret
        self._signing_key = aevo_perpetual_signing_key
        self._account_address = aevo_perpetual_account_address
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None
        self._instrument_ids: Dict[str, int] = {}
        self._instrument_names: Dict[str, str] = {}
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[AevoPerpetualAuth]:
        if self._api_key and self._api_secret and self._signing_key and self._account_address:
            return AevoPerpetualAuth(
                api_key=self._api_key,
                api_secret=self._api_secret,
                signing_key=self._signing_key,
                account_address=self._account_address,
                domain=self._domain,
            )
        return None

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
        return CONSTANTS.BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.MARKETS_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.MARKETS_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.PING_PATH_URL

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
        return 120

    @staticmethod
    def _signed_position_amount(amount: Decimal, position_side: PositionSide) -> Decimal:
        return -amount if position_side == PositionSide.SHORT else amount

    async def _make_network_check_request(self):
        await self._api_get(path_url=self.check_network_request_path)

    def get_price_by_type(self, trading_pair: str, price_type: PriceType) -> Decimal:
        price = super().get_price_by_type(trading_pair, price_type)
        if not price.is_nan():
            return price
        if price_type in {PriceType.MidPrice, PriceType.LastTrade}:
            fallback_price = self._get_funding_price_fallback(trading_pair)
            if fallback_price is not None:
                return fallback_price
        return price

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pairs_data = await self._api_get(
            path_url=CONSTANTS.MARKETS_PATH_URL,
            params={"instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE},
            limit_id=CONSTANTS.MARKETS_PATH_URL,
        )
        pairs_prices: List[Dict[str, str]] = []

        for pair_data in pairs_data:
            symbol = pair_data.get("instrument_name")
            price = pair_data.get("index_price")

            if symbol is None or price is None:
                continue

            pairs_prices.append({
                "symbol": symbol,
                "price": price,
            })

        return pairs_prices

    def supported_position_modes(self):
        return [PositionMode.ONEWAY]

    def set_position_mode(self, mode: PositionMode):
        if mode == PositionMode.HEDGE:
            self.logger().warning(
                "Aevo perpetual does not support HEDGE position mode. Using ONEWAY instead."
            )
            mode = PositionMode.ONEWAY
        super().set_position_mode(mode)

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        error_message = str(status_update_exception)
        is_order_not_exist = CONSTANTS.NOT_EXIST_ERROR in error_message

        return is_order_not_exist

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        error_message = str(cancelation_exception)
        is_order_not_exist = CONSTANTS.NOT_EXIST_ERROR in error_message

        return is_order_not_exist

    def _is_reduce_only_rejection_error(self, exception: Exception) -> bool:
        error_message = str(exception)
        return any(error_code in error_message for error_code in CONSTANTS.REDUCE_ONLY_REJECTION_ERRORS)

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

        if position_action == PositionAction.CLOSE and self._is_reduce_only_rejection_error(exception):
            self.logger().info(
                f"Ignoring rejected reduce-only close order {order_id} ({trade_type.name} {trading_pair}): {exception}"
            )
            self._order_tracker.process_order_update(OrderUpdate(
                trading_pair=trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.CANCELED,
                client_order_id=order_id,
                misc_updates={
                    "error_message": str(exception),
                    "error_type": exception.__class__.__name__,
                },
            ))
            safe_ensure_future(self._update_positions())

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

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth,
        )

    async def _make_trading_rules_request(self) -> Any:
        exchange_info = await self._api_get(
            path_url=self.trading_rules_request_path,
            params={"instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE},
        )
        return exchange_info

    async def _make_trading_pairs_request(self) -> Any:
        exchange_info = await self._api_get(
            path_url=self.trading_pairs_request_path,
            params={"instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE},
        )
        return exchange_info

    def _get_funding_price_fallback(self, trading_pair: str) -> Optional[Decimal]:
        try:
            funding_info = self.get_funding_info(trading_pair)
        except KeyError:
            return None
        price = funding_info.mark_price or funding_info.index_price or s_decimal_NaN
        return price if price > 0 else None

    def _resolve_trading_pair_symbols_duplicate(self, mapping: bidict, new_exchange_symbol: str, base: str, quote: str):
        expected_exchange_symbol = f"{base}{quote}"
        trading_pair = combine_to_hb_trading_pair(base, quote)
        current_exchange_symbol = mapping.inverse[trading_pair]
        if current_exchange_symbol == expected_exchange_symbol:
            pass
        elif new_exchange_symbol == expected_exchange_symbol:
            mapping.pop(current_exchange_symbol)
            mapping[new_exchange_symbol] = trading_pair
        else:
            self.logger().error(
                f"Could not resolve the exchange symbols {new_exchange_symbol} and {current_exchange_symbol}")
            mapping.pop(current_exchange_symbol)

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List):
        mapping = bidict()
        for symbol_data in filter(web_utils.is_exchange_information_valid, exchange_info):
            if symbol_data.get("instrument_type") != CONSTANTS.PERPETUAL_INSTRUMENT_TYPE:
                continue
            exchange_symbol = symbol_data["instrument_name"]
            base = symbol_data["underlying_asset"]
            quote = symbol_data["quote_asset"]
            trading_pair = combine_to_hb_trading_pair(base, quote)
            if trading_pair in mapping.inverse:
                self._resolve_trading_pair_symbols_duplicate(mapping, exchange_symbol, base, quote)
            else:
                mapping[exchange_symbol] = trading_pair
            self._instrument_ids[trading_pair] = int(symbol_data["instrument_id"])
            self._instrument_names[trading_pair] = exchange_symbol
        self._set_trading_pair_symbol_map(mapping)

    async def _format_trading_rules(self, exchange_info_dict: List) -> List[TradingRule]:
        return_val: List[TradingRule] = []
        for market in exchange_info_dict:
            try:
                if market.get("instrument_type") != CONSTANTS.PERPETUAL_INSTRUMENT_TYPE:
                    continue
                if not web_utils.is_exchange_information_valid(market):
                    continue

                base = market["underlying_asset"]
                quote = market["quote_asset"]
                trading_pair = combine_to_hb_trading_pair(base, quote)

                price_step = Decimal(str(market["price_step"]))
                amount_step = Decimal(str(market["amount_step"]))
                min_order_value = Decimal(str(market.get("min_order_value", "0")))

                return_val.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_base_amount_increment=amount_step,
                        min_price_increment=price_step,
                        min_order_size=amount_step,
                        min_order_value=min_order_value,
                        buy_order_collateral_token=quote,
                        sell_order_collateral_token=quote,
                    )
                )
            except Exception:
                self.logger().error(f"Error parsing trading rule for {market}.", exc_info=True)
        return return_val

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return AevoPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return AevoPerpetualAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain,
        )

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 position_action: PositionAction,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = is_maker or False
        fee = build_trade_fee(
            self.name,
            is_maker,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )
        return fee

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    def buy(self,
            trading_pair: str,
            amount: Decimal,
            order_type=OrderType.LIMIT,
            price: Decimal = s_decimal_NaN,
            **kwargs) -> str:
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length,
        )
        if order_type is OrderType.MARKET:
            reference_price = self.get_mid_price(trading_pair) if price.is_nan() else price
            market_price = reference_price * (Decimal("1") + CONSTANTS.MARKET_ORDER_SLIPPAGE)
            price = self.quantize_order_price(trading_pair, market_price)

        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return order_id

    def sell(self,
             trading_pair: str,
             amount: Decimal,
             order_type: OrderType = OrderType.LIMIT,
             price: Decimal = s_decimal_NaN,
             **kwargs) -> str:
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length,
        )
        if order_type is OrderType.MARKET:
            reference_price = self.get_mid_price(trading_pair) if price.is_nan() else price
            market_price = reference_price * (Decimal("1") - CONSTANTS.MARKET_ORDER_SLIPPAGE)
            price = self.quantize_order_price(trading_pair, market_price)

        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
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

        instrument_id = self._instrument_ids.get(trading_pair)
        if instrument_id is None:
            self.logger().error(f"Order {order_id} rejected: instrument not found for {trading_pair}.")
            raise KeyError(f"Instrument not found for {trading_pair}")
        is_buy = trade_type is TradeType.BUY
        timestamp = int(time.time())
        salt = random.randint(0, 10 ** 6)
        limit_price = web_utils.decimal_to_int(price)
        amount_int = web_utils.decimal_to_int(amount)

        signature = self._auth.sign_order(
            is_buy=is_buy,
            limit_price=limit_price,
            amount=amount_int,
            salt=salt,
            instrument=instrument_id,
            timestamp=timestamp,
        )

        api_params = {
            "instrument": instrument_id,
            "maker": self._account_address,
            "is_buy": is_buy,
            "amount": str(amount_int),
            "limit_price": str(limit_price),
            "salt": str(salt),
            "signature": signature,
            "timestamp": str(timestamp),
            "post_only": order_type is OrderType.LIMIT_MAKER,
            "reduce_only": position_action is PositionAction.CLOSE,
            "time_in_force": "IOC" if order_type is OrderType.MARKET else "GTC",
        }
        order_result = await self._api_post(
            path_url=CONSTANTS.ORDERS_PATH_URL,
            data=api_params,
            is_auth_required=True,
            limit_id=CONSTANTS.ORDERS_PATH_URL,
        )
        if order_result.get("error") is not None:
            self.logger().error(f"Order {order_id} failed: {order_result['error']}")
            raise IOError(f"Error submitting order {order_id}: {order_result['error']}")

        exchange_order_id = str(order_result.get("order_id"))
        return exchange_order_id, self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        exchange_order_id = await tracked_order.get_exchange_order_id()
        if exchange_order_id is None:
            return False

        cancel_result = await self._api_delete(
            path_url=CONSTANTS.ORDER_PATH_URL.format(order_id=exchange_order_id),
            is_auth_required=True,
            limit_id=CONSTANTS.ORDERS_PATH_URL,
        )

        if cancel_result.get("error") is not None:
            raise IOError(f"{cancel_result['error']}")

        return True

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        exchange_order_id = await tracked_order.get_exchange_order_id()
        order_update = await self._api_get(
            path_url=CONSTANTS.ORDER_PATH_URL.format(order_id=exchange_order_id),
            is_auth_required=True,
            limit_id=CONSTANTS.ORDERS_PATH_URL,
        )
        if order_update.get("error") is not None:
            raise IOError(order_update["error"])
        current_state = order_update.get("order_status")
        update_timestamp = int(order_update.get("timestamp", order_update.get("created_timestamp", "0"))) * 1e-9
        return OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=CONSTANTS.ORDER_STATE.get(current_state, OrderState.FAILED),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(order_update.get("order_id")),
        )

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        exchange_order_id = str(order.exchange_order_id)
        if exchange_order_id is None:
            return []

        start_time = int(order.creation_timestamp * 1e9)
        response = await self._api_get(
            path_url=CONSTANTS.TRADE_HISTORY_PATH_URL,
            params={
                "start_time": start_time,
                "instrument_type": CONSTANTS.PERPETUAL_INSTRUMENT_TYPE,
                "limit": 50,
            },
            is_auth_required=True,
            limit_id=CONSTANTS.TRADE_HISTORY_PATH_URL,
        )
        trade_updates: List[TradeUpdate] = []
        for trade in response.get("trade_history", []):
            if str(trade.get("order_id")) != exchange_order_id:
                continue
            fee_asset = order.quote_asset
            position_action = order.position
            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_action,
                percent_token=fee_asset,
                flat_fees=[TokenAmount(amount=Decimal(trade["fees"]), token=fee_asset)],
            )
            trade_updates.append(TradeUpdate(
                trade_id=str(trade.get("trade_id")),
                client_order_id=order.client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=order.trading_pair,
                fill_timestamp=int(trade.get("created_timestamp", "0")) * 1e-9,
                fill_price=Decimal(trade.get("price", "0")),
                fill_base_amount=Decimal(trade.get("amount", "0")),
                fill_quote_amount=Decimal(trade.get("price", "0")) * Decimal(trade.get("amount", "0")),
                fee=fee,
            ))
        return trade_updates

    async def _update_balances(self):
        account_info = await self._api_get(
            path_url=CONSTANTS.ACCOUNT_PATH_URL,
            is_auth_required=True,
            limit_id=CONSTANTS.ACCOUNT_PATH_URL,
        )
        balances = account_info.get("collaterals", [])
        if not balances and "collaterals" not in account_info:
            self.logger().warning(
                "Aevo account response did not include collaterals; balance update skipped.")
            return
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        for balance_entry in balances:
            asset_name = balance_entry["collateral_asset"]
            free_balance = Decimal(balance_entry.get("available_balance", "0"))
            total_balance = Decimal(balance_entry.get("balance", "0"))
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_positions(self):
        positions_info = await self._api_get(
            path_url=CONSTANTS.POSITIONS_PATH_URL,
            is_auth_required=True,
            limit_id=CONSTANTS.POSITIONS_PATH_URL,
        )

        positions = positions_info.get("positions", [])
        active_pairs = set()

        for position in positions:
            if position.get("instrument_type") != CONSTANTS.PERPETUAL_INSTRUMENT_TYPE:
                continue

            trading_pair = await self.trading_pair_associated_to_exchange_symbol(position["instrument_name"])
            active_pairs.add(trading_pair)
            position_side = PositionSide.LONG if position.get("side") == "buy" else PositionSide.SHORT
            amount = self._signed_position_amount(
                amount=Decimal(position.get("amount", "0")),
                position_side=position_side,
            )
            entry_price = Decimal(position.get("avg_entry_price", "0"))
            unrealized_pnl = Decimal(position.get("unrealized_pnl", "0"))
            leverage = Decimal(position.get("leverage", "1"))
            pos_key = self._perpetual_trading.position_key(trading_pair, position_side)

            if amount != 0:
                self._perpetual_trading.set_position(
                    pos_key,
                    Position(
                        trading_pair=trading_pair,
                        position_side=position_side,
                        unrealized_pnl=unrealized_pnl,
                        entry_price=entry_price,
                        amount=amount,
                        leverage=leverage,
                    )
                )
            else:
                self._perpetual_trading.remove_position(pos_key)

        if not positions:
            keys = list(self._perpetual_trading.account_positions.keys())
            for key in keys:
                self._perpetual_trading.remove_position(key)

    async def _get_position_mode(self) -> Optional[PositionMode]:
        return PositionMode.ONEWAY

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        return True, ""

    async def _ensure_instrument_id(self, trading_pair: str) -> bool:
        if trading_pair in self._instrument_ids:
            return True
        if not self.is_trading_required:
            return False
        try:
            await self._update_trading_rules()
        except Exception as exc:
            self.logger().network(
                f"Error updating trading rules while resolving instrument id for {trading_pair}: {exc}"
            )
        return trading_pair in self._instrument_ids

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        if not await self._ensure_instrument_id(trading_pair):
            return False, "Instrument not found"
        instrument_id = self._instrument_ids.get(trading_pair)
        if instrument_id is None:
            return False, "Instrument not found"
        try:
            await self._api_post(
                path_url=CONSTANTS.ACCOUNT_LEVERAGE_PATH_URL,
                data={
                    "instrument": instrument_id,
                    "leverage": leverage,
                },
                is_auth_required=True,
                limit_id=CONSTANTS.ACCOUNT_LEVERAGE_PATH_URL,
            )
            self._perpetual_trading.set_leverage(trading_pair, leverage)
            return True, ""
        except Exception as exception:
            return False, f"Error setting leverage: {exception}"

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[int, Decimal, Decimal]:
        return 0, Decimal("-1"), Decimal("-1")

    async def _user_stream_event_listener(self):
        user_channels = [
            CONSTANTS.WS_ORDERS_CHANNEL,
            CONSTANTS.WS_FILLS_CHANNEL,
            CONSTANTS.WS_POSITIONS_CHANNEL,
        ]
        async for event_message in self._iter_user_event_queue():
            try:
                if isinstance(event_message, dict):
                    channel: str = event_message.get("channel", None)
                    results = event_message.get("data", None)
                elif event_message is asyncio.CancelledError:
                    raise asyncio.CancelledError
                else:
                    raise Exception(event_message)

                if channel not in user_channels:
                    self.logger().error(
                        f"Unexpected message in user stream: {event_message}.")
                    continue

                if channel == CONSTANTS.WS_ORDERS_CHANNEL:
                    for order_msg in results.get("orders", []):
                        self._process_order_message(order_msg)
                elif channel == CONSTANTS.WS_FILLS_CHANNEL:
                    fill_msg = results.get("fill")
                    if fill_msg is not None:
                        await self._process_trade_message(fill_msg)
                elif channel == CONSTANTS.WS_POSITIONS_CHANNEL:
                    for position in results.get("positions", []):
                        await self._process_position_message(position)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _process_position_message(self, position: Dict[str, Any]):
        if position.get("instrument_type") != CONSTANTS.PERPETUAL_INSTRUMENT_TYPE:
            return

        trading_pair = await self.trading_pair_associated_to_exchange_symbol(position["instrument_name"])
        position_side = PositionSide.LONG if position.get("side") == "buy" else PositionSide.SHORT
        amount = self._signed_position_amount(
            amount=Decimal(position.get("amount", "0")),
            position_side=position_side,
        )
        entry_price = Decimal(position.get("avg_entry_price", "0"))
        unrealized_pnl = Decimal(position.get("unrealized_pnl", "0"))
        leverage = Decimal(position.get("leverage", "1"))
        pos_key = self._perpetual_trading.position_key(trading_pair, position_side)

        if amount != 0:
            self._perpetual_trading.set_position(
                pos_key,
                Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount,
                    leverage=leverage,
                )
            )
        else:
            self._perpetual_trading.remove_position(pos_key)

    async def _process_trade_message(self, trade: Dict[str, Any]):
        exchange_order_id = str(trade.get("order_id", ""))
        tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)

        if tracked_order is None:
            all_orders = self._order_tracker.all_fillable_orders
            for _, order in all_orders.items():
                await order.get_exchange_order_id()
            tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(exchange_order_id)
            if tracked_order is None:
                self.logger().debug(
                    f"Ignoring trade message with id {exchange_order_id}: not in in_flight_orders.")
                return

        fee_asset = tracked_order.quote_asset
        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=tracked_order.position,
            percent_token=fee_asset,
            flat_fees=[TokenAmount(amount=Decimal(trade.get("fees", "0")), token=fee_asset)],
        )
        trade_update: TradeUpdate = TradeUpdate(
            trade_id=str(trade.get("trade_id")),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=int(trade.get("created_timestamp", "0")) * 1e-9,
            fill_price=Decimal(trade.get("price", "0")),
            fill_base_amount=Decimal(trade.get("filled", "0")),
            fill_quote_amount=Decimal(trade.get("price", "0")) * Decimal(trade.get("filled", "0")),
            fee=fee,
        )
        self._order_tracker.process_trade_update(trade_update)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        exchange_order_id = str(order_msg.get("order_id", ""))
        tracked_order = self._order_tracker.all_updatable_orders_by_exchange_order_id.get(exchange_order_id)
        if not tracked_order:
            self.logger().debug(
                f"Ignoring order message with id {exchange_order_id}: not in in_flight_orders.")
            return
        current_state = order_msg.get("order_status")
        update_timestamp = int(order_msg.get("created_timestamp", "0")) * 1e-9
        order_update: OrderUpdate = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=CONSTANTS.ORDER_STATE.get(current_state, OrderState.FAILED),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
        )
        self._order_tracker.process_order_update(order_update=order_update)

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from Aevo. Check API key and network connection.",
                )
                await self._sleep(1.0)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        response = await self._api_get(
            path_url=f"{CONSTANTS.INSTRUMENT_PATH_URL}/{exchange_symbol}",
            limit_id=CONSTANTS.INSTRUMENT_PATH_URL,
        )
        price = response.get("mark_price") or response.get("index_price") or "0"
        return float(price)
