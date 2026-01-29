import asyncio
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
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
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class ArchitectPerpetualDerivative(PerpetualDerivativePyBase):
    web_utils = web_utils

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 12.0

    def __init__(
        self,
        balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
        rate_limits_share_pct: Decimal = Decimal("100"),
        architect_perpetual_api_key: str = None,
        architect_perpetual_api_secret: str = None,
        architect_perpetual_paper_trading: bool = False,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._api_key = architect_perpetual_api_key
        self._api_secret = architect_perpetual_api_secret
        self._paper_trading = architect_perpetual_paper_trading
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._position_mode = None
        self._last_trade_history_timestamp = None
        self._architect_client = None
        self._account_name: Optional[str] = None
        self._trading_pair_symbol_map: bidict = bidict()
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def authenticator(self) -> Optional[ArchitectPerpetualAuth]:
        if self._trading_required:
            return ArchitectPerpetualAuth(
                self._api_key,
                self._api_secret,
                self._paper_trading
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
        return "list_symbols"

    @property
    def trading_pairs_request_path(self) -> str:
        return "list_symbols"

    @property
    def check_network_request_path(self) -> str:
        return "who_am_i"

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

    async def _get_architect_client(self):
        if self._architect_client is None:
            from architect_py import AsyncClient
            endpoint = CONSTANTS.TESTNET_ENDPOINT if self._paper_trading else CONSTANTS.PERPETUAL_ENDPOINT
            self._architect_client = await AsyncClient.connect(
                api_key=self._api_key,
                api_secret=self._api_secret,
                paper_trading=self._paper_trading,
                endpoint=endpoint,
            )
            accounts = await self._architect_client.list_accounts()
            if accounts:
                self._account_name = accounts[0].account.name
        return self._architect_client

    async def _make_network_check_request(self):
        client = await self._get_architect_client()
        await client.who_am_i()

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

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth)

    async def _make_trading_rules_request(self) -> Any:
        client = await self._get_architect_client()
        symbols = await client.list_symbols()
        return symbols

    async def _make_trading_pairs_request(self) -> Any:
        client = await self._get_architect_client()
        symbols = await client.list_symbols()
        return symbols

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        d_price = Decimal(round(float(f"{price:.5g}"), 6))
        return d_price

    async def _update_trading_rules(self):
        client = await self._get_architect_client()
        symbols = await client.list_symbols()
        trading_rules_list = await self._format_trading_rules(symbols)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

    async def _format_trading_rules(self, symbols_info: List) -> List[TradingRule]:
        trading_rules = []
        for symbol_info in symbols_info:
            try:
                trading_pair = symbol_info.symbol if hasattr(symbol_info, 'symbol') else str(symbol_info)
                trading_rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=Decimal("0.001"),
                        min_price_increment=Decimal("0.01"),
                        min_base_amount_increment=Decimal("0.001"),
                        min_notional_size=Decimal("1"),
                        buy_order_collateral_token="USD",
                        sell_order_collateral_token="USD",
                    )
                )
            except Exception as e:
                self.logger().exception(f"Error parsing trading rule for {symbol_info}: {e}")
        return trading_rules

    async def _initialize_trading_pair_symbol_map(self):
        try:
            client = await self._get_architect_client()
            symbols = await client.list_symbols()
            for symbol_info in symbols:
                symbol = symbol_info.symbol if hasattr(symbol_info, 'symbol') else str(symbol_info)
                self._trading_pair_symbol_map[symbol] = symbol
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return ArchitectPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return ArchitectPerpetualUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    async def _status_polling_loop_fetch_updates(self):
        await safe_gather(
            self._update_order_status(),
            self._update_balances(),
            self._update_positions(),
        )

    async def _update_order_status(self):
        await self._update_orders()

    async def _update_orders(self):
        client = await self._get_architect_client()
        open_orders = await client.get_open_orders()
        for order in open_orders:
            tracked_order = self._order_tracker.fetch_tracked_order(order.id)
            if tracked_order is not None:
                new_state = CONSTANTS.ORDER_STATE.get(order.status, tracked_order.current_state)
                order_update = OrderUpdate(
                    client_order_id=tracked_order.client_order_id,
                    exchange_order_id=order.id,
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=order.timestamp if hasattr(order, 'timestamp') else None,
                    new_state=new_state,
                )
                self._order_tracker.process_order_update(order_update)

    async def _update_balances(self):
        client = await self._get_architect_client()
        if self._account_name:
            account_summary = await client.get_account_summary(account=self._account_name)
            if account_summary and hasattr(account_summary, 'balances'):
                for balance in account_summary.balances:
                    asset = balance.asset if hasattr(balance, 'asset') else "USD"
                    total = Decimal(str(balance.total)) if hasattr(balance, 'total') else Decimal("0")
                    available = Decimal(str(balance.available)) if hasattr(balance, 'available') else total
                    self._account_balances[asset] = total
                    self._account_available_balances[asset] = available

    async def _update_positions(self):
        client = await self._get_architect_client()
        if self._account_name:
            positions_summary = await client.get_positions_summary(account=self._account_name)
            if positions_summary:
                for pos_data in positions_summary:
                    trading_pair = pos_data.symbol if hasattr(pos_data, 'symbol') else None
                    if trading_pair:
                        amount = Decimal(str(pos_data.quantity)) if hasattr(pos_data, 'quantity') else Decimal("0")
                        entry_price = Decimal(str(pos_data.entry_price)) if hasattr(pos_data, 'entry_price') else Decimal("0")
                        unrealized_pnl = Decimal(str(pos_data.unrealized_pnl)) if hasattr(pos_data, 'unrealized_pnl') else Decimal("0")
                        leverage = Decimal(str(pos_data.leverage)) if hasattr(pos_data, 'leverage') else Decimal("1")
                        position_side = PositionSide.LONG if amount > 0 else PositionSide.SHORT
                        pos = Position(
                            trading_pair=trading_pair,
                            position_side=position_side,
                            unrealized_pnl=unrealized_pnl,
                            entry_price=entry_price,
                            amount=abs(amount),
                            leverage=leverage,
                        )
                        self._account_positions[trading_pair] = pos

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        position_action: PositionAction,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None
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
        pass

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        client = await self._get_architect_client()
        try:
            result = await client.cancel_order(order_id)
            return result is not None
        except Exception as e:
            if CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(e):
                await self._order_tracker.process_order_not_found(order_id)
            raise

    def buy(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type=OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs
    ) -> str:
        order_id = str(uuid.uuid4())
        if order_type is OrderType.MARKET:
            reference_price = self.get_mid_price(trading_pair) if price.is_nan() else price
            price = self.quantize_order_price(
                trading_pair,
                reference_price * Decimal(1 + CONSTANTS.MARKET_ORDER_SLIPPAGE)
            )

        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return order_id

    def sell(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = s_decimal_NaN,
        **kwargs
    ) -> str:
        order_id = str(uuid.uuid4())
        if order_type is OrderType.MARKET:
            reference_price = self.get_mid_price(trading_pair) if price.is_nan() else price
            price = self.quantize_order_price(
                trading_pair,
                reference_price * Decimal(1 - CONSTANTS.MARKET_ORDER_SLIPPAGE)
            )

        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return order_id

    async def _create_order(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        price: Decimal,
        **kwargs
    ):
        client = await self._get_architect_client()
        try:
            from architect_py import OrderDir, OrderType as ArchOrderType, TimeInForce

            direction = OrderDir.BUY if trade_type == TradeType.BUY else OrderDir.SELL
            arch_order_type = ArchOrderType.LIMIT if order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER] else ArchOrderType.MARKET

            order = await client.place_order(
                symbol=trading_pair,
                dir=direction,
                quantity=amount,
                order_type=arch_order_type,
                limit_price=price if arch_order_type == ArchOrderType.LIMIT else None,
                account=self._account_name,
                time_in_force=TimeInForce.GTC,
            )

            if order:
                order_update = OrderUpdate(
                    client_order_id=order_id,
                    exchange_order_id=str(order.id),
                    trading_pair=trading_pair,
                    update_timestamp=None,
                    new_state=CONSTANTS.ORDER_STATE.get("open"),
                )
                self._order_tracker.process_order_update(order_update)
        except Exception as e:
            self.logger().error(f"Error placing order: {e}")
            raise

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        **kwargs
    ) -> Tuple[str, float]:
        client = await self._get_architect_client()
        from architect_py import OrderDir, OrderType as ArchOrderType, TimeInForce

        direction = OrderDir.BUY if trade_type == TradeType.BUY else OrderDir.SELL
        arch_order_type = ArchOrderType.LIMIT if order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER] else ArchOrderType.MARKET

        order = await client.place_order(
            symbol=trading_pair,
            dir=direction,
            quantity=amount,
            order_type=arch_order_type,
            limit_price=price if arch_order_type == ArchOrderType.LIMIT else None,
            account=self._account_name,
            time_in_force=TimeInForce.GTC,
        )

        return str(order.id), float(order.timestamp) if hasattr(order, 'timestamp') else 0.0

    async def stop(self):
        if self._architect_client:
            await self._architect_client.close()
            self._architect_client = None
        await super().stop()
