import abc

from hummingbot.core.web_assistant.connections.data_types import RESTRequest


class RESTPreProcessorBase(abc.ABC):
    @abc.abstractmethod
    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        ...
