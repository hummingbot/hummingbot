# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

"""A few useful function/method decorators."""

from __future__ import annotations

import functools
import inspect
import sys
import warnings
from collections.abc import Callable, Generator
from typing import TypeVar

from astroid import util
from astroid.context import InferenceContext
from astroid.exceptions import InferenceError
from astroid.typing import InferenceResult

if sys.version_info >= (3, 10):
    from typing import ParamSpec
else:
    from typing_extensions import ParamSpec

_R = TypeVar("_R")
_P = ParamSpec("_P")


def path_wrapper(func):
    """Return the given infer function wrapped to handle the path.

    Used to stop inference if the node has already been looked
    at for a given `InferenceContext` to prevent infinite recursion
    """

    @functools.wraps(func)
    def wrapped(
        node, context: InferenceContext | None = None, _func=func, **kwargs
    ) -> Generator:
        """Wrapper function handling context."""
        if context is None:
            context = InferenceContext()
        if context.push(node):
            return

        yielded = set()

        for res in _func(node, context, **kwargs):
            # unproxy only true instance, not const, tuple, dict...
            if res.__class__.__name__ == "Instance":
                ares = res._proxied
            else:
                ares = res
            if ares not in yielded:
                yield res
                yielded.add(ares)

    return wrapped


def yes_if_nothing_inferred(
    func: Callable[_P, Generator[InferenceResult]]
) -> Callable[_P, Generator[InferenceResult]]:
    def inner(*args: _P.args, **kwargs: _P.kwargs) -> Generator[InferenceResult]:
        generator = func(*args, **kwargs)

        try:
            yield next(generator)
        except StopIteration:
            # generator is empty
            yield util.Uninferable
            return

        yield from generator

    return inner


def raise_if_nothing_inferred(
    func: Callable[_P, Generator[InferenceResult]],
) -> Callable[_P, Generator[InferenceResult]]:
    def inner(*args: _P.args, **kwargs: _P.kwargs) -> Generator[InferenceResult]:
        generator = func(*args, **kwargs)
        try:
            yield next(generator)
        except StopIteration as error:
            # generator is empty
            if error.args:
                raise InferenceError(**error.args[0]) from error
            raise InferenceError(
                "StopIteration raised without any error information."
            ) from error
        except RecursionError as error:
            raise InferenceError(
                f"RecursionError raised with limit {sys.getrecursionlimit()}."
            ) from error

        yield from generator

    return inner


# Expensive decorators only used to emit Deprecation warnings.
# If no other than the default DeprecationWarning are enabled,
# fall back to passthrough implementations.
if util.check_warnings_filter():  # noqa: C901

    def deprecate_default_argument_values(
        astroid_version: str = "3.0", **arguments: str
    ) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
        """Decorator which emits a DeprecationWarning if any arguments specified
        are None or not passed at all.

        Arguments should be a key-value mapping, with the key being the argument to check
        and the value being a type annotation as string for the value of the argument.

        To improve performance, only used when DeprecationWarnings other than
        the default one are enabled.
        """
        # Helpful links
        # Decorator for DeprecationWarning: https://stackoverflow.com/a/49802489
        # Typing of stacked decorators: https://stackoverflow.com/a/68290080

        def deco(func: Callable[_P, _R]) -> Callable[_P, _R]:
            """Decorator function."""

            @functools.wraps(func)
            def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
                """Emit DeprecationWarnings if conditions are met."""

                keys = list(inspect.signature(func).parameters.keys())
                for arg, type_annotation in arguments.items():
                    try:
                        index = keys.index(arg)
                    except ValueError:
                        raise ValueError(
                            f"Can't find argument '{arg}' for '{args[0].__class__.__qualname__}'"
                        ) from None
                    if (
                        # Check kwargs
                        # - if found, check it's not None
                        (arg in kwargs and kwargs[arg] is None)
                        # Check args
                        # - make sure not in kwargs
                        # - len(args) needs to be long enough, if too short
                        #   arg can't be in args either
                        # - args[index] should not be None
                        or arg not in kwargs
                        and (
                            index == -1
                            or len(args) <= index
                            or (len(args) > index and args[index] is None)
                        )
                    ):
                        warnings.warn(
                            f"'{arg}' will be a required argument for "
                            f"'{args[0].__class__.__qualname__}.{func.__name__}'"
                            f" in astroid {astroid_version} "
                            f"('{arg}' should be of type: '{type_annotation}')",
                            DeprecationWarning,
                            stacklevel=2,
                        )
                return func(*args, **kwargs)

            return wrapper

        return deco

    def deprecate_arguments(
        astroid_version: str = "3.0", **arguments: str
    ) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
        """Decorator which emits a DeprecationWarning if any arguments specified
        are passed.

        Arguments should be a key-value mapping, with the key being the argument to check
        and the value being a string that explains what to do instead of passing the argument.

        To improve performance, only used when DeprecationWarnings other than
        the default one are enabled.
        """

        def deco(func: Callable[_P, _R]) -> Callable[_P, _R]:
            @functools.wraps(func)
            def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
                keys = list(inspect.signature(func).parameters.keys())
                for arg, note in arguments.items():
                    try:
                        index = keys.index(arg)
                    except ValueError:
                        raise ValueError(
                            f"Can't find argument '{arg}' for '{args[0].__class__.__qualname__}'"
                        ) from None
                    if arg in kwargs or len(args) > index:
                        warnings.warn(
                            f"The argument '{arg}' for "
                            f"'{args[0].__class__.__qualname__}.{func.__name__}' is deprecated "
                            f"and will be removed in astroid {astroid_version} ({note})",
                            DeprecationWarning,
                            stacklevel=2,
                        )
                return func(*args, **kwargs)

            return wrapper

        return deco

else:

    def deprecate_default_argument_values(
        astroid_version: str = "3.0", **arguments: str
    ) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
        """Passthrough decorator to improve performance if DeprecationWarnings are
        disabled.
        """

        def deco(func: Callable[_P, _R]) -> Callable[_P, _R]:
            """Decorator function."""
            return func

        return deco

    def deprecate_arguments(
        astroid_version: str = "3.0", **arguments: str
    ) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
        """Passthrough decorator to improve performance if DeprecationWarnings are
        disabled.
        """

        def deco(func: Callable[_P, _R]) -> Callable[_P, _R]:
            """Decorator function."""
            return func

        return deco
