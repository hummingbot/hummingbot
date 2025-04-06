import asyncio
import inspect
import logging
import time
import threading


async def safe_wrapper(c):
    """
    Safely wraps a coroutine to handle exceptions. This function ensures that any unhandled exceptions in the coroutine are logged and the coroutine is not allowed to silently fail.

    If the coroutine is cancelled, the CancelledError exception is re-raised. For any other exceptions, the error is logged at the error level and the exception is re-raised.

    Args:
        c (coroutine): The coroutine to be wrapped.

    Returns:
        The result of the wrapped coroutine.
    """

    try:
        return await c
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logging.getLogger(__name__).error(
            f"Unhandled error in background task: {str(e)}", exc_info=True
        )


def safe_ensure_future(coro, *args, **kwargs):
    """
    Safely wraps a coroutine to handle exceptions. This function ensures that any unhandled exceptions in the coroutine are logged and the coroutine is not allowed to silently fail.

    If the coroutine is cancelled, the CancelledError exception is re-raised. For any other exceptions, the error is logged at the error level and the exception is re-raised.

    Args:
        coro (coroutine): The coroutine to be wrapped.
        *args: Additional arguments to pass to `asyncio.ensure_future`.
        **kwargs: Additional keyword arguments to pass to `asyncio.ensure_future`.

    Returns:
        The result of the wrapped coroutine.
    """

    return asyncio.ensure_future(safe_wrapper(coro), *args, **kwargs)


async def safe_gather(*args, **kwargs):
    """
    Safely gathers the results of multiple coroutines, handling any exceptions that may occur.

    This function wraps a call to `asyncio.gather()` and ensures that any unhandled exceptions in the gathered coroutines are logged at the debug level. If any exceptions occur, they are re-raised after being logged.

    Args:
        *args: The coroutines to be gathered.
        **kwargs: Additional keyword arguments to pass to `asyncio.gather()`.

    Returns:
        The results of the gathered coroutines.
    """

    try:
        return await asyncio.gather(*args, **kwargs)
    except Exception as e:
        logging.getLogger(__name__).debug(
            f"Unhandled error in background task: {str(e)}", exc_info=True
        )
        raise


async def wait_til(condition_func, timeout=10):
    """
    Waits until the given condition function returns True, or a timeout is reached.

    Args:
        condition_func (callable): A function that returns True when the condition is met.
        timeout (float, optional): The maximum time in seconds to wait for the condition to be met. Defaults to 10 seconds.

    Raises:
        Exception: If the condition function is never met within the specified timeout.
    """

    start_time = time.perf_counter()
    while True:
        if condition_func():
            return
        elif time.perf_counter() - start_time > timeout:
            raise Exception(
                f"{inspect.getsource(condition_func).strip()} condition is never met. Time out reached."
            )
        else:
            await asyncio.sleep(0.1)


async def run_command(*args):
    """
    Runs a command asynchronously and returns the stdout output.

    Args:
        *args: The command to execute and any arguments.

    Returns:
        The stdout output of the command as a string, with any trailing whitespace removed.
    """

    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return stdout.decode().strip()


def call_sync(coro, loop: asyncio.AbstractEventLoop, timeout: float = 30.0):
    """
    Runs a coroutine in a synchronous context, with an optional timeout.

    If the current thread is not the main thread, the coroutine is executed in a separate thread using `asyncio.run_coroutine_threadsafe()`. Otherwise, if the current event loop is not running, a new event loop is created and used to execute the coroutine with `asyncio.wait_for()`.

    Args:
        coro (coroutine): The coroutine to be executed.
        loop (asyncio.AbstractEventLoop, optional): The event loop to use. If not provided, the default event loop is used.
        timeout (float, optional): The maximum time in seconds to wait for the coroutine to complete. Defaults to 30 seconds.

    Returns:
        The result of the coroutine.

    Raises:
        Exception: If the coroutine does not complete within the specified timeout.
    """

    if threading.current_thread() != threading.main_thread():  # pragma: no cover
        fut = asyncio.run_coroutine_threadsafe(asyncio.wait_for(coro, timeout), loop)
        return fut.result()
    elif not loop.is_running():
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            logging.getLogger(__name__).debug(
                "Runtime error in call_sync - Using new event loop to exec coro",
                exc_info=True,
            )
            loop = asyncio.new_event_loop()
    return loop.run_until_complete(asyncio.wait_for(coro, timeout))
