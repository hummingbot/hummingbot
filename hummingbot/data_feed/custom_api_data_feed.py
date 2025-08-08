import asyncio
import logging
from decimal import Decimal
from typing import Optional

import aiohttp

from hummingbot.core.network_base import NetworkBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.pure_market_making.pure_market_making_config_map import pure_market_making_config_map as c_map


class CustomAPIDataFeed(NetworkBase):
    cadf_logger: Optional[HummingbotLogger] = None
    _cgdf_shared_instance: "CustomAPIDataFeed" = None

    @classmethod
    def get_instance(cls) -> "CustomAPIDataFeed":
        if cls._shared_instance is None:
            raise ValueError("CustomAPIDataFeed instance not initialized. Call initialize_instance() first.")
        return cls._shared_instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.cadf_logger is None:
            cls.cadf_logger = logging.getLogger(__name__)
        return cls.cadf_logger

    def __init__(self, api_url, update_interval: float = 5.0):
        super().__init__()
        self._ready_event = asyncio.Event()
        self._shared_client: Optional[aiohttp.ClientSession] = None
        self._api_url = api_url
        self._check_network_interval = 30.0
        self._ev_loop = asyncio.get_event_loop()
        self._price: Decimal = Decimal("0")
        self._update_interval: float = update_interval
        self.fetch_data_loop_task: Optional[asyncio.Task] = None

    @property
    def name(self) -> str:
        return "custom_api"

    @property
    def health_check_endpoint(self) -> str:
        return self._api_url

    async def start_network(self):
        await self.stop_network()
        self.fetch_data_loop_task = safe_ensure_future(self._fetch_data_loop())

    async def stop_network(self):
        if self.fetch_data_loop_task is not None:
            self.fetch_data_loop_task.cancel()
            self.fetch_data_loop_task = None

    def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def check_network(self) -> NetworkStatus:
        client = self._http_client()
        async with client.request("GET", self.health_check_endpoint) as resp:
            status_text = await resp.text()
            if resp.status != 200:
                raise Exception(f"Custom API Feed {self.name} server error: {status_text}")
        return NetworkStatus.CONNECTED

    def get_price(self) -> Decimal:
        return self._price

    async def _fetch_data_loop(self):
        while True:
            try:
                await self.fetch_price()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(f"Error fetching a new price from {self._api_url}.", exc_info=True,
                                      app_warning_msg="Couldn't fetch newest price from CustomAPI. "
                                                      f"Check network connection. Response: {str(e)}")

            await self._async_sleep(self._update_interval)

    async def fetch_price(self):
        client = self._http_client()
        self.logger().info(f"[DEBUG] Fetching price from URL: {self._api_url}")
        headers = c_map.get("header_custom_api").value

        async with client.request("GET", self._api_url, headers=headers) as resp:
            if resp.status != 200:
                resp_text = await resp.text()
                raise Exception(f"Custom API Feed {self.name} server error: {resp_text}")

            try:

                market = c_map.get("market").value.lower()
                price_source_custom_api = c_map.get("price_source_custom_api").value
                invert_custom_api_price = c_map.get("invert_custom_api_price").value
                coin_id_map = c_map.get("coin_id_overrides").value

                if "api.coingecko.com" in price_source_custom_api:
                    data = await resp.json()

                    pair_parts = market.split("-")

                    base_token = pair_parts[0].lower()
                    quote_token = pair_parts[1].lower()

                    # Map tokens to CoinGecko IDs using coin_id_map
                    base_coin_id = coin_id_map.get(base_token) or coin_id_map.get(base_token.upper())
                    quote_coin_id = coin_id_map.get(quote_token) or coin_id_map.get(quote_token.upper())

                    # Coingecko Response:
                    # {"native-decentralized-euro-protocol-share": {"usd": 0.379591}}
                    raw_price = Decimal(str(data[base_coin_id][quote_coin_id]))

                else:
                    # Default Parser - simple decimal from response text
                    resp_text = await resp.text()
                    raw_price = Decimal(str(resp_text))

                self.logger().info(f"Fetched price from API: {raw_price}")

                # Apply inversion if configured
                if invert_custom_api_price:
                    price = Decimal("1") / raw_price
                    self.logger().info(f"Price inverted: {raw_price} -> {price}")
                else:
                    price = raw_price
                    self.logger().info(f"Price used as-is: {price}")

                self._price = price
                self._ready_event.set()

            except Exception as e:
                raise Exception(f"Error parsing JSON response: {str(e)}")

    def start(self):
        NetworkBase.start(self)

    def stop(self):
        NetworkBase.stop(self)

    @staticmethod
    async def _async_sleep(delay: float):
        """Used to mock in test cases."""
        await asyncio.sleep(delay)
