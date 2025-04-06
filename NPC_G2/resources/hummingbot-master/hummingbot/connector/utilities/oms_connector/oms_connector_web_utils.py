import json
import time
from abc import ABC, abstractmethod
from typing import Optional

from hummingbot.connector.utilities.oms_connector import oms_connector_constants as CONSTANTS
from hummingbot.connector.utilities.oms_connector.oms_connector_auth import OMSConnectorAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.connections.data_types import WSRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_post_processors import WSPostProcessorBase
from hummingbot.core.web_assistant.ws_pre_processors import WSPreProcessorBase


class OMSConnectorURLCreatorBase(ABC):
    @abstractmethod
    def get_rest_url(self, path_url: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_ws_url(self) -> str:
        raise NotImplementedError


class OMSConnectorWSPreProcessor(WSPreProcessorBase):
    def __init__(self):
        self._msg_sequence_num = 0

    async def pre_process(self, request: WSRequest) -> WSRequest:
        request.payload[CONSTANTS.MSG_TYPE_FIELD] = CONSTANTS.REQ_MSG_TYPE
        sequence_num = self._generate_sequence_number()
        request.payload[CONSTANTS.MSG_SEQUENCE_FIELD] = sequence_num
        request.payload[CONSTANTS.MSG_DATA_FIELD] = json.dumps(request.payload[CONSTANTS.MSG_DATA_FIELD])
        return request

    def _generate_sequence_number(self) -> int:
        self._msg_sequence_num += 2
        return self._msg_sequence_num


class OMSConnectorWSPostProcessor(WSPostProcessorBase):
    async def post_process(self, response: WSResponse) -> WSResponse:
        if CONSTANTS.MSG_DATA_FIELD in response.data:
            response.data[CONSTANTS.MSG_DATA_FIELD] = json.loads(response.data[CONSTANTS.MSG_DATA_FIELD])
        return response


class OMSConnectorWebAssistantsFactory(WebAssistantsFactory):
    @property
    def auth(self) -> Optional[OMSConnectorAuth]:
        return self._auth


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    auth: Optional[OMSConnectorAuth] = None,
):
    throttler = throttler or create_throttler()
    api_factory = OMSConnectorWebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        ws_pre_processors=[OMSConnectorWSPreProcessor()],
        ws_post_processors=[OMSConnectorWSPostProcessor()],
    )
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None, domain: str = ""
) -> float:
    return _time() * 1e3


def _time() -> float:
    """Can be mocked in unit-tests without directly affecting `time.time()`"""
    return time.time()
