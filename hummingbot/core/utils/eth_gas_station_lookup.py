import asyncio
import logging
from typing import (
    Optional,
    Dict,
    Any
)
import aiohttp
from enum import Enum
from decimal import Decimal
from hummingbot.core.network_base import (
    NetworkBase,
    NetworkStatus
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.settings import CONNECTOR_SETTINGS

ETH_GASSTATION_API_URL = "https://data-api.defipulse.com/api/v1/egs/api/ethgasAPI.json?api-key={}"


def get_gas_price(in_gwei: bool = True) -> Decimal:
    if not global_config_map["ethgasstation_gas_enabled"].value:
        gas_price = global_config_map["manual_gas_price"].value
    else:
        gas_price = EthGasStationLookup.get_instance().gas_price
    return gas_price if in_gwei else gas_price / Decimal("1e9")


class GasLevel(Enum):
    fast = "fast"
    fastest = "fastest"
    safeLow = "safeLow"
    average = "average"


class EthGasStationLookup(NetworkBase):
    _egsl_logger: Optional[HummingbotLogger] = None
    _shared_instance: "EthGasStationLookup" = None

    @classmethod
    def get_instance(cls) -> "EthGasStationLookup":
        if cls._shared_instance is None:
            cls._shared_instance = EthGasStationLookup()
        return cls._shared_instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._egsl_logger is None:
            cls._egsl_logger = logging.getLogger(__name__)
        return cls._egsl_logger

    def __init__(self):
        super().__init__()
        self._gas_prices: Dict[str, Decimal] = {}
        self._async_task = None

    @property
    def api_key(self):
        return global_config_map["ethgasstation_api_key"].value

    @property
    def gas_level(self) -> GasLevel:
        return GasLevel[global_config_map["ethgasstation_gas_level"].value]

    @property
    def refresh_time(self):
        return global_config_map["ethgasstation_refresh_time"].value

    @property
    def gas_price(self):
        return self._gas_prices[self.gas_level]

    async def gas_price_update_loop(self):
        while True:
            try:
                url = ETH_GASSTATION_API_URL.format(self.api_key)
                async with aiohttp.ClientSession() as client:
                    response = await client.get(url=url)
                    if response.status != 200:
                        raise IOError(f"Error fetching current gas prices. "
                                      f"HTTP status is {response.status}.")
                    resp_data: Dict[str, Any] = await response.json()
                    for key, value in resp_data.items():
                        if key in GasLevel.__members__:
                            self._gas_prices[GasLevel[key]] = Decimal(str(value)) / Decimal("10")
                    prices_str = ', '.join([k.name + ': ' + str(v) for k, v in self._gas_prices.items()])
                    self.logger().info(f"Gas: [{prices_str}]")
                    for name, con_setting in CONNECTOR_SETTINGS.items():
                        if con_setting.use_eth_gas_lookup:
                            self.logger().info(f"Estimated gas used per transaction ({self.gas_level.name}): "
                                               f"{get_gas_price(False) * con_setting.gas_limit:.5f} ETH")
                    await asyncio.sleep(self.refresh_time)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error running logging task.", exc_info=True)
                await asyncio.sleep(self.refresh_time)

    async def start_network(self):
        self._async_task = safe_ensure_future(self.gas_price_update_loop())

    async def stop_network(self):
        if self._async_task is not None:
            self._async_task.cancel()
            self._async_task = None

    async def check_network(self) -> NetworkStatus:
        try:
            url = ETH_GASSTATION_API_URL.format(self.api_key)
            async with aiohttp.ClientSession() as client:
                response = await client.get(url=url)
                if response.status != 200:
                    raise Exception(f"Error connecting to {url}. HTTP status is {response.status}.")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def start(self):
        NetworkBase.start(self)

    def stop(self):
        NetworkBase.stop(self)
