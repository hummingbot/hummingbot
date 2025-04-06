import abc

from hummingbot.core.web_assistant.connections.data_types import WSRequest


class WSPreProcessorBase(abc.ABC):
    """An interface class that enables functionality injection into the `WSAssistant`.

    The logic provided by a class implementing this interface is applied to a request
    before it is sent out to the server.
    """

    @abc.abstractmethod
    async def pre_process(self, request: WSRequest) -> WSRequest:
        ...
