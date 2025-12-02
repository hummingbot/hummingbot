import sqlite3
import os
import time
from typing import Dict, Set

from pydantic import BaseModel
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher


class USDTQuoteSpreadViewerConfig(BaseModel):
    connector_name: str = "binance"
    interval_sec: int = 900  # 15 minutes


class USDTQuoteSpreadViewer(ScriptStrategyBase):
    connector_name: str = "binance"
    interval_sec: int = 900

    markets: Dict[str, Set[str]] = {
        "binance": {
            "BTC-USDT",
            "ETH-USDT",
            "LTC-USDT",
            "XRP-USDT",
            "ADA-USDT",
            "DOGE-USDT",
            "SOL-USDT"
        }
    }

    last_run: int = 0

    async def on_start(self):
        """
        Fetch trading pairs dynamically and subscribe to their order books after connectors are ready.
        """
        try:
            fetcher = TradingPairFetcher.get_instance()
            await fetcher.ready()
            trading_pairs = fetcher.trading_pairs

            if self.connector_name in trading_pairs:
                usdt_pairs = {p for p in trading_pairs[self.connector_name] if p.endswith("-USDT")}
                if usdt_pairs:
                    self.markets = {self.connector_name: usdt_pairs}
                    self.logger().info(f"Loaded {len(usdt_pairs)} USDT pairs dynamically.")

                    connector = self.connectors.get(self.connector_name)
                    if connector is not None:
                        if hasattr(connector, "add_markets"):
                            connector.add_markets(list(usdt_pairs))
                            self.logger().info(f"Subscribed to {len(usdt_pairs)} markets on {self.connector_name}.")
                        else:
                            self.logger().warning(
                                f"Connector {self.connector_name} does not support add_markets(). "
                                f"Skipping subscription, but markets are still set."
                            )
                    else:
                        self.logger().warning(f"Connector {self.connector_name} not found to subscribe markets.")

                else:
                    self.logger().warning("No USDT pairs found dynamically, using fallback list.")
            else:
                self.logger().warning(
                    f"TradingPairFetcher has no data for connector {self.connector_name}. Using fallback list."
                )
        except Exception as e:
            self.logger().error(f"Failed to load trading pairs dynamically: {e}")

        self.logger().info(f"Final markets: {self.markets}")

    # ------------------------------
    # SQLite save
    # ------------------------------
    def save_spread(self, ts, exchange, pair, bid, ask, spread):
        os.makedirs("data", exist_ok=True)
        db_path = os.path.join("data", "my_grid_strike.sqlite")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS spreads (
                    timestamp INTEGER,
                    exchange TEXT,
                    pair TEXT,
                    bid REAL,
                    ask REAL,
                    spread REAL
                )
            """)
            cursor.execute(
                "INSERT INTO spreads VALUES (?, ?, ?, ?, ?, ?)",
                (ts, exchange, pair, bid, ask, spread)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger().error(f"DB Insert Error: {e}")

    def on_tick(self):
        now = int(time.time())
        if now - self.last_run < self.interval_sec:
            return

        self.last_run = now

        for connector_name, trading_pairs in self.markets.items():
            connector = self.connectors.get(connector_name)

            if connector is None:
                self.logger().warning(f"{now} Connector not found: {connector_name}")
                continue

            if not connector.ready:
                self.logger().warning(f"{connector_name} connector not ready. Waiting...")
                continue

            for trading_pair in trading_pairs:
                try:
                    order_book = connector.get_order_book(trading_pair)

                    if order_book is None:
                        self.logger().warning(f"{connector_name} {trading_pair}: No order book yet")
                        continue

                    bids = list(order_book.bid_entries())
                    asks = list(order_book.ask_entries())

                    top_bid = bids[0].price if bids else None
                    top_ask = asks[0].price if asks else None

                    bid = top_bid
                    ask = top_ask

                    self.logger().info(f"{trading_pair} TB {top_bid} TA {top_ask}")


                    if bid is None or ask is None or ask <= 0:
                        continue

                    spread_pct = ((ask - bid) / bid) * 100

                    self.logger().info(
                        f"{connector_name} {trading_pair} - "
                        f"Bid: {bid:.6f}  Ask: {ask:.6f}  Spread: {spread_pct:.4f}%"
                    )

                    self.save_spread(now, connector_name, trading_pair, bid, ask, spread_pct)

                except Exception as e:
                    self.logger().warning(f"{connector_name} {trading_pair}: Error - {str(e)}")
