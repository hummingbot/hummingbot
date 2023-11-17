import asyncio
import logging
from dataclasses import dataclass, field
from functools import partial
from typing import Any, Awaitable, Callable, Dict, Generic, Tuple, TypeVar

from .errors import ExceptionWithItem

T = TypeVar('T')


@dataclass
class CallOrAwait(Generic[T]):
    """
    Wrapper for calling a function or awaiting a coroutine function.

    :param func: The function or coroutine to call.
    :param args: Positional arguments to pass to the function.
    :param kwargs: Keyword arguments to pass to the function.
    """
    func: Callable[..., Awaitable[T]] | Callable[..., T]
    args: Tuple[Any, ...] = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    logger: logging.Logger | None = field(default=None)

    def __post_init__(self):
        """
        Initializes the wrapper.

        :raises: TypeError if the function is not callable or
                the args are not a tuple or
                the kwargs is not a dict.
        """

        if self.func is None:
            return

        if not callable(self.func):
            raise TypeError("func must be a callable function")

        if not isinstance(self.args, tuple):
            raise TypeError("args must be a tuple")

        if not isinstance(self.kwargs, dict):
            raise TypeError("kwargs must be a dict")

        _call: Callable = partial(self.func, *self.args, **self.kwargs)

        if asyncio.iscoroutinefunction(self.func):
            self._call: Callable[..., Awaitable[T]] = _call
        else:
            self._call: Callable[..., Awaitable[T]] = partial(asyncio.to_thread, _call)

    async def call(self, *, logger: logging.Logger | None = None) -> T | None:
        """
        Calls a function or awaits a coroutine function.

        :param logger: Optional logger for logging events and exceptions. If not provided, no logging will occur.
        :raises: ExceptionWithItem if the function raises an exception.
                 Captures the function name, args, kwargs, and the original function.
        :return: The result of the function call.
        """
        if self.func is None:
            return None

        try:
            return await self._call()

        except Exception as e:
            name: str = getattr(self.func, '__name__', '[function name undefined]')
            if _logger := logger or self.logger:
                from .exception_log_manager import log_exception
                message: str = f"Failed while executing function: {name}. Error: {e}"
                log_exception(e, _logger, "ERROR", message)
            raise ExceptionWithItem(
                f"Failed while executing function: {name}.",
                item={
                    "func": name,
                    "args": self.args,
                    "kwargs": self.kwargs,
                    "original_function": self.func}
            ) from e
