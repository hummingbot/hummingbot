import functools
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
)

from web3.exceptions import (
    Web3ValidationError,
)
from web3.providers import (
    PersistentConnectionProvider,
)

if TYPE_CHECKING:
    from web3.main import (  # noqa: F401
        AsyncWeb3,
    )


def persistent_connection_provider_method(message: str = None) -> Callable[..., Any]:
    """
    Decorator that raises an exception if the provider is not an instance of
    ``PersistentConnectionProvider``.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def inner(self: "AsyncWeb3", *args: Any, **kwargs: Any) -> Any:
            nonlocal message
            if message is None:
                message = (
                    f"``{func.__name__}`` can only be called on a "
                    "``PersistentConnectionProvider`` instance."
                )

            if not isinstance(self.provider, PersistentConnectionProvider):
                raise Web3ValidationError(message)
            return func(self, *args, **kwargs)

        return inner

    return decorator
