from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def build_api_factory(
    throttler: AsyncThrottler, auth: AuthBase
) -> WebAssistantsFactory:
    """"
    Signed endpoints require the additional signing of the message with the secret wallet key.
    """
    api_factory = WebAssistantsFactory(
        throttler=throttler, auth=auth
    )
    return api_factory
