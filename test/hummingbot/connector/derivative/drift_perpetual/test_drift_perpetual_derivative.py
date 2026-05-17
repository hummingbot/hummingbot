"""
Targeted unit tests for the deterministic transformation logic of the
DriftPerpetualDerivative connector.

Scope note: the full AbstractPerpetualDerivativeTests conformance harness
(request/response flow contract) is intentionally NOT implemented here. That
harness is developed iteratively against a runnable Cython core; the local
environment has no built Cython core, so a blind conformance suite would be
unverifiable. These tests instead assert the pure transformation logic
(symbol mapping, order-body construction, balance/state parsing, WS demux)
which is verifiable by inspection and stable across the request flow.
"""
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

from bidict import bidict

from hummingbot.connector.derivative.drift_perpetual import drift_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.drift_perpetual.drift_perpetual_derivative import DriftPerpetualDerivative
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState


class DriftPerpetualDerivativeTests(IsolatedAsyncioWrapperTestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base = "SOL"
        cls.quote = CONSTANTS.CURRENCY  # USDC
        cls.ex_symbol = "SOL-PERP"
        cls.trading_pair = combine_to_hb_trading_pair(cls.base, cls.quote)  # SOL-USDC

    def setUp(self) -> None:
        super().setUp()
        self.connector = DriftPerpetualDerivative(
            drift_perpetual_gateway_host="127.0.0.1",
            drift_perpetual_gateway_rest_port=8080,
            drift_perpetual_gateway_ws_port=1337,
            drift_perpetual_sub_account_id=0,
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.connector._set_trading_pair_symbol_map(bidict({self.ex_symbol: self.trading_pair}))
        self.connector._market_index_map = {self.trading_pair: 0}

    # --- identity / config invariants ---

    def test_name_and_order_types(self):
        self.assertEqual("drift_perpetual", self.connector.name)
        self.assertEqual(
            {OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET},
            set(self.connector.supported_order_types()),
        )

    def test_drift_is_oneway_only(self):
        self.assertEqual([PositionMode.ONEWAY], self.connector.supported_position_modes())

    def test_client_order_id_config(self):
        self.assertEqual(CONSTANTS.MAX_ID_LEN, self.connector.client_order_id_max_length)
        self.assertEqual(CONSTANTS.HBOT_BROKER_ID, self.connector.client_order_id_prefix)
        self.assertTrue(self.connector.is_cancel_request_in_exchange_synchronous)

    def test_gateway_urls_are_loopback_versioned(self):
        self.assertEqual("http://127.0.0.1:8080/v2", self.connector.drift_gateway_rest_url)
        self.assertEqual("ws://127.0.0.1:1337", self.connector.drift_gateway_ws_url)

    def test_order_not_found_detects_tx_not_found(self):
        self.assertTrue(self.connector._is_order_not_found_during_status_update_error(Exception("Tx Not Found")))
        self.assertTrue(self.connector._is_order_not_found_during_cancelation_error(Exception("tx not found: x")))
        self.assertFalse(self.connector._is_order_not_found_during_status_update_error(Exception("rate limited")))

    def test_time_synchronizer_hooks_are_noops(self):
        # Gateway is co-located; no remote clock to sync against.
        self.assertFalse(self.connector._is_request_exception_related_to_time_synchronizer(Exception()))
        self.assertFalse(self.connector._is_request_result_an_error_related_to_time_synchronizer({}))

    # --- symbol map / market index ---

    def test_initialize_trading_pair_symbols_builds_index_map(self):
        exchange_info = {"perp": [
            {"symbol": "SOL-PERP", "marketIndex": 0, "status": "active"},
            {"symbol": "BTC-PERP", "marketIndex": 1, "status": "initialized"},
            {"symbol": "BAD-PERP", "marketIndex": 9, "status": "delisted"},  # filtered out
        ]}
        self.connector._initialize_trading_pair_symbols_from_exchange_info(exchange_info)
        sol = combine_to_hb_trading_pair("SOL", CONSTANTS.CURRENCY)
        btc = combine_to_hb_trading_pair("BTC", CONSTANTS.CURRENCY)
        self.assertEqual(0, self.connector._market_index_map[sol])
        self.assertEqual(1, self.connector._market_index_map[btc])
        self.assertNotIn("BAD-PERP", self.connector._market_index_map)
        self.assertNotIn(combine_to_hb_trading_pair("BAD", CONSTANTS.CURRENCY),
                         self.connector._market_index_map)

    async def test_format_trading_rules(self):
        exchange_info = {"perp": [{
            "symbol": "SOL-PERP", "marketIndex": 0, "status": "active",
            "minOrderSize": "0.1", "priceStep": "0.001", "amountStep": "0.01",
        }]}
        rules = await self.connector._format_trading_rules(exchange_info)
        self.assertEqual(1, len(rules))
        rule = rules[0]
        self.assertEqual(self.trading_pair, rule.trading_pair)
        self.assertEqual(Decimal("0.1"), rule.min_order_size)
        self.assertEqual(Decimal("0.001"), rule.min_price_increment)
        self.assertEqual(Decimal("0.01"), rule.min_base_amount_increment)
        self.assertEqual(CONSTANTS.CURRENCY, rule.buy_order_collateral_token)
        self.assertEqual(CONSTANTS.CURRENCY, rule.sell_order_collateral_token)

    # --- order placement body construction (Drift signed-amount semantics) ---

    async def test_place_order_buy_is_positive_signed_amount(self):
        self.connector._api_post = AsyncMock(return_value={"signature": "5xSIG"})
        ex_id, _ts = await self.connector._place_order(
            order_id="HBOT-1", trading_pair=self.trading_pair, amount=Decimal("2"),
            trade_type=TradeType.BUY, order_type=OrderType.LIMIT, price=Decimal("142.5"),
            position_action=PositionAction.OPEN,
        )
        body = self.connector._api_post.call_args.kwargs["data"]
        o = body["orders"][0]
        self.assertEqual(0, o["marketIndex"])
        self.assertEqual(CONSTANTS.MARKET_TYPE_PERP, o["marketType"])
        self.assertEqual(2.0, o["amount"])              # BUY -> +amount
        self.assertEqual(142.5, o["price"])
        self.assertFalse(o["postOnly"])                 # plain LIMIT
        self.assertFalse(o["reduceOnly"])               # OPEN
        self.assertEqual("5xSIG", ex_id)                # tx signature is the handle

    async def test_place_order_sell_is_negative_signed_amount(self):
        self.connector._api_post = AsyncMock(return_value={"signature": "s"})
        await self.connector._place_order(
            order_id="HBOT-2", trading_pair=self.trading_pair, amount=Decimal("3"),
            trade_type=TradeType.SELL, order_type=OrderType.LIMIT_MAKER, price=Decimal("100"),
            position_action=PositionAction.CLOSE,
        )
        o = self.connector._api_post.call_args.kwargs["data"]["orders"][0]
        self.assertEqual(-3.0, o["amount"])             # SELL -> -amount
        self.assertTrue(o["postOnly"])                  # LIMIT_MAKER
        self.assertTrue(o["reduceOnly"])                # CLOSE
        self.assertEqual("limit", o["orderType"])

    async def test_place_order_market_has_zero_price(self):
        self.connector._api_post = AsyncMock(return_value={"signature": "s"})
        await self.connector._place_order(
            order_id="HBOT-3", trading_pair=self.trading_pair, amount=Decimal("1"),
            trade_type=TradeType.BUY, order_type=OrderType.MARKET, price=Decimal("999"),
        )
        o = self.connector._api_post.call_args.kwargs["data"]["orders"][0]
        self.assertEqual(0, o["price"])                 # MARKET ignores price
        self.assertEqual("market", o["orderType"])

    async def test_place_cancel_uses_numeric_order_id(self):
        self.connector._api_request = AsyncMock(return_value={})
        tracked = MagicMock()
        tracked.trading_pair = self.trading_pair
        tracked.exchange_order_id = "778899"
        ok = await self.connector._place_cancel("HBOT-1", tracked)
        self.assertTrue(ok)
        self.assertEqual({"ids": [778899]}, self.connector._api_request.call_args.kwargs["data"])

    async def test_place_cancel_falls_back_to_market_when_id_non_numeric(self):
        self.connector._api_request = AsyncMock(return_value={})
        tracked = MagicMock()
        tracked.trading_pair = self.trading_pair
        tracked.exchange_order_id = "5xSIGNATURE"  # tx sig, not a numeric orderId
        await self.connector._place_cancel("HBOT-1", tracked)
        sent = self.connector._api_request.call_args.kwargs["data"]
        self.assertEqual(CONSTANTS.MARKET_TYPE_PERP, sent["marketType"])
        self.assertIn("marketIndex", sent)

    # --- balances ---

    async def test_update_balances_from_collateral(self):
        self.connector._api_get = AsyncMock(return_value={"total": "1500.25", "free": "1200.10"})
        await self.connector._update_balances()
        self.assertEqual(Decimal("1500.25"), self.connector._account_balances[CONSTANTS.CURRENCY])
        self.assertEqual(Decimal("1200.10"), self.connector._account_available_balances[CONSTANTS.CURRENCY])

    # --- order status state machine ---

    def _tracked(self, exch_id="111", executed=Decimal("0")):
        t = MagicMock()
        t.trading_pair = self.trading_pair
        t.client_order_id = "HBOT-1"
        t.exchange_order_id = exch_id
        t.executed_amount_base = executed
        return t

    async def test_request_order_status_open_partial_filled(self):
        async def resp_with(filled):
            self.connector._api_get = AsyncMock(return_value={"orders": [
                {"orderId": "111", "filled": filled, "amount": "5"}]})
            return await self.connector._request_order_status(self._tracked())

        self.assertEqual(OrderState.OPEN, (await resp_with("0")).new_state)
        self.assertEqual(OrderState.PARTIALLY_FILLED, (await resp_with("2")).new_state)
        self.assertEqual(OrderState.FILLED, (await resp_with("5")).new_state)

    async def test_request_order_status_absent_is_terminal(self):
        self.connector._api_get = AsyncMock(return_value={"orders": []})
        filled = await self.connector._request_order_status(self._tracked(executed=Decimal("5")))
        self.assertEqual(OrderState.FILLED, filled.new_state)
        canceled = await self.connector._request_order_status(self._tracked(executed=Decimal("0")))
        self.assertEqual(OrderState.CANCELED, canceled.new_state)

    # --- misc pure logic ---

    def test_client_order_id_to_int_match(self):
        self.assertTrue(self.connector._client_order_id_to_int_match("HBOT-12345-x", 12345))
        self.assertFalse(self.connector._client_order_id_to_int_match("HBOT-1", None))
        self.assertFalse(self.connector._client_order_id_to_int_match("HBOT-1", 99999))

    async def test_get_last_traded_price_matches_symbol_else_nan(self):
        self.connector._api_get = AsyncMock(return_value={"perp": [
            {"symbol": "SOL-PERP", "oraclePrice": 143.21},
            {"symbol": "BTC-PERP", "oraclePrice": 65000.0}]})
        price = await self.connector._get_last_traded_price(self.trading_pair)
        self.assertEqual(143.21, price)

        self.connector._api_get = AsyncMock(return_value={"perp": [{"symbol": "BTC-PERP", "oraclePrice": 1}]})
        nan_price = await self.connector._get_last_traded_price(self.trading_pair)
        self.assertNotEqual(nan_price, nan_price)  # NaN != NaN

    async def test_fetch_last_fee_payment_returns_no_payment_sentinel(self):
        ts, rate, amount = await self.connector._fetch_last_fee_payment(self.trading_pair)
        self.assertEqual((0, Decimal("-1"), Decimal("-1")), (ts, rate, amount))

    async def test_position_mode_set_accepts_oneway_only(self):
        ok, msg = await self.connector._trading_pair_position_mode_set(PositionMode.ONEWAY, self.trading_pair)
        self.assertTrue(ok)
        bad, msg2 = await self.connector._trading_pair_position_mode_set(PositionMode.HEDGE, self.trading_pair)
        self.assertFalse(bad)
        self.assertIn("ONEWAY", msg2)
