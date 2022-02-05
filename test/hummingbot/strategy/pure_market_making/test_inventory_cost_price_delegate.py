import unittest
from decimal import Decimal

from hummingbot.core.event.events import OrderFilledEvent, TradeType
from hummingbot.core.event.events import OrderType
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.model.inventory_cost import InventoryCost
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType,
)
from hummingbot.strategy.pure_market_making.inventory_cost_price_delegate import InventoryCostPriceDelegate


class TestInventoryCostPriceDelegate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trade_fill_sql = SQLConnectionManager(
            SQLConnectionType.TRADE_FILLS, db_path=""
        )
        cls.trading_pair = "BTC-USDT"
        cls.base_asset, cls.quote_asset = cls.trading_pair.split("-")

    def setUp(self):
        with self.trade_fill_sql.get_new_session() as session:
            for table in [InventoryCost.__table__]:
                with session.begin():
                    session.execute(table.delete())
        self.delegate = InventoryCostPriceDelegate(
            self.trade_fill_sql, self.trading_pair
        )

    def test_process_order_fill_event_buy(self):
        amount = Decimal("1")
        price = Decimal("9000")
        event = OrderFilledEvent(
            timestamp=1,
            order_id="order1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=price,
            amount=amount,
            trade_fee=AddedToCostTradeFee(percent=Decimal("0"), flat_fees=[]),
        )
        # first event creates DB record
        self.delegate.process_order_fill_event(event)
        with self.trade_fill_sql.get_new_session() as session:
            count = session.query(InventoryCost).count()
            self.assertEqual(count, 1)

            # second event causes update to existing record
            self.delegate.process_order_fill_event(event)
            record = InventoryCost.get_record(
                session, self.base_asset, self.quote_asset
            )
            self.assertEqual(record.base_volume, amount * 2)
            self.assertEqual(record.quote_volume, price * 2)

    def test_process_order_fill_event_sell(self):
        amount = Decimal("1")
        price = Decimal("9000")

        # Test when no records
        self.assertIsNone(self.delegate.get_price())

        with self.trade_fill_sql.get_new_session() as session:
            with session.begin():
                record = InventoryCost(
                    base_asset=self.base_asset,
                    quote_asset=self.quote_asset,
                    base_volume=amount,
                    quote_volume=amount * price,
                )
                session.add(record)

        amount_sell = Decimal("0.5")
        price_sell = Decimal("10000")
        event = OrderFilledEvent(
            timestamp=1,
            order_id="order1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            order_type=OrderType.LIMIT,
            price=price_sell,
            amount=amount_sell,
            trade_fee=AddedToCostTradeFee(percent=Decimal("0"), flat_fees=[]),
        )

        self.delegate.process_order_fill_event(event)
        with self.trade_fill_sql.get_new_session() as session:
            record = InventoryCost.get_record(
                session, self.base_asset, self.quote_asset
            )
            # Remaining base volume reduced by sold amount
            self.assertEqual(record.base_volume, amount - amount_sell)
            # Remaining quote volume has been reduced using original price
            self.assertEqual(record.quote_volume, amount_sell * price)

    def test_process_order_fill_event_sell_no_initial_cost_set(self):
        amount = Decimal("1")
        price = Decimal("9000")
        event = OrderFilledEvent(
            timestamp=1,
            order_id="order1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            order_type=OrderType.LIMIT,
            price=price,
            amount=amount,
            trade_fee=AddedToCostTradeFee(percent=Decimal("0"), flat_fees=[]),
        )
        with self.assertRaises(RuntimeError):
            self.delegate.process_order_fill_event(event)

    def test_get_price_by_type(self):
        amount = Decimal("1")
        price = Decimal("9000")

        # Test when no records
        self.assertIsNone(self.delegate.get_price())

        with self.trade_fill_sql.get_new_session() as session:
            with session.begin():
                record = InventoryCost(
                    base_asset=self.base_asset,
                    quote_asset=self.quote_asset,
                    base_volume=amount,
                    quote_volume=amount * price,
                )
                session.add(record)

        delegate_price = self.delegate.get_price()
        self.assertEqual(delegate_price, price)

    def test_get_price_by_type_zero_division(self):
        # Test for situation when position was fully closed with profit
        amount = Decimal("0")

        with self.trade_fill_sql.get_new_session() as session:
            with session.begin():
                record = InventoryCost(
                    base_asset=self.base_asset,
                    quote_asset=self.quote_asset,
                    base_volume=amount,
                    quote_volume=amount,
                )
                session.add(record)
                self.assertIsNone(self.delegate.get_price())
