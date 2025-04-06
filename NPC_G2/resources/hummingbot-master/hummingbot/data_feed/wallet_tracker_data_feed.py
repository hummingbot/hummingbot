import asyncio
import logging
from decimal import Decimal
from typing import Dict, Optional, Set

import pandas as pd

from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.network_base import NetworkBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class WalletTrackerDataFeed(NetworkBase):
    dex_logger: Optional[HummingbotLogger] = None
    gateway_client = GatewayHttpClient.get_instance()

    def __init__(
        self,
        chain: str,
        network: str,
        wallets: Set[str],
        tokens: Set[str],
        update_interval: float = 1.0,
    ) -> None:
        super().__init__()
        self._ev_loop = asyncio.get_event_loop()
        self._chain = chain
        self._network = network
        self._tokens = tokens
        self._wallet_balances: Dict[str, Dict[str, float]] = {wallet: {} for wallet in wallets}
        self._update_interval = update_interval
        self.fetch_data_loop_task: Optional[asyncio.Task] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.dex_logger is None:
            cls.dex_logger = logging.getLogger(__name__)
        return cls.dex_logger

    @property
    def name(self) -> str:
        return f"WalletTrackerDataFeed[{self.chain}-{self.network}]"

    @property
    def chain(self) -> str:
        return self._chain

    @property
    def network(self) -> str:
        return self._network

    @property
    def tokens(self) -> Set[str]:
        return self._tokens

    @property
    def wallet_balances(self) -> Dict[str, Dict[str, float]]:
        return self._wallet_balances

    @property
    def wallet_balances_df(self) -> pd.DataFrame:
        return pd.DataFrame(self._wallet_balances).T

    def is_ready(self) -> bool:
        return all(len(wallet_balances) > 0 for wallet_balances in self._wallet_balances.values())

    async def check_network(self) -> NetworkStatus:
        is_gateway_online = await self.gateway_client.ping_gateway()
        if not is_gateway_online:
            self.logger().warning("Gateway is not online. Please check your gateway connection.")
        return NetworkStatus.CONNECTED if is_gateway_online else NetworkStatus.NOT_CONNECTED

    async def start_network(self) -> None:
        await self.stop_network()
        self.fetch_data_loop_task = safe_ensure_future(self._fetch_data_loop())

    async def stop_network(self) -> None:
        if self.fetch_data_loop_task is not None:
            self.fetch_data_loop_task.cancel()
            self.fetch_data_loop_task = None

    async def _fetch_data_loop(self) -> None:
        while True:
            try:
                await self._fetch_data()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(
                    f"Error getting data from {self.name}"
                    f"Check network connection. Error: {e}",
                )
            await self._async_sleep(self._update_interval)

    async def _fetch_data(self) -> None:
        wallet_balances_tasks = [
            asyncio.create_task(self._update_balances_by_wallet(wallet))
            for wallet in self._wallet_balances.keys()
        ]
        await asyncio.gather(*wallet_balances_tasks)

    async def _update_balances_by_wallet(self, wallet: str) -> None:
        data = await self.gateway_client.get_balances(
            self.chain,
            self.network,
            wallet,
            list(self._tokens)
        )
        self._wallet_balances[wallet] = {token: Decimal(balance) for token, balance in data['balances'].items()}

    @staticmethod
    async def _async_sleep(delay: float) -> None:
        """Used to mock in test cases."""
        await asyncio.sleep(delay)
