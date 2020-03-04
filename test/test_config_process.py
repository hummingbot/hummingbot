#!/usr/bin/env python
from os.path import (
    join,
    realpath,
)
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))
import sys; sys.path.append(realpath(join(__file__, "../../bin")))
import unittest
from hummingbot.client.hummingbot_application import HummingbotApplication
from bin.hummingbot import main
import asyncio


class HummingBotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.new_event_loop()

    async def _test_main(self):
        asyncio.ensure_future(main())
        await asyncio.sleep(5)
        HummingbotApplication.main_application()._handle_command("config")
        await asyncio.sleep(50)

    def test_main(self):
        self.ev_loop.run_until_complete(self._test_main())


def suite():
    suite = unittest.TestSuite()
    suite.addTest(HummingBotTest('test_main'))
    return suite


if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    runner.run(suite())
