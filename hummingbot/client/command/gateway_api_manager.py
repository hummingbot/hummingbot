from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, Generator, Optional

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

    async def _check_node_status(self, chain: str, network: str, node_url: str) -> bool:
        """
        Verify that the node url is valid. If it is an empty string,
        ignore it, but let the user know they cannot connect to the node.
        """

        resp = await GatewayHttpClient.get_instance().get_network_status(chain, network)

        if resp.get("currentBlockNumber", -1) > 0:
            self.notify(f"Successfully pinged the node url for {chain}-{network}: {node_url}.")
            return True
        return False

    async def _test_node_url(self, chain: str, network: str) -> Optional[str]:
        """
        Get the node url from user input, then check that it is valid.
        """
        with begin_placeholder_mode(self):
            while True:
                node_url: str = await self.app.prompt(prompt=f"Enter a node url (with API key if necessary) for {chain}-{network}: >>> ")

                self.app.clear_input()
                self.app.change_prompt(prompt="")

                if self.app.to_stop_config:
                    self.app.to_stop_config = False
                    self.stop()
                    return None
                try:
                    node_url = node_url.strip()  # help check for an empty string which is valid input

                    await self._update_gateway_chain_network_node_url(chain, network, node_url)

                    self.notify("Restarting gateway to update with new node url...")
                    # wait about 30 seconds for the gateway to restart
                    gateway_live = await self.ping_gateway_api(30)
                    if not gateway_live:
                        self.notify("Error: unable to restart gateway. Try 'start' again after gateway is running.")
                        self.notify("Stopping strategy...")
                        self.stop()

                    success: bool = await self._check_node_status(chain, network, node_url)
                    if not success:
                        # the node URL test was unsuccessful, try again
                        continue
                    return node_url
                except Exception:
                    self.notify(f"Error occured when trying to ping the node URL: {node_url}.")

    async def _test_node_url_from_gateway_config(self, chain: str, network: str, attempt_connection: bool = True) -> bool:
        """
        Check if gateway node URL for a chain and network works
        """
        # XXX: This should be removed once nodeAPIKey is deprecated from Gateway service
        config_dict: Dict[str, Any] = await GatewayHttpClient.get_instance().get_configuration()
        chain_config: Optional[Dict[str, Any]] = config_dict.get(chain)
        if chain_config is not None:
            networks: Optional[Dict[str, Any]] = chain_config.get("networks")
            if networks is not None:
                network_config: Optional[Dict[str, Any]] = networks.get(network)
                if network_config is not None:
                    node_url: Optional[str] = network_config.get("nodeURL")
                    if not attempt_connection:
                        while True:
                            change_node: str = await self.app.prompt(prompt=f"Do you want to continue to use node url '{node_url}' for {chain}-{network}? (Yes/No) ")
                            if self.app.to_stop_config:
                                return
                            if change_node in ["Y", "y", "Yes", "yes", "N", "n", "No", "no"]:
                                break
                            self.notify("Invalid input. Please try again or exit config [CTRL + x].\n")

                        self.app.clear_input()
                        # they use an existing wallet
                        if change_node is not None and change_node in ["N", "n", "No", "no"]:
                            node_url: str = await self.app.prompt(prompt=f"Enter a new node url (with API key if necessary) for {chain}-{network}: >>> ")
                            await self._update_gateway_chain_network_node_url(chain, network, node_url)
                            self.notify("Restarting gateway to update with new node url...")
                            # wait about 30 seconds for the gateway to restart
                            await self.ping_gateway_api(30)
                        return True
                    success: bool = await self._check_node_status(chain, network, node_url)
                    if not success:
                        try:
                            return await self._test_node_url(chain, network)
                        except Exception:
                            self.notify(f"Unable to successfully ping the node url for {chain}-{network}: {node_url}. Please try again (it may require an API key).")
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
