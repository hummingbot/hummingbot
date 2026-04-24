import time
from asyncio import Lock

from hummingbot.connector.derivative.architect_perpetual import (
    architect_perpetual_constants as CONSTANTS,
    architect_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_web_utils import (
    build_api_factory_without_time_synchronizer_pre_processor,
)
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class ArchitectPerpetualAuth(AuthBase):
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        time_provider: TimeSynchronizer,
        domain: str,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._time_provider = time_provider
        self._domain = domain
        self._api_factory = build_api_factory_without_time_synchronizer_pre_processor()

        self._token_lock = Lock()
        self._expiration_seconds = 2_592_000  # 30 days
        self._token: str = ""
        self._token_expiration_ts: float = 0

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        token = await self._get_token_for_rest_request(request=request)
        request.headers = request.headers or {}
        request.headers["Authorization"] = f"Bearer {token}"
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request

    async def get_token_for_ws_stream(self) -> str:
        await self._update_token()
        return self._token

    async def _get_token_for_rest_request(self, request: RESTRequest) -> str:
        if (
            not self._token
            or (
                request.endpoint_url == CONSTANTS.RISK_ENDPOINT  # update during balance polling — not critical
                and self._token_expiration_ts - 130 < self._time()  # LONG_POLL_INTERVAL = 120 seconds
            )
        ):
            await self._update_token()
        return self._token

    async def _update_token(self):
        async with self._token_lock:
            url = web_utils.public_rest_url(CONSTANTS.AUTH_TOKEN_ENDPOINT, domain=self._domain)
            rest_assistant = await self._api_factory.get_rest_assistant()
            pre_request_time = self._time()
            response = await rest_assistant.execute_request(
                url=url,
                throttler_limit_id=CONSTANTS.AUTH_TOKEN_ENDPOINT,
                data={
                    "api_key": self._api_key,
                    "api_secret": self._api_secret,
                    "expiration_seconds": self._expiration_seconds,
                },
                method=RESTMethod.POST,
            )
            self._token_expiration_ts = pre_request_time + self._expiration_seconds
            self._token = response["token"]

    @staticmethod
    def _time() -> float:
        return time.time()
