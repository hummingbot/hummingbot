import unittest
import asyncio
import time
from threading import Thread
from aiohttp import web
from aiohttp.web_app import Application
from decimal import Decimal
from hummingbot.data_feed.custom_api_data_feed import CustomAPIDataFeed
from hummingbot.core.network_base import NetworkStatus


def async_run(func):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(func)


_price = Decimal("1.00")
_app = None


async def price_response(request):
    global _price
    _price += Decimal("0.01")
    return web.Response(text=str(_price))


def start_simple_web_app():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _app = web.Application(loop=loop)
    _app.add_routes([web.get('/', price_response)])
    web.run_app(_app)


def stop_web_app():
    async_run(_app.shutdown())


class CustomAPIFeedUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        thread = Thread(target=start_simple_web_app)
        thread.daemon = True
        thread.start()
        time.sleep(1)

    @classmethod
    def tearDown(cls):
        if _app is not None:
            stop_web_app()

    def test_fetch_price(self):
        api_feed = CustomAPIDataFeed(api_url="http://localhost:8080/")
        api_feed.start()
        async_run(api_feed.get_ready())
        self.assertTrue(api_feed.network_status == NetworkStatus.CONNECTED)
        price = api_feed.get_price()
        self.assertGreater(price, 1)


if __name__ == "__main__":
    unittest.main()
