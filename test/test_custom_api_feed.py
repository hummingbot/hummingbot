import asyncio
from aiohttp import web
from aiohttp.test_utils import (
    AioHTTPTestCase,
    TestClient
)
from hummingbot.data_feed.custom_api_data_feed import CustomAPIDataFeed
from hummingbot.core.network_base import NetworkStatus


def async_run(func):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(func)


async def api_price(request):
    return web.Response(text='0.1')


class CustomAPIFeedUnitTest(AioHTTPTestCase):

    async def get_application(self):
        async def api_price(request):
            return web.Response(text='1')
        async def api_error(request):
            return web.HTTPFound('/redirect')
        app = web.Application()
        app.router.add_get('/', api_price)
        app.router.add_get('/error', api_error)
        return app

    def test_fetch_price(self):
        api_feed = CustomAPIDataFeed(api_url="/")
        api_feed._shared_client: TestClient = self.client
        api_feed.start()
        self.loop.run_until_complete(api_feed.check_network())
        self.loop.run_until_complete(api_feed.fetch_price())
        assert api_feed.network_status == NetworkStatus.CONNECTED
        price = api_feed.get_price()
        assert price == 1

    def test_fetch_server_error(self):
        api_feed = CustomAPIDataFeed(api_url="/error")
        api_feed._shared_client = self.client
        api_feed.start()
        with self.assertRaises(Exception) as context:
            async_run(api_feed.check_network())
        self.assertTrue('server error:' in str(context.exception))
