from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def build_api_factory(
    throttler: AsyncThrottler, api_key: str, auth: AuthBase
) -> WebAssistantsFactory:
    """The API KEY(if available) is used for "public" endpoints as well. "Signed" endpoints
    require the additional signing of the message with the secret wallet key."""
    rest_pre_processors = [
        APIKeyStitcher(api_key=api_key),
    ]
    api_factory = WebAssistantsFactory(
        throttler=throttler, rest_pre_processors=rest_pre_processors, auth=auth
    )
    return api_factory


class APIKeyStitcher(RESTPreProcessorBase):
    def __init__(self, api_key: str):
        self._api_key = api_key

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        request.headers = request.headers if request.headers is not None else {}
        if self._api_key is not None and len(self._api_key) > 0:
            request.headers["x-apikey"] = self._api_key
        return request
