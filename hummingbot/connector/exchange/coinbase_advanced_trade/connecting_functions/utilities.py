import asyncio
import logging
from functools import partial
from typing import Any, AsyncGenerator, Awaitable, Callable, Generator, Iterable, Type, TypeVar, Union

from ..pipe import PipePutPtl
from ..pipe.data_types import FromDataT, ToDataT
from .call_or_await import CallOrAwait
from .errors import ConditionalPutError, DataGeneratorError, DataTransformerError, DestinationPutError, SourceGetError
from .exception_log_manager import log_exception, raise_with_item, try_except_conditional_raise


async def _no_async_op():
    pass


def _no_sync_op():
    pass


T = TypeVar('T')
U = TypeVar('U')

MultiTypeDataT = T | Iterable[T] | AsyncGenerator[T, None]

MultiTypeDataHandlerT = Union[
    Callable[[T], U] |
    Callable[[T], Iterable[U]] |
    Callable[[T], Awaitable[U]] |
    Callable[[T], Generator[U, None, None]] |
    Callable[[T], AsyncGenerator[U, None]]
]


async def data_to_async_generator(
        data: MultiTypeDataT | None,
        *,
        exception: Type[Exception] = DataGeneratorError,
        logger: logging.Logger | None = None
) -> AsyncGenerator[T, None]:
    """
    Constructs an async generator for the given data.

    :param data: The data to construct an async generator from. Can be a single item,
                 a synchronous generator, or an async generator.
    :param exception: Exception to raise if the handler raises an exception.
    :param logger: Optional logger for logging events and exceptions.
                   If not provided, no logging will occur.
    :return: An async generator yielding items from the data.
    :raises: TypeError if the data is not an Iterable or AsyncGenerator.
             ExceptionWithItem (DataGeneratorError as default) if the data generation raises an exception.

    """
    if data is None:
        return

    try:
        if isinstance(data, AsyncGenerator):
            async for sub_item in data:
                yield sub_item

        elif isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
            for sub_item in data:
                yield sub_item

        else:
            yield data

    except Exception as e:
        log_exception(e, logger, 'ERROR')
        raise_with_item(e, exception, data)


async def _apply_transform(
        generator: AsyncGenerator[T, None],
        transform: MultiTypeDataHandlerT,
        *,
        logger: logging.Logger | None = None,
) -> AsyncGenerator[U, None]:
    """
    Applies a transform function to each item in an async generator.

    :param generator: The async generator to transform.
    :param transform: The transform function to apply to each item.
    :param logger: Optional logger for logging events and exceptions.
    :return: An async generator yielding transformed items from the original generator.
    """

    call: Callable[[...], Awaitable[U]] = partial(CallOrAwait, transform)
    try_call: Callable[[CallOrAwait[U]], Awaitable[U]] = partial(try_except_conditional_raise,
                                                                 exception=DataTransformerError,
                                                                 logger=logger)
    data_gen: Callable[[MultiTypeDataT], AsyncGenerator[U, None]] = partial(data_to_async_generator, logger=logger)

    try:
        if transform is None:
            async for item in generator:
                yield item
            return

        async for item in generator:
            transformed: MultiTypeDataT = await try_call(call((item,)))
            async_gen: AsyncGenerator[U, None] = data_gen(transformed)

            async for u in async_gen:
                yield u

    except asyncio.CancelledError as e:
        log_exception(e, logger, 'WARNING', "Failed while executing transform")
        return

    except (DataTransformerError, DataGeneratorError) as e:
        raise e

    except Exception as e:
        log_exception(e, logger, 'ERROR', "Failed while executing transform")
        raise SourceGetError from e


async def transform_async_generator(
        generator: AsyncGenerator[T, None] | None,
        transform: MultiTypeDataHandlerT | None,
        *,
        exception: Type[Exception] | None = None,
        logger: logging.Logger | None = None,
) -> AsyncGenerator[U, None]:
    """
    Transforms an async generator.

    :param generator: The async generator to transform.
    :param transform: The transform function to apply to each item.
    :param exception: Exception to raise if the handler raises an exception.
    :param logger: Optional logger for logging events and exceptions.
    :return: An async generator yielding transformed items from the original generator.
    :raises: TypeError if the generator is not an AsyncGenerator or
             if the transform is not callable.
             ExceptionWithItem if the transform raises an exception.
    """
    if not isinstance(generator, AsyncGenerator):
        raise TypeError("generator must be an AsyncGenerator")

    if transform is not None and not callable(transform):
        raise TypeError("Item processor (func) must be a callable function")

    if generator is None:
        return

    try:
        async for item in _apply_transform(generator, transform, logger=logger):
            yield item

    except asyncio.CancelledError as e:
        log_exception(e, logger, 'WARNING', "Failed while executing transform")
        return

    except Exception as e:
        log_exception(e, logger, 'ERROR', "Failed while executing transform")
        raise_with_item(e, exception)


async def put_on_condition(
        data: MultiTypeDataT | None,
        *args: Any,
        destination: PipePutPtl[ToDataT],
        on_condition: Callable[[FromDataT | ToDataT], bool] | None = None,
        logger: logging.Logger | None = None,
        **kwargs: Any) -> None:
    """
    Puts an item into a destination pipe if the item meets a condition.

    :param data: The item to put into the destination pipe.
    :param destination: The destination pipe to put the item into.
    :param on_condition: An optional function that validates whether the result should be put into the destination.
    :param logger: Optional logger for logging events and exceptions. If not provided, no logging will occur.
    :param kwargs: Optional keyword arguments to pass to the destination pipe's put() method.
    :raises: TypeError if the data_generator is not an AsyncGenerator.
             DataGeneratorError if the data_generator raises an exception.
             ConditionalPutError if the on_condition function raises an exception.
             DestinationPutError if the destination pipe's put() method raises an exception.
    """
    if on_condition is None:
        on_condition: Callable[[FromDataT | ToDataT], bool] = lambda x: True

    try:
        async for item in data_to_async_generator(data, exception=DataGeneratorError):
            if await try_except_conditional_raise(
                    CallOrAwait(on_condition, (item,)),
                    exception=ConditionalPutError):
                await try_except_conditional_raise(
                    CallOrAwait(
                        destination.put,
                        (item, *args),
                        kwargs
                    ),
                    exception=DestinationPutError, )

    except (ConditionalPutError, DestinationPutError, DataGeneratorError) as e:
        log_exception(e, logger, 'ERROR', "Failed to put item into destination pipe.")
        e.item = {"data": data, "item": e.item}
        raise e

    except Exception as e:
        log_exception(e, logger, 'ERROR', "Failure of the data generator.")
        raise e
