import asyncio
import re
from asyncio import Event
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from bidict import bidict

from hummingbot.connector.constants import MINUTE, s_decimal_NaN
from hummingbot.connector.derivative.architect_perpetual import (
    architect_perpetual_constants as CONSTANTS,
    architect_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_api_order_book_data_source import (
    ArchitectPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_auth import ArchitectPerpetualAuth
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_user_stream_data_source import (
    ArchitectPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_utils import DEFAULT_FEES
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_numeric_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class ArchitectPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils
    TRADING_RULES_INTERVAL = MINUTE  # to update instrument price-bands every minute

    def __init__(
        self,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        use_auth_for_public_endpoints: bool = False,  # used for MarketDataProvider.update_rates_task
    ):
        self._api_key = api_key
        self._api_secret = api_secret
        self._trading_pairs = trading_pairs or []
        self._trading_required = trading_required
        self._domain = domain
        self._client_order_id_nonce_provider = NonceCreator.for_microseconds()
        self._additional_instruments_info: Dict[str, "AdditionalInstrumentInfo"] = {}
        self._real_time_balance_update = False  # no WS updates for balances
        self._trading_rules_updates_event = Event()
        self._trading_pair_parsing_warrning_issued: set[str] = set()
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> ArchitectPerpetualAuth:
        return ArchitectPerpetualAuth(
            api_key=self._api_key,
            api_secret=self._api_secret,
            time_provider=self._time_synchronizer,
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
        raise NotImplementedError  # uses numeric client order ID

    @property
    def client_order_id_prefix(self) -> str:
        raise NotImplementedError  # uses numeric client order ID

    @property
    def trading_rules_request_path(self) -> str:
        raise NotImplementedError  # _update_trading_rules is re-implemented below

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.EXCHANGE_INFO_ENDPOINT

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.SERVER_TIME_ENDPOINT

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
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def supported_position_modes(self):
        return [PositionMode.ONEWAY]

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pairs_prices = await self._api_get(path_url=CONSTANTS.TICKERS_INFO_ENDPOINT, is_auth_required=True)
        return pairs_prices

    def buy(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type=OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs,
    ) -> str:
        order_id = str(
            get_new_numeric_client_order_id(
                nonce_creator=self._client_order_id_nonce_provider,
                max_id_bit_count=CONSTANTS.MAX_ORDER_ID_BIT_COUNT,
            ),
        )
        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            ),
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
        order_id = str(
            get_new_numeric_client_order_id(
                nonce_creator=self._client_order_id_nonce_provider,
                max_id_bit_count=CONSTANTS.MAX_ORDER_ID_BIT_COUNT,
            ),
        )
        safe_ensure_future(
            self._create_order(
                trade_type=TradeType.SELL,
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                **kwargs,
            ),
        )
        return order_id

    async def _update_trading_rules(self):
        exchange_info = await self._api_get(path_url=CONSTANTS.EXCHANGE_INFO_ENDPOINT)
        tickers_info = await self._api_get(
            path_url=CONSTANTS.TICKERS_INFO_ENDPOINT,
            is_auth_required=True,
        )
        tickers_map = {
            ticker_data["s"]: ticker_data
            for ticker_data in tickers_info["tickers"]
        }
        self._additional_instruments_info.clear()
        self._trading_rules.clear()
        s_decimal_hundred = Decimal("100")
        tickers_info_printed_on_exception = False
        for instrument_data in exchange_info["instruments"]:
            try:
                symbol, base, quote = self._get_symbol_base_and_quote_from_exchange_info_instrument(
                    instrument_data=instrument_data
                )
                if symbol is not None:
                    trading_pair = combine_to_hb_trading_pair(base=base, quote=quote)
                    ticker_data = tickers_map[symbol]
                    price_band = AdditionalInstrumentInfo(
                        leverage=int(s_decimal_hundred / Decimal(instrument_data["initial_margin_pct"])),
                        upper_price_bound=Decimal(ticker_data["pu"]),
                        lower_price_bound=Decimal(ticker_data["pl"]),
                    )
                    self._additional_instruments_info[trading_pair] = price_band
                    min_order_size = Decimal(instrument_data["minimum_order_size"])
                    trading_rule = TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=min_order_size,
                        min_price_increment=Decimal(instrument_data["tick_size"]),
                        min_base_amount_increment=min_order_size,
                        min_notional_size=min_order_size * price_band.lower_price_bound,
                    )
                    self._trading_rules[trading_rule.trading_pair] = trading_rule
                    self._perpetual_trading.set_leverage(trading_pair, price_band.leverage)
            except Exception:
                if not tickers_info_printed_on_exception:
                    self.logger().error(f"Errors while processing tickers info: {tickers_info}.")
                    tickers_info_printed_on_exception = True
                self.logger().exception(
                    f"Error parsing the trading pair rule: {instrument_data}. Skipping."
                )
        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        self._trading_rules_updates_event.set()

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return "no matching orders" in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return "HTTP status is 400. Error:" in str(cancelation_exception)

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        success = mode == PositionMode.ONEWAY
        return success, "" if success else "The Architect exchange only supports One-Way position mode."

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        await self._trading_rules_updates_event.wait()
        additional_pair_info = self._additional_instruments_info[trading_pair]
        if leverage != additional_pair_info.leverage:
            success = False
            reason = f"Leverage for {trading_pair} is fixed at {additional_pair_info.leverage}."
        else:
            success = True
            reason = ""
        return success, reason

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")
        response = await self._api_get(
            path_url=CONSTANTS.FUNDING_EVENTS_ENDPOINT,
            is_auth_required=True,
        )
        funding_events = response["funding_transactions"]
        for event_data in funding_events:
            payment = Decimal(event_data["funding_amount"])
            funding_rate = Decimal(event_data["funding_rate"])
            timestamp = pd.Timestamp(event_data["timestamp"]).timestamp()
        return timestamp, funding_rate, payment

    async def _fetch_last_funding_info(self, trading_pair: str) -> List:
        current_time_ns = int(self._time() * 1e9)
        params = {
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "start_timestamp_ns": current_time_ns - int(7 * 24 * 60 * 60 * 1e9),
            "end_timestamp_ns": current_time_ns,
        }
        response = await self._api_get(
            path_url=CONSTANTS.FUNDING_INFO_ENDPOINT,
            params=params,
            is_auth_required=True,
        )
        return response["funding_rates"]

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
        user_info = await self._api_get(
            path_url=CONSTANTS.USER_INFO_ENDPOINT,
            is_auth_required=True,
        )

        trade_fee_schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal(user_info["maker_fee"]),
            taker_percent_fee_decimal=Decimal(user_info["taker_fee"])
        )
        for trading_pair in self._trading_pairs:
            self._trading_fees[trading_pair] = trade_fee_schema

    async def _user_stream_event_listener(self):
        event_to_state_map = {
            "e": OrderState.CANCELED,
            "n": OrderState.OPEN,
            "c": OrderState.CANCELED,
            "j": OrderState.FAILED,
            "x": OrderState.FAILED,
            "p": OrderState.PARTIALLY_FILLED,
            "f": OrderState.FILLED,
        }
        async for event_message in self._iter_user_event_queue():
            try:
                channel = event_message.get("t", None)
                if channel in event_to_state_map:
                    order_data = event_message["o"]
                    if "cid" in order_data:
                        order_id = str(order_data["cid"])
                        updatable_order = (
                            self._order_tracker.all_updatable_orders.get(order_id)
                        )
                    else:
                        updatable_order = (
                            self._order_tracker.all_updatable_orders_by_exchange_order_id.get(order_data["oid"])
                        )
                    if updatable_order is not None:
                        new_state = event_to_state_map[channel]
                        misc_update = None
                        if new_state == OrderState.FAILED:
                            if channel == "j":
                                misc_update = {"reason": event_message["txt"]}
                            else:
                                misc_update = {"reason": order_data["o"]}
                        new_order_update = OrderUpdate(
                            trading_pair=updatable_order.trading_pair,
                            update_timestamp=self.current_timestamp,
                            new_state=new_state,
                            client_order_id=updatable_order.client_order_id,
                            exchange_order_id=order_data["oid"],
                            misc_updates=misc_update,
                        )
                        self._order_tracker.process_order_update(new_order_update)
                        if channel in ["p", "f"]:
                            trade_data = event_message["xs"]
                            fill_price = Decimal(trade_data["p"])
                            fill_base_amount = Decimal(trade_data["q"])
                            fill_quote_amount = fill_base_amount * fill_price
                            fee_amount = (
                                fill_quote_amount * (
                                    DEFAULT_FEES.taker_percent_fee_decimal
                                    if trade_data["agg"]
                                    else DEFAULT_FEES.maker_percent_fee_decimal
                                )
                            )
                            flat_fees = [TokenAmount(amount=fee_amount, token=updatable_order.quote_asset)]
                            fee = TradeFeeBase.new_perpetual_fee(
                                fee_schema=self.trade_fee_schema(),
                                position_action=updatable_order.position,
                                percent_token=updatable_order.quote_asset,
                                flat_fees=flat_fees,
                            )
                            trade_update = TradeUpdate(
                                trade_id=trade_data["tid"],
                                client_order_id=updatable_order.client_order_id,
                                exchange_order_id=order_data["oid"],
                                trading_pair=updatable_order.trading_pair,
                                fill_timestamp=event_message["ts"],
                                fill_price=fill_price,
                                fill_base_amount=fill_base_amount,
                                fill_quote_amount=fill_quote_amount,
                                fee=fee,
                            )
                            self._order_tracker.process_trade_update(trade_update)
                    # else:
                    #     self._logger.warning(f"Received order update for unrecognized client order: {event_message}.")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        raise NotImplementedError  # _update_trading_rules is re-implemented above

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        response = await self._api_get(
            path_url=CONSTANTS.ORDER_FILLS_ENDPOINT,
            params={"order_id": order.exchange_order_id},
            is_auth_required=True,
        )
        fills_data = response["fills"]
        order_fills_data = [
            fill_data for fill_data in fills_data
            if fill_data["order_id"] == order.exchange_order_id
        ]

        trade_updates = []
        for order_fill_data in order_fills_data:
            fill_price = Decimal(order_fill_data["price"])
            fill_base_amount = Decimal(order_fill_data["quantity"])
            flat_fees = [TokenAmount(amount=Decimal(order_fill_data["fee"]), token=order.quote_asset)]
            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=order.position,
                percent_token=order.quote_asset,
                flat_fees=flat_fees,
            )
            trade_update = TradeUpdate(
                trade_id=order_fill_data["trade_id"],
                client_order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
                trading_pair=order.trading_pair,
                fill_timestamp=pd.Timestamp(order_fill_data["timestamp"]).timestamp(),
                fill_price=fill_price,
                fill_base_amount=fill_base_amount,
                fill_quote_amount=fill_price * fill_base_amount,
                fee=fee,
            )
            trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        response = await self._api_get(
            path_url=CONSTANTS.ORDER_STATUS_ENDPOINT,
            params={"client_order_id": int(tracked_order.client_order_id)},
            is_auth_required=True,
        )
        if "error" in response:
            raise IOError(str(response))
        updated_order_data = response["status"]

        order_update: OrderUpdate = OrderUpdate(
            trading_pair=tracked_order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=CONSTANTS.ORDER_STATUS_MAP[updated_order_data["state"]],
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=updated_order_data["order_id"],
        )

        return order_update

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth,
            domain=self._domain,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return ArchitectPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return ArchitectPerpetualUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain
        )

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for instrument_data in exchange_info["instruments"]:
            try:
                symbol, base, quote = self._get_symbol_base_and_quote_from_exchange_info_instrument(
                    instrument_data=instrument_data
                )
                if symbol is not None:
                    trading_pair = combine_to_hb_trading_pair(base, quote)
                    mapping[symbol] = trading_pair
            except Exception as exception:
                self.logger().error(
                    f"There was an error parsing a trading pair information ({exception})."
                    f" Symbol data: {instrument_data}."
                )
        self._set_trading_pair_symbol_map(mapping)

    def _get_symbol_base_and_quote_from_exchange_info_instrument(
        self, instrument_data
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        symbol = instrument_data["symbol"]
        quote = instrument_data["quote_currency"]
        match = re.match(pattern=fr"(\w+){quote}-PERP", string=symbol)
        if match is not None:
            base = match.group(1)
        else:
            alt_match = re.match(pattern=r"(\w+)-PERP", string=symbol)
            if alt_match is not None:
                base = alt_match.group(1)
            else:
                if symbol not in self._trading_pair_parsing_warrning_issued:
                    self.logger().warning(f"Could not parse base token for {symbol}.")
                    self._trading_pair_parsing_warrning_issued.add(symbol)
                return None, None, None
        return symbol, base, quote

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        ticker_response = await self._api_get(
            path_url=CONSTANTS.SINGLE_TICKER_INFO_ENDPOINT,
            params={
                "symbol": symbol,
            },
            is_auth_required=True,
        )

        return float(ticker_response["ticker"]["p"])

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CANCEL_ORDER_ENDPOINT,
            data={"oid": tracked_order.exchange_order_id},
            is_auth_required=True,
        )
        return cancel_result["cxl_rx"]

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Optional[Decimal],
        **kwargs,
    ) -> Tuple[str, float]:
        exchange_pair = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        is_buy = trade_type == TradeType.BUY
        if order_type == OrderType.MARKET:
            price_band = self._additional_instruments_info[trading_pair]
            price = self.quantize_order_price(
                trading_pair=trading_pair,
                price=price_band.upper_price_bound if is_buy else price_band.lower_price_bound,
            )
        resp = await self._api_post(
            path_url=CONSTANTS.PLACE_ORDER_ENDPOINT,
            data={
                "d": "B" if is_buy else "S",
                "p": str(price),
                "po": order_type == OrderType.LIMIT_MAKER,
                "q": int(amount),
                "s": exchange_pair,
                "tif": "GTC",
                "cid": int(order_id),
            },
            is_auth_required=True,
        )
        return resp["oid"], self.current_timestamp

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_balances_and_positions(),
            self._update_order_status(),
        )

    async def _update_positions(self):
        await self._update_balances_and_positions()

    async def _update_balances(self):
        await self._update_balances_and_positions()

    async def _update_balances_and_positions(self):
        response = await self._api_get(
            path_url=CONSTANTS.RISK_ENDPOINT,
            is_auth_required=True,
        )
        data = response["risk_snapshot"]

        self._account_available_balances["USD"] = Decimal(data["initial_margin_available"])
        self._account_balances["USD"] = Decimal(data["balance_usd"])

        self._perpetual_trading._account_positions.clear()
        for exchange_symbol, position_data in data["per_symbol"].items():
            if position_data["signed_quantity"] > 0:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=exchange_symbol)
                amount = Decimal(position_data["signed_quantity"])
                position = Position(
                    trading_pair=trading_pair,
                    position_side=PositionSide.LONG if amount > Decimal("0") else PositionSide.SHORT,
                    unrealized_pnl=Decimal(position_data["unrealized_pnl"]),
                    entry_price=Decimal(position_data["average_price"]),
                    amount=abs(amount),
                    leverage=self._perpetual_trading.get_leverage(trading_pair=trading_pair),
                )
                pos_key = self._perpetual_trading.position_key(trading_pair, position.position_side)
                self._perpetual_trading.set_position(pos_key, position)


@dataclass
class AdditionalInstrumentInfo:
    leverage: int
    upper_price_bound: Decimal
    lower_price_bound: Decimal
