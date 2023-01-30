import asyncio
import inspect
import logging
import time


async def safe_wrapper(c):
    try:
        return await c
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logging.getLogger(__name__).error(f"Unhandled error in background task: {str(e)}", exc_info=True)


def safe_ensure_future(coro, *args, **kwargs):
    return asyncio.ensure_future(safe_wrapper(coro), *args, **kwargs)


async def safe_gather(*args, **kwargs):
    try:
        return await asyncio.gather(*args, **kwargs)
    except Exception as e:
        logging.getLogger(__name__).debug(f"Unhandled error in background task: {str(e)}", exc_info=True)
        raise


async def wait_til(condition_func, timeout=10):
    start_time = time.perf_counter()
    while True:
        if condition_func():
            return
        elif time.perf_counter() - start_time > timeout:
            raise Exception(f"{inspect.getsource(condition_func).strip()} condition is never met. Time out reached.")
        else:
            await asyncio.sleep(0.1)


async def run_command(*args):
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    return stdout.decode().strip()


def call_sync(coro,
              loop: asyncio.AbstractEventLoop,
              timeout: float = 30.0):
    import threading
    if threading.current_thread() != threading.main_thread():  # pragma: no cover
        fut = asyncio.run_coroutine_threadsafe(
            asyncio.wait_for(coro, timeout),
            loop
        )
        return fut.result()
    elif not loop.is_running():
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            logging.getLogger(__name__).debug(
                "Runtime error in call_sync - Using new event loop to exec coro",
                exc_info=True
            )
            loop = asyncio.new_event_loop()
    return loop.run_until_complete(asyncio.wait_for(coro, timeout))
