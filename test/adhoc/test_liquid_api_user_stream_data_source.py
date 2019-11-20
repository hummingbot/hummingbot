import asyncio
import concurrent
import inspect
import os

from unittest import TestCase
from hummingbot.market.liquid.liquid_auth import LiquidAuth
from hummingbot.market.liquid.liquid_api_user_stream_data_source import LiquidAPIUserStreamDataSource

PATCH_BASE_PATH = \
    'hummingbot.market.liquid.liquid_api_user_stream_data_source.LiquidAPIUserStreamDataSource.{method}'

liquid_api_key = os.environ.get('LIQUID_API_KEY')
liquid_secret_key = os.environ.get('LIQUID_SECRET_KEY')


class TestLiquidAPIUserStreamDataSource(TestCase):

    def test_listen_for_user_stream(self):
        timeout = 5
        q = asyncio.Queue()
        loop = asyncio.get_event_loop()

        user_stream_ds = LiquidAPIUserStreamDataSource(
            liquid_auth=LiquidAuth(
                api_key=liquid_api_key,
                secret_key=liquid_secret_key
            ),
            symbols=['LCXBTC', 'ETHUSD']
        )

        print('{class_name} test {test_name} is going to run for {timeout} seconds, starting now'.format(
            class_name=self.__class__.__name__,
            test_name=inspect.stack()[0][3],
            timeout=timeout))

        try:
            loop.run_until_complete(
                # Force exit from event loop after set timeout seconds
                asyncio.wait_for(
                    user_stream_ds.listen_for_user_stream(
                        ev_loop=loop, output=q),
                    timeout=timeout
                )
            )
        except concurrent.futures.TimeoutError as e:
            print(e)
