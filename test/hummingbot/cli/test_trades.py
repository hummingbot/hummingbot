"""``hbot trades`` — the ingestion feed: --since filtering and row shape."""
import json
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hummingbot.cli.commands import trades as trades_mod
from hummingbot.cli.data import get_trades
from hummingbot.model import get_declarative_base
from hummingbot.model.order import Order
from hummingbot.model.trade_fill import TradeFill


def _make_db(path: Path, fills: list) -> None:
    engine = create_engine(f"sqlite:///{path}")
    get_declarative_base().metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    for f in fills:
        session.add(Order(
            id=f["order_id"], config_file_path="conf_x.yml", strategy="s",
            market=f["market"], symbol=f["pair"], base_asset="ETH", quote_asset="USDT",
            creation_timestamp=f["ts_ms"], order_type="LIMIT", amount=1, leverage=1,
            price=f["price"], position="NIL", last_status="FILLED",
            last_update_timestamp=f["ts_ms"]))
        session.add(TradeFill(
            config_file_path="conf_x.yml", strategy="s", market=f["market"],
            symbol=f["pair"], base_asset="ETH", quote_asset="USDT",
            timestamp=f["ts_ms"], order_id=f["order_id"], trade_type=f["side"],
            order_type="LIMIT", price=f["price"], amount=f["amount"],
            trade_fee={"flat_fees": []}, exchange_trade_id=f["trade_id"],
            position="NIL"))
    session.commit()
    session.close()
    engine.dispose()


class TradesSinceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db = self.tmp / "bot.sqlite"
        now_ms = int(time.time() * 1000)
        self.t0 = now_ms - 60_000
        self.t1 = now_ms - 30_000
        self.t2 = now_ms
        _make_db(self.db, [
            {"ts_ms": self.t0, "order_id": "o1", "trade_id": "t1", "market": "kucoin",
             "pair": "ETH-USDT", "side": "BUY", "price": 3000, "amount": 1},
            {"ts_ms": self.t1, "order_id": "o2", "trade_id": "t2", "market": "kucoin",
             "pair": "ETH-USDT", "side": "SELL", "price": 3100, "amount": 1},
            {"ts_ms": self.t2, "order_id": "o3", "trade_id": "t3", "market": "kucoin",
             "pair": "ETH-USDT", "side": "BUY", "price": 3050, "amount": 2},
        ])

    def test_since_is_inclusive_and_ascending(self):
        fills = get_trades(str(self.db), since_ms=self.t1)
        self.assertEqual([t.exchange_trade_id for t in fills], ["t2", "t3"])

    def test_no_since_returns_everything(self):
        self.assertEqual(len(get_trades(str(self.db))), 3)

    def test_command_emits_canonical_rows(self):
        buf = StringIO()
        with patch("hummingbot.cli.commands._common.resolve_db_for_command",
                   return_value=(str(self.db), None, False)), redirect_stdout(buf):
            trades_mod.trades(name=None, since=self.t1 / 1000.0, limit=None, as_json=True)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["count"], 2)
        row = payload["trades"][0]
        self.assertEqual(row["trade_id"], "t2")
        self.assertEqual(row["side"], "sell")
        self.assertEqual(row["pair"], "ETH-USDT")
        self.assertAlmostEqual(row["ts"], self.t1 / 1000.0)
        self.assertEqual(row["price"], "3100")


class InjectedCredentialsTest(unittest.TestCase):
    """HBOT_CREDENTIALS strict precedence at the single read point."""

    def tearDown(self):
        from hummingbot.client.config.security import Security
        Security.inject_credentials({})

    def test_injected_connector_never_merges_with_disk(self):
        from hummingbot.client.config.security import Security
        with patch.object(Security, "decrypted_value") as decrypted:
            Security.inject_credentials(
                {"kucoin": {"kucoin_api_key": "fresh", "kucoin_secret_key": "fresh2"}})
            keys = Security.api_keys("kucoin")
            self.assertEqual(keys, {"kucoin_api_key": "fresh", "kucoin_secret_key": "fresh2"})
            decrypted.assert_not_called()  # the on-disk keystore is unreachable

    def test_uninjected_connector_falls_through_to_keystore(self):
        from hummingbot.client.config.security import Security
        Security.inject_credentials({"kucoin": {"kucoin_api_key": "fresh"}})
        with patch.object(Security, "decrypted_value", return_value=None) as decrypted:
            self.assertEqual(Security.api_keys("gate_io"), {})
            decrypted.assert_called_once_with("gate_io")


if __name__ == "__main__":
    unittest.main()
