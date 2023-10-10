import json
import os
from datetime import datetime
from typing import Dict

from hummingbot import data_path
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.core.event.events import OrderBookEvent, OrderBookTradeEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DownloadTradesAndOrderBookSnapshots(ScriptStrategyBase):
    exchange = os.getenv("EXCHANGE", "binance_paper_trade")
    trading_pairs = os.getenv("TRADING_PAIRS", "ETH-USDT,BTC-USDT")
    depth = int(os.getenv("DEPTH", 50))
    trading_pairs = [pair for pair in trading_pairs.split(",")]
    last_dump_timestamp = 0
    time_between_csv_dumps = 10

    ob_temp_storage = {trading_pair: [] for trading_pair in trading_pairs}
    trades_temp_storage = {trading_pair: [] for trading_pair in trading_pairs}
    current_date = None
    ob_file_paths = {}
    trades_file_paths = {}
    markets = {exchange: set(trading_pairs)}
    subscribed_to_order_book_trade_event: bool = False

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.create_order_book_and_trade_files()
        self.order_book_trade_event = SourceInfoEventForwarder(self._process_public_trade)

    def on_tick(self):
        if not self.subscribed_to_order_book_trade_event:
            self.subscribe_to_order_book_trade_event()
        self.check_and_replace_files()
        for trading_pair in self.trading_pairs:
            order_book_data = self.get_order_book_dict(self.exchange, trading_pair, self.depth)
            self.ob_temp_storage[trading_pair].append(order_book_data)
        if self.last_dump_timestamp < self.current_timestamp:
            self.dump_and_clean_temp_storage()

    def get_order_book_dict(self, exchange: str, trading_pair: str, depth: int = 50):
        order_book = self.connectors[exchange].get_order_book(trading_pair)
        snapshot = order_book.snapshot
        return {
            "ts": self.current_timestamp,
            "bids": snapshot[0].loc[:(depth - 1), ["price", "amount"]].values.tolist(),
            "asks": snapshot[1].loc[:(depth - 1), ["price", "amount"]].values.tolist(),
        }

    def dump_and_clean_temp_storage(self):
        for trading_pair, order_book_info in self.ob_temp_storage.items():
            file = self.ob_file_paths[trading_pair]
            json_strings = [json.dumps(obj) for obj in order_book_info]
            json_data = '\n'.join(json_strings)
            file.write(json_data)
            self.ob_temp_storage[trading_pair] = []
        for trading_pair, trades_info in self.trades_temp_storage.items():
            file = self.trades_file_paths[trading_pair]
            json_strings = [json.dumps(obj) for obj in trades_info]
            json_data = '\n'.join(json_strings)
            file.write(json_data)
            self.trades_temp_storage[trading_pair] = []
        self.last_dump_timestamp = self.current_timestamp + self.time_between_csv_dumps

    def check_and_replace_files(self):
        current_date = datetime.now().strftime("%Y-%m-%d")
        if current_date != self.current_date:
            for file in self.ob_file_paths.values():
                file.close()
            self.create_order_book_and_trade_files()

    def create_order_book_and_trade_files(self):
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        self.ob_file_paths = {trading_pair: self.get_file(self.exchange, trading_pair, "order_book_snapshots", self.current_date) for
                              trading_pair in self.trading_pairs}
        self.trades_file_paths = {trading_pair: self.get_file(self.exchange, trading_pair, "trades", self.current_date) for
                                  trading_pair in self.trading_pairs}

    @staticmethod
    def get_file(exchange: str, trading_pair: str, source_type: str, current_date: str):
        file_path = data_path() + f"/{exchange}_{trading_pair}_{source_type}_{current_date}.txt"
        return open(file_path, "a")

    def _process_public_trade(self, event_tag: int, market: ConnectorBase, event: OrderBookTradeEvent):
        self.trades_temp_storage[event.trading_pair].append({
            "ts": event.timestamp,
            "price": event.price,
            "q_base": event.amount,
            "side": event.type.name.lower(),
        })

    def subscribe_to_order_book_trade_event(self):
        for market in self.connectors.values():
            for order_book in market.order_books.values():
                order_book.add_listener(OrderBookEvent.TradeEvent, self.order_book_trade_event)
        self.subscribed_to_order_book_trade_event = True
