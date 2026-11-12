"""An order the tracker lost must still be cancellable on Bitget perpetual.

Same defect as the spot connector, on the venue two Condor packs trade perps on
(``midas``, ``quad_threat``). ``cancel`` resolves a client order id through
``in_flight_orders``, so a quote that outlives its executor cannot be reached --
and the shutdown sweep deliberately refuses to cancel an order it cannot attribute
("LEFT ALONE, no executor of this session claims them").

Bitget's futures cancel takes symbol, product type and margin coin alongside the
venue's own order id, so the connector can clear an orphaned contract without ever
consulting the tracker.
"""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from hummingbot.connector.derivative.bitget_perpetual import (
    bitget_perpetual_constants as CONSTANTS,
)
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_derivative import (
    BitgetPerpetualDerivative,
)
from hummingbot.connector.exchange_py_base import ExchangePyBase


class BitgetPerpetualCancelByExchangeOrderIdTest(unittest.TestCase):
    def setUp(self) -> None:
        self.exchange = BitgetPerpetualDerivative(
            bitget_perpetual_api_key="testKey",
            bitget_perpetual_secret_key="testSecret",
            bitget_perpetual_passphrase="testPass",
            trading_pairs=["BTC-USDT"],
        )

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_base_contract_is_present(self):
        self.assertIn("cancel_by_exchange_order_id", dir(ExchangePyBase))

    def test_classic_account_sends_symbol_product_type_and_order_id(self):
        posted = {}

        async def fake_post(path_url, data=None, is_auth_required=False, **kwargs):
            posted["path_url"] = path_url
            posted["data"] = data
            return {"code": CONSTANTS.RET_CODE_OK, "msg": "success"}

        with patch.object(self.exchange, "_is_unified_account", AsyncMock(return_value=False)), \
                patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                             AsyncMock(return_value="BTCUSDT")), \
                patch.object(self.exchange, "product_type_associated_to_trading_pair",
                             AsyncMock(return_value="USDT-FUTURES")), \
                patch.object(self.exchange, "get_buy_collateral_token",
                             return_value="USDT"), \
                patch.object(self.exchange, "_api_post", side_effect=fake_post):
            result = self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "5566778899"))

        self.assertEqual("5566778899", result)
        self.assertEqual(CONSTANTS.CLASSIC_CANCEL_ORDER_ENDPOINT, posted["path_url"])
        self.assertEqual("BTCUSDT", posted["data"]["symbol"])
        self.assertEqual("USDT-FUTURES", posted["data"]["productType"])
        self.assertEqual("USDT", posted["data"]["marginCoin"])
        self.assertEqual("5566778899", posted["data"]["orderId"])

    def test_unified_account_cancels_by_order_id_alone(self):
        posted = {}

        async def fake_post(path_url, data=None, is_auth_required=False, **kwargs):
            posted["path_url"] = path_url
            posted["data"] = data
            return {"code": CONSTANTS.RET_CODE_OK, "msg": "success"}

        with patch.object(self.exchange, "_is_unified_account", AsyncMock(return_value=True)), \
                patch.object(self.exchange, "_api_post", side_effect=fake_post):
            result = self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "42"))

        self.assertEqual("42", result)
        self.assertEqual(CONSTANTS.CANCEL_ORDER_ENDPOINT, posted["path_url"])
        self.assertEqual({"orderId": "42"}, posted["data"])

    def test_venue_rejection_raises_with_the_cause(self):
        async def fake_post(path_url, data=None, is_auth_required=False, **kwargs):
            return {"code": "43001", "msg": "Order does not exist"}

        with patch.object(self.exchange, "_is_unified_account", AsyncMock(return_value=False)), \
                patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                             AsyncMock(return_value="BTCUSDT")), \
                patch.object(self.exchange, "product_type_associated_to_trading_pair",
                             AsyncMock(return_value="USDT-FUTURES")), \
                patch.object(self.exchange, "get_buy_collateral_token",
                             return_value="USDT"), \
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
