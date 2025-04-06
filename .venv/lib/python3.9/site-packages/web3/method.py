import functools
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)
import warnings

from eth_utils.curried import (
    to_tuple,
)
from eth_utils.toolz import (
    pipe,
)

from web3._utils.batching import (
    RPC_METHODS_UNSUPPORTED_DURING_BATCH,
)
from web3._utils.method_formatters import (
    get_error_formatters,
    get_null_result_formatters,
    get_request_formatters,
    get_result_formatters,
)
from web3._utils.rpc_abi import (
    RPC,
)
from web3.exceptions import (
    MethodNotSupported,
    Web3TypeError,
    Web3ValidationError,
    Web3ValueError,
)
from web3.types import (
    RPCEndpoint,
    TFunc,
    TReturn,
)

if TYPE_CHECKING:
    from web3 import (  # noqa: F401
        PersistentConnectionProvider,
        Web3,
    )
    from web3.module import Module  # noqa: F401


Munger = Callable[..., Any]


@to_tuple
def _apply_request_formatters(
    params: Any, request_formatters: Dict[RPCEndpoint, Callable[..., TReturn]]
) -> Tuple[Any, ...]:
    if request_formatters:
        formatted_params = pipe(params, request_formatters)
        return formatted_params
    return params


def _set_mungers(
    mungers: Optional[Sequence[Munger]], is_property: bool
) -> Sequence[Any]:
    if is_property and mungers:
        raise Web3ValidationError("Mungers cannot be used with a property.")

    return (
        mungers
        if mungers
        else [default_munger]
        if is_property
        else [default_root_munger]
    )


def default_munger(_module: "Module", *args: Any, **kwargs: Any) -> Tuple[()]:
    if args or kwargs:
        raise Web3ValidationError("Parameters cannot be passed to a property.")
    return ()


def default_root_munger(_module: "Module", *args: Any) -> List[Any]:
    return [*args]


class Method(Generic[TFunc]):
    """
    Method object for web3 module methods

    Calls to the Method go through these steps:

    1. input munging - includes normalization, parameter checking, early parameter
    formatting. Any processing on the input parameters that need to happen before
    json_rpc method string selection occurs.

            A note about mungers: The first (root) munger should reflect the desired
        api function arguments. In other words, if the api function wants to
        behave as: `get_balance(account, block_identifier=None)`, the root munger
        should accept these same arguments, with the addition of the module as
        the first argument e.g.:

        ```
        def get_balance_root_munger(module, account, block_identifier=None):
            if block_identifier is None:
                block_identifier = DEFAULT_BLOCK
            return module, [account, block_identifier]
        ```

        all mungers should return an argument list.

        if no munger is provided, a default munger expecting no method arguments
        will be used.

    2. method selection - The json_rpc_method argument can be method string or a
    function that returns a method string. If a callable is provided the processed
    method inputs are passed to the method selection function, and the returned
    method string is used.

    3. request and response formatters are set - formatters are retrieved
    using the json rpc method string.

    4. After the parameter processing from steps 1-3 the request is made using
    the calling function returned by the module attribute ``retrieve_caller_fn``
    and the response formatters are applied to the output.
    """

    def __init__(
        self,
        json_rpc_method: Optional[RPCEndpoint] = None,
        mungers: Optional[Sequence[Munger]] = None,
        request_formatters: Optional[Callable[..., TReturn]] = None,
        result_formatters: Optional[Callable[..., TReturn]] = None,
        null_result_formatters: Optional[Callable[..., TReturn]] = None,
        method_choice_depends_on_args: Optional[Callable[..., RPCEndpoint]] = None,
        is_property: bool = False,
    ):
        self.json_rpc_method = json_rpc_method
        self.mungers = _set_mungers(mungers, is_property)
        self.request_formatters = request_formatters or get_request_formatters
        self.result_formatters = result_formatters or get_result_formatters
        self.null_result_formatters = (
            null_result_formatters or get_null_result_formatters
        )
        self.method_choice_depends_on_args = method_choice_depends_on_args
        self.is_property = is_property

    def __get__(
        self,
        module: Optional["Module"] = None,
        _type: Optional[Type["Module"]] = None,
    ) -> TFunc:
        self._module = module
        if module is None:
            raise Web3TypeError(
                "Direct calls to methods are not supported. "
                "Methods must be called from a module instance, "
                "usually attached to a web3 instance."
            )

        provider = module.w3.provider
        if hasattr(provider, "_is_batching") and provider._is_batching:
            if self.json_rpc_method in RPC_METHODS_UNSUPPORTED_DURING_BATCH:
                raise MethodNotSupported(
                    f"Method `{self.json_rpc_method}` is not supported within a batch "
                    "request."
                )
            return module.retrieve_request_information(self)
        else:
            return module.retrieve_caller_fn(self)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.__get__(self._module)(*args, **kwargs)

    @property
    def method_selector_fn(
        self,
    ) -> Callable[..., Union[RPCEndpoint, Callable[..., RPCEndpoint]]]:
        """Gets the method selector from the config."""
        if callable(self.json_rpc_method):
            return self.json_rpc_method
        elif isinstance(self.json_rpc_method, (str,)):
            return lambda *_: self.json_rpc_method
        raise Web3ValueError(
            "``json_rpc_method`` config invalid.  May be a string or function"
        )

    def input_munger(self, module: "Module", args: Any, kwargs: Any) -> List[Any]:
        # This function takes the input parameters and munges them.
        # See the test_process_params test in ``tests/core/method-class/test_method.py``
        # for an example with multiple mungers.
        return functools.reduce(
            lambda args, munger: munger(module, *args, **kwargs), self.mungers, args
        )

    def process_params(
        self, module: "Module", *args: Any, **kwargs: Any
    ) -> Tuple[
        Tuple[Union[RPCEndpoint, Callable[..., RPCEndpoint]], Tuple[RPCEndpoint, ...]],
        Tuple[
            Union[TReturn, Dict[str, Callable[..., Any]]],
            Callable[..., Any],
            Union[TReturn, Callable[..., Any]],
        ],
    ]:
        params = self.input_munger(module, args, kwargs)

        if self.method_choice_depends_on_args:
            # If the method choice depends on the args that get passed in,
            # the first parameter determines which method needs to be called
            self.json_rpc_method = self.method_choice_depends_on_args(value=params[0])

            pending_or_latest_filter_methods = [
                RPC.eth_newPendingTransactionFilter,
                RPC.eth_newBlockFilter,
            ]
            if self.json_rpc_method in pending_or_latest_filter_methods:
                # For pending or latest filter methods, use params to determine
                # which method to call, but don't pass them through with the request
                params = []

        method = self.method_selector_fn()
        response_formatters = (
            self.result_formatters(method, module),
            get_error_formatters(method),
            self.null_result_formatters(method),
        )
        request = (
            method,
            _apply_request_formatters(params, self.request_formatters(method)),
        )
        return request, response_formatters


class DeprecatedMethod:
    def __init__(
        self, method: Method[Callable[..., Any]], old_name: str, new_name: str
    ) -> None:
        self.method = method
        self.old_name = old_name
        self.new_name = new_name

    def __get__(
        self, obj: Optional["Module"] = None, obj_type: Optional[Type["Module"]] = None
    ) -> Any:
        warnings.warn(
            f"{self.old_name} is deprecated in favor of {self.new_name}",
            category=DeprecationWarning,
            stacklevel=2,
        )
        return self.method.__get__(obj, obj_type)
