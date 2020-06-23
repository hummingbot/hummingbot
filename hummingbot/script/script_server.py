from multiprocessing import Process, Queue
from hummingbot.script.script_process import run_script
from hummingbot.script.script_interface import StrategyParameters, OnTick
from decimal import Decimal
import asyncio


async def listen_to_client(child_queue):
    while True:
        if child_queue.empty():
            await asyncio.sleep(1)
            continue
        item = child_queue.get()
        print(f"parent gets: {item.__class__}")


def listen_to_client_sync():
    while True:
        item = child_queue.get()
        print(f"parent gets: {item.__class__}")


async def main(ev_loop, parent_queue, child_queue, proc):
    await asyncio.sleep(1)

    # async_scheduler = AsyncCallScheduler(call_interval=0.5)
    # safe_ensure_future(async_scheduler.call_async(listen_to_client_sync))
    asyncio.ensure_future(listen_to_client(child_queue))
    await asyncio.sleep(1)
    parent_queue.put(OnTick(Decimal(100), StrategyParameters(1, 2, 3)))
    await asyncio.sleep(1)
    # asyncio.ensure_future(listen_to_client(child_queue), loop=ev_loop)
    await asyncio.sleep(2)
    proc.join()


if __name__ == '__main__':
    proc = None
    parent_queue = Queue()
    child_queue = Queue()
    proc = Process(target=run_script, args=(parent_queue, child_queue,))
    proc.start()
    ev_loop = asyncio.get_event_loop()
    ev_loop.run_until_complete(main(ev_loop, parent_queue, child_queue, proc))
