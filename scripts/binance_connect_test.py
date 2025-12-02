import asyncio
from typing import Dict, Set, List

from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.client.config.security import Security
from hummingbot.data_feed.market_data_provider import MarketDataProvider  # adjust import path if needed
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
class BinanceConnectTest(ScriptStrategyBase):
    tick_interval = 300

    markets: Dict[str, Set[str]] = {}
    
    connector_name = "binance"

    def connect_to_binance(self):
        self.logger().info("Initializing Binance connection...")

        api_keys = Security.api_keys("binance")
        if not api_keys:
            self.logger().error("No Binance API keys. Run `config binance`.")
            return

        # ScriptStrategyBase will create/connect markets from `markets` automatically. [web:16]

        # Wait until connectors are actually ready before logging pairs
        self.logger().info(f"{api_keys}")
        self.logger().info("Creating trading pairs")
        self.wait_and_log_trading_pairs()

        self.logger().info("on_start completed, waiting for connectors to be ready...")

    def wait_and_log_trading_pairs(self):
        """
        Wait until all connectors in this script are ready, then log all Binance trading pairs.
        Uses MarketDataProvider.get_trading_pairs(), which reads connector.trading_pairs. [web:24]
        """
        # Poll until ScriptStrategyBase marks all connectors ready
        # while not self.ready_to_trade:
        #     await asyncio.sleep(1)

        self.logger().info("All connectors ready, fetching trading pairs via MarketDataProvider...")

        # Use the same connectors dict that ScriptStrategyBase manages
        self.logger().info(f"Connectors available: {self.connector_name}")
        
        self.logger().info(f"{self.connectors}")
        
        connector_setting = AllConnectorSettings.get_connector_settings()[self.connector_name]
        inst = TradingPairFetcher.get_instance()
        binance_pairs: List[str] = inst.trading_pairs
        
        # mdp = MarketDataProvider(self.connectors)

        # # This directly uses connector.trading_pairs, no extra background fetch required. [web:24]
        # binance_pairs: List[str] = mdp.get_trading_pairs("binance")

        self.logger().info(f"Total Binance pairs (from connector.trading_pairs): {len(binance_pairs)}")

        usdt_pairs = [p for p in binance_pairs if p.endswith("-USDT")]
        self.logger().info(f"Total Binance USDT pairs: {len(usdt_pairs)}")

        for p in usdt_pairs[:40]:
            self.logger().info(f"- {p}")
            
        self.market = {
            self.connector_name: set(usdt_pairs)
        }

        self.logger().info("Finished logging Binance USDT pairs.")

    def on_tick(self):
        """
        Spread logging, unchanged, but guard on readiness.
        """
        
        self.connect_to_binance()
        # self.on_start()
        # if not self.ready_to_trade:
        #     # core already logs "binance is not ready. Please wait...", keep this light
        #     return

        for connector_name, trading_pairs in self.markets.items():
            connector = self.connectors.get(connector_name)
            if connector is None:
                self.logger().error(f"Connector {connector_name} not found!")
                continue

            for pair in trading_pairs:
                try:
                    bid = connector.get_price(pair, is_buy=False)
                    ask = connector.get_price(pair, is_buy=True)

                    if bid is None or ask is None:
                        continue

                    spread = ask - bid
                    mid = (ask + bid) / 2
                    spread_pct = (spread / mid) * 100 if mid > 0 else 0

                    self.logger().info(
                        f"{pair} → BID: {bid}, ASK: {ask}, "
                        f"SPREAD: {spread:.6f} ({spread_pct:.4f}%)"
                    )
                except Exception as e:
                    self.logger().warning(f"{pair} error: {e}")
