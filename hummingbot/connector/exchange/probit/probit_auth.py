#!/usr/bin/env python

import base64
import time

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

    @property
    def oauth_token(self):
        return self._oauth_token

    @property
    def token_payload(self):
        payload = f"{self.api_key}:{self.secret_key}".encode()
        return base64.b64encode(payload).decode()

    def token_has_expired(self):
        now: int = int(time.time())
        return now >= self._oauth_token_expiration_time

    def update_oauth_token(self, new_token: str):
        self._oauth_token = new_token

    def update_expiration_time(self, expiration_time: int):
        self._oauth_token_expiration_time = expiration_time

    async def get_oauth_token(self) -> str:
        if self._oauth_token is None or self._token_has_expired():
            self._oauth_token = await self.generate_oauth_token()
        return self._oauth_token

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
