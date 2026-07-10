"""BTC price feed from Vishwa Lab oracle."""

import asyncio
import logging
from decimal import Decimal
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class BTCPriceFeed:
    """Fetches BTC price from vault.vishwalab.com oracle."""

    def __init__(self, url: str, update_interval: float = 10.0):
        self._url = url
        self._update_interval = update_interval
        self._price: Optional[Decimal] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False

    @property
    def price(self) -> Optional[Decimal]:
        return self._price

    @property
    def is_ready(self) -> bool:
        return self._price is not None

    async def start(self):
        self._running = True
        self._client = httpx.AsyncClient(timeout=10.0)
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(f"BTCPriceFeed started, polling {self._url} every {self._update_interval}s")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.aclose()

    async def _poll_loop(self):
        while self._running:
            try:
                await self._fetch_price()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error fetching BTC price: {e}")
            await asyncio.sleep(self._update_interval)

    async def _fetch_price(self):
        """Fetch price from the oracle API."""
        resp = await self._client.get(self._url)
        if resp.status_code != 200:
            raise Exception(f"Oracle API returned status {resp.status_code}")

        data = resp.json()

        # Try to extract price from various response formats
        if isinstance(data, (int, float)):
            self._price = Decimal(str(data))
        elif isinstance(data, dict):
            if "price" in data:
                self._price = Decimal(str(data["price"]))
            elif "value" in data:
                self._price = Decimal(str(data["value"]))
            elif "data" in data and isinstance(data["data"], dict):
                if "price" in data["data"]:
                    self._price = Decimal(str(data["data"]["price"]))
                elif "value" in data["data"]:
                    self._price = Decimal(str(data["data"]["value"]))
            elif "result" in data:
                self._price = Decimal(str(data["result"]))
            else:
                for v in data.values():
                    if isinstance(v, (int, float)):
                        self._price = Decimal(str(v))
                        break
        elif isinstance(data, str):
            self._price = Decimal(data.strip())

        if self._price:
            logger.debug(f"BTC price updated: {self._price}")
        else:
            logger.warning(f"Could not parse price from response: {data}")
