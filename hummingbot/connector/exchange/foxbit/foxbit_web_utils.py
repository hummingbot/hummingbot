from typing import Any, Callable, Dict, Optional

import hummingbot.connector.exchange.foxbit.foxbit_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str,
                    domain: str = CONSTANTS.DEFAULT_DOMAIN,
                    ) -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :param domain: The default value is "com.br". Not in use at this time.
    :return: the full URL to the endpoint
    """
    return f"https://{CONSTANTS.REST_URL}/rest/{CONSTANTS.PUBLIC_API_VERSION}/{path_url}"


def private_rest_url(path_url: str,
                     domain: str = CONSTANTS.DEFAULT_DOMAIN,
                     ) -> str:
    """
    Creates a full URL for provided private REST endpoint
    :param path_url: a private REST endpoint
    :param domain: The default value is "com.br". Not in use at this time.
    :return: the full URL to the endpoint
    """
    return f"https://{CONSTANTS.REST_URL}/rest/{CONSTANTS.PRIVATE_API_VERSION}/{path_url}"


def rest_endpoint_url(full_url: str,
                      ) -> str:
    """
    Creates a REST endpoint
    :param full_url: a full url
    :return: the URL endpoint
    """
    url_size = len(f"https://{CONSTANTS.REST_URL}")
    return full_url[url_size:]


def websocket_url() -> str:
    """
    Creates a full URL for provided WebSocket endpoint
    :return: the full URL to the endpoint
    """
    return f"wss://{CONSTANTS.WSS_URL}/"


def format_ws_header(header: Dict[str, Any]) -> Dict[str, Any]:
    retValue = {}
    retValue.update(CONSTANTS.WS_HEADER.copy())
    retValue.update(header)
    return retValue


def build_api_factory(throttler: Optional[AsyncThrottler] = None,
                      time_synchronizer: Optional[TimeSynchronizer] = None,
                      domain: str = CONSTANTS.DEFAULT_DOMAIN,
                      time_provider: Optional[Callable] = None,
                      auth: Optional[AuthBase] = None,
                      ) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(
        throttler=throttler,
        domain=domain,
    ))
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
        ])
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(throttler: Optional[AsyncThrottler] = None,
                                  domain: str = CONSTANTS.DEFAULT_DOMAIN,
                                  ) -> float:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response = await rest_assistant.execute_request(url=public_rest_url(path_url=CONSTANTS.SERVER_TIME_PATH_URL,
                                                                        domain=domain),
                                                    method=RESTMethod.GET,
                                                    throttler_limit_id=CONSTANTS.SERVER_TIME_PATH_URL,
                                                    )
    server_time = response["timestamp"]
    return server_time
