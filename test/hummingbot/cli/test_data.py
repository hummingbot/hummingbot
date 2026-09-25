import time
import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hummingbot.cli.data import get_trades
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import SQLConnectionManager
from hummingbot.model.trade_fill import TradeFill


class DataReadTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "bot.sqlite")
        engine = create_engine(f"sqlite:///{self.db_path}")
        SQLConnectionManager.get_declarative_base().metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        self._seed()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _seed(self) -> None:
        fee = AddedToCostTradeFee(percent=Decimal("0.1"))
        now_ms = int(time.time() * 1e3)
        rows = [
            # (offset_seconds_ago, side, price, amount)
            (10 * 86400, "BUY", 100, 1),    # 10 days ago
            (1 * 3600, "BUY", 110, 2),      # 1 hour ago
            (60, "SELL", 120, 1),           # 1 minute ago
        ]
        with self.Session() as session:
            for i, (ago, side, price, amount) in enumerate(rows):
                session.add(Order(
                    id=f"o{i}",
                    config_file_path="bot.yml",
                    strategy="bot",
                    market="binance",
                    symbol="BTC-USDT",
                    base_asset="BTC",
                    quote_asset="USDT",
                    creation_timestamp=now_ms - ago * 1000 - 1000,
                    order_type="LIMIT",
                    amount=amount,
                    leverage=1,
                    price=price,
                    last_status="FILLED",
                    last_update_timestamp=now_ms - ago * 1000,
                ))
                session.add(TradeFill(
                    config_file_path="bot.yml",
                    strategy="bot",
                    market="binance",
                    symbol="BTC-USDT",
                    base_asset="BTC",
                    quote_asset="USDT",
                    timestamp=now_ms - ago * 1000,
                    order_id=f"o{i}",
                    trade_type=side,
                    order_type="LIMIT",
                    price=price,
                    amount=amount,
                    leverage=1,
                    trade_fee=fee.to_json(),
                    exchange_trade_id=f"e{i}",
                ))
            session.commit()

    def test_get_all_trades_ascending(self):
        trades = get_trades(self.db_path)
        self.assertEqual(len(trades), 3)
        ts = [t.timestamp for t in trades]
        self.assertEqual(ts, sorted(ts))  # ascending

    def test_days_filter(self):
        trades = get_trades(self.db_path, days=1)
        self.assertEqual(len(trades), 2)  # excludes the 10-day-old fill

    def test_limit_returns_most_recent(self):
        trades = get_trades(self.db_path, limit=1)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].trade_type, "SELL")  # the newest fill

    def test_config_filter_excludes_other_strategies(self):
        self.assertEqual(len(get_trades(self.db_path, config_file_path="bot")), 3)
        self.assertEqual(len(get_trades(self.db_path, config_file_path="other")), 0)

    def test_to_pandas_after_detach(self):
        # to_pandas reads trade.order.creation_timestamp; get_trades must eager-load the
        # relationship so this works after the rows are detached from the session.
        trades = get_trades(self.db_path)
        df = TradeFill.to_pandas(trades)
        self.assertEqual(len(df), 3)
        self.assertIn("Age", df.columns)


if __name__ == "__main__":
    unittest.main()
