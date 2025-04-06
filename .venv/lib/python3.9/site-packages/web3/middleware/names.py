from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Sequence,
    Union,
    cast,
)

from toolz import (
    merge,
)

from web3._utils.normalizers import (
    abi_ens_resolver,
    async_abi_ens_resolver,
)
from web3._utils.rpc_abi import (
    RPC_ABIS,
    abi_request_formatters,
)
from web3.types import (
    RPCEndpoint,
)

from .._utils.abi import (
    abi_data_tree,
    async_data_tree_map,
    strip_abi_type,
)
from .._utils.formatters import (
    recursive_map,
)
from ..exceptions import (
    Web3TypeError,
)
from .base import (
    Web3Middleware,
)
from .formatting import (
    FormattingMiddlewareBuilder,
)

if TYPE_CHECKING:
    from web3 import (  # noqa: F401
        AsyncWeb3,
        Web3,
    )


def _is_logs_subscription_with_optional_args(method: RPCEndpoint, params: Any) -> bool:
    return method == "eth_subscribe" and len(params) == 2 and params[0] == "logs"


async def async_format_all_ens_names_to_address(
    async_web3: "AsyncWeb3",
    abi_types_for_method: Sequence[Any],
    data: Sequence[Any],
) -> Sequence[Any]:
    # provide a stepwise version of what the curried formatters do
    abi_typed_params = abi_data_tree(abi_types_for_method, data)
    formatted_data_tree = await async_data_tree_map(
        async_web3,
        async_abi_ens_resolver,
        abi_typed_params,
    )
    formatted_params = recursive_map(strip_abi_type, formatted_data_tree)
    return formatted_params


async def async_apply_ens_to_address_conversion(
    async_web3: "AsyncWeb3",
    params: Any,
    abi_types_for_method: Union[Sequence[str], Dict[str, str]],
) -> Any:
    if isinstance(abi_types_for_method, Sequence):
        formatted_params = await async_format_all_ens_names_to_address(
            async_web3, abi_types_for_method, params
        )
        return formatted_params

    elif isinstance(abi_types_for_method, dict):
        # first arg is a dict but other args may be preset
        # e.g. eth_call({...}, "latest")
        # this is similar to applying a dict formatter at index 0 of the args
        param_dict = params[0]
        fields = list(abi_types_for_method.keys() & param_dict.keys())
        formatted_params = await async_format_all_ens_names_to_address(
            async_web3,
            [abi_types_for_method[field] for field in fields],
            [param_dict[field] for field in fields],
        )
        formatted_dict = dict(zip(fields, formatted_params))
        formatted_params_dict = merge(param_dict, formatted_dict)
        return (formatted_params_dict, *params[1:])

    else:
        raise Web3TypeError(
            f"ABI definitions must be a list or dictionary, "
            f"got {abi_types_for_method!r}"
        )


class ENSNameToAddressMiddleware(Web3Middleware):
    _formatting_middleware = None

    def request_processor(self, method: "RPCEndpoint", params: Any) -> Any:
        if self._formatting_middleware is None:
            normalizers = [
                abi_ens_resolver(self._w3),
            ]
            self._formatting_middleware = FormattingMiddlewareBuilder.build(
                request_formatters=abi_request_formatters(normalizers, RPC_ABIS)
            )

        return self._formatting_middleware(self._w3).request_processor(method, params)

    # -- async -- #

    async def async_request_processor(self, method: "RPCEndpoint", params: Any) -> Any:
        abi_types_for_method = RPC_ABIS.get(method, None)

        if abi_types_for_method is not None:
            if _is_logs_subscription_with_optional_args(method, params):
                # eth_subscribe optional logs params are unique.
                # Handle them separately here.
                (formatted_dict,) = await async_apply_ens_to_address_conversion(
                    cast("AsyncWeb3", self._w3),
                    (params[1],),
                    {
                        "address": "address",
                        "topics": "bytes32[]",
                    },
                )
                params = (params[0], formatted_dict)

            else:
                params = await async_apply_ens_to_address_conversion(
                    cast("AsyncWeb3", self._w3),
                    params,
                    abi_types_for_method,
                )

        return method, params
