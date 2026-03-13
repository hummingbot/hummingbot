import unittest

from hummingbot.model.range_position_update import RangePositionUpdate


class TestRangePositionUpdate(unittest.TestCase):
    """Test RangePositionUpdate model"""

    def test_repr(self):
        """Test __repr__ method for RangePositionUpdate"""
        update = RangePositionUpdate(
            id=1,
            hb_id="range-SOL-USDC-001",
            timestamp=1234567890,
            tx_hash="tx_sig_123",
            token_id=0,
            trade_fee="{}",
            order_action="ADD",
            position_address="pos_addr_123",
        )

        repr_str = repr(update)

        self.assertIn("RangePositionUpdate", repr_str)
        self.assertIn("id=1", repr_str)
        self.assertIn("hb_id='range-SOL-USDC-001'", repr_str)
        self.assertIn("timestamp=1234567890", repr_str)
        self.assertIn("tx_hash='tx_sig_123'", repr_str)
        self.assertIn("order_action=ADD", repr_str)
        self.assertIn("position_address=pos_addr_123", repr_str)

    def test_repr_with_none_values(self):
        """Test __repr__ with None values"""
        update = RangePositionUpdate(
            id=2,
            hb_id="range-SOL-USDC-002",
            timestamp=1234567891,
            tx_hash=None,
            token_id=0,
            trade_fee="{}",
            order_action=None,
            position_address=None,
        )

        repr_str = repr(update)

        self.assertIn("RangePositionUpdate", repr_str)
        self.assertIn("id=2", repr_str)
        self.assertIn("hb_id='range-SOL-USDC-002'", repr_str)

    def test_model_fields(self):
        """Test all model fields can be set"""
        update = RangePositionUpdate(
            hb_id="range-SOL-USDC-003",
            timestamp=1234567892,
            tx_hash="tx_sig_456",
            token_id=0,
            trade_fee='{"flat_fees": []}',
            trade_fee_in_quote=0.15,
            config_file_path="conf_lp_test.yml",
            market="meteora/clmm",
            order_action="REMOVE",
            trading_pair="SOL-USDC",
            position_address="pos_addr_456",
            lower_price=95.0,
            upper_price=105.0,
            mid_price=100.0,
            base_amount=5.0,
            quote_amount=500.0,
            base_fee=0.05,
            quote_fee=5.0,
            position_rent=0.002,
            position_rent_refunded=0.002,
        )

        self.assertEqual(update.hb_id, "range-SOL-USDC-003")
        self.assertEqual(update.timestamp, 1234567892)
        self.assertEqual(update.tx_hash, "tx_sig_456")
        self.assertEqual(update.token_id, 0)
        self.assertEqual(update.trade_fee_in_quote, 0.15)
        self.assertEqual(update.config_file_path, "conf_lp_test.yml")
        self.assertEqual(update.market, "meteora/clmm")
        self.assertEqual(update.order_action, "REMOVE")
        self.assertEqual(update.trading_pair, "SOL-USDC")
        self.assertEqual(update.position_address, "pos_addr_456")
        self.assertEqual(update.lower_price, 95.0)
        self.assertEqual(update.upper_price, 105.0)
        self.assertEqual(update.mid_price, 100.0)
        self.assertEqual(update.base_amount, 5.0)
        self.assertEqual(update.quote_amount, 500.0)
        self.assertEqual(update.base_fee, 0.05)
        self.assertEqual(update.quote_fee, 5.0)
        self.assertEqual(update.position_rent, 0.002)
        self.assertEqual(update.position_rent_refunded, 0.002)


if __name__ == "__main__":
    unittest.main()
