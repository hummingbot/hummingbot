import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, patch

from hummingbot.notifier.notifier_base import NotifierBase


class TestNotifierBase(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

    @patch.object(NotifierBase, "_send_message", new_callable=AsyncMock)
    async def test_notifier_base(self, send_message_mock):
        """
        Unit tests for hummingbot.notifier.notifier_base.NotifierBase
        """
        # create a NotifierBase instance
        notifier_base = NotifierBase()
        notifier_base._sleep = AsyncMock()
        send_message_mock.side_effect = [None, Exception("test exception"), asyncio.CancelledError]

        # test start
        notifier_base.start()
        await asyncio.sleep(0.001)
        self.assertTrue(notifier_base._send_message_task)

        # test stop
        notifier_base.stop()
        await asyncio.sleep(0.001)
        self.assertFalse(notifier_base._send_message_task)

        # test send_message_from_queue
        notifier_base.start()
        # first message
        notifier_base.add_message_to_queue("test message")
        self.assertEqual(notifier_base._message_queue.qsize(), 1)
        await asyncio.sleep(0.001)
        self.assertEqual(notifier_base._message_queue.qsize(), 0)
        notifier_base.add_message_to_queue("test message 2")
        notifier_base.add_message_to_queue("test message 3")
        await asyncio.sleep(0.001)
        await asyncio.sleep(0.001)
        self.assertEqual(notifier_base._message_queue.qsize(), 0)
        notifier_base.stop()
