import asyncio
import logging
from typing import Optional
import aiohttp

from hummingbot.logger import HummingbotLogger


class LogServerClient:
    lsc_logger: Optional[HummingbotLogger] = None
    _lsc_shared_instance: "LogServerClient" = None

    @classmethod
    def get_instance(cls) -> "LogServerClient":
        if cls._lsc_shared_instance is None:
            cls._lsc_shared_instance = LogServerClient()
        return cls._lsc_shared_instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.lsc_logger is None:
            cls.lsc_logger = logging.getLogger(__name__)
        return cls.lsc_logger

    def __init__(self):
        self.queue = asyncio.Queue()
        self.consume_queue_task = None
        self.started = False

    def request(self, req):
        if not self.started:
            self.start()
        self.queue.put_nowait(req)

    async def consume_queue(self, session):
        while True:
            try:
                req = await self.queue.get()
                async with session.request(req["method"], req["url"], **req["request_obj"]) as resp:
                    resp_text = await resp.text()
                    self.logger().debug(f"Sent logs: {resp.status} {resp.url} {resp_text} ",
                                        extra={"do_not_send": True})

            except asyncio.CancelledError:
                raise
            except aiohttp.ClientError:
                self.logger().network(f"Network error sending logs.", exc_info=True, extra={"do_not_send": True})
                return
            except Exception:
                self.logger().network(f"Unexpected error sending logs.", exc_info=True, extra={"do_not_send": True})
                return

    async def request_loop(self):
        while True:
            loop = asyncio.get_event_loop()
            try:
                async with aiohttp.ClientSession(loop=loop,
                                                 connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
                    await self.consume_queue(session)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(f"Unexpected error running logging task.",
                                      exc_info=True, extra={"do_not_send": True})
                await asyncio.sleep(5.0)

    def start(self):
        self.consume_queue_task = asyncio.ensure_future(self.request_loop())
        self.started = True

    def stop(self):
        if self.consume_queue_task:
            self.consume_queue_task.cancel()
        self.started = False
