import functools
import threading
from typing import (
    Any,
    Callable,
    TypeVar,
    cast,
)
import warnings

from web3.exceptions import (
    Web3ValueError,
)

TFunc = TypeVar("TFunc", bound=Callable[..., Any])


def reject_recursive_repeats(to_wrap: Callable[..., Any]) -> Callable[..., Any]:
    """
    Prevent simple cycles by returning None when called recursively with same instance
    """
    # types ignored b/c dynamically set attribute
    to_wrap.__already_called = {}  # type: ignore

    @functools.wraps(to_wrap)
    def wrapped(*args: Any) -> Any:
        arg_instances = tuple(map(id, args))
        thread_id = threading.get_ident()
        thread_local_args = (thread_id,) + arg_instances
        if thread_local_args in to_wrap.__already_called:  # type: ignore
            raise Web3ValueError(f"Recursively called {to_wrap} with {args!r}")
        to_wrap.__already_called[thread_local_args] = True  # type: ignore
        try:
            wrapped_val = to_wrap(*args)
        finally:
            del to_wrap.__already_called[thread_local_args]  # type: ignore
        return wrapped_val

    return wrapped


def deprecated_for(replace_message: str) -> Callable[..., Any]:
    """
    Decorate a deprecated function, with info about what to use instead, like:

    @deprecated_for("to_bytes()")
    def toAscii(arg):
        ...
    """

    def decorator(to_wrap: TFunc) -> TFunc:
        @functools.wraps(to_wrap)
        def wrapper(*args: Any, **kwargs: Any) -> Callable[..., Any]:
            warnings.warn(
                f"{to_wrap.__name__} is deprecated in favor of {replace_message}",
                category=DeprecationWarning,
                stacklevel=2,
            )
            return to_wrap(*args, **kwargs)

        return cast(TFunc, wrapper)

    return decorator
