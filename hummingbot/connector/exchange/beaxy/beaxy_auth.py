# -*- coding: utf-8 -*-

import logging
import asyncio
from typing import Dict, Any, Optional
from time import monotonic
from datetime import datetime

import aiohttp

from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger

from hummingbot.connector.exchange.beaxy.beaxy_constants import BeaxyConstants

s_logger = None

SAFE_TIME_PERIOD_SECONDS = 10
TOKEN_REFRESH_PERIOD_SECONDS = 10 * 60
MIN_TOKEN_LIFE_TIME_SECONDS = 30
TOKEN_OBTAIN_TIMEOUT = 30


class BeaxyAuth:

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self._session_data_cache: Dict[str, Any] = {}

        self.token: Optional[str] = None
        self.token_obtain = asyncio.Event()
        self.token_obtain_started = False
        self.token_valid_to: float = 0
        self.token_next_refresh: float = 0
        self.token_obtain_start_time = 0
        self.token_raw_expires = 0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def is_token_valid(self):
        return self.token_valid_to > monotonic()

    def token_timings_str(self):
        return f'auth req start time {self.token_obtain_start_time}, token validness sec {self.token_raw_expires}'

    def invalidate_token(self):
        self.token_valid_to = 0

    async def get_token(self):

        for _ in range(3):
            if self.is_token_valid():
                return self.token

            # token is invalid, waiting for a renew
            if not self.token_obtain_started:
                # if process of refreshing is not started, start it
                await self._update_token()

                if not self.is_token_valid():
                    continue
                return self.token

            # waiting for fresh token
            await asyncio.wait_for(self.token_obtain.wait(), timeout=TOKEN_OBTAIN_TIMEOUT)

            if not self.is_token_valid():
                continue
            return self.token

        raise ValueError('Invalid auth token timestamp')

    async def _update_token(self):

        self.token_obtain.clear()
        self.token_obtain_started = True

        try:

            start_time = monotonic()
            start_timestamp = datetime.now()

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
                    self.token_raw_expires = data['expires_in']

                    # include safe interval, e.g. time that approx network request can take
                    self.token_obtain_start_time = start_timestamp
                    self.token_valid_to = start_time + int(data['expires_in']) - SAFE_TIME_PERIOD_SECONDS
                    self.token_next_refresh = start_time + TOKEN_REFRESH_PERIOD_SECONDS

                    if not self.is_token_valid():
                        raise ValueError('Invalid auth token timestamp')

                    self.token_obtain.set()

        finally:
            self.token_obtain_started = False

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
                    app_warning_msg='Could not fetch trading rule updates on Beaxy. '
                                    'Check network connection.'
                )
                await asyncio.sleep(0.5)

    async def generate_auth_dict(self, http_method: str, path: str, body: str = '') -> Dict[str, Any]:
        auth_token = await self.get_token()
        return {'Authorization': f'Bearer {auth_token}'}
