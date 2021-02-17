# -*- coding: utf-8 -*-

import logging
import base64
import random
import asyncio
from typing import Dict, Any, Optional
from time import monotonic

import aiohttp
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import HMAC, SHA384, SHA256

from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.logger import HummingbotLogger

from hummingbot.connector.exchange.beaxy.beaxy_constants import BeaxyConstants

s_logger = None

SAFE_TIME_PERIOD_SECONDS = 10
TOKEN_REFRESH_PERIOD_SECONDS = 10 * 60
MIN_TOKEN_LIFE_TIME_SECONDS = 30


class BeaxyAuth:

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self._session_data_cache: Dict[str, Any] = {}

        self.token: Optional[str] = None
        self.token_obtain = asyncio.Event()
        self.token_valid_to: float = 0
        self.token_next_refresh: float = 0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def is_token_valid(self):
        return self.token_valid_to > monotonic()

    def invalidate_token(self):
        self.token_valid_to = 0

    async def get_token(self):
        if self.is_token_valid():
            return self.token

        # token is invalid, waiting for a renew
        if not self.token_obtain.is_set():
            # if process of refreshing is not started, start it
            await self._update_token()
            return self.token

        # waiting for fresh token
        await self.token_obtain.wait()
        return self.token

    async def _update_token(self):

        self.token_obtain.clear()

        async with aiohttp.ClientSession() as client:
            async with client.post(
                    f'{BeaxyConstants.TradingApi.BASE_URL}{BeaxyConstants.TradingApi.TOKEN_ENDPOINT}',
                    json={'api_key_id': self.api_key, 'api_secret': self.api_secret}
            ) as response:
                response: aiohttp.ClientResponse = response
                if response.status != 200:
                    raise IOError(f'Error while connecting to login token endpoint. HTTP status is {response.status}.')
                data: Dict[str, str] = await response.json()

                if data['type'] != 'Bearer':
                    raise IOError(f'Error while connecting to login token endpoint. Token type is {data["type"]}.')

                if int(data['expires_in']) < MIN_TOKEN_LIFE_TIME_SECONDS:
                    raise IOError(f'Error while connecting to login token endpoint. Token lifetime to small {data["expires_in"]}.')

                self.token = data['access_token']
                current_time = monotonic()

                # include safe interval, e.g. time that approx network request can take
                self.token_valid_to = current_time + int(data['expires_in']) - SAFE_TIME_PERIOD_SECONDS
                self.token_next_refresh = current_time + TOKEN_REFRESH_PERIOD_SECONDS

                self.token_obtain.set()

    async def _auth_token_polling_loop(self):
        """
        Separate background process that periodically regenerates auth token
        """
        while True:
            try:
                await safe_gather(self._update_token())
                await asyncio.sleep(TOKEN_REFRESH_PERIOD_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    'Unexpected error while fetching auth token.',
                    exc_info=True,
                    app_warning_msg=f'Could not fetch trading rule updates on Beaxy. '
                                    f'Check network connection.'
                )
                await asyncio.sleep(0.5)

    async def generate_auth_dict(self, http_method: str, path: str, body: str = "") -> Dict[str, Any]:
        auth_token = await self.get_token()
        return {'Authorization': f'Bearer {auth_token}'}

    async def generate_ws_auth_dict(self) -> Dict[str, Any]:
        session_data = await self.__get_session_data()
        headers = {'X-Deltix-Nonce': str(get_tracking_nonce()), 'X-Deltix-Session-Id': session_data['session_id']}
        payload = self.__build_ws_payload(headers)
        hmac = HMAC.new(key= self.__int_to_bytes(session_data['sign_key'], signed=True), msg=bytes(payload, 'utf-8'), digestmod=SHA384)
        digestb64 = base64.b64encode(hmac.digest())
        headers['X-Deltix-Signature'] = digestb64.decode('utf-8')
        return headers

    async def __get_session_data(self) -> Dict[str, Any]:
        if not self._session_data_cache:
            dh_number = random.getrandbits(64 * 8)
            login_attempt = await self.__login_attempt()
            sign_key = await self.__login_confirm(login_attempt, dh_number)
            retval = {'sign_key': sign_key, 'session_id': login_attempt['session_id']}
            self._session_data_cache = retval

        return self._session_data_cache

    async def __login_confirm(self, login_attempt: Dict[str, str], dh_number: int) -> int:
        dh_modulus = int.from_bytes(base64.b64decode(login_attempt['dh_modulus']), 'big', signed= False)
        dh_base = int.from_bytes(base64.b64decode(login_attempt['dh_base']), 'big', signed= False)
        msg = base64.b64decode(login_attempt['challenge'])
        digest = SHA256.new(msg)
        pem = f'-----BEGIN PRIVATE KEY-----\n{self.api_secret}\n-----END PRIVATE KEY-----'
        privateKey = RSA.importKey(pem)
        encryptor = PKCS1_v1_5.new(privateKey)
        encrypted_msg = base64.b64encode(encryptor.sign(digest)).decode('utf-8')
        dh_key_raw = pow(dh_base, dh_number, dh_modulus)
        dh_key_bytes = self.__int_to_bytes(dh_key_raw, signed=True)
        dh_key = base64.b64encode(dh_key_bytes).decode('utf-8')

        async with aiohttp.ClientSession() as client:
            async with client.post(
                    f'{BeaxyConstants.TradingApi.BASE_URL_V1}{BeaxyConstants.TradingApi.LOGIN_CONFIRM_ENDPOINT}', json = {'session_id': login_attempt['session_id'], 'signature': encrypted_msg, 'dh_key': dh_key}) as response:
                response: aiohttp.ClientResponse = response
                if response.status != 200:
                    raise IOError(f'Error while connecting to login confirm endpoint. HTTP status is {response.status}.')
                data: Dict[str, str] = await response.json()
                dh_key_result = int.from_bytes(base64.b64decode(data['dh_key']), 'big', signed= False)
                return pow(dh_key_result, dh_number, dh_modulus)

    def __int_to_bytes(self, i: int, *, signed: bool = False) -> bytes:
        length = ((i + ((i * signed) < 0)).bit_length() + 7 + signed) // 8
        return i.to_bytes(length, byteorder='big', signed=signed)

    async def __login_attempt(self) -> Dict[str, str]:
        async with aiohttp.ClientSession() as client:
            async with client.post(f'{BeaxyConstants.TradingApi.BASE_URL_V1}{BeaxyConstants.TradingApi.LOGIN_ATTEMT_ENDPOINT}', json = {'api_key_id': self.api_key}) as response:
                response: aiohttp.ClientResponse = response
                if response.status != 200:
                    raise IOError(f'Error while connecting to login attempt endpoint. HTTP status is {response.status}.')
                data: Dict[str, str] = await response.json()
                return data

    def __build_payload(self, http_method: str, path: str, query_params: Dict[str, str], headers: Dict[str, str], body: str = ""):
        query_params_stringified = '&'.join([f'{k}={query_params[k]}' for k in sorted(query_params)])
        headers_stringified = '&'.join([f'{k}={headers[k]}' for k in sorted(headers)])
        return f'{http_method.upper()}{path.lower()}{query_params_stringified}{headers_stringified}{body}'

    def __build_ws_payload(self, headers: Dict[str, str]) -> str:
        headers_stringified = '&'.join([f'{k}={headers[k]}' for k in sorted(headers)])
        return f'CONNECT/websocket/v1{headers_stringified}'
