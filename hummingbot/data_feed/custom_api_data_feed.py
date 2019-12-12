import asyncio
import logging
from typing import (
    Dict,
    Optional,
)
from hummingbot.core.network_base import NetworkBase, NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.async_utils import safe_ensure_future


class CustomAPIFeed(NetworkBase):
    cadf_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.cadf_logger is None:
            cls.cadf_logger = logging.getLogger(__name__)
        return cls.cadf_logger

    def __init__(self, api_url, update_interval: float = 5.0):
        super().__init__()
        self._api_url = api_url
        self._check_network_interval = 30.0
        self._ev_loop = asyncio.get_event_loop()
        self._price = 0
        self._update_interval: float = update_interval
        self._fetch_price_task: Optional[asyncio.Task] = None

    @property
    def name(self):
        return "custom_api"

    @property
    def health_check_endpoint(self):
        return self._api_url

    def get_price(self) -> float:
        return self._price

    async def fetch_price_loop(self):
        while True:
            try:
                await self.fetch_price()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(f"Error fetching a new price from {self._api_url}.", exc_info=True,
                                      app_warning_msg="Couldn't fetch newest price from CustomAPI. "
                                                      "Check network connection.")

            await asyncio.sleep(self._update_interval)

    async def fetch_price(self):
        try:
            client = await self._http_client()
            async with client.request("GET", self._api_url) as resp:
                self._price = resp.text()

            self._ready_event.set()
        except Exception:
            raise

    async def start_network(self):
        await self.stop_network()
        self._fetch_price_task = safe_ensure_future(self.fetch_price_loop())

    async def stop_network(self):
        if self._fetch_price_task is not None:
            self._fetch_price_task.cancel()
            self._fetch_price_task = None

    def start(self):
        super().start(self)

    def stop(self):
        super.stop(self)
