import abc

from hummingbot.core.web_assistant.connections.data_types import WSRequest


class WSPreProcessorBase(abc.ABC):
    @abc.abstractmethod
    async def pre_process(self, request: WSRequest) -> WSRequest:
        ...
