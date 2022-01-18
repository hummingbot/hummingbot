import unittest

from hummingbot.connector.derivative.perpetual_finance.perpetual_finance_derivative import (
    PerpetualFinanceDerivative
)


class PerpetualFinanceDerivativeTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.base = "HBOT"
        self.quote = "COINALPHA"
        self.trading_pair = f"{self.base}-{self.quote}"
        self.exchange = PerpetualFinanceDerivative(
            trading_pairs=[self.trading_pair],
            wallet_private_key="someKey",
            ethereum_rpc_url="someUrl",
        )

    def test_get_buy_and_sell_collateral_token(self):
        buy_collateral_token = self.exchange.get_buy_collateral_token(self.trading_pair)
        sell_collateral_token = self.exchange.get_sell_collateral_token(self.trading_pair)

        self.assertEqual(self.quote, buy_collateral_token)
        self.assertEqual(self.quote, sell_collateral_token)
