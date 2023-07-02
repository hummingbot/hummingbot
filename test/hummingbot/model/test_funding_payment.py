import unittest
from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
from pandas.testing import assert_frame_equal
from sqlalchemy.orm import Session

from hummingbot.model.funding_payment import FundingPayment


class FundingPaymentUnitTest(unittest.TestCase):
    def setUp(self):
        self.sql_session = MagicMock(spec=Session)
        self.timestamp = "1627512000000"
        self.market = "binance"
        self.trading_pair = "ETH/USDT"

        self.payment = FundingPayment(
            timestamp=self.timestamp,
            config_file_path="config.yaml",
            market=self.market,
            rate=0.1,
            symbol=self.trading_pair,
            amount=100.0
        )

    def test_get_funding_payments(self):
        self.sql_session.query().filter().order_by().all.return_value = [self.payment]

        result = FundingPayment.get_funding_payments(
            sql_session=self.sql_session,
            timestamp=self.timestamp,
            market=self.market,
            trading_pair=self.trading_pair
        )

        self.assertEqual(result, [self.payment])

    def test_to_pandas(self):
        payments = [self.payment]
        expected_columns = ["Index", "Timestamp", "Exchange", "Market", "Rate", "Amount"]
        expected_data = [
            [1, datetime.fromtimestamp(int(self.timestamp) / 1e3).strftime("%Y-%m-%d %H:%M:%S"),
             self.market, self.payment.rate, self.trading_pair, self.payment.amount]
        ]
        expected_df = pd.DataFrame(data=expected_data, columns=expected_columns)
        expected_df.set_index('Index', inplace=True)

        result = FundingPayment.to_pandas(payments)

        assert_frame_equal(result, expected_df)


if __name__ == "__main__":
    unittest.main()
