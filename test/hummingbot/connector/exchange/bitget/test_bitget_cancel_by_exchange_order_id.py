"""An order the tracker lost must still be cancellable on Bitget spot.

``cancel`` takes a client order id and reads ``in_flight_orders``, so it only
reaches orders the running process placed. When a bot crashes, is archived or is
restarted while a quote rests, the order is still live at the venue and nothing in
the connector can reach it -- hummingbot-api's
``POST /trading/{acct}/{conn}/orders/by-exchange-id/{id}/cancel`` answers 501 for
any connector without this method.

A live Condor agent on Bitget proved the symptom: its winddown reported "2 resting
order(s) LEFT ALONE, no executor of this session claims them", because the orders
outlived the executor records and the sweep refuses to cancel what it cannot
attribute.

Bitget keeps the symbol on the order, so the connector can cancel by venue id
without the tracker. Two routes exist and both are exercised here: the classic
spot route needs ``symbol`` + ``orderId``, the V3 unified-account route needs
``orderId`` alone.
"""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.bitget import bitget_constants as CONSTANTS
from hummingbot.connector.exchange.bitget.bitget_exchange import BitgetExchange
from hummingbot.connector.exchange_py_base import ExchangePyBase


class BitgetCancelByExchangeOrderIdTest(unittest.TestCase):
    def setUp(self) -> None:
        self.exchange = BitgetExchange(
            bitget_api_key="testKey",
            bitget_secret_key="testSecret",
            bitget_passphrase="testPass",
            trading_pairs=["BTC-USDT"],
        )

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_base_contract_is_present(self):
        """The contract is declared on the base, so an unimplemented connector fails loudly."""
        self.assertIn("cancel_by_exchange_order_id", dir(ExchangePyBase))

    def test_classic_account_cancels_with_symbol_and_order_id(self):
        posted = {}

        async def fake_post(path_url, data=None, is_auth_required=False, **kwargs):
            posted["path_url"] = path_url
            posted["data"] = data
            return {"code": CONSTANTS.RET_CODE_OK, "msg": "success"}

        with patch.object(self.exchange, "_is_unified_account", AsyncMock(return_value=False)), \
                patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                             AsyncMock(return_value="BTCUSDT")), \
                patch.object(self.exchange, "_api_post", side_effect=fake_post):
            result = self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "1234567890"))

        self.assertEqual("1234567890", result)
        self.assertEqual(CONSTANTS.CLASSIC_CANCEL_ORDER_ENDPOINT, posted["path_url"])
        self.assertEqual("BTCUSDT", posted["data"]["symbol"])
        self.assertEqual("1234567890", posted["data"]["orderId"])

    def test_unified_account_cancels_by_order_id_alone(self):
        posted = {}

        async def fake_post(path_url, data=None, is_auth_required=False, **kwargs):
            posted["path_url"] = path_url
            posted["data"] = data
            return {"code": CONSTANTS.RET_CODE_OK, "msg": "success"}

        with patch.object(self.exchange, "_is_unified_account", AsyncMock(return_value=True)), \
                patch.object(self.exchange, "_api_post", side_effect=fake_post):
            result = self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "99"))

        self.assertEqual("99", result)
        self.assertEqual(CONSTANTS.CANCEL_ORDER_ENDPOINT, posted["path_url"])
        self.assertEqual({"orderId": "99"}, posted["data"])

    def test_venue_rejection_raises_with_the_cause(self):
        async def fake_post(path_url, data=None, is_auth_required=False, **kwargs):
            return {"code": "40034", "msg": "Order does not exist"}

        with patch.object(self.exchange, "_is_unified_account", AsyncMock(return_value=False)), \
                patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                             AsyncMock(return_value="BTCUSDT")), \
                patch.object(self.exchange, "_api_post", side_effect=fake_post):
            with self.assertRaises(IOError):
                self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "404"))

    def test_empty_order_id_is_refused_before_any_request(self):
        posted = AsyncMock()

        with patch.object(self.exchange, "_is_unified_account", AsyncMock(return_value=False)), \
                patch.object(self.exchange, "_api_post", posted):
            with self.assertRaises(ValueError):
                self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", ""))

        posted.assert_not_called()


if __name__ == "__main__":
    unittest.main()
