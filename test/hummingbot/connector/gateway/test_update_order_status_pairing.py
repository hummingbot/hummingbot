import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hummingbot.connector.gateway.gateway_base import GatewayBase
from hummingbot.core.data_type.common import TradeType

T0 = 1640000000.0


class Conn(GatewayBase):
    def __init__(self, chain="solana"):
        super().__init__(
            connector_name="test_connector", chain=chain, network="mainnet-beta",
            address="addr", trading_pairs=["SOL-USDC"], trading_required=True,
        )
        self._native_currency = "SOL"

    @property
    def name(self):
        return "test"


@pytest.fixture
def loop():
    lp = asyncio.new_event_loop()
    asyncio.set_event_loop(lp)
    yield lp
    lp.close()


def make(chain="solana", ids=("A",)):
    c = Conn(chain)
    c._set_current_timestamp(T0)
    for i in ids:
        c.start_tracking_order(order_id=i, exchange_order_id=i * 88, trading_pair="SOL-USDC",
                               trade_type=TradeType.BUY, price=Decimal("100"), amount=Decimal("1"))
    return c


def poll(loop, c, orders, status_by_hash):
    gw = MagicMock()

    async def gts(chain, network, tx_hash):
        return {"signature": tx_hash, "txStatus": status_by_hash[tx_hash], "fee": 0}

    gw.get_transaction_status = AsyncMock(side_effect=gts)
    with patch.object(Conn, "_get_gateway_instance", return_value=gw):
        loop.run_until_complete(asyncio.wait_for(c.update_order_status(orders), 2))


def misses(c, oid):
    return c._order_tracker._order_not_found_records[oid]


def test_hash_failure_does_not_shift_results(loop):
    c = make(ids=("A", "B"))
    c._set_current_timestamp(T0 + c.TX_NOT_FOUND_DEADLINE + 1)
    a = c._order_tracker.fetch_tracked_order("A")
    b = c._order_tracker.fetch_tracked_order("B")
    a.get_exchange_order_id = AsyncMock(side_effect=Exception("no hash"))
    poll(loop, c, [a, b], {b.exchange_order_id: -2})
    assert misses(c, "A") == 0
    assert misses(c, "B") == 1
