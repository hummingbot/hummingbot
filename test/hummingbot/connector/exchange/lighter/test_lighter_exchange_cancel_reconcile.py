import asyncio
import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

try:
    from hummingbot.connector.exchange.lighter.lighter_exchange import LighterExchange
    from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate
    _LIGHTER_EXCHANGE_AVAILABLE = True
except ModuleNotFoundError:
    _LIGHTER_EXCHANGE_AVAILABLE = False


@unittest.skipUnless(_LIGHTER_EXCHANGE_AVAILABLE, "Core exchange runtime modules are unavailable in this local environment")
class LighterExchangeCancelReconcileTests(IsolatedAsyncioWrapperTestCase):
    async def test_execute_order_cancel_reconciles_code_5_to_canceled(self):
        exchange = LighterExchange.__new__(LighterExchange)

        order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-1",
                "exchange_order_id": "100",
                "trading_pair": "LINK-USDC",
            },
        )()

        exchange._place_cancel = AsyncMock(side_effect=IOError('{"success":false,"error":"Failed to cancel order","code":5}'))
        exchange._request_order_status = AsyncMock(
            return_value=OrderUpdate(
                client_order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
                trading_pair=order.trading_pair,
                update_timestamp=1.0,
                new_state=OrderState.CANCELED,
            )
        )

        processed_updates = []

        class Tracker:
            def process_order_update(self, update):
                processed_updates.append(update)

            async def process_order_not_found(self, client_order_id):
                _ = client_order_id

        exchange._order_tracker = Tracker()
        exchange.logger = MagicMock(return_value=MagicMock())

        result = await exchange._execute_order_cancel(order)

        self.assertEqual(order.client_order_id, result)
        self.assertEqual(1, len(processed_updates))
        self.assertEqual(OrderState.CANCELED, processed_updates[0].new_state)

    async def test_execute_order_cancel_keeps_tracking_when_reconcile_open(self):
        exchange = LighterExchange.__new__(LighterExchange)

        order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-2",
                "exchange_order_id": "101",
                "trading_pair": "LINK-USDC",
            },
        )()

        exchange._place_cancel = AsyncMock(side_effect=IOError('{"success":false,"error":"Failed to cancel order","code":5}'))
        exchange._request_order_status = AsyncMock(
            return_value=OrderUpdate(
                client_order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
                trading_pair=order.trading_pair,
                update_timestamp=1.0,
                new_state=OrderState.OPEN,
            )
        )

        class Tracker:
            def process_order_update(self, update):
                _ = update

            async def process_order_not_found(self, client_order_id):
                _ = client_order_id

        exchange._order_tracker = Tracker()
        exchange.logger = MagicMock(return_value=MagicMock())

        result = await exchange._execute_order_cancel(order)

        self.assertIsNone(result)

    async def test_execute_order_cancel_timeout_keeps_tracking_and_schedules_reconcile(self):
        exchange = LighterExchange.__new__(LighterExchange)

        order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-3",
                "exchange_order_id": None,
                "trading_pair": "UNI-USDC",
            },
        )()

        exchange._execute_order_cancel_and_process_update = AsyncMock(side_effect=asyncio.TimeoutError())
        exchange._schedule_unmatched_private_event_reconcile = MagicMock()

        class Tracker:
            async def process_order_not_found(self, client_order_id):
                _ = client_order_id

        exchange._order_tracker = Tracker()
        exchange.logger = MagicMock(return_value=MagicMock())

        result = await exchange._execute_order_cancel(order)

        self.assertIsNone(result)
        exchange._schedule_unmatched_private_event_reconcile.assert_called_once()
