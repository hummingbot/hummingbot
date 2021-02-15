#!/usr/bin/env python

import aiohttp
import base64
import time
import ujson

import hummingbot.connector.exchange.probit.probit_constants as constants

from typing import Dict, Any


class ProbitAuth():
    """
    Auth class required by ProBit API
    Learn more at https://docs-en.probit.com/docs/authorization-1
    """
    def __init__(self, api_key: str, secret_key: str):
        self.api_key: str = api_key
        self.secret_key: str = secret_key
        self._oauth_token: str = None
        self._oauth_token_expiration_time: int = -1
        self._http_client: aiohttp.ClientSession = aiohttp.ClientSession()

    def _token_has_expired(self):
        now: int = int(time.time())
        return now >= self._oauth_token_expiration_time

    def _update_expiration_time(self, expiration_time: int):
        self._oauth_token_expiration_time = expiration_time

    async def _generate_oauth_token(self) -> str:
        try:
            now: int = int(time.time())
            headers: Dict[str, Any] = self.get_headers()
            payload = f"{self.api_key}:{self.secret_key}".encode()
            b64_payload = base64.b64encode(payload).decode()
            headers.update({
                "Authorization": f"Basic {b64_payload}"
            })
            body = ujson.dumps({
                "grant_type": "client_credentials"
            })
            resp = await self._http_client.post(url=constants.TOKEN_URL,
                                                headers=headers,
                                                data=body)
            if resp.status != 200:
                raise ValueError(f"{__name__}: Error occurred retrieving new OAuth Token. Response: {resp}")

            token_resp = await resp.json()

            # POST /token endpoint returns both access_token and expires_in
            # Updates _oauth_token_expiration_time

            self._update_expiration_time(now + token_resp["expires_in"])
            return token_resp["access_token"]
        except Exception as e:
            raise e

    async def _get_oauth_token(self) -> str:
        if self._oauth_token is None or self._token_has_expired():
            self._oauth_token = await self._generate_oauth_token()
        return self._oauth_token

    async def generate_auth_dict(self):
        """
        Generates authentication signature and return it in a dictionary along with other inputs
        :return: a dictionary of request info including the request signature
        """

        headers = self.get_headers()

        access_token = await self._get_oauth_token()
        headers.update({
            "Authorization": f"Bearer {access_token}"
        })

        return headers

    def get_headers(self) -> Dict[str, Any]:
        """
        Generates authentication headers required by ProBit
        :return: a dictionary of auth headers
        """

        return {
            "Content-Type": 'application/json',
        }
