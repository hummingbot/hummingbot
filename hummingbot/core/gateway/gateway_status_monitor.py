import asyncio
import logging
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.client.settings import (
    GATEWAY_CHAINS,
    GATEWAY_CONNECTORS,
    GATEWAY_ETH_CONNECTORS,
    GATEWAY_NAMESPACES,
    AllConnectorSettings,
    ConnectorSetting,
    ConnectorType,
)
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.gateway_config_utils import build_config_namespace_keys

POLL_INTERVAL = 2.0
POLL_TIMEOUT = 1.0

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class GatewayStatus(Enum):
    ONLINE = 1
    OFFLINE = 2


class GatewayStatusMonitor:
    _monitor_task: Optional[asyncio.Task]
    _gateway_status: GatewayStatus
    _sm_logger: Optional[logging.Logger] = None

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls._sm_logger is None:
            cls._sm_logger = logging.getLogger(__name__)
        return cls._sm_logger

    def __init__(self, app: "HummingbotApplication"):
        self._app = app
        self._gateway_status = GatewayStatus.OFFLINE
        self._monitor_task = None
        self._gateway_config_keys: List[str] = []
        self._gateway_ready_event: asyncio.Event = asyncio.Event()

    @property
    def ready(self) -> bool:
        return self.gateway_status is GatewayStatus.ONLINE

    @property
    def ready_event(self) -> asyncio.Event:
        return self._gateway_ready_event

    @property
    def gateway_status(self) -> GatewayStatus:
        return self._gateway_status

    @property
    def gateway_config_keys(self) -> List[str]:
        return self._gateway_config_keys

    @gateway_config_keys.setter
    def gateway_config_keys(self, new_config: List[str]):
        self._gateway_config_keys = new_config

    def start(self):
        self._monitor_task = safe_ensure_future(self._monitor_loop())

    def stop(self):
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            self._monitor_task = None

    async def wait_for_online_status(self, max_tries: int = 30):
        """
        Wait for gateway status to go online with a max number of tries. If it
        is online before time is up, it returns early, otherwise it returns the
        current status after the max number of tries.

        :param max_tries: maximum number of retries (default is 30)
        """
        while True:
            if self.ready or max_tries <= 0:
                return self.ready
            await asyncio.sleep(POLL_INTERVAL)
            max_tries = max_tries - 1

    async def _monitor_loop(self):
        while True:
            try:
                gateway_http_client = self._get_gateway_instance()
                if await asyncio.wait_for(gateway_http_client.ping_gateway(), timeout=POLL_TIMEOUT):
                    if self.gateway_status is GatewayStatus.OFFLINE:
                        # Clear all collections
                        GATEWAY_CONNECTORS.clear()
                        GATEWAY_ETH_CONNECTORS.clear()
                        GATEWAY_CHAINS.clear()
                        GATEWAY_NAMESPACES.clear()

                        # Get connectors
                        gateway_connectors = await gateway_http_client.get_connectors(fail_silently=True)

                        # Build connector list with trading types appended
                        connector_list = []
                        eth_connector_list = []
                        for connector in gateway_connectors.get("connectors", []):
                            name = connector["name"]
                            chain = connector.get("chain", "")
                            trading_types = connector.get("trading_types", [])

                            # Add each trading type as a separate entry
                            for trading_type in trading_types:
                                connector_full_name = f"{name}/{trading_type}"
                                connector_list.append(connector_full_name)
                                # Add to Ethereum connectors if chain is ethereum
                                if chain.lower() == "ethereum":
                                    eth_connector_list.append(connector_full_name)

                        GATEWAY_CONNECTORS.extend(connector_list)
                        GATEWAY_ETH_CONNECTORS.extend(eth_connector_list)

                        # Update AllConnectorSettings with gateway connectors
                        await self._register_gateway_connectors(connector_list)

                        # Get chains using the dedicated endpoint
                        try:
                            chains_response = await gateway_http_client.get_chains(fail_silently=True)
                            if chains_response and "chains" in chains_response:
                                # Extract just the chain names from the response
                                chain_names = [chain_info["chain"] for chain_info in chains_response["chains"]]
                                GATEWAY_CHAINS.extend(chain_names)
                        except Exception:
                            pass

                        # Get namespaces using the dedicated endpoint
                        try:
                            namespaces_response = await gateway_http_client.get_namespaces(fail_silently=True)
                            if namespaces_response and "namespaces" in namespaces_response:
                                GATEWAY_NAMESPACES.extend(sorted(namespaces_response["namespaces"]))
                        except Exception:
                            pass

                        # Update config keys for backward compatibility
                        await self.update_gateway_config_key_list()

                    # If gateway was already online, ensure connectors are registered
                    if self._gateway_status is GatewayStatus.ONLINE and not GATEWAY_CONNECTORS:
                        # Gateway is online but connectors haven't been registered yet
                        await self.ensure_gateway_connectors_registered()

                    self._gateway_status = GatewayStatus.ONLINE
                else:
                    if self._gateway_status is GatewayStatus.ONLINE:
                        self.logger().info("Connection to Gateway container lost...")
                        self._gateway_status = GatewayStatus.OFFLINE

            except asyncio.CancelledError:
                raise
            except Exception:
                """
                We wouldn't be changing any status here because whatever error happens here would have been a result of manipulation data from
                the try block. They wouldn't be as a result of http related error because they're expected to fail silently.
                """
                pass
            finally:
                if self.gateway_status is GatewayStatus.ONLINE:
                    if not self._gateway_ready_event.is_set():
                        self.logger().info("Gateway Service is ONLINE.")
                    self._gateway_ready_event.set()
                else:
                    self._gateway_ready_event.clear()
                await asyncio.sleep(POLL_INTERVAL)

    async def _fetch_gateway_configs(self) -> Dict[str, Any]:
        return await self._get_gateway_instance().get_configuration(fail_silently=True)

    async def update_gateway_config_key_list(self):
        try:
            config_list: List[str] = []
            config_dict: Dict[str, Any] = await self._fetch_gateway_configs()
            build_config_namespace_keys(config_list, config_dict)

            self.gateway_config_keys = config_list
        except Exception:
            self.logger().error("Error fetching gateway configs. Please check that Gateway service is online. ",
                                exc_info=True)

    def _get_gateway_instance(self) -> GatewayHttpClient:
        gateway_instance = GatewayHttpClient.get_instance(self._app.client_config_map)
        return gateway_instance

    async def _register_gateway_connectors(self, connector_list: List[str]):
        """Register gateway connectors in AllConnectorSettings"""
        all_settings = AllConnectorSettings.get_connector_settings()
        for connector_name in connector_list:
            if connector_name not in all_settings:
                # Create connector setting for gateway connector
                all_settings[connector_name] = ConnectorSetting(
                    name=connector_name,
                    type=ConnectorType.GATEWAY_DEX,
                    centralised=False,
                    example_pair="ETH-USDC",
                    use_ethereum_wallet=False,  # Gateway handles wallet internally
                    trade_fee_schema=TradeFeeSchema(
                        maker_percent_fee_decimal=Decimal("0.003"),
                        taker_percent_fee_decimal=Decimal("0.003"),
                    ),
                    config_keys=None,
                    is_sub_domain=False,
                    parent_name=None,
                    domain_parameter=None,
                    use_eth_gas_lookup=False,
                )

    async def ensure_gateway_connectors_registered(self):
        """Ensure gateway connectors are registered in AllConnectorSettings"""
        if self.gateway_status is not GatewayStatus.ONLINE:
            return

        try:
            gateway_http_client = self._get_gateway_instance()
            gateway_connectors = await gateway_http_client.get_connectors(fail_silently=True)

            # Build connector list with trading types appended
            connector_list = []
            for connector in gateway_connectors.get("connectors", []):
                name = connector["name"]
                trading_types = connector.get("trading_types", [])

                # Add each trading type as a separate entry
                for trading_type in trading_types:
                    connector_full_name = f"{name}/{trading_type}"
                    connector_list.append(connector_full_name)

            # Register the connectors
            await self._register_gateway_connectors(connector_list)

        except Exception as e:
            self.logger().error(f"Error ensuring gateway connectors are registered: {e}", exc_info=True)
