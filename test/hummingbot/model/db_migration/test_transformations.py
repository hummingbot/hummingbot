from unittest import TestCase
from unittest.mock import MagicMock

from hummingbot.model.db_migration.transformations import ConvertPriceAndAmountColumnsToBigint


class ConvertPriceAndAmountColumnsToBigintTests(TestCase):

    def test_name(self):
        self.assertEqual("ConvertPriceAndAmountColumnsToBigint", ConvertPriceAndAmountColumnsToBigint(self).name)

    def test_to_version(self):
        self.assertEqual(20220130, ConvertPriceAndAmountColumnsToBigint(self).to_version)

    def test_apply_changes_trade_fill_and_order_tables(self):
        executed_queries = []
        mock = MagicMock()
        mock.engine.execute.side_effect = lambda query: executed_queries.append(query)

        ConvertPriceAndAmountColumnsToBigint(migrator=self).apply(mock)

        self.assertIn("create table Order_dg_tmp", executed_queries[0])
        self.assertIn("CAST(amount * 1000000 AS INTEGER)", executed_queries[1])
        self.assertIn("CAST(price * 1000000 AS INTEGER", executed_queries[1])
        self.assertEquals('drop table "Order";', executed_queries[2])
        self.assertEquals('alter table Order_dg_tmp rename to "Order";', executed_queries[3])

        self.assertIn("create table TradeFill_dg_tmp", executed_queries[8])
        self.assertNotIn("id INTEGER", executed_queries[8])
        self.assertIn("constraint TradeFill_pk", executed_queries[8])
        self.assertIn("primary key (market, order_id, exchange_trade_id)", executed_queries[8])
        self.assertIn("CAST(amount * 1000000 AS INTEGER)", executed_queries[9])
        self.assertIn("CAST(price * 1000000 AS INTEGER", executed_queries[9])
        self.assertEquals('drop table TradeFill;', executed_queries[10])
        self.assertEquals('alter table TradeFill_dg_tmp rename to TradeFill;', executed_queries[11])
