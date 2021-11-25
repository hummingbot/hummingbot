import asyncio
import datetime

from functools import partial

from dydx3 import Client
from dydx3.errors import DydxApiError

BASE_URL = 'https://api.dydx.exchange'
FILLS_ROUTE = '/v2/fills'


class DydxPerpetualAsyncAPIError(DydxApiError):
    def __init__(self, status_code, msg):
        self.status_code = status_code
        self.msg = msg
        self.response = None
        self.request = None


class DydxPerpetualClientWrapper:
    def __init__(self, api_key, api_secret, passphrase, account_number, stark_private_key, ethereum_address):
        self._api_credentials = {'key': api_key,
                                 'secret': api_secret,
                                 'passphrase': passphrase}
        self.client = Client(host = BASE_URL,
                             api_key_credentials = self._api_credentials,
                             stark_private_key = stark_private_key)
        self._loop = asyncio.get_event_loop()
        self._ethereum_address = ethereum_address
        self._account_number = account_number

    @property
    def api_credentials(self):
        return self._api_credentials

    @property
    def account_number(self):
        return self._account_number

    async def place_order(self, market, side, amount, price, order_type, postOnly, clientId, limit_fee, expiration):
        account = await self.get_account()
        dydx_client_id = 10 * int("".join([n for n in clientId if n.isdigit()]))
        if side == 'SELL':
            dydx_client_id += 1
        time_in_force = 'IOC' if order_type == 'MARKET' else 'GTT'
        trailing_percent = 0 if order_type == 'MARKET' else None

        f = self._loop.run_in_executor(None, partial(self.client.private.create_order,
                                                     position_id=account['account']['positionId'],
                                                     market=market,
                                                     side=side,
                                                     size=amount,
                                                     price=price,
                                                     order_type=order_type,
                                                     post_only=postOnly,
                                                     client_id=str(dydx_client_id),
                                                     limit_fee=limit_fee,
                                                     expiration_epoch_seconds=expiration,
                                                     time_in_force=time_in_force,
                                                     trailing_percent=trailing_percent))
        return await f

    async def cancel_order(self, exchange_order_id):
        f = self._loop.run_in_executor(None, partial(self.client.private.cancel_order,
                                                     order_id=exchange_order_id))
        return await f

    async def get_my_balances(self):
        f = self._loop.run_in_executor(None, partial(self.client.private.get_account,
                                                     ethereum_address=self._ethereum_address))
        return await f

    async def get_my_positions(self):
        f = self._loop.run_in_executor(None, self.client.private.get_positions)
        return await f

    async def get_order(self, exchange_order_id):
        f = self._loop.run_in_executor(None, partial(self.client.private.get_order_by_id,
                                                     order_id=exchange_order_id))
        return await f

    async def get_markets(self):
        f = self._loop.run_in_executor(None, self.client.public.get_markets)
        return await f

    async def get_fills(self, exchange_order_id):
        f = self._loop.run_in_executor(None, partial(self.client.private.get_fills,
                                                     order_id=exchange_order_id,
                                                     limit=100))
        return await f

    async def get_account(self):
        f = self._loop.run_in_executor(None, partial(self.client.private.get_account,
                                                     ethereum_address=self._ethereum_address))
        return await f

    async def get_funding_payments(self, market: str, before_ts: float):
        iso_ts = datetime.datetime.utcfromtimestamp(before_ts).isoformat()
        f = self._loop.run_in_executor(None, partial(self.client.private.get_funding_payments,
                                                     market=market,
                                                     limit=100,
                                                     effective_before_or_at=iso_ts
                                                     ))
        return await f

    async def get_server_time(self):
        f = self._loop.run_in_executor(None, self.client.public.get_time)
        return await f

    def sign(self, request_path, method, timestamp, data):
        sign = self.client.private.sign(request_path=request_path,
                                        method=method,
                                        iso_timestamp=timestamp,
                                        data=data)
        return sign
