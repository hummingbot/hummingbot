from typing import List, Tuple

import hummingbot
from hummingbot.core.utils.symbol_fetcher import SymbolFetcher
from hummingbot.strategy.discovery.discovery_config_map import discovery_config_map
from hummingbot.strategy.discovery.discovery import DiscoveryMarketPair, DiscoveryStrategy


def start(self: "hummingbot.client.hummingbot_application.HummingbotApplication"):
    try:
        market_1 = discovery_config_map.get("primary_market").value.lower()
        market_2 = discovery_config_map.get("secondary_market").value.lower()
        target_symbol_1 = list(discovery_config_map.get("target_symbol_1").value)
        target_symbol_2 = list(discovery_config_map.get("target_symbol_2").value)
        target_profitability = float(discovery_config_map.get("target_profitability").value)
        target_amount = float(discovery_config_map.get("target_amount").value)
        equivalent_token: List[List[str]] = list(discovery_config_map.get("equivalent_tokens").value)

        if not target_symbol_2:
            target_symbol_2 = SymbolFetcher.get_instance().symbols.get(market_2, [])
        if not target_symbol_1:
            target_symbol_1 = SymbolFetcher.get_instance().symbols.get(market_1, [])

        market_names: List[Tuple[str, List[str]]] = [(market_1, target_symbol_1), (market_2, target_symbol_2)]
        target_base_quote_1: List[Tuple[str, str]] = self._initialize_market_assets(market_1, target_symbol_1)
        target_base_quote_2: List[Tuple[str, str]] = self._initialize_market_assets(market_2, target_symbol_2)

        self._trading_required = False
        self._initialize_wallet(token_symbols=[])  # wallet required only for dex hard dependency
        self._initialize_markets(market_names)

        self.market_pair = DiscoveryMarketPair(
            *(
                [self.markets[market_1], self.markets[market_1].get_active_exchange_markets]
                + [self.markets[market_2], self.markets[market_2].get_active_exchange_markets]
            )
        )
        self.strategy = DiscoveryStrategy(
            market_pairs=[self.market_pair],
            target_symbols=target_base_quote_1 + target_base_quote_2,
            equivalent_token=equivalent_token,
            target_profitability=target_profitability,
            target_amount=target_amount,
        )
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Error initializing strategy.", exc_info=True)
