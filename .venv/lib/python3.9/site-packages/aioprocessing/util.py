import asyncio


def run_in_executor(executor, callback, *args, loop=None, **kwargs):
    if not loop:
        loop = asyncio.get_event_loop()
    if kwargs:
        return loop.run_in_executor(
            executor, lambda: callback(*args, **kwargs)
        )
    else:
        return loop.run_in_executor(executor, callback, *args)
