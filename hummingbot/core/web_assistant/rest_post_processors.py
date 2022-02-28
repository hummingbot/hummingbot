import abc

from hummingbot.core.web_assistant.connections.data_types import RESTResponse


class RESTPostProcessorBase(abc.ABC):
    """An interface class that enables functionality injection into the `RESTAssistant`.

    The logic provided by a class implementing this interface is applied to a response
    before it is returned to the caller.
    """

    @abc.abstractmethod
    async def post_process(self, response: RESTResponse) -> RESTResponse:
        ...
