import unittest
import asyncio
from aiohttp import web
from decimal import Decimal
from hummingbot.data_feed.custom_api_data_feed import CustomAPIFeed


class SimpleWebApp:
    def __init__(self, price = Decimal("0.1")):
        self._price = price
        self._app = web.Application()
        self._app.add_routes([web.get('/', price)])

    async def price(self, request):
        self._price += Decimal("0.01")
        return web.Response(text=str(self._price))

    def start(self):
        web.run_app(self._app)


def async_run(func):
    loop = asyncio.new_event_loop()
    loop.run_until_complete(func)


class CustomAPIFeedUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        web_app = SimpleWebApp(price=Decimal("0.1"))
        web_app.start()

    def test_fetch_price(self):
        api_feed = CustomAPIFeed(api_url="http://localhost:8080/")
        self.assertEqual(api_feed.get_price(), Decimal("0.1"))


if __name__ == "__main__":
    unittest.main()
