import abc

from hummingbot.core.api_delegate.data_types import WSResponse


class WSPostProcessorBase(abc.ABC):
    @abc.abstractmethod
    async def post_process(self, response: WSResponse) -> WSResponse:
        ...
