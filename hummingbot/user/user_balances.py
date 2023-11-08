import logging
from decimal import Decimal
from functools import lru_cache
from typing import Dict, List, Optional, Set

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ReadOnlyClientConfigAdapter, get_connector_class
from hummingbot.client.config.security import Security
from hummingbot.client.settings import AllConnectorSettings, GatewayConnectionSetting, gateway_connector_trading_pairs
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.gateway_config_utils import flatten
from hummingbot.core.utils.market_price import get_last_price


class UserBalances:
    __instance = None

    @staticmethod
    def connect_market(exchange, client_config_map: ClientConfigMap, **api_details):
        connector = None
        conn_setting = AllConnectorSettings.get_connector_settings()[exchange]
        if api_details or conn_setting.uses_gateway_generic_connector():
            connector_class = get_connector_class(exchange)
            read_only_client_config = ReadOnlyClientConfigAdapter.lock_config(client_config_map)
            init_params = conn_setting.conn_init_parameters(
                trading_pairs=gateway_connector_trading_pairs(conn_setting.name),
                api_keys=api_details,
                client_config_map=read_only_client_config,
            )

            # collect trading pairs from the gateway connector settings
            trading_pairs: List[str] = gateway_connector_trading_pairs(conn_setting.name)

            # collect unique trading pairs that are for balance reporting only
            if conn_setting.uses_gateway_generic_connector():
                config: Optional[Dict[str, str]] = GatewayConnectionSetting.get_connector_spec_from_market_name(conn_setting.name)
                if config is not None:
                    existing_pairs = set(flatten([x.split("-") for x in trading_pairs]))

                    other_tokens: Set[str] = set(config.get("tokens", "").split(","))
                    other_tokens.discard("")
                    tokens: List[str] = [t for t in other_tokens if t not in existing_pairs]
                    if tokens != [""]:
                        trading_pairs.append("-".join(tokens))

            connector = connector_class(**init_params)
        return connector

    # return error message if the _update_balances fails
    @staticmethod
    async def _update_balances(market) -> Optional[str]:
        try:
            await market._update_balances()
        except Exception as e:
            logging.getLogger().debug(f"Failed to update balances for {market}", exc_info=True)
            return str(e)
        return None

    @staticmethod
    def instance():
        if UserBalances.__instance is None:
            UserBalances()
        return UserBalances.__instance

    @staticmethod
    @lru_cache(maxsize=10)
    def is_gateway_market(exchange_name: str) -> bool:
        return (
            exchange_name in sorted(
                AllConnectorSettings.get_gateway_amm_connector_names().union(
                    AllConnectorSettings.get_gateway_evm_amm_lp_connector_names()
                ).union(
                    AllConnectorSettings.get_gateway_clob_connector_names()
                )
            )
        )

    def __init__(self):
        if UserBalances.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            UserBalances.__instance = self
        self._markets = {}

    async def add_exchange(self, exchange, client_config_map: ClientConfigMap, **api_details) -> Optional[str]:
        self._markets.pop(exchange, None)
        is_gateway_market = self.is_gateway_market(exchange)
        if not is_gateway_market:
            market = UserBalances.connect_market(exchange, client_config_map, **api_details)
            if not market:
                return "API keys have not been added."
            err_msg = await UserBalances._update_balances(market)
            if err_msg is None:
                self._markets[exchange] = market
            return err_msg

    def all_balances(self, exchange) -> Dict[str, Decimal]:
        if exchange not in self._markets:
            return {}
        return self._markets[exchange].get_all_balances()

    async def update_exchange_balance(self, exchange_name: str, client_config_map: ClientConfigMap) -> Optional[str]:
        is_gateway_market = self.is_gateway_market(exchange_name)
        if is_gateway_market and exchange_name in self._markets:
            # we want to refresh gateway connectors always, since the applicable tokens change over time.
            # doing this will reinitialize and fetch balances for active trading pair
            del self._markets[exchange_name]
        if exchange_name in self._markets:
            return await self._update_balances(self._markets[exchange_name])
        else:
            await Security.wait_til_decryption_done()
            api_keys = Security.api_keys(exchange_name) if not is_gateway_market else {}
            return await self.add_exchange(exchange_name, client_config_map, **api_keys)

    # returns error message for each exchange
    async def update_exchanges(
        self,
        client_config_map: ClientConfigMap,
        reconnect: bool = False,
        exchanges: Optional[List[str]] = None
    ) -> Dict[str, Optional[str]]:
        exchanges = exchanges or []
        tasks = []
        # Update user balances
        if len(exchanges) == 0:
            exchanges = [cs.name for cs in AllConnectorSettings.get_connector_settings().values()]
        exchanges: List[str] = [
            cs.name
            for cs in AllConnectorSettings.get_connector_settings().values()
            if not cs.use_ethereum_wallet
            and cs.name in exchanges
            and not cs.name.endswith("paper_trade")
        ]

        if reconnect:
            self._markets.clear()
        for exchange in exchanges:
            tasks.append(self.update_exchange_balance(exchange, client_config_map))
        results = await safe_gather(*tasks)
        return {ex: err_msg for ex, err_msg in zip(exchanges, results)}

    # returns only for non-gateway connectors since balance command no longer reports gateway connector balances
    async def all_balances_all_exchanges(self, client_config_map: ClientConfigMap) -> Dict[str, Dict[str, Decimal]]:
        await self.update_exchanges(client_config_map)
        return {k: v.get_all_balances() for k, v in sorted(self._markets.items(), key=lambda x: x[0]) if not self.is_gateway_market(k)}

    # returns only for non-gateway connectors since balance command no longer reports gateway connector balances
    def all_available_balances_all_exchanges(self) -> Dict[str, Dict[str, Decimal]]:
        return {k: v.available_balances for k, v in sorted(self._markets.items(), key=lambda x: x[0]) if not self.is_gateway_market(k)}

    async def balances(self, exchange, client_config_map: ClientConfigMap, *symbols) -> Dict[str, Decimal]:
        if await self.update_exchange_balance(exchange, client_config_map) is None:
            results = {}
            for token, bal in self.all_balances(exchange).items():
                matches = [s for s in symbols if s.lower() == token.lower()]
                if matches:
                    results[matches[0]] = bal
            return results

    @staticmethod
    def validate_ethereum_wallet() -> Optional[str]:
        return "Connector deprecated."

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
