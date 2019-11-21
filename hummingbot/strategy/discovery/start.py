import asyncio
import csv
import pandas as pd
from os.path import (
    join,
    dirname,
)
from typing import (
    List,
    Tuple,
)

import hummingbot
from hummingbot.client.hummingbot_application import MARKET_CLASSES
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
from hummingbot.strategy.discovery.discovery_config_map import discovery_config_map
from hummingbot.strategy.discovery.discovery import DiscoveryMarketPair, DiscoveryStrategy


async def save_discovery_output(self: "hummingbot.client.hummingbot_application.HummingbotApplication"):
    """
    Export discovery strategy output dataframes into a csv file
    """
    fname: str = f"discovery_strategy_output_{pd.Timestamp.now().strftime('%Y-%m-%d-%H-%M-%S')}.csv"
    path = join(dirname(__file__), f"../../../logs/{fname}")
    self.logger().info(f"Saving discovery output...")

    df_list: List[pd.DataFrame] = self.strategy.get_status_dataframes()
    df_titles = ["Market Stats", "Arbitrage Opportunities", "Conversion Rates"]
    if len(df_list) > 0:
        try:
            with open(path, "w") as handle:
                writer = csv.writer(handle, lineterminator='\n')
                for df, title in zip(df_list, df_titles):
                    writer.writerow([title])
                    df.to_csv(handle, index=False)
                    writer.writerow([])
            self.logger().info(f"Successfully saved discovery output to {path}.")
        except Exception as e:
            self.logger().error(f"Error saving discovery result as csv: {str(e)}")
    else:
        self.logger().error("No discovery result to export.")


async def check_discovery_strategy_ready_loop(self: "hummingbot.client.hummingbot_application.HummingbotApplication"):
    """
    Periodically check if the discovery strategy is ready, and notify the user when it is.
    """
    while True:
        try:
            if self.strategy.all_markets_ready:
                await save_discovery_output(self)
                self._notify("Discovery completed. Run status [CTRL + S] to see the report")
                break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"Error in check_discovery_strategy_ready_loop: {str(e)}", exc_info=True)
        finally:
            await asyncio.sleep(5.0)


def start(self: "hummingbot.client.hummingbot_application.HummingbotApplication"):
    try:
        market_1 = discovery_config_map.get("primary_market").value.lower()
        market_2 = discovery_config_map.get("secondary_market").value.lower()
        target_trading_pair_1 = list(discovery_config_map.get("target_trading_pair_1").value)
        target_trading_pair_2 = list(discovery_config_map.get("target_trading_pair_2").value)
        target_profitability = float(discovery_config_map.get("target_profitability").value)
        target_amount = float(discovery_config_map.get("target_amount").value)
        equivalent_token: List[List[str]] = list(discovery_config_map.get("equivalent_tokens").value)

        def filter_trading_pair_by_single_token(self, market_name, single_token_list):
            matched_trading_pairs = set()
            all_trading_pairs: List[str] = TradingPairFetcher.get_instance().trading_pairs.get(market_name, [])
            all_trading_pairs = self._convert_to_exchange_trading_pair(market_name, all_trading_pairs)
            for t in all_trading_pairs:
                try:
                    base_token, quote_token = MARKET_CLASSES[market_name].split_trading_pair(t)
                except Exception:
                    # In case there is an error when parsing trading pairs, ignore that trading pair and continue
                    # with the rest
                    self.logger().error(f"Error parsing trading_pair on {market_name}: {t}", exc_info=True)
                    continue
                if base_token in single_token_list or quote_token in single_token_list:
                    matched_trading_pairs.add(t)
            return list(matched_trading_pairs)

        def process_trading_pair_list(market_name, trading_pair_list):
            filtered_trading_pair = []
            single_tokens = []
            for t in trading_pair_list:
                if t[0] == "<" and t[-1] == ">":
                    single_tokens.append(t[1:-1])
                else:
                    filtered_trading_pair.append(t)
            return filtered_trading_pair + filter_trading_pair_by_single_token(self, market_name, single_tokens)

        if not target_trading_pair_1:
            target_trading_pair_1 = TradingPairFetcher.get_instance().trading_pairs.get(market_1, [])
        if not target_trading_pair_2:
            target_trading_pair_2 = TradingPairFetcher.get_instance().trading_pairs.get(market_2, [])

        target_trading_pairs_1: List[str] = self._convert_to_exchange_trading_pair(market_1, target_trading_pair_1)
        target_trading_pairs_2: List[str] = self._convert_to_exchange_trading_pair(market_2, target_trading_pair_2)

        target_trading_pairs_1 = process_trading_pair_list(market_1, target_trading_pairs_1)
        target_trading_pairs_2 = process_trading_pair_list(market_2, target_trading_pairs_2)

        target_base_quote_1: List[Tuple[str, str]] = self._initialize_market_assets(market_1, target_trading_pairs_1)
        target_base_quote_2: List[Tuple[str, str]] = self._initialize_market_assets(market_2, target_trading_pairs_2)

        market_names: List[Tuple[str, List[str]]] = [(market_1, target_trading_pairs_1), (market_2, target_trading_pairs_2)]

        self._trading_required = False
        self._initialize_wallet(token_trading_pairs=[])  # wallet required only for dex hard dependency
        self._initialize_markets(market_names)

        self.market_pair = DiscoveryMarketPair(
            *(
                [self.markets[market_1], self.markets[market_1].get_active_exchange_markets]
                + [self.markets[market_2], self.markets[market_2].get_active_exchange_markets]
            )
        )

        self.strategy = DiscoveryStrategy(
            market_pairs=[self.market_pair],
            target_trading_pairs=target_base_quote_1 + target_base_quote_2,
            equivalent_token=equivalent_token,
            target_profitability=target_profitability,
            target_amount=target_amount,
        )

        safe_ensure_future(check_discovery_strategy_ready_loop(self))
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Error initializing strategy.", exc_info=True)
