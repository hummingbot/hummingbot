import asyncio
import logging
from typing import Any, Dict, Optional

import aiohttp

from hummingbot.core.network_base import NetworkBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_retry import async_retry
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class LogServerClient(NetworkBase):
    lsc_logger: Optional[HummingbotLogger] = None
    _lsc_shared_instance: "LogServerClient" = None

    @classmethod
    def get_instance(cls, log_server_url: str = "https://api.coinalpha.com/reporting-proxy-v2/") -> "LogServerClient":
        if cls._lsc_shared_instance is None:
            cls._lsc_shared_instance = LogServerClient(log_server_url=log_server_url)
        return cls._lsc_shared_instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.lsc_logger is None:
            cls.lsc_logger = logging.getLogger(__name__)
        return cls.lsc_logger

    def __init__(self, log_server_url: str = "https://api.coinalpha.com/reporting-proxy-v2/"):
        super().__init__()
        self.queue: asyncio.Queue = asyncio.Queue()
        self.consume_queue_task: Optional[asyncio.Task] = None
        self.log_server_url: str = log_server_url

    def request(self, req):
        if not self.started:
            self.start()
        self.queue.put_nowait(req)

    @async_retry(retry_count=3, exception_types=[asyncio.TimeoutError, EnvironmentError], raise_exp=True)
    async def send_log(self, session: aiohttp.ClientSession, request_dict: Dict[str, Any]):
        async with session.request(request_dict["method"], request_dict["url"], **request_dict["request_obj"]) as resp:
            resp_text = await resp.text()
            self.logger().debug(f"Sent logs: {resp.status} {resp.url} {resp_text} ",
                                extra={"do_not_send": True})
            if resp.status != 200 and resp.status not in {404, 405, 400}:
                raise EnvironmentError("Failed sending logs to log server.")

    async def consume_queue(self, session):
        while True:
            try:
                req = await self.queue.get()
                self.logger().debug(f"Remote logging payload: {req}")
                await self.send_log(session, req)
            except asyncio.CancelledError:
                raise
            except aiohttp.ClientError:
                self.logger().network("Network error sending logs.", exc_info=True, extra={"do_not_send": True})
                return
            except Exception:
                self.logger().network("Unexpected error sending logs.", exc_info=True, extra={"do_not_send": True})
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
                self.logger().network("Unexpected error running logging task.",
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
                async with session.get(self.log_server_url) as resp:
                    if resp.status != 200:
                        raise Exception("Log proxy server is down.")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED
