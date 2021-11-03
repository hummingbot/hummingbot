import abc

from hummingbot.core.api_delegate.connections.data_types import RESTResponse


class RESTPostProcessorBase(abc.ABC):
    @abc.abstractmethod
    async def post_process(self, response: RESTResponse) -> RESTResponse:
        ...
