import abc

from hummingbot.core.web_assistant.connections.data_types import RESTResponse


class RESTPostProcessorBase(abc.ABC):
    @abc.abstractmethod
    async def post_process(self, response: RESTResponse) -> RESTResponse:
        ...
