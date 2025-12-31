import asyncio
import secrets
import time
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.derivative.aevo_perpetual import (
    aevo_perpetual_constants as CONSTANTS,
    aevo_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_api_order_book_data_source import (
    AevoPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_auth import AevoPerpetualAuth
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_user_stream_data_source import (
    AevoPerpetualUserStreamDataSource,
)
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_utils import (
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
    decimal_to_padded_int,
    padded_int_to_decimal,
)
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

apm_logger = None


class AevoPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 12.0

    def __init__(
        self,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        aevo_perpetual_api_key: str = None,
        aevo_perpetual_api_secret: str = None,
        aevo_perpetual_signing_key: str = None,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._api_key = aevo_perpetual_api_key
        self._api_secret = aevo_perpetual_api_secret
        self._signing_key = aevo_perpetual_signing_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None
        self._instrument_map: Dict[str, int] = {}
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[AevoPerpetualAuth]:
        if self._trading_required:
            return AevoPerpetualAuth(
                api_key=self._api_key,
                api_secret=self._api_secret,
                signing_key=self._signing_key,
                is_testnet="testnet" in self._domain,
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
        return CONSTANTS.MARKETS_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.MARKETS_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.TIME_URL

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

    async def _make_network_check_request(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.TIME_URL, domain=self._domain)
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.TIME_URL,
        )

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

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

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
        exchange_pair = convert_to_exchange_trading_pair(trading_pair)
        instrument_id = self._instrument_map.get(exchange_pair, 0)

        is_buy = trade_type == TradeType.BUY
        limit_price = decimal_to_padded_int(price)
        amount_int = decimal_to_padded_int(amount, decimals=8)
        salt = secrets.randbits(128)
        timestamp = int(time.time())

        order_signature = self.authenticator.sign_order(
            maker=self.authenticator.signing_address,
            is_buy=is_buy,
            limit_price=limit_price,
            amount=amount_int,
            salt=salt,
            instrument=instrument_id,
            timestamp=timestamp,
        )

        order_data = {
            "instrument": instrument_id,
            "maker": self.authenticator.signing_address,
            "is_buy": is_buy,
            "amount": str(amount_int),
            "limit_price": str(limit_price),
            "salt": str(salt),
            "signature": order_signature["signature"],
            "timestamp": timestamp,
        }

        if order_type == OrderType.MARKET:
            order_data["time_in_force"] = "IOC"
        elif order_type == OrderType.LIMIT_MAKER:
            order_data["post_only"] = True

        url = web_utils.private_rest_url(path_url=CONSTANTS.ORDERS_URL, domain=self._domain)
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.POST,
            data=order_data,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.ORDERS_URL,
        )

        exchange_order_id = response.get("order_id", "")
        return exchange_order_id, time.time()

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        exchange_order_id = tracked_order.exchange_order_id

        url = web_utils.private_rest_url(
            path_url=CONSTANTS.ORDER_URL.format(order_id=exchange_order_id),
            domain=self._domain,
        )
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.DELETE,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.ORDERS_URL,
        )

        if response.get("success"):
            return True
        return False

    async def _update_trading_rules(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.MARKETS_URL, domain=self._domain)
        rest_assistant = await self._api_factory.get_rest_assistant()
        exchange_info = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.MARKETS_URL,
        )

        self._trading_rules.clear()
        self._instrument_map.clear()

        for market in exchange_info:
            try:
                instrument_name = market.get("instrument_name", "")
                if not instrument_name.endswith("-PERP"):
                    continue

                trading_pair = convert_from_exchange_trading_pair(instrument_name)
                self._instrument_map[instrument_name] = market.get("instrument_id", 0)

                min_order_size = Decimal(str(market.get("min_order_value", "0.001")))
                price_step = Decimal(str(market.get("price_step", "0.01")))
                size_step = Decimal(str(market.get("amount_step", "0.001")))

                self._trading_rules[trading_pair] = TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=min_order_size,
                    min_price_increment=price_step,
                    min_base_amount_increment=size_step,
                    buy_order_collateral_token=CONSTANTS.CURRENCY,
                    sell_order_collateral_token=CONSTANTS.CURRENCY,
                )
            except Exception:
                self.logger().exception(f"Error parsing trading rule for {market}")

    async def _update_balances(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.ACCOUNT_INFO_URL, domain=self._domain)
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.ACCOUNT_INFO_URL,
        )

        self._account_available_balances.clear()
        self._account_balances.clear()

        balance = Decimal(str(response.get("balance", 0)))
        available = Decimal(str(response.get("available_balance", 0)))

        self._account_balances[CONSTANTS.CURRENCY] = balance
        self._account_available_balances[CONSTANTS.CURRENCY] = available

    async def _update_positions(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.POSITIONS_URL, domain=self._domain)
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.POSITIONS_URL,
        )

        for position_data in response:
            try:
                instrument_name = position_data.get("instrument_name", "")
                trading_pair = convert_from_exchange_trading_pair(instrument_name)

                amount = Decimal(str(position_data.get("amount", 0)))
                if amount == Decimal("0"):
                    continue

                position_side = PositionSide.LONG if amount > 0 else PositionSide.SHORT
                entry_price = Decimal(str(position_data.get("avg_entry_price", 0)))
                unrealized_pnl = Decimal(str(position_data.get("unrealized_pnl", 0)))
                leverage = Decimal(str(position_data.get("leverage", 1)))

                position = Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=abs(amount),
                    leverage=leverage,
                )
                self._perpetual_trading.set_position(trading_pair, position_side, position)
            except Exception:
                self.logger().exception(f"Error parsing position: {position_data}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        try:
            url = web_utils.private_rest_url(
                path_url=f"{CONSTANTS.TRADES_URL}?order_id={order.exchange_order_id}",
                domain=self._domain,
            )
            rest_assistant = await self._api_factory.get_rest_assistant()
            response = await rest_assistant.execute_request(
                url=url,
                method=RESTMethod.GET,
                is_auth_required=True,
                throttler_limit_id=CONSTANTS.TRADES_URL,
            )

            for trade in response:
                fee = TradeFeeBase.new_perpetual_fee(
                    fee_schema=self._trading_fees.get(order.trading_pair),
                    trade_type=order.trade_type,
                    percent_token=CONSTANTS.CURRENCY,
                    flat_fees=[TokenAmount(amount=Decimal(str(trade.get("fee", 0))), token=CONSTANTS.CURRENCY)],
                )

                trade_update = TradeUpdate(
                    trade_id=str(trade.get("trade_id")),
                    client_order_id=order.client_order_id,
                    exchange_order_id=order.exchange_order_id,
                    trading_pair=order.trading_pair,
                    fee=fee,
                    fill_base_amount=Decimal(str(trade.get("amount", 0))),
                    fill_quote_amount=Decimal(str(trade.get("amount", 0))) * Decimal(str(trade.get("price", 0))),
                    fill_price=Decimal(str(trade.get("price", 0))),
                    fill_timestamp=float(trade.get("timestamp", time.time() * 1e9)) / 1e9,
                )
                trade_updates.append(trade_update)
        except Exception:
            self.logger().exception(f"Error fetching trades for order {order.client_order_id}")

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        url = web_utils.private_rest_url(
            path_url=CONSTANTS.ORDER_URL.format(order_id=tracked_order.exchange_order_id),
            domain=self._domain,
        )
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.ORDERS_URL,
        )

        order_status = response.get("order_status", "")
        new_state = CONSTANTS.ORDER_STATE.get(order_status, OrderState.OPEN)

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            update_timestamp=time.time(),
            new_state=new_state,
        )
        return order_update

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                channel = event_message.get("channel", "")
                data = event_message.get("data", {})

                if channel == CONSTANTS.WS_ORDERS_CHANNEL:
                    await self._process_order_update(data)
                elif channel == CONSTANTS.WS_FILLS_CHANNEL:
                    await self._process_trade_update(data)
                elif channel == CONSTANTS.WS_POSITIONS_CHANNEL:
                    await self._process_position_update(data)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream event listener")

    async def _process_order_update(self, data: Dict[str, Any]):
        client_order_id = data.get("client_order_id")
        if client_order_id not in self._order_tracker.all_orders:
            return

        order_status = data.get("order_status", "")
        new_state = CONSTANTS.ORDER_STATE.get(order_status, OrderState.OPEN)

        order_update = OrderUpdate(
            client_order_id=client_order_id,
            exchange_order_id=data.get("order_id"),
            trading_pair=convert_from_exchange_trading_pair(data.get("instrument_name", "")),
            update_timestamp=time.time(),
            new_state=new_state,
        )
        self._order_tracker.process_order_update(order_update)

    async def _process_trade_update(self, data: Dict[str, Any]):
        client_order_id = data.get("client_order_id")
        if client_order_id not in self._order_tracker.all_orders:
            return

        tracked_order = self._order_tracker.all_orders.get(client_order_id)
        if not tracked_order:
            return

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self._trading_fees.get(tracked_order.trading_pair),
            trade_type=tracked_order.trade_type,
            percent_token=CONSTANTS.CURRENCY,
            flat_fees=[TokenAmount(amount=Decimal(str(data.get("fee", 0))), token=CONSTANTS.CURRENCY)],
        )

        trade_update = TradeUpdate(
            trade_id=str(data.get("trade_id")),
            client_order_id=client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fee=fee,
            fill_base_amount=Decimal(str(data.get("amount", 0))),
            fill_quote_amount=Decimal(str(data.get("amount", 0))) * Decimal(str(data.get("price", 0))),
            fill_price=Decimal(str(data.get("price", 0))),
            fill_timestamp=float(data.get("timestamp", time.time() * 1e9)) / 1e9,
        )
        self._order_tracker.process_trade_update(trade_update)

    async def _process_position_update(self, data: Dict[str, Any]):
        pass

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self.authenticator,
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return AevoPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._api_factory,
            domain=self._domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return AevoPerpetualUserStreamDataSource(
            auth=self.authenticator,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._api_factory,
            domain=self._domain,
        )

    async def _format_trading_rules(self, exchange_info: Dict[str, Any]) -> List[TradingRule]:
        return []

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
        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
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
