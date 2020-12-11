import asyncio
import requests
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
from hummingbot.client.settings import GATEAWAY_CA_CERT_PATH, GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH

ETH_GASSTATION_API_URL = "https://data-api.defipulse.com/api/v1/egs/api/ethgasAPI.json?api-key={}"


def get_gas_price(in_gwei: bool = True) -> Decimal:
    if not global_config_map["ethgasstation_gas_enabled"].value:
        gas_price = global_config_map["manual_gas_price"].value
    else:
        gas_price = EthGasStationLookup.get_instance().gas_price
    return gas_price if in_gwei else gas_price / Decimal("1e9")


def get_gas_limit(connector_name: str) -> int:
    gas_limit = request_gas_limit(connector_name)
    return gas_limit


def request_gas_limit(connector_name: str) -> int:
    host = global_config_map["gateway_api_host"].value
    port = global_config_map["gateway_api_port"].value
    balancer_max_swaps = global_config_map["balancer_max_swaps"].value

    base_url = ':'.join(['https://' + host, port])
    url = f"{base_url}/{connector_name}/gas-limit"

    ca_certs = GATEAWAY_CA_CERT_PATH
    client_certs = (GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH)
    params = {"maxSwaps": balancer_max_swaps} if connector_name == "balancer" else {}
    response = requests.post(url, data=params, verify=ca_certs, cert=client_certs)
    parsed_response = response.json()
    if response.status_code != 200:
        err_msg = ""
        if "error" in parsed_response:
            err_msg = f" Message: {parsed_response['error']}"
        raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.{err_msg}")
    if "error" in parsed_response:
        raise Exception(f"Error: {parsed_response['error']}")
    return parsed_response['gasLimit']


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
        self._gas_limits: Dict[str, Decimal] = {}
        self._balancer_max_swaps: int = global_config_map["balancer_max_swaps"].value
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

    @property
    def gas_limits(self):
        return self._gas_limits

    @gas_limits.setter
    def gas_limits(self, gas_limits: Dict[str, int]):
        for key, value in gas_limits.items():
            self._gas_limits[key] = value

    @property
    def balancer_max_swaps(self):
        return self._balancer_max_swaps

    @balancer_max_swaps.setter
    def balancer_max_swaps(self, max_swaps: int):
        self._balancer_max_swaps = max_swaps

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
                    self.logger().info(f"Gas levels: [{prices_str}]")
                    for name, con_setting in CONNECTOR_SETTINGS.items():
                        if con_setting.use_eth_gas_lookup:
                            self._gas_limits[name] = get_gas_limit(name)
                            self.logger().info(f"{name} Gas estimate:"
                                               f" limit = {self._gas_limits[name]:.0f},"
                                               f" price = {self.gas_level.name},"
                                               f" estimated cost = {get_gas_price(False) * self._gas_limits[name]:.5f} ETH")
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
