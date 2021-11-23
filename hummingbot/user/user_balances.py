from hummingbot.core.utils.market_price import get_last_price
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.client.config.security import Security
from hummingbot.client.config.config_helpers import get_connector_class, get_eth_wallet_private_key
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.connector.connector.balancer.balancer_connector import BalancerConnector
from hummingbot.connector.derivative.perpetual_finance.perpetual_finance_derivative import PerpetualFinanceDerivative
from hummingbot.client.settings import ethereum_required_trading_pairs
from typing import Optional, Dict, List
from decimal import Decimal

from web3 import Web3


class UserBalances:
    __instance = None

    @staticmethod
    def connect_market(exchange, **api_details):
        connector = None
        conn_setting = AllConnectorSettings.get_connector_settings()[exchange]
        if not conn_setting.use_ethereum_wallet:
            connector_class = get_connector_class(exchange)
            init_params = conn_setting.conn_init_parameters(api_details)
            connector = connector_class(**init_params)
        return connector

    # return error message if the _update_balances fails
    @staticmethod
    async def _update_balances(market) -> Optional[str]:
        try:
            await market._update_balances()
        except Exception as e:
            return str(e)
        return None

    @staticmethod
    def instance():
        if UserBalances.__instance is None:
            UserBalances()
        return UserBalances.__instance

    def __init__(self):
        if UserBalances.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            UserBalances.__instance = self
        self._markets = {}

    async def add_exchange(self, exchange, **api_details) -> Optional[str]:
        self._markets.pop(exchange, None)
        market = UserBalances.connect_market(exchange, **api_details)
        err_msg = await UserBalances._update_balances(market)
        if err_msg is None:
            self._markets[exchange] = market
        return err_msg

    def all_balances(self, exchange) -> Dict[str, Decimal]:
        if exchange not in self._markets:
            return None
        return self._markets[exchange].get_all_balances()

    async def update_exchange_balance(self, exchange) -> Optional[str]:
        if exchange in self._markets:
            return await self._update_balances(self._markets[exchange])
        else:
            api_keys = await Security.api_keys(exchange)
            if api_keys:
                return await self.add_exchange(exchange, **api_keys)
            else:
                return "API keys have not been added."

    # returns error message for each exchange
    async def update_exchanges(self, reconnect: bool = False,
                               exchanges: List[str] = []) -> Dict[str, Optional[str]]:
        tasks = []
        # Update user balances, except connectors that use Ethereum wallet.
        if len(exchanges) == 0:
            exchanges = [cs.name for cs in AllConnectorSettings.get_connector_settings().values()]
        exchanges = [cs.name for cs in AllConnectorSettings.get_connector_settings().values() if not cs.use_ethereum_wallet
                     and cs.name in exchanges and not cs.name.endswith("paper_trade")]
        if reconnect:
            self._markets.clear()
        for exchange in exchanges:
            tasks.append(self.update_exchange_balance(exchange))
        results = await safe_gather(*tasks)
        return {ex: err_msg for ex, err_msg in zip(exchanges, results)}

    async def all_balances_all_exchanges(self) -> Dict[str, Dict[str, Decimal]]:
        await self.update_exchanges()
        return {k: v.get_all_balances() for k, v in sorted(self._markets.items(), key=lambda x: x[0])}

    def all_avai_balances_all_exchanges(self) -> Dict[str, Dict[str, Decimal]]:
        return {k: v.available_balances for k, v in sorted(self._markets.items(), key=lambda x: x[0])}

    async def balances(self, exchange, *symbols) -> Dict[str, Decimal]:
        if await self.update_exchange_balance(exchange) is None:
            results = {}
            for token, bal in self.all_balances(exchange).items():
                matches = [s for s in symbols if s.lower() == token.lower()]
                if matches:
                    results[matches[0]] = bal
            return results

    @staticmethod
    def ethereum_balance() -> Decimal:
        ethereum_wallet = global_config_map.get("ethereum_wallet").value
        ethereum_rpc_url = global_config_map.get("ethereum_rpc_url").value
        web3 = Web3(Web3.HTTPProvider(ethereum_rpc_url))
        balance = web3.eth.getBalance(ethereum_wallet)
        balance = web3.fromWei(balance, "ether")
        return balance

    @staticmethod
    async def eth_n_erc20_balances() -> Dict[str, Decimal]:
        ethereum_rpc_url = global_config_map.get("ethereum_rpc_url").value
        # Todo: Use generic ERC20 balance update
        connector = BalancerConnector(ethereum_required_trading_pairs(),
                                      get_eth_wallet_private_key(),
                                      ethereum_rpc_url,
                                      True)
        await connector._update_balances()
        return connector.get_all_balances()

    @staticmethod
    async def xdai_balances() -> Dict[str, Decimal]:
        connector = PerpetualFinanceDerivative("",
                                               get_eth_wallet_private_key(),
                                               "",
                                               True)
        await connector._update_balances()
        return connector.get_all_balances()

    @staticmethod
    def validate_ethereum_wallet() -> Optional[str]:
        if global_config_map.get("ethereum_wallet").value is None:
            return "Ethereum wallet is required."
        if global_config_map.get("ethereum_rpc_url").value is None:
            return "ethereum_rpc_url is required."
        if global_config_map.get("ethereum_rpc_ws_url").value is None:
            return "ethereum_rpc_ws_url is required."
        if global_config_map.get("ethereum_wallet").value not in Security.private_keys():
            return "Ethereum private key file does not exist or corrupts."
        try:
            UserBalances.ethereum_balance()
        except Exception as e:
            return str(e)
        return None

    @staticmethod
    async def base_amount_ratio(exchange, trading_pair, balances) -> Optional[Decimal]:
        try:
            base, quote = trading_pair.split("-")
            base_amount = balances.get(base, 0)
            quote_amount = balances.get(quote, 0)
            price = await get_last_price(exchange, trading_pair)
            total_value = base_amount + (quote_amount / price)
            return None if total_value <= 0 else base_amount / total_value
        except Exception:
            return None
