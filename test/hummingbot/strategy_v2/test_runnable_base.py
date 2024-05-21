import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest

from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.runnable_base import RunnableBase


class TestRunnableBase(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
    def setUp(self):
        self.component = RunnableBase(update_interval=0.1)
        self.set_loggers(loggers=[self.component.logger()])

    async def test_start_and_stop_executor(self):
        self.component.start()
        self.assertEqual(RunnableStatus.RUNNING, self.component.status)
        self.component.stop()
        self.assertEqual(RunnableStatus.TERMINATED, self.component.status)

    async def test_executor_raises_exception(self):
        async def raise_exception():
            raise Exception("Test")

        self.component.control_task = raise_exception
        self.component.start()
        await asyncio.sleep(0.05)
        self.is_logged("Test", "error")
