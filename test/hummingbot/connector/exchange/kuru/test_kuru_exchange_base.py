import logging
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.exchange.kuru.kuru_exchange import KuruExchange
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, TradeUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee


class KuruExchangeTestBase:
    level = 0
    private_key = "0x0123456789012345678901234567890123456789012345678901234567890123"  # noqa: mock
    wallet_address = "0x14791697260E4c9A71f18484C9f997B308e59325"
    market_address = "0x065C9d28E428A0db40191a54d33d5b7c71a9C394"
    trading_pair = "MON-USDC"

    def setUp(self) -> None:
        super().setUp()  # type: ignore[misc]
        self.log_records = []
        self.connector = KuruExchange(
            kuru_private_key=self.private_key,
            kuru_market_address=self.market_address,
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.connector.logger().setLevel(1)
        self.connector.logger().addHandler(self)

        self.market_config = SimpleNamespace(
            market_symbol=self.trading_pair,
            price_precision=100000000,
            size_precision=10000000000,
            tick_size=100,
            base_token_decimals=18,
            quote_token_decimals=6,
            base_symbol="MON",
            quote_symbol="USDC",
        )
        self.connector._market_config = self.market_config
        self.connector._initialize_trading_pair_symbols_from_exchange_info({})

        self.connector._kuru_auth = MagicMock()
        self.connector._kuru_auth.address = self.wallet_address
        self.connector._kuru_auth.get_wallet_config.return_value = "wallet-config"

        self.client = MagicMock()
        self.client.place_orders = AsyncMock(return_value="0xtxhash")
        self.client.cancel_all_active_orders_for_market = AsyncMock()
        self.client.is_healthy = MagicMock(return_value=True)
        self.client.start = AsyncMock()
        self.client.stop = AsyncMock()
        self.client.subscribe_to_orderbook = AsyncMock()
        self.client.set_order_callback = MagicMock()
        self.client.set_orderbook_callback = MagicMock()
        self.client.orders_manager = MagicMock()
        self.client.orders_manager.get_kuru_order_id = MagicMock(return_value=None)
        self.client.orders_manager.cloid_to_order = {}
        self.client.executor = SimpleNamespace()
        self.client.user = SimpleNamespace(
            get_margin_balances=AsyncMock(return_value=(0, 0)),
        )
        self.connector._client = self.client

        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.active_orders = {}
        self.connector._order_tracker.fetch_order = MagicMock(return_value=None)
        self.connector._order_tracker.process_order_update = MagicMock()
        self.connector._order_tracker.process_trade_update = MagicMock()

    def tearDown(self) -> None:
        self.connector.logger().removeHandler(self)
        super().tearDown()  # type: ignore[misc]

    def handle(self, record: logging.LogRecord):
        self.log_records.append(record)

    def _is_logged(self, level_name: str, message: str) -> bool:
        return any(
            record.levelname == level_name and record.getMessage() == message
            for record in self.log_records
        )

    def make_order(
        self,
        client_order_id: str = "OID-1",
        trade_type: TradeType = TradeType.BUY,
        order_type: OrderType = OrderType.LIMIT,
        price: Decimal = Decimal("2"),
        amount: Decimal = Decimal("10"),
        creation_timestamp: float = 1000.0,
        initial_state: OrderState = OrderState.OPEN,
        exchange_order_id: str = "ex-1",
        executed_amount_base: Decimal = Decimal("0"),
        order_fills=None,
    ) -> InFlightOrder:
        order = InFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount,
            creation_timestamp=creation_timestamp,
            initial_state=initial_state,
        )
        order.executed_amount_base = executed_amount_base
        order.order_fills = order_fills or {}
        return order

    def make_sdk_order(
        self,
        cloid: str = "OID-1",
        status=None,
        order_type=None,
        side=None,
        kuru_order_id=None,
        filled_sizes=None,
        price=2.0,
        size=10.0,
    ):
        return SimpleNamespace(
            cloid=cloid,
            status=status,
            order_type=order_type,
            side=side,
            kuru_order_id=kuru_order_id,
            filled_sizes=filled_sizes or [],
            price=price,
            size=size,
        )

    def existing_fill(self, client_order_id: str = "OID-1") -> TradeUpdate:
        return TradeUpdate(
            trade_id=f"{client_order_id}_0",
            client_order_id=client_order_id,
            exchange_order_id="77",
            trading_pair=self.trading_pair,
            fill_timestamp=1000.0,
            fill_price=Decimal("2"),
            fill_base_amount=Decimal("1"),
            fill_quote_amount=Decimal("2"),
            fee=AddedToCostTradeFee(percent=Decimal("0")),
            is_taker=False,
        )

    @property
    def expected_trading_rule(self) -> TradingRule:
        return TradingRule(
            trading_pair=self.trading_pair,
            min_price_increment=Decimal("0.000001"),
            min_base_amount_increment=Decimal("0.0000000001"),
            supports_limit_orders=True,
            supports_market_orders=False,
            buy_order_collateral_token="USDC",
            sell_order_collateral_token="MON",
        )
