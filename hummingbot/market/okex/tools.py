import zlib



def inflate(data):
    """decrypts the OKEx data.
    Copied from OKEx SDK: https://github.com/okex/V3-Open-API-SDK/blob/d8becc67af047726c66d9a9b29d99e99c595c4f7/okex-python-sdk-api/websocket_example.py#L46"""
    decompress = zlib.decompressobj(
            -zlib.MAX_WBITS
    )
    inflated = decompress.decompress(data)
    inflated += decompress.flush()
    return inflated

# from typing import (
#     Any,
#     AsyncIterable,
#     Dict,
#     List,
#     Optional,
# )

# from hummingbot.market.okex.constants import *
# import aiohttp
# from aiohttp.test_utils import TestClient
# import json

# class AbstractMarket():

#     async def _http_client(self) -> aiohttp.ClientSession:
#         if self._shared_client is None:
#             self._shared_client = aiohttp.ClientSession()
#         return self._shared_client
#     async def _api_request(self,
#                            method,
#                            path_url,
#                            params: Optional[Dict[str, Any]] = None,
#                            data=None,
#                            is_auth_required: bool = False) -> Dict[str, Any]:
        
#         content_type = "application/json" if method == "post" else "application/x-www-form-urlencoded"
#         headers = {"Content-Type": content_type}
        
#         url = urljoin(OKEX_BASE_URL, path_url)
        
#         client = await self._http_client()
#         if is_auth_required:
#             params = self._okex_auth.add_auth_to_params(method, path_url, params)

#         # aiohttp TestClient requires path instead of url
#         if isinstance(client, TestClient):
#             response_coro = client.request(
#                 method=method.upper(),
#                 path=f"/{path_url}",
#                 headers=headers,
#                 params=params,
#                 data=ujson.dumps(data),
#                 timeout=100
#             )
#         else:
#             # real call
#             response_coro = client.request(
#                 method=method.upper(),
#                 url=url,
#                 headers=headers,
#                 params=params,
#                 data=ujson.dumps(data),
#                 timeout=100
#             )

#         async with response_coro as response:
#             if response.status != 200:
#                 raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.")
#             try:
#                 parsed_response = await response.json()
#             except Exception:
#                 raise IOError(f"Error parsing data from {url}.")

#             data = parsed_response.get("data")
#             if data is None:
#                 self.logger().error(f"Error received from {url}. Response is {parsed_response}.")
#                 raise OKExAPIError({"error": parsed_response})
#             return data