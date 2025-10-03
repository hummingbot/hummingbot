from hummingbot.connector.derivative.asterdex_perpetual import asterdex_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def build_api_factory() -> WebAssistantsFactory:
    return WebAssistantsFactory(
        rest_pre_processors=[],
        rest_post_processors=[],
        ws_pre_processors=[],
        ws_post_processors=[],
    )
