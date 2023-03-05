import asyncio
import logging
from typing import Dict, List, Optional, Set

from hummingbot.client.settings import GatewayConnectionSetting
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.gateway.types import WalletBalances
from hummingbot.core.network_base import NetworkBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.data_feed.utils import split_base_quote
from hummingbot.logger import HummingbotLogger


class BalanceDataFeed(NetworkBase):
    dex_logger: Optional[HummingbotLogger] = None
    gateway_client = GatewayHttpClient.get_instance()

    def __init__(
        self,
        chains: List[str],
        network: str,
        trading_pairs: Set[str],
        update_interval: float,
    ) -> None:
        super().__init__()
        self._ev_loop = asyncio.get_event_loop()
        # segregated by chains
        self._balances: Dict[str, WalletBalances] = {}
        self._update_interval = update_interval
        self.fetch_data_loop_task: Optional[asyncio.Task] = None
        # param required for DEX API request
        self.chains = chains
        self.network = network
        self.trading_pairs = trading_pairs
        self.wallet_address: Optional[str] = None
        self._load_wallet_address()

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.dex_logger is None:
            cls.dex_logger = logging.getLogger(__name__)
        return cls.dex_logger

    @property
    def name(self) -> str:
        return f"BalanceDataFeed"

    @property
    def is_wallet_address_set(self) -> bool:
        return self.wallet_address is not None

    @property
    def token_symbols(self) -> List[str]:
        token_symbols = set()
        for trading_pair in self.trading_pairs:
            base_token, quote_token = split_base_quote(trading_pair)
            token_symbols.add(base_token)
            token_symbols.add(quote_token)
        return list(token_symbols)

    @property
    def balances(self) -> Dict[str, WalletBalances]:
        return self._balances

    def is_ready(self) -> bool:
        return len(self._balances) == len(self.chains)

    async def check_network(self) -> NetworkStatus:
        is_gateway_online = await self.gateway_client.ping_gateway()
        if not is_gateway_online:
            self.logger().warning(f"Gateway is not online. Please check your gateway connection.")
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
                self.logger().network(
                    f"Error getting data from {self.name}",
                    exc_info=True,
                    app_warning_msg=f"Couldn't fetch newest prices from {self.name}. "
                    f"Check network connection. Error: {e}",
                )
            await self._async_sleep(self._update_interval)

    async def _fetch_data(self) -> None:
        if self.is_wallet_address_set:
            await self._update_wallet_balances()
        return

    async def _update_wallet_balances(self) -> None:
        query_chain_balances_tasks = [
            asyncio.create_task(self._register_chain_wallet_balances(chain)) for chain in self.chains
        ]
        await asyncio.gather(*query_chain_balances_tasks)

    async def _register_chain_wallet_balances(self, chain: str) -> None:
        assert self.wallet_address, "Wallet address is not set."
        chain_balances = await self.gateway_client.get_balances(
            chain, self.network, self.wallet_address, self.token_symbols
        )
        self._balances[chain] = WalletBalances(**chain_balances)
        return

    def _load_wallet_address(self) -> None:
        gateway_conf = GatewayConnectionSetting.load()
        wallets = [w for w in gateway_conf if w["chain"] in self.chains and w["network"] == self.network]
        if len(wallets) > 0:
            wallet_addresses = list(set([w["wallet_address"] for w in wallets]))
            self.wallet_address = wallet_addresses[0]
        return

    @staticmethod
    async def _async_sleep(delay: float) -> None:
        """Used to mock in test cases."""
        await asyncio.sleep(delay)
