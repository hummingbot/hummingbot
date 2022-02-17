import aiohttp
import json
import ssl
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.settings import (
    GATEAWAY_CA_CERT_PATH,
    GATEAWAY_CLIENT_CERT_PATH,
    GATEAWAY_CLIENT_KEY_PATH,
)
from typing import Any, Dict, Optional


class GatewayHttpClient:
    """
    An HTTP client for making requests to the gateway API.
    """

    def __init__(self):
        super().__init__()
        self._shared_client: Optional[aiohttp.ClientSession] = None

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if self._shared_client is None:
            ssl_ctx = ssl.create_default_context(cafile=GATEAWAY_CA_CERT_PATH)
            ssl_ctx.load_cert_chain(GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH)
            conn = aiohttp.TCPConnector(ssl_context=ssl_ctx)
            self._shared_client = aiohttp.ClientSession(connector=conn)
        return self._shared_client

    async def api_request(self,
                          method: str,
                          path_url: str,
                          params: Dict[str, Any] = {},
                          fail_silently: bool = False) -> Optional[Dict[str, Any]]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param params: A dictionary of required params for the end point
        :returns A response in json format.
        """
        base_url = f"https://{global_config_map['gateway_api_host'].value}:" \
                   f"{global_config_map['gateway_api_port'].value}"
        url = f"{base_url}/{path_url}"
        client = await self._http_client()

        parsed_response = {}
        try:
            if method == "get":
                if len(params) > 0:
                    response = await client.get(url, params=params)
                else:
                    response = await client.get(url)
            elif method == "post":
                response = await client.post(url, json=params)
            parsed_response = json.loads(await response.text())
            if response.status != 200:
                if "error" in parsed_response:
                    err_msg = f"Error on {method.upper()} Error: {parsed_response['error']}"
                else:
                    err_msg = f"Error on {method.upper()} Error: {parsed_response}"
                    # self.logger().error(
                    #     err_msg,
                    #     exc_info=True
                    # )
                    raise Exception(err_msg)
        except Exception as e:
            if not fail_silently:
                raise e

        return parsed_response


gateway_http_client = GatewayHttpClient()
