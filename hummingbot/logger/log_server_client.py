import asyncio
import logging
from typing import Optional
import aiohttp

from hummingbot.core.network_base import NetworkBase, NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class LogServerClient(NetworkBase):
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
        super().__init__()
        self.queue = asyncio.Queue()
        self.consume_queue_task = None

    def request(self, req):
        if not self.started:
            self.start()
        self.queue.put_nowait(req)

    async def consume_queue(self, session):
        while True:
            try:
                req = await self.queue.get()
                self.logger().debug(
                    f"Remote logging payload: {req}"
                )
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

    async def start_network(self):
        self.consume_queue_task = safe_ensure_future(self.request_loop())

    async def stop_network(self):
        if self.consume_queue_task is not None:
            self.consume_queue_task.cancel()
            self.consume_queue_task = None

    async def check_network(self) -> NetworkStatus:
        try:
            loop = asyncio.get_event_loop()
            async with aiohttp.ClientSession(loop=loop,
                                             connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
                async with session.get("https://api.coinalpha.com/reporting-proxy/") as resp:
                    status_text = await resp.text()
                    if status_text != "OK":
                        raise Exception("Log proxy server is down.")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def start(self):
        NetworkBase.start(self)

    def stop(self):
        NetworkBase.stop(self)
