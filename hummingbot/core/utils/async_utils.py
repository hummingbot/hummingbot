import asyncio
import logging


def asyncio_ensure_future(*args, **kwargs):
    try:
        asyncio.ensure_future(*args, **kwargs)
    except Exception as e:
        logging.getLogger().error(f"Unhandled error in background task: {str(e)}", exc_info=True)


async def asyncio_gather(*args, **kwargs):
    try:
        await asyncio.gather(*args, **kwargs)
    except Exception as e:
        logging.getLogger().debug(f"Unhandled error in background task: {str(e)}", exc_info=True)
