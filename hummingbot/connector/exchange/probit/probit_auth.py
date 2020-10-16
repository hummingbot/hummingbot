import base64
from typing import Dict, Any

import aiohttp
import ujson
import time


class ProbitAuth():
    """
    Auth class required by probit API
    Learn more at https://docs-en.probit.com/docs/authorization-1
    """
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.access_token = ""
        self.expire_at = 0

    async def generate_auth_dict(
        self,
        data: Dict[str, Any] = None
    ):
        """
        Generates access token and return it in a dictionary along with other inputs
        :return: a dictionary of request info including the access_token
        """

        data = data or {}
        now = time.time()

        if self.expire_at < now:
            key_string = self.api_key + ":" + self.secret_key
            auth_header = 'Basic ' + base64.b64encode(key_string.encode('ASCII')).decode('utf8')
            headers = {
                'Content-Type': 'application/json',
                'Authorization': auth_header
            }
            body = {
                'grant_type': 'client_credentials'
            }

            client = aiohttp.ClientSession()
            async with client.request("POST", url="https://accounts.probit.com/token", headers=headers, params=None, data=ujson.dumps(body)) as response:
                if response.status == 200:
                    try:
                        resp: Dict[str, Any] = await response.json()
                        self.access_token = resp.get("access_token", "")
                        self.expire_at = now + (resp.get("expires_in", 0) * 9 / 10)
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for kucoin trading pairs

        data["access_token"] = self.access_token
        return data

    async def get_headers(self) -> Dict[str, Any]:
        """
        Generates authentication headers required by probit
        :return: a dictionary of auth headers
        """

        auth_dict = await self.generate_auth_dict()
        return {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + auth_dict["access_token"]
        }
