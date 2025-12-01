import sqlite3
from typing import Dict, Set
from hummingbot.core.data_type.common import PriceType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
import os
import time
from hummingbot.strategy_v2.models.executor_actions import StoreExecutorAction
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher

class USDTQuoteSpreadViewer(ScriptStrategyBase):

    interval_sec = 900  # 15 minutes
    last_run = 0

    # Manually defined markets
    markets: Dict[str, Set[str]] = {
        "binance_perpetual": {"BTC-USDT", "ETH-USDT", "LTC-USDT", "XRP-USDT", "ADA-USDT", "DOGE-USDT", "SOL-USDT"}
    }

    connector_name = "binance_perpetual"

    def __init__(self, *args, **kwargs):
        # get all trading pairs
        super().__init__(*args, **kwargs)

        try:
            connector_setting = AllConnectorSettings.get_connector_settings()[self.connector_name]
            inst = TradingPairFetcher.get_instance()
            trading_pairs = inst.trading_pairs
            self.logger().info(f"Trading pairs: {trading_pairs}")
            # self.markets = {self.connector_name: set(trading_pairs)}
        except Exception as e:
            self.logger().error(f"Error fetching trading pairs: {str(e)}")
        # trading_pairs = gateway_connector_trading_pairs(conn_setting.name)
        # self.logger().info(trading_pairs)
        # self.markets = {self.connectors: set(trading_pairs)}
        # super().__init__()
        # pass

    def store_spread_executor(self, ts, exchange, pair, bid, ask, spread):
        action = StoreExecutorAction(
            controller_id="spread_viewer",
            executor_id=f"{exchange}_{pair}_{ts}",
            payload={"timestamp": ts, "exchange": exchange, "pair": pair, "bid": bid, "ask": ask, "spread": spread},
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
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS spreads (timestamp INTEGER, exchange TEXT, pair TEXT, bid REAL, ask REAL, spread REAL)"
            )
            # self.logger().info(f"Spread Table Ensured in DB: {db_path}")
            cursor.execute("INSERT INTO spreads VALUES (?, ?, ?, ?, ?, ?)", (ts, exchange, pair, bid, ask, spread))
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
                    # market_books = [(self._market_info.market, self._market_info.trading_pair)]
                    order_book = connector.get_order_book(trading_pair)
                    mid_price = MarketDataProvider.get_instance().get_price_by_type(
                        connector_name, trading_pair, PriceType.MidPrice
                    )
                    self.logger().info(f"Mid Price for {trading_pair}: {mid_price}")
                    market = MarketDataProvider.get_instance().get_market(connector_name)
                    bid_price = market.get_price(trading_pair, False)
                    ask_price = market.get_price(trading_pair, True)

                    if bid_price and ask_price and ask_price > 0:
                        spread_pct = ((bid_price - ask_price) / bid_price) * 100

                        # Log to console
                        self.logger().info(
                            f"{connector_name} {trading_pair}: "
                            f"Bid={bid_price:.4f} Ask={ask_price:.4f} Spread={spread_pct:.4f}%"
                        )

                        # Save to DB
                        self.save_spread(now, connector_name, trading_pair, bid_price, ask_price, spread_pct)

                except Exception as e:
                    self.logger().warning(f"{connector_name} {trading_pair}: Error - {str(e)}")
