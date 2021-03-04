#!/usr/bin/env python

import aiohttp
import base64
import time
import ujson

import hummingbot.connector.exchange.probit.probit_constants as CONSTANTS

from typing import Dict, Any


class ProbitAuth():
    """
    Auth class required by ProBit API
    Learn more at https://docs-en.probit.com/docs/authorization-1
    """
    def __init__(self, api_key: str, secret_key: str, domain: str = "com"):
        self.api_key: str = api_key
        self.secret_key: str = secret_key

        self._domain = domain
        self._oauth_token: str = None
        self._oauth_token_expiration_time: int = -1

    @property
    def oauth_token(self):
        return self._oauth_token

    @property
    def token_payload(self):
        payload = f"{self.api_key}:{self.secret_key}".encode()
        return base64.b64encode(payload).decode()

    @property
    def token_has_expired(self):
        now: int = int(time.time())
        return now >= self._oauth_token_expiration_time

    def update_oauth_token(self, new_token: str):
        self._oauth_token = new_token

    def update_expiration_time(self, expiration_time: int):
        self._oauth_token_expiration_time = expiration_time

    async def get_auth_headers(self, http_client: aiohttp.ClientSession = aiohttp.ClientSession()) -> Dict[str, Any]:
        if self.token_has_expired:
            try:
                now: int = int(time.time())
                headers = self.get_headers()
                headers.update({
                    "Authorization": f"Basic {self.token_payload}"
                })
                body = ujson.dumps({
                    "grant_type": "client_credentials"
                })
                resp = await http_client.post(url=CONSTANTS.TOKEN_URL.format(self._domain),
                                              headers=headers,
                                              data=body)
                token_resp = await resp.json()

                if resp.status != 200:
                    raise ValueError(f"Error occurred retrieving new OAuth Token. Response: {token_resp}")

                # POST /token endpoint returns both access_token and expires_in
                # Updates _oauth_token_expiration_time

                self.update_expiration_time(now + token_resp["expires_in"])
                self.update_oauth_token(token_resp["access_token"])
            except Exception as e:
                raise e

        return self.generate_auth_dict()

    async def get_ws_auth_payload(self) -> Dict[str, Any]:
        await self.get_auth_headers()
        return {
            "type": "authorization",
            "token": self._oauth_token
        }

    def generate_auth_dict(self):
        """
        Generates authentication signature and return it in a dictionary along with other inputs
        :return: a dictionary of request info including the request signature
        """

        headers = self.get_headers()

        headers.update({
            "Authorization": f"Bearer {self._oauth_token}"
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
