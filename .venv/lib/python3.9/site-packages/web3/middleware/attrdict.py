from abc import (
    ABC,
)
from typing import (
    TYPE_CHECKING,
    Any,
    cast,
)

from web3.datastructures import (
    AttributeDict,
)
from web3.middleware.base import (
    Web3Middleware,
)

if TYPE_CHECKING:
    from web3 import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )
    from web3.providers import (  # noqa: F401
        PersistentConnectionProvider,
    )
    from web3.types import (  # noqa: F401
        RPCEndpoint,
        RPCResponse,
    )


def _handle_async_response(response: "RPCResponse") -> "RPCResponse":
    """
    Process the RPC response by converting nested dictionaries into AttributeDict.
    """
    if "result" in response:
        response["result"] = AttributeDict.recursive(response["result"])
    elif "params" in response and "result" in response["params"]:
        # subscription response
        response["params"]["result"] = AttributeDict.recursive(
            response["params"]["result"]
        )

    return response


class AttributeDictMiddleware(Web3Middleware, ABC):
    """
    Converts any result which is a dictionary into an `AttributeDict`.

    Note: Accessing `AttributeDict` properties via attribute
        (e.g. my_attribute_dict.property1) will not preserve typing.
    """

    def response_processor(self, method: "RPCEndpoint", response: "RPCResponse") -> Any:
        if "result" in response:
            new_result = AttributeDict.recursive(response["result"])
            response = {**response, "result": new_result}
        return response

    # -- async -- #

    async def async_response_processor(
        self, method: "RPCEndpoint", response: "RPCResponse"
    ) -> Any:
        if self._w3.provider.has_persistent_connection:
            provider = cast("PersistentConnectionProvider", self._w3.provider)
            provider._request_processor.append_middleware_response_processor(
                response, _handle_async_response
            )
            return response
        else:
            return _handle_async_response(response)


AttributeDictMiddleware = AttributeDictMiddleware
