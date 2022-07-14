import json
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, Generator, Optional

import aiohttp

from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


@contextmanager
def begin_placeholder_mode(hb: "HummingbotApplication") -> Generator["HummingbotApplication", None, None]:
    hb.app.clear_input()
    hb.placeholder_mode = True
    hb.app.hide_input = True
    try:
        yield hb
    finally:
        hb.app.to_stop_config = False
        hb.placeholder_mode = False
        hb.app.hide_input = False
        hb.app.change_prompt(prompt=">>> ")


class GatewayChainApiManager:
    """
    Manage and test connections from gateway to chain urls.
    """

    async def _test_evm_node(self, chain: str, network: str, node_url: str) -> bool:
        """
        Verify that the node url is valid. If it is an empty string,
        ignore it, but let the user know they cannot connect to the node.
        """
        async with aiohttp.ClientSession() as tmp_client:
            headers = {"Content-Type": "application/json"}
            data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_blockNumber",
                "params": []
            }

            resp = await tmp_client.post(url=node_url,
                                         data=json.dumps(data),
                                         headers=headers)

            success = resp.status == 200
            if success:
                self.notify(f"Successfully pinged the node url for {chain}-{network}: {node_url}.")
            else:
                self.notify(f"Unable to successfully ping the node url for {chain}-{network}: {node_url}. Please try again (it may require an API key).")
            return success

    async def _get_node_url(self, chain: str, network: str) -> Optional[str]:
        """
        Get the node url from user input, then check that it is valid.
        """
        with begin_placeholder_mode(self):
            while True:
                node_url: str = await self.app.prompt(prompt=f"Enter a node url (with API key if necessary) for {chain}-{network}: >>> ")

                self.app.clear_input()

                if self.app.to_stop_config:
                    self.app.to_stop_config = False
                    return None
                try:
                    node_url = node_url.strip()  # help check for an empty string which is valid input
                    # TODO: different behavior will be necessary for non-EVM nodes
                    success: bool = await self._test_evm_node(chain, network, node_url)
                    if not success:
                        # the node URL test was unsuccessful, try again
                        continue
                    return node_url
                except Exception:
                    self.notify(f"Error occured when trying to ping the node URL: {node_url}.")
                    raise

    async def _test_node_url_from_gateway_config(self, chain: str, network: str) -> bool:
        """
        Check if gateway node URL for a chain and network works
        """
        config_dict: Dict[str, Any] = await GatewayHttpClient.get_instance().get_configuration()
        chain_config: Optional[Dict[str, Any]] = config_dict.get(chain)
        if chain_config is not None:
            networks: Optional[Dict[str, Any]] = chain_config.get("networks")
            if networks is not None:
                network_config: Optional[Dict[str, Any]] = networks.get(network)
                if network_config is not None:
                    node_url: Optional[str] = network_config.get("nodeURL")
                    if node_url is not None:
                        return await self._test_evm_node(chain, network, node_url)
                    else:
                        self.notify(f"{chain}.networks.{network}.nodeURL was not found in the gateway config.")
                        return False
                else:
                    self.notify(f"{chain}.networks.{network} was not found in the gateway config.")
                    return False
            else:
                self.notify(f"{chain}.networks was not found in the gateway config.")
                return False
        else:
            self.notify(f"{chain} was not found in the gateway config.")
            return False

    @staticmethod
    async def _update_gateway_chain_network_node_url(chain: str, network: str, node_url: str):
        """
        Update a chain and network's node URL in gateway
        """
        await GatewayHttpClient.get_instance().update_config(f"{chain}.networks.{network}.nodeURL", node_url)
