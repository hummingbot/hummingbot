import unittest
import asyncio
import time
from threading import Thread
from aiohttp import web
from aiohttp.web_app import Application
from decimal import Decimal
from hummingbot.data_feed.custom_api_data_feed import CustomAPIDataFeed
from hummingbot.core.network_base import NetworkStatus
from multiprocessing import Process


def async_run(func):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(func)


class SimpleWebApp:
    @classmethod
    def api_url(cls):
        return "http://localhost:16233/"

    _shared_instance: "SimpleWebApp" = None

    @classmethod
    def get_instance(cls) -> "SimpleWebApp":
        if cls._shared_instance is None:
            cls._shared_instance = SimpleWebApp()
        return cls._shared_instance

    def __init__(self, response_price=1, to_return_404=False):
        self._price = response_price
        self._app = None
        self.loop = None
        self._to_return_404 = to_return_404

    def set_params(self, response_price, to_return_404=False):
        self._price = response_price
        self._to_return_404 = to_return_404

    async def price_response(self, request):
        if self._to_return_404:
            return web.HTTPFound('/redirect')
        else:
            return web.Response(text=str(self._price))

    def start_web_app(self):
        self.loop = asyncio.get_event_loop()
        asyncio.set_event_loop(self.loop)
        self._app = web.Application(loop=self.loop)
        self._app.add_routes([web.get('/', self.price_response)])
        web.run_app(self._app, port=16233)

    def start(self):
        p = Process(target=self.start_web_app)
        p.daemon = True
        p.start()
        time.sleep(2)
        return p

    def stop(self):
        async_run(self._app.shutdown())


class CustomAPIFeedUnitTest(unittest.TestCase):

    def test_fetch_price(self):
        SimpleWebApp.get_instance().set_params(1, False)
        p = SimpleWebApp.get_instance().start()
        api_feed = CustomAPIDataFeed(api_url=SimpleWebApp.api_url())
        api_feed.start()
        async_run(api_feed.check_network())
        self.assertTrue(api_feed.network_status == NetworkStatus.CONNECTED)
        price = api_feed.get_price()
        self.assertEqual(price, 1)
        p.terminate()

    def test_fetch_server_error(self):
        SimpleWebApp.get_instance().set_params(1, True)
        p = SimpleWebApp.get_instance().start()
        api_feed = CustomAPIDataFeed(api_url=SimpleWebApp.api_url())
        api_feed.start()
        with self.assertRaises(Exception) as context:
            async_run(api_feed.check_network())
        self.assertTrue('server error:' in str(context.exception))
        p.terminate()


if __name__ == "__main__":
    unittest.main()
