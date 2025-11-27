import sqlite3
from typing import Dict, Set
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
import os
import time
from hummingbot.strategy_v2.models.executor_actions import StoreExecutorAction

class USDTQuoteSpreadViewer(ScriptStrategyBase):

    interval_sec = 900  # 15 minutes
    last_run = 0

    # Manually defined markets
    markets: Dict[str, Set[str]] = {
        "binance_paper_trade": {
            "BTC-USDT", "ETH-USDT", "LTC-USDT",
            "XRP-USDT", "ADA-USDT", "DOGE-USDT", "SOL-USDT"
        },
    }
    
    def store_spread_executor(self, ts, exchange, pair, bid, ask, spread):
        action = StoreExecutorAction(
            controller_id="spread_viewer",
            executor_id=f"{exchange}_{pair}_{ts}",
            payload={
                "timestamp": ts,
                "exchange": exchange,
                "pair": pair,
                "bid": bid,
                "ask": ask,
                "spread": spread
            }
        )
        try:
            self.store_executor(action)
        except Exception as e:
            self.logger().error(f"Failed to store spread executor: {str(e)}")

    def save_spread(self, ts, exchange, pair, bid, ask, spread):
        db_path = os.path.join("data", "my_grid_strike.sqlite")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS spreads (timestamp INTEGER, exchange TEXT, pair TEXT, bid REAL, ask REAL, spread REAL)")
            # self.logger().info(f"Spread Table Ensured in DB: {db_path}")
            cursor.execute(
                "INSERT INTO spreads VALUES (?, ?, ?, ?, ?, ?)",
                (ts, exchange, pair, bid, ask, spread)
            )
            conn.commit()
            # self.logger().info(f"DB Path Used: {db_path}")
            conn.close()
        except Exception as e:
            self.logger().error(f"DB Insert Error: {e}")

    # ------------ Spread Calculation ------------ #
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

            for trading_pair in trading_pairs:
                try:
                    order_book = connector.get_order_book(trading_pair)
                    bid = order_book.get_price(True)
                    ask = order_book.get_price(False)

                    if bid and ask and ask > 0:
                        spread_pct = ((ask - bid) / bid) * 100

                        # Log to console
                        self.logger().info(
                            f"{connector_name} {trading_pair}: "
                            f"Bid={bid:.4f} Ask={ask:.4f} Spread={spread_pct:.4f}%"
                        )

                        # Save to DB
                        self.save_spread(
                            now,
                            connector_name,
                            trading_pair,
                            bid,
                            ask,
                            spread_pct
                        )

                except Exception as e:
                    self.logger().warning(
                        f"{connector_name} {trading_pair}: Error - {str(e)}"
                    )
