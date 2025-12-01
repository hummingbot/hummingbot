from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
from hummingbot.client.config.security import Security
from hummingbot.core.connector_manager import ConnectorManager
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from typing import Dict, Set
import asyncio


class BinanceConnectTest(ScriptStrategyBase):
    tick_interval = 900  # 15 minutes

    markets = {
    }

    connector_ready = False

    async def on_start(self):
        self.logger().info("Initializing Binance connection...")

        api_keys = Security.api_keys("binance")
        if not api_keys:
            self.logger().error("❌ No Binance API keys. Run `config binance`.")
            return

        self.manager = ConnectorManager(ClientConfigAdapter({}))

        self.connector = self.manager.create_connector(
            connector_name="binance",
            trading_pairs=[],
            trading_required=False,
            api_keys=api_keys
        )

        self.logger().info("Binance connector created. Waiting for websocket init...")
        await asyncio.sleep(3)

        # Start periodic fetch
        asyncio.create_task(self.periodic_fetch_pairs())

        self.connector_ready = True
        self.logger().info("✔ Binance connector ready.")

    async def periodic_fetch_pairs(self):
        while True:
            await self.fetch_and_print_pairs()
            await asyncio.sleep(900)  

    def on_tick(self):
        for connector_name, trading_pairs in self.markets.items():
            connector = self.connectors.get(connector_name)
            if connector is None:
                self.logger().error(f"Connector {connector_name} not found!")
                continue

            for pair in trading_pairs:
                try:
                    bid = connector.get_price(pair, False)
                    ask = connector.get_price(pair, True)

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
                    
    async def fetch_and_print_pairs(self):
        """
        This part can be async because it is called with asyncio.create_task().
        """
        fetcher = TradingPairFetcher.get_instance()
        await fetcher.fetch_data()

        all_pairs = fetcher.trading_pairs.get("binance", [])
        self.logger().info(f"Total Binance pairs: {len(all_pairs)}")

        usdt_pairs = [p for p in all_pairs if p.endswith("-USDT")]
        self.logger().info(f"Total Binance USDT pairs: {len(usdt_pairs)}")

        # Print a few only
        for p in usdt_pairs[:40]:
            self.logger().info(f"- {p}")

        self.logger().info("✔ Finished fetching Binance USDT pairs.")
