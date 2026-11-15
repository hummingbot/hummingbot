import hashlib
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

from neutronx_sdk import TESTNET, ClientIdAllocator, OrderRequest, Wallet
from neutronx_sdk.models import FeeTier, Market, Order, OrderbookParams, Position, SubaccountBalance

from hummingbot.connector.derivative.neutronx_perpetual.data_sources.tx_queue import (
    CancelledOrder,
    CancelOutcome,
    PlacedOrder,
)

INDEXER_URL = "https://indexer.test/v1"
INDEXER_WS_URL = "wss://indexer.test/v1/ws"
NETWORK = TESTNET.with_indexer(INDEXER_URL, INDEXER_WS_URL)
PRIVATE_KEY = hashlib.sha256(b"neutronx-connector-tests").hexdigest()
WALLET = Wallet.from_hex(PRIVATE_KEY)
ACCOUNT = WALLET.address
BLOCK_TIME = "2026-11-10T12:00:00+00:00"
FILL_FEE = "0.325"


def market(
    pair: str = "BTC/USDC",
    status: str = "ACTIVE",
    tick: str = "0.5",
    min_quantity: str = "0.001",
    max_leverage: int = 10,
    effective_max_leverage: Optional[int] = None,
    max_slippage: str = "0.01",
) -> Market:
    return Market(
        pair=pair,
        status=status,
        tick_size=Decimal(tick),
        min_quantity=Decimal(min_quantity),
        max_leverage=Decimal(max_leverage),
        maker_fee_rate=Decimal("0.0002"),
        taker_fee_rate=Decimal("0.0005"),
        maintenance_margin=Decimal("0.01"),
        price_band_percent=Decimal("0.5"),
        effective_max_leverage=Decimal(max_leverage if effective_max_leverage is None else effective_max_leverage),
        max_slippage=Decimal(max_slippage),
    )


def orderbook_params(rate_limit: int = 30) -> OrderbookParams:
    return OrderbookParams(
        maker_fee_rate=Decimal("0.0002"),
        taker_fee_rate=Decimal("0.0005"),
        min_order_notional=10,
        max_open_orders_per_user=500,
        rate_limit_per_block=rate_limit,
        short_term_enabled=True,
        short_term_order_ttl_blocks=20,
        short_term_per_block_limit=500,
        short_term_max_gas_wanted=1_000_000,
        trading_halted=False,
        min_gas_price=Decimal(0),
        max_gas_wanted=0,
    )


def chain_order(
    order_id: int,
    status: str = "OPEN",
    client_id: int = 0,
    pair: str = "BTC/USDC",
    quantity: str = "0.01",
    filled: str = "0",
) -> Order:
    return Order(
        order_id=order_id,
        pair=pair,
        side="BUY",
        order_type="LIMIT",
        status=status,
        price=Decimal(65000),
        quantity=Decimal(quantity),
        filled_quantity=Decimal(filled),
        leverage=Decimal(3),
        time_in_force="GTC",
        reduce_only=False,
        post_only=False,
        client_id=client_id,
        flags=0,
        good_til_block=0,
        subaccount_id=0,
        band_state="",
        agent_key_id=0,
        block_height=100,
    )


def chain_position(pair: str = "BTC/USDC", side: str = "SHORT", quantity: str = "0.2") -> Position:
    return Position(
        position_id=1,
        pair=pair,
        side=side,
        status="OPEN",
        quantity=Decimal(quantity),
        entry_price=Decimal(65000),
        leverage=Decimal(3),
        initial_margin=Decimal(4000),
        margin_type="CROSS",
        subaccount_id=0,
        unrealized_pnl=Decimal("-1.5"),
        maintenance_margin=None,
        mark_price=Decimal(65010),
        liquidation_price=None,
        liquidation_reachable=None,
    )


def order_json(
    order_id: int,
    status: str = "OPEN",
    filled: str = "0",
    client_id: Optional[int] = None,
    quantity: str = "0.01",
) -> Dict[str, Any]:
    return {
        "id": order_id,
        "client_id": client_id,
        "subaccount_id": 0,
        "pair": "BTCUSDC",
        "side": "BUY",
        "type": "LIMIT",
        "status": status,
        "price": "65000",
        "quantity": quantity,
        "filled": filled,
        "time_in_force": "GTC",
        "block_height": 100,
        "time": BLOCK_TIME,
        "updated_at": BLOCK_TIME,
    }


def fill_json(
    fill_id: str,
    order_id: int,
    quantity: str = "0.01",
    role: Optional[str] = None,
    price: str = "65000",
    time: str = BLOCK_TIME,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": fill_id,
        "pair": "BTCUSDC",
        "side": "BUY",
        "price": price,
        "quantity": quantity,
        "fee": FILL_FEE,
        "order_id": order_id,
        "subaccount_id": 0,
        "block_height": 101,
        "time": time,
    }
    if role is not None:
        payload["role"] = role
    return payload


def frame(channel: str, data: Any, frame_type: str = "snapshot", stream_id: str = ACCOUNT) -> Dict[str, Any]:
    return {"type": frame_type, "channel": channel, "id": stream_id, "seq": 1, "ts": BLOCK_TIME, "data": data}


class FakeDataSource:
    def __init__(self) -> None:
        self.network = NETWORK
        self.account_address = ACCOUNT
        self.subaccount_id = 0
        self.client_ids = ClientIdAllocator(start=100)
        self.markets_result: Tuple[Market, ...] = (market(), market("ETH/USDC", tick="0.01"), market("OLD/USDC", "DELISTED"))
        self.params = orderbook_params()
        self.open_orders_result: Tuple[Order, ...] = ()
        self.orders: Dict[int, Order] = {}
        self.order_lookups: List[int] = []
        self.balance_result = SubaccountBalance(
            subaccount_id=0,
            denom="ibc/USDC",
            total=Decimal(1000),
            locked=Decimal(0),
            available=Decimal(900),
            withdrawable=Decimal(900),
            margin_in_positions=Decimal(100),
            unrealized_pnl=Decimal(0),
            equity=Decimal(1000),
            maintenance_required=Decimal(10),
            open_positions_count=1,
            locked_orders_count=0,
        )
        self.positions_result: Tuple[Position, ...] = ()
        self.fee_tier_result = FeeTier(
            tier_index=1,
            maker_fee_rate=Decimal(0),
            taker_fee_rate=Decimal("0.0004"),
            trailing_volume=0,
            pending_volume=0,
            has_next_tier=True,
            next_threshold=0,
            volume_to_next=0,
        )
        self.placed: List[OrderRequest] = []
        self.place_result = PlacedOrder(order_id=555, status="OPEN", filled=Decimal(0))
        self.cancelled: List[int] = []
        self.cancel_outcome = CancelOutcome.CANCELLED
        self.cancel_outcomes: Dict[int, CancelOutcome] = {}
        self.place_error: Optional[Exception] = None
        self.cancel_errors: Dict[int, Exception] = {}
        self.order_error: Optional[Exception] = None
        self.markets_error: Optional[Exception] = None
        self.on_place: Optional[Callable[[], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None
        self.on_order: Optional[Callable[[], None]] = None
        self.started = False
        self.start_calls = 0
        self.node_checks = 0

    @property
    def trading_ready(self) -> bool:
        return self.started

    async def start_trading(self) -> None:
        self.start_calls += 1
        self.started = True

    async def stop(self) -> None:
        self.started = False

    async def close(self) -> None:
        await self.stop()

    async def check_node(self) -> int:
        self.node_checks += 1
        return 1000

    async def markets(self) -> Tuple[Market, ...]:
        if self.markets_error is not None:
            raise self.markets_error
        return self.markets_result

    async def orderbook_params(self, refresh: bool = False) -> OrderbookParams:
        return self.params

    async def open_orders(self) -> Tuple[Order, ...]:
        return self.open_orders_result

    async def order(self, order_id: int) -> Optional[Order]:
        self.order_lookups.append(order_id)
        self._notify(self.on_order)
        if self.order_error is not None:
            raise self.order_error
        return self.orders.get(order_id)

    async def balance(self) -> SubaccountBalance:
        return self.balance_result

    async def positions(self) -> Tuple[Position, ...]:
        return self.positions_result

    async def fee_tier(self) -> FeeTier:
        return self.fee_tier_result

    async def place(self, request: OrderRequest) -> PlacedOrder:
        self.placed.append(request)
        self._notify(self.on_place)
        if self.place_error is not None:
            raise self.place_error
        return self.place_result

    async def cancel(self, order_id: int) -> CancelledOrder:
        self.cancelled.append(order_id)
        self._notify(self.on_cancel)
        if order_id in self.cancel_errors:
            raise self.cancel_errors[order_id]
        return CancelledOrder(order_id=order_id, outcome=self.cancel_outcomes.get(order_id, self.cancel_outcome))

    @staticmethod
    def _notify(callback: Optional[Callable[[], None]]) -> None:
        if callback is not None:
            callback()
