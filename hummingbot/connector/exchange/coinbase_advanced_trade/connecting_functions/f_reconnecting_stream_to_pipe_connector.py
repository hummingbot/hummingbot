import asyncio
import logging
from typing import Awaitable, Callable, Tuple, Type

from ..pipe.data_types import HandlerT, ToDataT
from ..pipe.protocols import PipePutPtl
from .errors import _ReconnectError
from .exception_log_manager import log_exception, log_if_possible
from .f_stream_to_pipe_connector import _StreamSourcePtl, stream_to_pipe_connector


async def _reconnect_logic(
        connect: Callable[[], Awaitable[None]],
        disconnect: Callable[[], Awaitable[None]],
        interval: float) -> None:
    """Helper function to handle reconnection logic."""
    await disconnect()
    await asyncio.sleep(interval)
    await connect()


async def reconnecting_stream_to_pipe_connector(
        *,
        source: _StreamSourcePtl,
        handler: HandlerT,
        destination: PipePutPtl[ToDataT],
        connect: Callable[[], Awaitable[None]],
        disconnect: Callable[[], Awaitable[None]],
        reconnect_interval: float = 1,
        max_reconnect_attempts: int = 5,
        reconnect_exception_type: Tuple[Type[Exception], ...] = (ConnectionError,),
        put_timeout: float = 0.1,
        logger: logging.Logger | None = None) -> None:
    """
    Auto-ReConnects a source StreamMessageIteratorPtl to a destination pipe using a handler function.
    Calls stream_to_pipe_connector() in a loop.

    The handler function can be a synchronous function, an asynchronous function,
    a generator function, or an asynchronous generator function.

    If the handler is a generator or async generator, it is expected to yield
    items that will be put into the destination pipe.

    If the handler is a function or async function, it is expected to return
    a single item that will be put into the destination pipe.

    If the task is cancelled, it will stop the destination pipe.

    :param source: The source stream to receive items from.
    :param handler: The handler function to process items.
    :param destination: The destination pipe to put items into.
    :param connect: A function that will be called to connect to the source.
    :param disconnect: A function that will be called to disconnect from the source.
    :param reconnect_interval: The time to wait between reconnection attempts.
    :param max_reconnect_attempts: The maximum number of reconnection attempts.
    :param reconnect_exception_type: The exception types to allow reconnecting on.
    :param put_timeout: Allowed window to wait for a full pipe to release a spot
    :param logger: Optional logger for logging events and exceptions. If not provided, no logging will occur.
    """

    def reset_on_success():
        nonlocal reconnection_attempts
        reconnection_attempts = 0

    reconnection_attempts: int = 0
    await connect()
    while True:
        try:
            await stream_to_pipe_connector(source=source,
                                           handler=handler,
                                           destination=destination,
                                           allow_reconnect=True,
                                           on_successful_reconnect=reset_on_success,
                                           reconnect_exception_type=reconnect_exception_type,
                                           put_timeout=put_timeout,
                                           logger=logger)
            await disconnect()
            break

        except _ReconnectError as e:
            reconnection_attempts += 1

            if reconnection_attempts > max_reconnect_attempts:
                log_exception(e, logger, 'ERROR', "Max reconnection attempts reached. Aborting")
                await disconnect()
                raise ConnectionError("Max reconnection attempts reached")

            await _reconnect_logic(connect, disconnect, reconnect_interval)

        except asyncio.CancelledError as e:
            log_if_possible(logger, 'WARNING', "Task was cancelled. Closing downstream Pipe")
            await disconnect()
            raise asyncio.CancelledError from e

        except Exception as e:
            log_exception(e, logger, 'ERROR', "Unhandled exception. Closing downstream Pipe")
            await disconnect()
            raise e
