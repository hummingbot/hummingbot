import asyncio
import logging


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
