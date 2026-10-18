import asyncio
import json
import re
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

from hummingbot.connector.derivative.true_perpetual import (
    true_perpetual_constants as CONSTANTS,
    true_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.true_perpetual.true_perpetual_api_order_book_data_source import (
    TruePerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.true_perpetual.true_perpetual_derivative import TruePerpetualDerivative
from hummingbot.connector.derivative.true_perpetual.true_perpetual_user_stream_data_source import (
    TruePerpetualUserStreamDataSource,
)
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent


class TruePerpetualDerivativeTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{cls.quote_asset}"
        cls.domain = CONSTANTS.DOMAIN

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.exchange = TruePerpetualDerivative(
            true_perpetual_api_key="tbk_test",
            true_perpetual_api_secret="tbs_test",
            trading_pairs=[self.trading_pair],
            trading_required=True,
            domain=self.domain,
        )
        self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
        self.exchange._set_current_timestamp(1700000000)
        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)
        self.exchange._set_trading_pair_symbol_map(bidict({self.symbol: self.trading_pair}))
        self.exchange._trading_rules[self.trading_pair] = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("1"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("10"),
            buy_order_collateral_token="USDC",
            sell_order_collateral_token="USDC",
        )
        self._initialize_event_loggers()

    def handle(self, record):
        self.log_records.append(record)

    async def _drain(self):
        # order updates are applied by the tracker in scheduled futures
        for _ in range(5):
            await asyncio.sleep(0)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _initialize_event_loggers(self):
        self.buy_order_created_logger = EventLogger()
        self.sell_order_created_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.order_failure_logger = EventLogger()
        self.buy_order_completed_logger = EventLogger()
        for event, logger in (
            (MarketEvent.BuyOrderCreated, self.buy_order_created_logger),
            (MarketEvent.SellOrderCreated, self.sell_order_created_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.OrderFailure, self.order_failure_logger),
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
        ):
            self.exchange.add_listener(event, logger)

    # ── url helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _regex(url: str):
        return re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")

    def _url(self, path: str):
        return web_utils.rest_url(path, domain=self.domain)

    # ── fixtures ────────────────────────────────────────────────────────────

    def _markets_response(self) -> Dict[str, Any]:
        return {"ok": True, "markets": [
            {"symbol": self.symbol, "base": "BTC", "quote": "USDC", "active": True, "lotSize": "0.001",
             "tickSize": "1", "minOrderNotionalUsd": "10", "maxOrderSize": "50", "maxLeverage": 50,
             "makerFeePct": "0.02", "takerFeePct": "0.065", "fundingRate8h": "0.0001"},
            {"symbol": "ETHUSDC", "base": "ETH", "quote": "USDC", "active": True, "lotSize": "0.01",
             "tickSize": "0.1", "minOrderNotionalUsd": "10", "maxLeverage": 40,
             "makerFeePct": "0.02", "takerFeePct": "0.065"},
            {"symbol": "DEADUSDC", "base": "DEAD", "quote": "USDC", "active": False, "lotSize": "1", "tickSize": "1"},
            {"symbol": "BROKENUSDC", "base": "BROKEN", "quote": "USDC", "active": True},
        ]}

    def _account_response(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "account": {"equityUsd": "8553.8", "freeCollateralUsd": "7400.1", "marginUsed": "1153.7"},
            "positionsOk": True,
            "positions": [
                {"market": self.symbol, "size": "0.01", "entry_price": "80000", "unrealized_pnl": "12.5", "leverage": "5"},
            ],
        }

    def _tracked_order(self, order_id: str = "OID1", exchange_id: Optional[str] = "42599337",
                       trade_type: TradeType = TradeType.BUY, state: OrderState = OrderState.OPEN) -> InFlightOrder:
        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id=exchange_id,
            trading_pair=self.trading_pair,
            trade_type=trade_type,
            price=Decimal("81000"),
            amount=Decimal("0.002"),
            order_type=OrderType.LIMIT,
            position_action=PositionAction.OPEN,
        )
        order = self.exchange.in_flight_orders[order_id]
        if state != OrderState.PENDING_CREATE:
            order.current_state = state
        return order

    # ── identity ────────────────────────────────────────────────────────────

    def test_properties(self):
        self.assertEqual("true_perpetual", self.exchange.name)
        self.assertEqual(CONSTANTS.DOMAIN, self.exchange.domain)
        self.assertEqual(CONSTANTS.RATE_LIMITS, self.exchange.rate_limits_rules)
        self.assertEqual(CONSTANTS.MAX_ORDER_ID_LEN, self.exchange.client_order_id_max_length)
        self.assertEqual("HBOT", self.exchange.client_order_id_prefix)
        self.assertEqual(CONSTANTS.MARKETS_PATH_URL, self.exchange.trading_rules_request_path)
        self.assertEqual(CONSTANTS.MARKETS_PATH_URL, self.exchange.trading_pairs_request_path)
        self.assertEqual(CONSTANTS.SERVER_TIME_PATH_URL, self.exchange.check_network_request_path)
        self.assertEqual([self.trading_pair], self.exchange.trading_pairs)
        self.assertTrue(self.exchange.is_cancel_request_in_exchange_synchronous)
        self.assertTrue(self.exchange.is_trading_required)
        self.assertEqual(600, self.exchange.funding_fee_poll_interval)
        self.assertEqual([OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER], self.exchange.supported_order_types())
        self.assertEqual([PositionMode.ONEWAY], self.exchange.supported_position_modes())
        self.assertEqual("USDC", self.exchange.get_buy_collateral_token(self.trading_pair))
        self.assertEqual("USDC", self.exchange.get_sell_collateral_token(self.trading_pair))
        self.assertTrue(self.exchange.authenticator.configured)
        self.assertIsInstance(self.exchange._create_order_book_data_source(), TruePerpetualAPIOrderBookDataSource)
        self.assertIsInstance(self.exchange._create_user_stream_data_source(), TruePerpetualUserStreamDataSource)

    def test_error_classification(self):
        self.assertTrue(self.exchange._is_request_exception_related_to_time_synchronizer(IOError("timestamp_out_of_window")))
        self.assertFalse(self.exchange._is_request_exception_related_to_time_synchronizer(IOError("bad_signature")))
        self.assertTrue(self.exchange._is_order_not_found_during_status_update_error(IOError("order_not_found: x")))
        self.assertFalse(self.exchange._is_order_not_found_during_status_update_error(IOError("rate_limited")))
        self.assertTrue(self.exchange._is_order_not_found_during_cancelation_error(IOError("order_not_open")))
        self.assertTrue(self.exchange._is_order_not_found_during_cancelation_error(IOError("Order Not Found")))
        self.assertFalse(self.exchange._is_order_not_found_during_cancelation_error(IOError("emergency_stop")))

    # ── markets, symbols, rules, fees ───────────────────────────────────────

    async def test_symbol_map_skips_inactive_and_incomplete_markets(self):
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(self._markets_response())
        mapping = await self.exchange.trading_pair_symbol_map()
        self.assertEqual({self.symbol: "BTC-USDC", "ETHUSDC": "ETH-USDC"}, dict(mapping))

    @aioresponses()
    async def test_update_trading_rules(self, mock_api):
        mock_api.get(self._url(CONSTANTS.MARKETS_PATH_URL), body=json.dumps(self._markets_response()))
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(self._markets_response())
        await self.exchange._update_trading_rules()

        rule = self.exchange._trading_rules[self.trading_pair]
        self.assertEqual(Decimal("0.001"), rule.min_order_size)
        self.assertEqual(Decimal("1"), rule.min_price_increment)
        self.assertEqual(Decimal("0.001"), rule.min_base_amount_increment)
        self.assertEqual(Decimal("10"), rule.min_notional_size)
        self.assertEqual(Decimal("50"), rule.max_order_size)
        self.assertEqual("USDC", rule.buy_order_collateral_token)
        eth_rule = self.exchange._trading_rules["ETH-USDC"]
        self.assertEqual(Decimal("0.1"), eth_rule.min_price_increment)
        self.assertNotIn("DEAD-USDC", self.exchange._trading_rules)
        self.assertNotIn("BROKEN-USDC", self.exchange._trading_rules)

    @aioresponses()
    async def test_markets_are_cached(self, mock_api):
        mock_api.get(self._url(CONSTANTS.MARKETS_PATH_URL), body=json.dumps(self._markets_response()))
        first = await self.exchange.markets()
        second = await self.exchange.markets()
        self.assertIs(first, second)
        self.assertEqual(1, len(mock_api.requests))
        info = await self.exchange.market_info(self.symbol)
        self.assertEqual(50, info["maxLeverage"])

    @aioresponses()
    async def test_market_info_refreshes_cache_for_unknown_symbol(self, mock_api):
        url = self._url(CONSTANTS.MARKETS_PATH_URL)
        mock_api.get(url, body=json.dumps({"ok": True, "markets": []}))
        mock_api.get(url, body=json.dumps(self._markets_response()))
        self.assertEqual({}, await self.exchange.markets())
        info = await self.exchange.market_info(self.symbol)
        self.assertEqual(self.symbol, info["symbol"])

    @aioresponses()
    async def test_update_trading_fees_and_get_fee(self, mock_api):
        mock_api.get(self._url(CONSTANTS.MARKETS_PATH_URL), body=json.dumps(self._markets_response()))
        await self.exchange._update_trading_fees()
        self.assertEqual(Decimal("0.0002"), self.exchange._trading_fees[self.trading_pair]["maker"])
        self.assertEqual(Decimal("0.00065"), self.exchange._trading_fees[self.trading_pair]["taker"])

        maker_fee = self.exchange._get_fee("BTC", "USDC", OrderType.LIMIT, TradeType.BUY, PositionAction.OPEN, Decimal("1"), Decimal("80000"))
        self.assertEqual(Decimal("0.0002"), maker_fee.percent)
        taker_fee = self.exchange._get_fee("BTC", "USDC", OrderType.MARKET, TradeType.SELL, PositionAction.CLOSE, Decimal("1"), Decimal("80000"))
        self.assertEqual(Decimal("0.00065"), taker_fee.percent)
        explicit = self.exchange._get_fee("BTC", "USDC", OrderType.LIMIT, TradeType.BUY, PositionAction.OPEN, Decimal("1"), Decimal("80000"), is_maker=False)
        self.assertEqual(Decimal("0.00065"), explicit.percent)

    def test_get_fee_falls_back_to_defaults_without_live_fees(self):
        fee = self.exchange._get_fee("ETH", "USDC", OrderType.LIMIT, TradeType.BUY, PositionAction.OPEN, Decimal("1"), Decimal("3000"))
        self.assertEqual(Decimal("0.0002"), fee.percent)
        fee = self.exchange._get_fee("ETH", "USDC", OrderType.MARKET, TradeType.BUY, PositionAction.OPEN, Decimal("1"), Decimal("3000"))
        self.assertEqual(Decimal("0.00065"), fee.percent)

    @aioresponses()
    async def test_get_last_traded_prices(self, mock_api):
        mock_api.get(self._regex(self._url(CONSTANTS.TICKER_PATH_URL)), body=json.dumps({
            "ok": True, "data": {"results": [{"symbol": self.symbol, "last_traded_price": "82012.5"}, {"symbol": "ETHUSDC", "last_traded_price": None}]},
        }), repeat=True)
        prices = await self.exchange.get_last_traded_prices([self.trading_pair])
        self.assertEqual({self.trading_pair: 82012.5}, prices)
        self.assertEqual(82012.5, await self.exchange._get_last_traded_price(self.trading_pair))

    @aioresponses()
    async def test_check_network(self, mock_api):
        mock_api.get(self._url(CONSTANTS.SERVER_TIME_PATH_URL), body=json.dumps({"ok": True, "serverTime": 1700000000000}))
        from hummingbot.core.network_iterator import NetworkStatus
        self.assertEqual(NetworkStatus.CONNECTED, await self.exchange.check_network())

    # ── websocket token ─────────────────────────────────────────────────────

    @aioresponses()
    async def test_ws_token_is_fetched_and_cached(self, mock_api):
        import time
        mock_api.post(self._url(CONSTANTS.WS_TOKEN_PATH_URL), body=json.dumps({
            "ok": True, "token": "tok_abc", "expiresAt": int((time.time() + 3600) * 1000), "url": CONSTANTS.WSS_URL}))
        self.assertEqual("tok_abc", await self.exchange.ws_token())
        self.assertEqual("tok_abc", await self.exchange.ws_token())
        self.assertEqual(1, len(mock_api.requests))

    @aioresponses()
    async def test_ws_token_failure_is_tolerated(self, mock_api):
        mock_api.post(self._url(CONSTANTS.WS_TOKEN_PATH_URL), status=500, body="boom")
        self.assertIsNone(await self.exchange.ws_token())

    async def test_ws_token_without_credentials(self):
        exchange = TruePerpetualDerivative(true_perpetual_api_key="", true_perpetual_api_secret="",
                                           trading_pairs=[self.trading_pair], trading_required=False)
        self.assertIsNone(await exchange.ws_token())

    # ── placing orders ──────────────────────────────────────────────────────

    @aioresponses()
    async def test_place_limit_maker_order(self, mock_api):
        url = self._url(CONSTANTS.PLACE_ORDER_PATH_URL)
        mock_api.post(url, body=json.dumps({"ok": True, "order": {"id": 42599337, "status": "open", "timestamp": 1700000000500}}))

        exchange_id, transact_time = await self.exchange._place_order(
            order_id="OID1", trading_pair=self.trading_pair, amount=Decimal("0.002"), trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT_MAKER, price=Decimal("81000"), position_action=PositionAction.OPEN)

        self.assertEqual("42599337", exchange_id)
        self.assertEqual(1700000000.5, transact_time)
        request = next(iter(mock_api.requests.values()))[0]
        body = json.loads(request.kwargs["data"])
        self.assertEqual({
            "market": self.symbol, "side": "buy", "type": "limit", "size": "0.002", "postOnly": True,
            "reduceOnly": False, "clientOrderId": "OID1", "price": "81000",
        }, body)
        self.assertEqual("tbk_test", request.kwargs["headers"]["X-TRUE-KEY"])
        self.assertIn("X-TRUE-SIGN", request.kwargs["headers"])

    @aioresponses()
    async def test_place_market_close_order(self, mock_api):
        mock_api.post(self._url(CONSTANTS.PLACE_ORDER_PATH_URL), body=json.dumps({"ok": True, "order": {"order_id": "77"}}))
        exchange_id, _ = await self.exchange._place_order(
            order_id="OID2", trading_pair=self.trading_pair, amount=Decimal("0.002"), trade_type=TradeType.SELL,
            order_type=OrderType.MARKET, price=Decimal("0"), position_action=PositionAction.CLOSE)
        self.assertEqual("77", exchange_id)
        body = json.loads(next(iter(mock_api.requests.values()))[0].kwargs["data"])
        self.assertEqual("sell", body["side"])
        self.assertEqual("market", body["type"])
        self.assertTrue(body["reduceOnly"])
        self.assertFalse(body["postOnly"])
        self.assertNotIn("price", body)

    @aioresponses()
    async def test_place_order_refused_by_venue(self, mock_api):
        mock_api.post(self._url(CONSTANTS.PLACE_ORDER_PATH_URL), status=403,
                      body=json.dumps({"ok": False, "error": "position_notional_cap", "message": "cap 1000 USD"}))
        with self.assertRaises(IOError) as context:
            await self.exchange._place_order(
                order_id="OID3", trading_pair=self.trading_pair, amount=Decimal("0.002"), trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT, price=Decimal("81000"), position_action=PositionAction.OPEN)
        self.assertIn("position_notional_cap", str(context.exception))
        self.assertIn("cap 1000 USD", str(context.exception))

    @aioresponses()
    async def test_place_order_without_id_fails(self, mock_api):
        mock_api.post(self._url(CONSTANTS.PLACE_ORDER_PATH_URL), body=json.dumps({"ok": True, "order": {}}))
        with self.assertRaises(IOError):
            await self.exchange._place_order(
                order_id="OID4", trading_pair=self.trading_pair, amount=Decimal("0.002"), trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT, price=Decimal("81000"), position_action=PositionAction.OPEN)

    @aioresponses()
    async def test_create_order_emits_created_event(self, mock_api):
        mock_api.post(self._url(CONSTANTS.PLACE_ORDER_PATH_URL), body=json.dumps({"ok": True, "order": {"id": 1, "timestamp": 1700000000000}}))
        await self.exchange._create_order(
            trade_type=TradeType.BUY, order_id="OID5", trading_pair=self.trading_pair, amount=Decimal("0.002"),
            order_type=OrderType.LIMIT, price=Decimal("81000"), position_action=PositionAction.OPEN)
        await self._drain()
        self.assertIn("OID5", self.exchange.in_flight_orders)
        self.assertEqual("1", self.exchange.in_flight_orders["OID5"].exchange_order_id)
        self.assertEqual(1, len(self.buy_order_created_logger.event_log))
        self.assertEqual(0, len(self.order_failure_logger.event_log))

    @aioresponses()
    async def test_create_order_failure_emits_failure_event(self, mock_api):
        mock_api.post(self._url(CONSTANTS.PLACE_ORDER_PATH_URL), status=400,
                      body=json.dumps({"ok": False, "error": "price_out_of_band"}))
        await self.exchange._create_order(
            trade_type=TradeType.SELL, order_id="OID6", trading_pair=self.trading_pair, amount=Decimal("0.002"),
            order_type=OrderType.LIMIT, price=Decimal("81000"), position_action=PositionAction.OPEN)
        await self._drain()
        self.assertNotIn("OID6", self.exchange.in_flight_orders)
        self.assertEqual(1, len(self.order_failure_logger.event_log))
        self.assertEqual("OID6", self.order_failure_logger.event_log[0].order_id)

    # ── cancelling ──────────────────────────────────────────────────────────

    @aioresponses()
    async def test_cancel_order_successful(self, mock_api):
        order = self._tracked_order()
        mock_api.delete(self._regex(self._url("/orders/42599337")), body=json.dumps({"ok": True}))
        self.assertTrue(await self.exchange._place_cancel(order.client_order_id, order))
        request = next(iter(mock_api.requests.values()))[0]
        self.assertIn(f"market={self.symbol}", str(request.kwargs.get("url") or next(iter(mock_api.requests.keys()))[1]))

    @aioresponses()
    async def test_cancel_order_not_found_marks_order(self, mock_api):
        order = self._tracked_order()
        mock_api.delete(self._regex(self._url("/orders/42599337")), status=404,
                        body=json.dumps({"ok": False, "error": "order_not_found"}))
        with self.assertRaises(IOError) as context:
            await self.exchange._place_cancel(order.client_order_id, order)
        self.assertIn(CONSTANTS.ORDER_NOT_FOUND_ERROR, str(context.exception))

    @aioresponses()
    async def test_cancel_order_refused(self, mock_api):
        order = self._tracked_order()
        mock_api.delete(self._regex(self._url("/orders/42599337")), status=409,
                        body=json.dumps({"ok": False, "error": "venue_busy", "detail": {"retry": True}}))
        with self.assertRaises(IOError) as context:
            await self.exchange._place_cancel(order.client_order_id, order)
        self.assertIn("venue_busy", str(context.exception))

    @aioresponses()
    async def test_execute_cancel_emits_cancelled_event(self, mock_api):
        order = self._tracked_order()
        mock_api.delete(self._regex(self._url("/orders/42599337")), body=json.dumps({"ok": True}))
        await self.exchange._execute_cancel(self.trading_pair, order.client_order_id)
        await self._drain()
        self.assertEqual(1, len(self.order_cancelled_logger.event_log))
        self.assertNotIn("OID1", self.exchange.in_flight_orders)

    # ── order status ────────────────────────────────────────────────────────

    async def _status_update(self, mock_api, order_payload: Dict[str, Any], ok: bool = True, status: int = 200):
        order = self._tracked_order()
        mock_api.get(self._regex(self._url("/orders/42599337")), status=status,
                     body=json.dumps({"ok": ok, "order": order_payload} if ok else {"ok": False, **order_payload}))
        return order, await self.exchange._request_order_status(order)

    @aioresponses()
    async def test_request_order_status_normalized_states(self, mock_api):
        for venue_status, expected in (("open", OrderState.OPEN), ("partially_filled", OrderState.PARTIALLY_FILLED),
                                       ("filled", OrderState.FILLED), ("cancelled", OrderState.CANCELED),
                                       ("expired", OrderState.CANCELED), ("rejected", OrderState.FAILED)):
            self.exchange._order_tracker._in_flight_orders.clear()
            mock_api.get(self._regex(self._url("/orders/42599337")), body=json.dumps({
                "ok": True, "order": {"id": 42599337, "status": venue_status, "timestamp": 1700000001000}}))
            order = self._tracked_order()
            update = await self.exchange._request_order_status(order)
            self.assertEqual(expected, update.new_state, venue_status)
            self.assertEqual("42599337", update.exchange_order_id)
            self.assertEqual("OID1", update.client_order_id)
            self.assertEqual(1700000001.0, update.update_timestamp)

    @aioresponses()
    async def test_request_order_status_legacy_closed_mapping(self, mock_api):
        order, update = await self._status_update(mock_api, {"status": "closed", "remainingSize": "0", "filledSize": "0.002"})
        self.assertEqual(OrderState.FILLED, update.new_state)
        self.exchange._order_tracker._in_flight_orders.clear()
        order, update = await self._status_update(mock_api, {"status": "closed", "remainingSize": "0.002", "filledSize": "0", "cancelReason": "USER_CANCELED"})
        self.assertEqual(OrderState.CANCELED, update.new_state)
        self.exchange._order_tracker._in_flight_orders.clear()
        order, update = await self._status_update(mock_api, {"status": "weird", "remainingSize": "0.001", "filledSize": "0.001"})
        self.assertEqual(OrderState.PARTIALLY_FILLED, update.new_state)
        self.exchange._order_tracker._in_flight_orders.clear()
        order, update = await self._status_update(mock_api, {"status": "weird", "remainingSize": "0.002", "filledSize": "0"})
        self.assertEqual(OrderState.OPEN, update.new_state)

    @aioresponses()
    async def test_request_order_status_error_raises(self, mock_api):
        order = self._tracked_order()
        mock_api.get(self._regex(self._url("/orders/42599337")), status=404,
                     body=json.dumps({"ok": False, "error": "order_not_found", "message": "no such order"}))
        with self.assertRaises(IOError) as context:
            await self.exchange._request_order_status(order)
        self.assertTrue(self.exchange._is_order_not_found_during_status_update_error(context.exception))

    @aioresponses()
    async def test_update_order_status_processes_fills_and_completion(self, mock_api):
        order = self._tracked_order()
        mock_api.get(self._regex(self._url(CONSTANTS.FILLS_PATH_URL)), body=json.dumps({"ok": True, "page": {"next": None, "results": [
            {"id": "177396390-1", "order_id": 42599337, "price": "81000", "size": "0.002", "fee": "0.0324",
             "fee_currency": "USDC", "liquidity": "maker", "side": "buy", "created_at": 1700000002000, "market": self.symbol},
            {"id": "177396391-1", "order_id": 1, "price": "81000", "size": "0.002", "fee": "0", "side": "buy",
             "created_at": 1700000002000, "market": self.symbol},
        ]}}), repeat=True)
        mock_api.get(self._regex(self._url("/orders/42599337")), body=json.dumps({
            "ok": True, "order": {"id": 42599337, "status": "filled", "timestamp": 1700000003000}}), repeat=True)

        await self.exchange._update_order_status()
        await self._drain()

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("81000"), fill_event.price)
        self.assertEqual(Decimal("0.002"), fill_event.amount)
        self.assertEqual([("USDC", Decimal("0.0324"))], [(f.token, f.amount) for f in fill_event.trade_fee.flat_fees])
        self.assertEqual(1, len(self.buy_order_completed_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertEqual({}, self.exchange._fills_cache)

    @aioresponses()
    async def test_update_orders_fills_survives_fills_error(self, mock_api):
        order = self._tracked_order()
        mock_api.get(self._regex(self._url(CONSTANTS.FILLS_PATH_URL)), status=500, body="down")
        await self.exchange._update_orders_fills([order])
        self.assertEqual(0, len(self.order_filled_logger.event_log))
        self.assertTrue(any("Failed to fetch TRUE fills" in r.getMessage() for r in self.log_records))

    async def test_all_trade_updates_without_exchange_id(self):
        order = self._tracked_order(exchange_id=None, state=OrderState.PENDING_CREATE)
        self.assertEqual([], await self.exchange._all_trade_updates_for_order(order))

    # ── balances and positions ──────────────────────────────────────────────

    @aioresponses()
    async def test_update_balances_and_positions(self, mock_api):
        mock_api.get(self._url(CONSTANTS.ACCOUNT_PATH_URL), body=json.dumps(self._account_response()))
        await self.exchange._update_balances()

        self.assertEqual(Decimal("8553.8"), self.exchange.get_balance("USDC"))
        self.assertEqual(Decimal("7400.1"), self.exchange.get_available_balance("USDC"))
        positions = self.exchange.account_positions
        self.assertEqual(1, len(positions))
        position = next(iter(positions.values()))
        self.assertEqual(self.trading_pair, position.trading_pair)
        self.assertEqual(PositionSide.LONG, position.position_side)
        self.assertEqual(Decimal("0.01"), position.amount)
        self.assertEqual(Decimal("80000"), position.entry_price)
        self.assertEqual(Decimal("12.5"), position.unrealized_pnl)
        self.assertEqual(Decimal("5"), position.leverage)

    @aioresponses()
    async def test_update_positions_short_and_removal(self, mock_api):
        url = self._url(CONSTANTS.POSITIONS_PATH_URL)
        mock_api.get(url, body=json.dumps({"ok": True, "positionsOk": True, "positions": [
            {"market": self.symbol, "size": "-0.5", "entry_price": "82000", "unrealized_pnl": "-3", "leverage": "10"},
            {"market": "UNKNOWNUSDC", "size": "1"},
        ]}))
        await self.exchange._update_positions()
        position = next(iter(self.exchange.account_positions.values()))
        self.assertEqual(PositionSide.SHORT, position.position_side)
        self.assertEqual(Decimal("-0.5"), position.amount)
        self.assertEqual(1, len(self.exchange.account_positions))

        mock_api.get(url, body=json.dumps({"ok": True, "positionsOk": True, "positions": [{"market": self.symbol, "size": "0"}]}))
        await self.exchange._update_positions()
        self.assertEqual(0, len(self.exchange.account_positions))

    @aioresponses()
    async def test_update_positions_flat_account_clears_stale_position(self, mock_api):
        await self.exchange._apply_positions([{"market": self.symbol, "size": "0.1", "entry_price": "1", "leverage": "1"}])
        self.assertEqual(1, len(self.exchange.account_positions))
        mock_api.get(self._url(CONSTANTS.POSITIONS_PATH_URL), body=json.dumps({"ok": True, "positionsOk": True, "positions": []}))
        await self.exchange._update_positions()
        self.assertEqual(0, len(self.exchange.account_positions))

    @aioresponses()
    async def test_update_positions_skipped_when_venue_unreadable(self, mock_api):
        await self.exchange._apply_positions([{"market": self.symbol, "size": "0.1", "entry_price": "1", "leverage": "1"}])
        mock_api.get(self._url(CONSTANTS.POSITIONS_PATH_URL), body=json.dumps({"ok": True, "positionsOk": False, "positions": []}))
        await self.exchange._update_positions()
        self.assertEqual(1, len(self.exchange.account_positions))

    # ── leverage, position mode, funding ────────────────────────────────────

    @aioresponses()
    async def test_set_leverage_success(self, mock_api):
        mock_api.post(self._url(CONSTANTS.LEVERAGE_PATH_URL), body=json.dumps({"ok": True, "market": self.symbol, "leverage": 5}))
        self.assertEqual((True, ""), await self.exchange._set_trading_pair_leverage(self.trading_pair, 5))
        body = json.loads(next(iter(mock_api.requests.values()))[0].kwargs["data"])
        self.assertEqual({"market": self.symbol, "leverage": 5}, body)

    @aioresponses()
    async def test_set_leverage_over_cap(self, mock_api):
        mock_api.post(self._url(CONSTANTS.LEVERAGE_PATH_URL), status=400,
                      body=json.dumps({"ok": False, "error": "leverage_too_high", "maxLeverage": 50}))
        success, message = await self.exchange._set_trading_pair_leverage(self.trading_pair, 100)
        self.assertFalse(success)
        self.assertIn("leverage_too_high", message)
        self.assertIn(f"max 50x on {self.symbol}", message)

    async def test_position_mode(self):
        self.assertEqual((True, ""), await self.exchange._trading_pair_position_mode_set(PositionMode.ONEWAY, self.trading_pair))
        success, message = await self.exchange._trading_pair_position_mode_set(PositionMode.HEDGE, self.trading_pair)
        self.assertFalse(success)
        self.assertIn("ONEWAY", message)

    async def test_fetch_last_fee_payment_is_empty(self):
        self.assertEqual((0, Decimal("-1"), Decimal("-1")), await self.exchange._fetch_last_fee_payment(self.trading_pair))

    # ── user stream ─────────────────────────────────────────────────────────

    async def test_user_stream_account_event_updates_balances_and_positions(self):
        event = {"event": "account", "data": {
            "account": {"equityUsd": "9000", "freeCollateralUsd": "8000"},
            "positionsOk": True,
            "positions": [{"market": self.symbol, "size": "-0.02", "entry_price": "83000", "unrealized_pnl": "1", "leverage": "3"}],
        }}
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event, {"event": "warning", "data": {"code": "x"}}, asyncio.CancelledError()]
        self.exchange._user_stream_tracker._user_stream = mock_queue
        try:
            await self.exchange._user_stream_event_listener()
        except asyncio.CancelledError:
            pass
        self.assertEqual(Decimal("9000"), self.exchange.get_balance("USDC"))
        self.assertEqual(Decimal("8000"), self.exchange.get_available_balance("USDC"))
        position = next(iter(self.exchange.account_positions.values()))
        self.assertEqual(PositionSide.SHORT, position.position_side)
        self.assertEqual(Decimal("-0.02"), position.amount)

    async def test_user_stream_listener_logs_unexpected_errors(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [{"event": "account", "data": {"account": {"equityUsd": "not-a-number"}}}, asyncio.CancelledError()]
        self.exchange._user_stream_tracker._user_stream = mock_queue
        with patch.object(self.exchange, "_sleep", AsyncMock()):
            try:
                await self.exchange._user_stream_event_listener()
            except asyncio.CancelledError:
                pass
        self.assertTrue(self._is_logged("ERROR", "Unexpected error in the TRUE account stream listener."))

    async def test_iter_user_event_queue_retries_on_error(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [RuntimeError("x"), {"event": "warning", "data": {}}, asyncio.CancelledError()]
        self.exchange._user_stream_tracker._user_stream = mock_queue
        received = []
        with patch.object(self.exchange, "_sleep", AsyncMock()):
            try:
                async for event in self.exchange._iter_user_event_queue():
                    received.append(event)
            except asyncio.CancelledError:
                pass
        self.assertEqual([{"event": "warning", "data": {}}], received)

    # ── polling loop ────────────────────────────────────────────────────────

    @aioresponses()
    async def test_status_polling_loop_fetch_updates(self, mock_api):
        mock_api.get(self._url(CONSTANTS.ACCOUNT_PATH_URL), body=json.dumps(self._account_response()))
        await self.exchange._status_polling_loop_fetch_updates()
        self.assertEqual(Decimal("8553.8"), self.exchange.get_balance("USDC"))
