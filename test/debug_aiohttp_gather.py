#!/usr/bin/env python

import aiohttp
import asyncio
import pandas as pd
import random
import time
from typing import (
    NamedTuple,
    List,
    Dict,
    Optional
)
from hummingbot.core.utils.async_utils import safe_gather

shared_client_session: Optional[aiohttp.ClientSession] = None


class FetchTask(NamedTuple):
    nonce: int
    future: asyncio.Future

    @classmethod
    def create_task(cls):
        global shared_client_session
        nonce: int = random.randint(0, 0xffffffff)
        future: asyncio.Future = shared_client_session.get("https://postman-echo.com/get", params={"nonce": nonce})
        return FetchTask(nonce, future)


async def init_client():
    global shared_client_session
    if shared_client_session is None:
        shared_client_session = aiohttp.ClientSession()


async def generate_tasks(length: int) -> List[FetchTask]:
    return [FetchTask.create_task() for _ in range(0, length)]


async def main():
    await init_client()

    while True:
        try:
            tasks: List[FetchTask] = await generate_tasks(10)
            results: List[aiohttp.ClientResponse] = await safe_gather(*[t.future for t in tasks])
            data: List[Dict[str, any]] = await safe_gather(*[r.json() for r in results])
            mismatches: int = 0

            for task, response in zip(tasks, data):
                returned_nonce: int = int(response["args"]["nonce"])
                if task.nonce != returned_nonce:
                    print(f"  - Error: requested for {task.nonce} but got {returned_nonce} back.")
                    mismatches += 1

            if mismatches < 1:
                print(f"[{str(pd.Timestamp.utcnow())}] All fetches passed.")
            else:
                print(f"[{str(pd.Timestamp.utcnow())}] {mismatches} out of 10 requests failed.")

            now: float = time.time()
            next_tick: float = now // 1 + 1
            await asyncio.sleep(next_tick - now)
        except asyncio.CancelledError:
            raise


if __name__ == "__main__":
    ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    try:
        ev_loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Done!")
