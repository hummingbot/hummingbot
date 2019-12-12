import unittest
import asyncio
import time
from threading import Thread
from aiohttp import web
from decimal import Decimal
from hummingbot.data_feed.custom_api_data_feed import CustomAPIFeed

_price = Decimal("1.00")


async def price_response(request):
    global _price
    _price += Decimal("0.01")
    return web.Response(text=str(_price))


def start_simple_web_app():
    app = web.Application()
    app.add_routes([web.get('/', price_response)])
    web.run_app(app)


def async_run(func):
    loop = asyncio.new_event_loop()
    loop.run_until_complete(func)


class CustomAPIFeedUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wst = Thread(target=start_simple_web_app)
        wst.start()
        time.sleep(1000)

    def test_fetch_price(self):
        api_feed = CustomAPIFeed(api_url="http://localhost:8080/")
        self.assertEqual(api_feed.get_price(), Decimal("1.01"))


if __name__ == "__main__":
    unittest.main()
