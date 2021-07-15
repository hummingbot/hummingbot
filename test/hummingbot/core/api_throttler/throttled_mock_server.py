from aiohttp import web

from hummingbot.core.mock_api.mock_web_server import MockWebServer

BASE_URL = "www.hbottesst.com"

TEST_PATH_URL = "/test"


class ThrottledMockServer(MockWebServer):
    def __init__(self):
        super().__init__()
        self._request_count = 0

    @property
    def request_count(self) -> int:
        return self._request_count

    def reset_request_count(self):
        self._request_count = 0

    async def _handler(self, request: web.Request):
        self._request_count += 1
        return await super()._handler(request)
