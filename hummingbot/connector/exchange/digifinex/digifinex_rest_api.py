from typing import Callable, Dict, Any
import aiohttp
import json
import urllib
from hummingbot.connector.exchange.digifinex.digifinex_auth import DigifinexAuth
from hummingbot.connector.exchange.digifinex import digifinex_constants as Constants
from hummingbot.connector.exchange.digifinex import digifinex_utils


class DigifinexRestApi:

    def __init__(self, auth: DigifinexAuth, http_client_getter: Callable[[], aiohttp.ClientSession]):
        self._auth = auth
        self._http_client = http_client_getter

    async def request(self,
                      method: str,
                      path_url: str,
                      params: Dict[str, Any] = {},
                      is_auth_required: bool = False) -> Dict[str, Any]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param is_auth_required: Whether an authentication is required, when True the function will add encrypted
        signature to the request.
        :returns A response in json format.
        """
        url = f"{Constants.REST_URL}/{path_url}"
        client = await self._http_client()
        if is_auth_required:
            request_id = digifinex_utils.RequestId.generate_request_id()
            headers = self._auth.get_private_headers(path_url, request_id, params)
        else:
            headers = {}

        if method == "get":
            url = f'{url}?{urllib.parse.urlencode(params)}'
            response = await client.get(url, headers=headers)
        elif method == "post":
            response = await client.post(url, data=params, headers=headers)
        else:
            raise NotImplementedError

        try:
            parsed_response = json.loads(await response.text())
        except Exception as e:
            raise IOError(f"Error parsing data from {url}. Error: {str(e)}")
        if response.status != 200:
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. "
                          f"Message: {parsed_response}")
        if parsed_response["code"] != 0:
            raise IOError(f"{url} API call failed, response: {parsed_response}")
        # print(f"REQUEST: {method} {path_url} {params}")
        # print(f"RESPONSE: {parsed_response}")
        return parsed_response

    async def get_balance(self) -> Dict[str, Any]:
        """
        Calls REST API to update total and available balances.
        """
        account_info = await self.request("get", "spot/assets", {}, True)
        return account_info
