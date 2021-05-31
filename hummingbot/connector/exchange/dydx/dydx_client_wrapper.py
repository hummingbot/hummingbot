import aiohttp
import asyncio
from functools import partial

from dydx.client import Client
from dydx.exceptions import DydxAPIError

BASE_URL = 'https://api.dydx.exchange'
FILLS_ROUTE = '/v2/fills'


class DydxAsyncAPIError(DydxAPIError):
    def __init__(self, status_code, msg):
        self.status_code = status_code
        self.msg = msg
        self.response = None
        self.request = None


class DYDXClientWrapper:
    def __init__(self, private_key, node, account_number):
        self.client = Client(private_key = private_key,
                             node = node,
                             account_number = account_number)
        self._loop = asyncio.get_event_loop()

    async def place_order(self, market, side, amount, price, fillOrKill, postOnly, clientId):
        f = self._loop.run_in_executor(None, partial(self.client.place_order,
                                                     market = market,
                                                     side = side,
                                                     amount = amount,
                                                     price = price,
                                                     fillOrKill = fillOrKill,
                                                     postOnly = postOnly,
                                                     clientId = clientId))
        return await f

    async def cancel_order(self, exchange_order_id):
        f = self._loop.run_in_executor(None, self.client.cancel_order, exchange_order_id)
        return await f

    async def get_my_balances(self):
        f = self._loop.run_in_executor(None, self.client.get_my_balances)
        return await f

    async def get_order(self, exchange_order_id):
        f = self._loop.run_in_executor(None, self.client.get_order, exchange_order_id)
        return await f

    async def get_markets(self):
        f = self._loop.run_in_executor(None, self.client.get_markets)
        return await f

    async def get_fills(self, exchange_order_id):
        async with aiohttp.ClientSession() as client:
            response: aiohttp.ClientResponse = await client.get(
                f"{BASE_URL}{FILLS_ROUTE}",
                params={
                    'orderId': exchange_order_id,
                    'limit': 100
                }
            )

            if response.status >= 300:
                try:
                    msg = await response.json()
                except ValueError:
                    msg = await response.text()
                raise DydxAsyncAPIError(response.status, msg)

            return await response.json()
