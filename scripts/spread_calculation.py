import asyncio
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
from hummingbot.core.utils.async_utils import safe_ensure_future

class USDTQuoteSpreadViewer(ScriptStrategyBase):

    interval_sec = 900  # 15 minutes
    last_run = 0

    # Manually defined markets
    markets: Dict[str, Set[str]] = {
        "binance": ['BTC-USDT', 'ETH-USDT', 'XRP-USDT']  # Example pairs
    }

    connector_name = "binance"

    def create_markets(self):
        try:
            connector_setting = AllConnectorSettings.get_connector_settings()[self.connector_name]
            inst = TradingPairFetcher.get_instance()
            trading_pairs = inst.trading_pairs.get(self.connector_name, [])
            
            usdt_pairs = [p for p in trading_pairs if p.endswith("-USDT")]
            
            self.markets[self.connector_name] = set(usdt_pairs)
            
        except Exception as e:
            self.logger().error(f"Error fetching trading pairs: {str(e)}")
        self.__init__(connectors=self.connectors)

    async def grid(self):
        now = int(time.time())
        if now - self.last_run < self.interval_sec:
            return

        self.last_run = now
        
        self.create_markets()
                
        for connector_name, trading_pairs in self.markets.items():
            connector = self.connectors.get(connector_name)
            if connector is None:
                self.logger().error(f"Connector {connector_name} not found!")
                continue

            for pair in trading_pairs:
                try:
                    order_book = await connector._orderbook_ds._order_book_snapshot(pair)
                    bid = None
                    ask = None
                    if order_book is not None:
                        bid = float(order_book.content['bids'][0][0])                    
                        ask = float(order_book.content['asks'][0][0])

                    if bid is None or ask is None:
                        continue

                    spread = ask - bid
                    
                    mid_price = (bid + ask) / 2
                    spread_pct = (spread / mid_price) * 100 if mid_price > 0 else 0

                    self.logger().info(
                        f"{pair} → BID: {bid}, ASK: {ask}, "
                        f"SPREAD: {spread:.6f} ({spread_pct:.4f}%)"
                    )
                except Exception as e:
                    self.logger().warning(f"{pair} error: {e}")
                    
    def on_tick(self):
        safe_ensure_future(self.grid())
        
