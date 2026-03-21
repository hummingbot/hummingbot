import time
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.kuru.kuru_exchange import (
    OrderState,
    OrderType,
    SdkOrderSide,
    SdkOrderStatus,
    SdkOrderType,
    TradeType,
)

from .test_kuru_exchange_base import KuruExchangeTestBase


class TestKuruExchangeOrders(KuruExchangeTestBase, IsolatedAsyncioTestCase):

    @patch("hummingbot.connector.exchange.kuru.kuru_exchange.SdkOrder")
    async def test_place_order_builds_sdk_limit_order(self, sdk_order_cls):
        sdk_order_instance = MagicMock()
        sdk_order_cls.return_value = sdk_order_instance

        exchange_order_id, timestamp = await self.connector._place_order(
            order_id="OID-1",
            trading_pair=self.trading_pair,
            amount=Decimal("3.5"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("12.25"),
        )

        sdk_order_cls.assert_called_once_with(
            cloid="OID-1",
            order_type=SdkOrderType.LIMIT,
            side=SdkOrderSide.BUY,
            price=12.25,
            size=3.5,
            post_only=True,
        )
        self.assertEqual("0xtxhash", exchange_order_id)
        self.assertGreater(timestamp, 0)
        self.client.place_orders.assert_awaited_once_with([sdk_order_instance])

    async def test_place_cancel_skips_terminal_order(self):
        tracked_order = self.make_order(initial_state=OrderState.FILLED)

        cancelled = await self.connector._place_cancel("OID-1", tracked_order)

        self.assertTrue(cancelled)
        self.client.orders_manager.get_kuru_order_id.assert_not_called()

    @patch("hummingbot.connector.exchange.kuru.kuru_exchange.SdkOrder")
    async def test_place_cancel_uses_kuru_order_id_mapping(self, sdk_order_cls):
        sdk_order_instance = MagicMock()
        sdk_order_cls.return_value = sdk_order_instance
        self.client.orders_manager.get_kuru_order_id.return_value = 1234
        tracked_order = self.make_order()

        cancelled = await self.connector._place_cancel("OID-1", tracked_order)

        self.assertTrue(cancelled)
        sdk_order_cls.assert_called_once_with(
            cloid="OID-1",
            order_type=SdkOrderType.CANCEL,
            order_ids_to_cancel=[1234],
        )
        self.client.place_orders.assert_awaited_once_with([sdk_order_instance])

    async def test_place_cancel_falls_back_to_cancel_all_when_mapping_missing(self):
        tracked_order = self.make_order()
        self.connector._cancel_all_active_orders_for_market = AsyncMock(return_value=True)

        cancelled = await self.connector._place_cancel("OID-1", tracked_order)

        self.assertTrue(cancelled)
        self.connector._cancel_all_active_orders_for_market.assert_awaited_once()

    async def test_process_sdk_order_event_ignores_cancel_type_event(self):
        tracked_order = self.make_order()
        self.connector._order_tracker.fetch_order.return_value = tracked_order
        sdk_order = self.make_sdk_order(
            status=SdkOrderStatus.ORDER_CANCELLED,
            order_type=SdkOrderType.CANCEL,
        )

        await self.connector._process_sdk_order_event(sdk_order)

        self.connector._order_tracker.process_order_update.assert_not_called()

    async def test_process_sdk_order_event_ignores_unknown_order(self):
        sdk_order = self.make_sdk_order(
            status=SdkOrderStatus.ORDER_PLACED,
            order_type=SdkOrderType.LIMIT,
        )

        await self.connector._process_sdk_order_event(sdk_order)

        self.connector._order_tracker.process_order_update.assert_not_called()

    async def test_process_sdk_order_event_updates_states(self):
        cases = [
            (SdkOrderStatus.ORDER_PLACED, OrderState.OPEN),
            (SdkOrderStatus.ORDER_CANCELLED, OrderState.CANCELED),
            (SdkOrderStatus.ORDER_TIMEOUT, OrderState.FAILED),
            (SdkOrderStatus.ORDER_FAILED, OrderState.FAILED),
        ]

        for status, expected_state in cases:
            with self.subTest(status=status):
                self.connector._order_tracker.process_order_update.reset_mock()
                tracked_order = self.make_order(exchange_order_id="pending-id")
                self.connector._order_tracker.fetch_order.return_value = tracked_order
                sdk_order = self.make_sdk_order(
                    status=status,
                    order_type=SdkOrderType.LIMIT,
                    kuru_order_id=88,
                )

                await self.connector._process_sdk_order_event(sdk_order)

                order_update = self.connector._order_tracker.process_order_update.call_args.args[0]
                self.assertEqual(expected_state, order_update.new_state)
                if status == SdkOrderStatus.ORDER_PLACED:
                    self.assertEqual("88", order_update.exchange_order_id)
                else:
                    self.assertEqual("pending-id", order_update.exchange_order_id)

    async def test_process_sdk_order_event_processes_partial_and_full_fills(self):
        tracked_order = self.make_order(exchange_order_id="77")
        self.connector._order_tracker.fetch_order.return_value = tracked_order
        self.connector._process_fills = MagicMock()

        for status, expected_state in (
            (SdkOrderStatus.ORDER_PARTIALLY_FILLED, OrderState.PARTIALLY_FILLED),
            (SdkOrderStatus.ORDER_FULLY_FILLED, OrderState.FILLED),
        ):
            with self.subTest(status=status):
                self.connector._order_tracker.process_order_update.reset_mock()
                sdk_order = self.make_sdk_order(
                    status=status,
                    order_type=SdkOrderType.LIMIT,
                    filled_sizes=[1.0],
                )

                await self.connector._process_sdk_order_event(sdk_order)

                self.connector._process_fills.assert_called_with(sdk_order, tracked_order)
                order_update = self.connector._order_tracker.process_order_update.call_args.args[0]
                self.assertEqual(expected_state, order_update.new_state)

    def test_process_fills_only_emits_new_fills(self):
        tracked_order = self.make_order(
            price=Decimal("10"),
            order_fills={"OID-1_0": self.existing_fill()},
        )
        sdk_order = self.make_sdk_order(
            filled_sizes=[1.0, 2.0],
            kuru_order_id=77,
        )

        self.connector._process_fills(sdk_order, tracked_order)

        self.connector._order_tracker.process_trade_update.assert_called_once()
        trade_update = self.connector._order_tracker.process_trade_update.call_args.args[0]
        self.assertEqual("OID-1_1", trade_update.trade_id)
        self.assertEqual(Decimal("2.0"), trade_update.fill_base_amount)
        self.assertEqual(Decimal("20.0"), trade_update.fill_quote_amount)
        self.assertEqual(Decimal("0"), trade_update.fee.percent)
        self.assertFalse(trade_update.is_taker)

    async def test_request_order_status_returns_sdk_status_and_exchange_id(self):
        tracked_order = self.make_order(initial_state=OrderState.PENDING_CREATE, exchange_order_id="temp-id")
        sdk_order = self.make_sdk_order(
            status=SdkOrderStatus.ORDER_PLACED,
            kuru_order_id=999,
        )
        self.client.orders_manager.cloid_to_order = {"OID-1": sdk_order}

        status_update = await self.connector._request_order_status(tracked_order)

        self.assertEqual(OrderState.OPEN, status_update.new_state)
        self.assertEqual("999", status_update.exchange_order_id)

    async def test_request_order_status_keeps_recent_missing_order_state(self):
        tracked_order = self.make_order(
            initial_state=OrderState.PENDING_CREATE,
            creation_timestamp=time.time(),
            exchange_order_id="temp-id",
        )
        self.client.orders_manager.cloid_to_order = {}

        status_update = await self.connector._request_order_status(tracked_order)

        self.assertEqual(OrderState.PENDING_CREATE, status_update.new_state)
        self.assertEqual("temp-id", status_update.exchange_order_id)

    async def test_request_order_status_raises_for_old_missing_order(self):
        tracked_order = self.make_order(
            creation_timestamp=time.time() - 120,
            exchange_order_id="temp-id",
        )
        self.client.orders_manager.cloid_to_order = {}

        with self.assertRaises(Exception):
            await self.connector._request_order_status(tracked_order)

    async def test_all_trade_updates_for_order_returns_empty_when_missing(self):
        order = self.make_order()
        self.client.orders_manager.cloid_to_order = {}

        updates = await self.connector._all_trade_updates_for_order(order)

        self.assertEqual([], updates)

    async def test_all_trade_updates_for_order_builds_updates_for_all_sdk_fills(self):
        order = self.make_order(price=Decimal("7"), exchange_order_id="temp-id")
        sdk_order = self.make_sdk_order(
            filled_sizes=[1.0, 2.5],
            kuru_order_id=321,
        )
        self.client.orders_manager.cloid_to_order = {"OID-1": sdk_order}

        updates = await self.connector._all_trade_updates_for_order(order)

        self.assertEqual(2, len(updates))
        self.assertEqual("321", updates[0].exchange_order_id)
        self.assertEqual(Decimal("7.0"), updates[0].fill_quote_amount)
        self.assertEqual(Decimal("17.5"), updates[1].fill_quote_amount)
