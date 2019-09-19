import asyncio
import logging


def safe_ensure_future(coro, *args, **kwargs):
    async def safe_wrapper(c):
        try:
            return await c
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logging.getLogger().error(f"Unhandled error in background task: {str(e)}", exc_info=True)

    return asyncio.ensure_future(safe_wrapper(coro), *args, **kwargs)


async def safe_gather(*args, **kwargs):
    try:
        return await asyncio.gather(*args, **kwargs)
    except Exception as e:
        logging.getLogger().debug(f"Unhandled error in background task: {str(e)}", exc_info=True)
        raise
