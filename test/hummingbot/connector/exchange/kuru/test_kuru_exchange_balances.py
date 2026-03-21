import time
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.in_flight_order import OrderState

from .test_kuru_exchange_base import KuruExchangeTestBase


class TestKuruExchangeBalances(KuruExchangeTestBase, IsolatedAsyncioTestCase):

    async def test_update_balances_converts_margin_and_locks_open_orders(self):
        self.client.user.get_margin_balances = AsyncMock(
            return_value=(2 * 10**18, 100 * 10**6)
        )
        buy_order = self.make_order(
            client_order_id="BUY-1",
            price=Decimal("2"),
            amount=Decimal("10"),
            executed_amount_base=Decimal("3"),
        )
        sell_order = self.make_order(
            client_order_id="SELL-1",
            trade_type=TradeType.SELL,
            amount=Decimal("5"),
            executed_amount_base=Decimal("1"),
        )
        self.connector._order_tracker.active_orders = {
            buy_order.client_order_id: buy_order,
            sell_order.client_order_id: sell_order,
        }

        await self.connector._update_balances()

        self.assertEqual(Decimal("2"), self.connector._account_balances["MON"])
        self.assertEqual(Decimal("100"), self.connector._account_balances["USDC"])
        self.assertEqual(Decimal("0"), self.connector._account_available_balances["MON"])
        self.assertEqual(Decimal("86"), self.connector._account_available_balances["USDC"])

    def test_expire_ghost_orders_only_marks_old_unmapped_orders(self):
        old_ghost = self.make_order(client_order_id="old-ghost", creation_timestamp=time.time() - 120)
        young_ghost = self.make_order(client_order_id="young-ghost", creation_timestamp=time.time())
        mapped_order = self.make_order(client_order_id="mapped", creation_timestamp=time.time() - 120)
        done_order = self.make_order(
            client_order_id="done",
            creation_timestamp=time.time() - 120,
            initial_state=OrderState.FAILED,
        )
        self.connector._order_tracker.active_orders = {
            old_ghost.client_order_id: old_ghost,
            young_ghost.client_order_id: young_ghost,
            mapped_order.client_order_id: mapped_order,
            done_order.client_order_id: done_order,
        }
        self.client.orders_manager.get_kuru_order_id.side_effect = lambda client_order_id: {
            "old-ghost": None,
            "young-ghost": None,
            "mapped": 77,
            "done": None,
        }[client_order_id]

        self.connector._expire_ghost_orders()

        self.connector._order_tracker.process_order_update.assert_called_once()
        update = self.connector._order_tracker.process_order_update.call_args.args[0]
        self.assertEqual("old-ghost", update.client_order_id)
        self.assertEqual(OrderState.FAILED, update.new_state)

    def test_mark_ghost_orders_failed_only_marks_unmapped_active_orders(self):
        old_ghost = self.make_order(client_order_id="old-ghost")
        mapped_order = self.make_order(client_order_id="mapped")
        self.connector._order_tracker.active_orders = {
            old_ghost.client_order_id: old_ghost,
            mapped_order.client_order_id: mapped_order,
        }
        self.client.orders_manager.get_kuru_order_id.side_effect = lambda client_order_id: {
            "old-ghost": None,
            "mapped": 12,
        }[client_order_id]

        self.connector._mark_ghost_orders_failed()

        self.connector._order_tracker.process_order_update.assert_called_once()
        update = self.connector._order_tracker.process_order_update.call_args.args[0]
        self.assertEqual("old-ghost", update.client_order_id)
        self.assertEqual(OrderState.FAILED, update.new_state)

    async def test_cancel_orders_without_kuru_mapping_on_startup_triggers_cancel_all(self):
        order = self.make_order(client_order_id="ghost")
        self.connector._order_tracker.active_orders = {order.client_order_id: order}
        self.client.orders_manager.get_kuru_order_id.return_value = None
        self.connector._cancel_all_active_orders_for_market = AsyncMock(return_value=True)

        await self.connector._cancel_orders_without_kuru_mapping_on_startup()

        self.connector._cancel_all_active_orders_for_market.assert_awaited_once()

    async def test_cancel_orders_without_kuru_mapping_on_startup_skips_when_all_are_mapped(self):
        order = self.make_order(client_order_id="mapped")
        self.connector._order_tracker.active_orders = {order.client_order_id: order}
        self.client.orders_manager.get_kuru_order_id.return_value = 88
        self.connector._cancel_all_active_orders_for_market = AsyncMock(return_value=True)

        await self.connector._cancel_orders_without_kuru_mapping_on_startup()

        self.connector._cancel_all_active_orders_for_market.assert_not_awaited()
