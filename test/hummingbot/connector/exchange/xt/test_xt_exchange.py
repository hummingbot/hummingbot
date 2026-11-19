import asyncio
import json
import re
from decimal import Decimal
from unittest.mock import AsyncMock

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.connector.exchange.xt import xt_constants as CONSTANTS, xt_web_utils as web_utils
from hummingbot.connector.exchange.xt.xt_exchange import XtExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount


class XtExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):
    @staticmethod
    def response(result):
        return {"rc": 0, "mc": "SUCCESS", "result": result}

    def symbol_info(self, base=None, quote=None):
        base, quote = base or self.base_asset, quote or self.quote_asset
        return {
            "symbol": self.exchange_symbol_for_tokens(base, quote),
            "baseCurrency": base.lower(), "quoteCurrency": quote.lower(),
            "state": "ONLINE", "tradingEnabled": True, "openapiEnabled": False,
            "orderTypes": [], "timeInForces": [],
            "pricePrecision": 4, "quantityPrecision": 3, "quoteCurrencyPrecision": 6,
            "makerFeeRate": "0.001", "takerFeeRate": "0.002",
            "filters": [
                {"filter": "PRICE", "min": "0.0001", "max": "100000", "tickSize": "0.0001"},
                {"filter": "QUANTITY", "min": "0.001", "max": "1000000", "tickSize": "0.001"},
                {"filter": "QUOTE_QTY", "min": "1"},
            ],
        }

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)

    @property
    def latest_prices_url(self):
        return web_utils.public_rest_url(CONSTANTS.TICKER_PRICE_PATH_URL) + f"?symbol={self.exchange_trading_pair}"

    @property
    def network_status_url(self):
        return web_utils.public_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)

    @property
    def trading_rules_url(self):
        return self.all_symbols_url

    @property
    def order_creation_url(self):
        return web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)

    @property
    def balance_url(self):
        return web_utils.private_rest_url(CONSTANTS.BALANCES_PATH_URL)

    @property
    def all_symbols_request_mock_response(self):
        return self.response({"symbols": [self.symbol_info()]})

    @property
    def latest_prices_request_mock_response(self):
        return self.response([{"s": self.exchange_trading_pair, "p": str(self.expected_latest_price)}])

    @property
    def all_symbols_including_invalid_pair_mock_response(self):
        invalid = self.symbol_info("INVALID", "PAIR")
        invalid["state"] = "OFFLINE"
        return "INVALID-PAIR", self.response({"symbols": [self.symbol_info(), invalid]})

    @property
    def network_status_request_successful_mock_response(self):
        return self.response({"serverTime": 1640780000000})

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        info = self.symbol_info()
        info["filters"][0]["tickSize"] = "not-a-number"
        return self.response({"symbols": [info]})

    @property
    def order_creation_request_successful_mock_response(self):
        return self.response({"orderId": self.expected_exchange_order_id})

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return self.response({"assets": [
            {"currency": self.base_asset.lower(), "availableAmount": "10", "totalAmount": "15"},
            {"currency": self.quote_asset.lower(), "availableAmount": "2000", "totalAmount": "2000"},
        ]})

    @property
    def balance_request_mock_response_only_base(self):
        response = self.balance_request_mock_response_for_base_and_quote
        response["result"]["assets"].pop()
        return response

    @property
    def balance_event_websocket_update(self):
        return {"topic": "balance", "data": {"z": "SPOT", "c": self.base_asset.lower(), "b": "15", "f": "5"}}

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            self.trading_pair, min_order_size=Decimal("0.001"), max_order_size=Decimal("1000000"),
            min_price_increment=Decimal("0.0001"), min_base_amount_increment=Decimal("0.001"),
            min_quote_amount_increment=Decimal("0.000001"), min_notional_size=Decimal("1"),
            supports_market_orders=False,
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        info = self.trading_rules_request_erroneous_mock_response["result"]["symbols"][0]
        return f"Error parsing the trading pair rule {info}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "123456789012345678"

    @property
    def is_order_fill_http_update_included_in_status_update(self):
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self):
        return True

    @property
    def expected_partial_fill_price(self):
        return Decimal("10500")

    @property
    def expected_partial_fill_amount(self):
        return Decimal("0.5")

    @property
    def expected_fill_fee(self):
        return DeductedFromReturnsTradeFee(flat_fees=[TokenAmount(self.quote_asset, Decimal("30"))])

    @property
    def expected_fill_trade_id(self):
        return "987654321"

    def exchange_symbol_for_tokens(self, base_token, quote_token):
        return f"{base_token}_{quote_token}".lower()

    def create_exchange_instance(self):
        return XtExchange(xt_api_key="testAPIKey", xt_api_secret="testSecret", trading_pairs=[self.trading_pair])

    def validate_auth_credentials_present(self, request_call: RequestCall):
        headers = request_call.kwargs["headers"]
        self.assertEqual("testAPIKey", headers["validate-appkey"])
        self.assertTrue(headers["validate-signature"])
        self.assertIn("validate-timestamp", headers)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_trading_pair, data["symbol"])
        self.assertEqual(order.trade_type.name, data["side"])
        self.assertEqual("LIMIT", data["type"])
        self.assertEqual("GTC", data["timeInForce"])
        self.assertEqual("SPOT", data["bizType"])
        self.assertEqual(order.amount, Decimal(data["quantity"]))
        self.assertEqual(order.price, Decimal(data["price"]))
        self.assertEqual(order.client_order_id, data["clientOrderId"])

    def validate_order_cancelation_request(self, order, request_call):
        self.assertEqual({}, request_call.kwargs.get("params") or {})

    def validate_order_status_request(self, order, request_call):
        self.assertEqual({}, request_call.kwargs.get("params") or {})

    def validate_trades_request(self, order, request_call):
        params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, params["symbol"])
        self.assertEqual(order.exchange_order_id, str(params["orderId"]))

    def order_url(self, order):
        return web_utils.private_rest_url(CONSTANTS.ORDER_STATUS_PATH_URL.format(order_id=order.exchange_order_id))

    @staticmethod
    def url_pattern(url):
        return re.compile(r"^" + re.escape(url) + r"(?:\?.*)?$")

    def configure_successful_cancelation_response(self, order, mock_api, callback=None):
        url = self.order_url(order)
        mock_api.delete(self.url_pattern(url), payload=self.response({"orderId": order.exchange_order_id}), callback=callback)
        return url

    def configure_erroneous_cancelation_response(self, order, mock_api, callback=None):
        url = self.order_url(order)
        mock_api.delete(self.url_pattern(url), status=400, callback=callback)
        return url

    def configure_order_not_found_error_cancelation_response(self, order, mock_api, callback=None):
        url = self.order_url(order)
        mock_api.delete(self.url_pattern(url), payload={"rc": 1, "mc": "ORDER_005", "result": None}, callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(self, successful_order, erroneous_order, mock_api):
        return [self.configure_successful_cancelation_response(successful_order, mock_api),
                self.configure_erroneous_cancelation_response(erroneous_order, mock_api)]

    def status_response(self, order, state):
        return self.response({
            "orderId": order.exchange_order_id, "clientOrderId": order.client_order_id,
            "symbol": self.exchange_trading_pair, "state": state, "updatedTime": 1640780001000,
            **({"executedQty": "0"} if state == "CANCELED" else {}),
        })

    def configure_status(self, order, mock_api, state, callback=None, executed_qty=None):
        url = self.order_url(order)
        response = self.status_response(order, state)
        if executed_qty is not None:
            response["result"]["executedQty"] = str(executed_qty)
        mock_api.get(self.url_pattern(url), payload=response, callback=callback)
        return url

    def configure_completely_filled_order_status_response(self, order, mock_api, callback=None):
        return self.configure_status(order, mock_api, "FILLED", callback)

    def configure_canceled_order_status_response(self, order, mock_api, callback=None):
        self.configure_empty_trade_history(mock_api)
        return self.configure_status(order, mock_api, "CANCELED", callback)

    def configure_open_order_status_response(self, order, mock_api, callback=None):
        return self.configure_status(order, mock_api, "NEW", callback)

    def configure_partially_filled_order_status_response(self, order, mock_api, callback=None):
        return self.configure_status(order, mock_api, "PARTIALLY_FILLED", callback)

    def configure_http_error_order_status_response(self, order, mock_api, callback=None):
        url = self.order_url(order)
        mock_api.get(self.url_pattern(url), status=401, callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(self, order, mock_api, callback=None):
        url = self.order_url(order)
        mock_api.get(self.url_pattern(url), payload={"rc": 1, "mc": "ORDER_005", "result": None}, callback=callback)
        return [url]

    def trade_row(self, order, partial=False):
        amount = self.expected_partial_fill_amount if partial else order.amount
        price = self.expected_partial_fill_price if partial else order.price
        return {
            "tradeId": self.expected_fill_trade_id, "orderId": order.exchange_order_id,
            "symbol": self.exchange_trading_pair, "price": str(price), "quantity": str(amount),
            "quoteQty": str(price * amount), "fee": "30", "feeCurrency": self.quote_asset.lower(),
            "time": 1640780001000,
        }

    def configure_trade(self, order, mock_api, partial=False, callback=None):
        url = web_utils.private_rest_url(CONSTANTS.TRADE_HISTORY_PATH_URL)
        mock_api.get(self.url_pattern(url), payload=self.response({"items": [self.trade_row(order, partial)], "hasNext": False}),
                     callback=callback, repeat=True)
        return url

    def configure_partial_fill_trade_response(self, order, mock_api, callback=None):
        return self.configure_trade(order, mock_api, partial=True, callback=callback)

    def configure_full_fill_trade_response(self, order, mock_api, callback=None):
        return self.configure_trade(order, mock_api, callback=callback)

    def configure_erroneous_http_fill_trade_response(self, order, mock_api, callback=None):
        url = web_utils.private_rest_url(CONSTANTS.TRADE_HISTORY_PATH_URL)
        mock_api.get(self.url_pattern(url), status=400, callback=callback)
        return url

    def order_event(self, order, state):
        return {"topic": "order", "data": {"i": order.exchange_order_id, "ci": order.client_order_id,
                                           "st": state, "t": 1640780001000,
                                           **({"eq": "0"} if state == "CANCELED" else {})}}

    def order_event_for_new_order_websocket_update(self, order):
        return self.order_event(order, "NEW")

    def order_event_for_canceled_order_websocket_update(self, order):
        return self.order_event(order, "CANCELED")

    def order_event_for_full_fill_websocket_update(self, order):
        return self.order_event(order, "FILLED")

    def trade_event_for_full_fill_websocket_update(self, order):
        return {"topic": "trade", "data": {
            "i": self.expected_fill_trade_id, "oi": order.exchange_order_id, "p": str(order.price),
            "q": str(order.amount), "v": str(order.amount * order.price), "t": 1640780001000,
        }}

    def track_order(self, client_order_id="HBOT-test-order", exchange_order_id="123456789012345678", amount=Decimal("1")):
        self.exchange.start_tracking_order(
            order_id=client_order_id, exchange_order_id=exchange_order_id, trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT, trade_type=TradeType.BUY, price=Decimal("10000"), amount=amount,
        )
        return self.exchange.in_flight_orders[client_order_id]

    async def listen_to_events(self, *events):
        queue = AsyncMock()
        queue.get.side_effect = [*events, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = queue
        with self.assertRaises(asyncio.CancelledError):
            await self.exchange._user_stream_event_listener()
        await asyncio.sleep(0)

    @aioresponses()
    async def test_create_limit_maker_uses_gtx_for_both_sides(self, mock_api):
        self._simulate_trading_rules_initialized()
        mock_api.post(self.order_creation_url, payload=self.order_creation_request_successful_mock_response, repeat=True)
        for side in (TradeType.BUY, TradeType.SELL):
            order_id = f"HBOT-{side.name}"
            await self.exchange._create_order(side, order_id, self.trading_pair, Decimal("1"),
                                              OrderType.LIMIT_MAKER, Decimal("10000"))
            self.assertIn(order_id, self.exchange.in_flight_orders)
        requests = self._all_executed_requests(mock_api, self.order_creation_url)
        self.assertEqual(2, len(requests))
        for request, side in zip(requests, ("BUY", "SELL")):
            body = json.loads(request.kwargs["data"])
            self.assertEqual("GTX", body["timeInForce"])
            self.assertEqual("LIMIT", body["type"])
            self.assertEqual(side, body["side"])

    @aioresponses()
    async def test_standard_client_order_ids_fit_xt_limit(self, mock_api):
        self._simulate_trading_rules_initialized()
        mock_api.post(self.order_creation_url, payload=self.order_creation_request_successful_mock_response, repeat=True)
        ids = [self.exchange.buy(self.trading_pair, Decimal("1"), OrderType.LIMIT, Decimal("10000")),
               self.exchange.sell(self.trading_pair, Decimal("1"), OrderType.LIMIT_MAKER, Decimal("10000"))]
        await asyncio.sleep(0.1)
        self.assertEqual(2, len(set(ids)))
        for client_order_id in ids:
            self.assertTrue(client_order_id.startswith(CONSTANTS.HBOT_ORDER_ID_PREFIX))
            self.assertLessEqual(len(client_order_id), 22)
            self.assertIn(client_order_id, self.exchange.in_flight_orders)
        self.assertEqual(2, len(self._all_executed_requests(mock_api, self.order_creation_url)))

    @aioresponses()
    async def test_fee_rates_from_exchange_metadata(self, mock_api):
        mock_api.get(self.all_symbols_url, payload=self.all_symbols_request_mock_response)
        await self.exchange._update_trading_fees()
        for order_type, is_maker, expected in [(OrderType.LIMIT_MAKER, True, "0.001"), (OrderType.LIMIT, False, "0.002")]:
            fee = self.exchange.get_fee(self.base_asset, self.quote_asset, order_type, TradeType.BUY,
                                        Decimal("1"), Decimal("10000"), is_maker=is_maker)
            self.assertEqual(Decimal(expected), fee.percent)

    @aioresponses()
    async def test_symbol_discovery_supports_another_quote(self, mock_api):
        info = self.response({"symbols": [self.symbol_info(), self.symbol_info("BTC", "USDT")]})
        mock_api.get(self.all_symbols_url, payload=info)
        self.exchange._set_trading_pair_symbol_map(None)
        self.assertEqual([self.trading_pair, "BTC-USDT"], await self.exchange.all_trading_pairs())
        self.assertEqual("btc_usdt", await self.exchange.exchange_symbol_associated_to_pair("BTC-USDT"))

    @aioresponses()
    async def test_duplicate_private_trade_is_emitted_once(self, mock_api):
        order = self.track_order(amount=Decimal("2"))
        event = self.trade_event_for_full_fill_websocket_update(order)
        event["data"]["q"] = str(self.expected_partial_fill_amount)
        event["data"]["p"] = str(self.expected_partial_fill_price)
        event["data"]["v"] = str(self.expected_partial_fill_amount * self.expected_partial_fill_price)
        self.configure_partial_fill_trade_response(order, mock_api)
        self.configure_partial_fill_trade_response(order, mock_api)
        await self.listen_to_events(event, event)
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(self.expected_partial_fill_amount, order.executed_amount_base)
        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)

    @aioresponses()
    async def test_duplicate_rest_and_websocket_fill_is_emitted_once(self, mock_api):
        order = self.track_order(amount=Decimal("2"))
        event = self.trade_event_for_full_fill_websocket_update(order)
        self.configure_full_fill_trade_response(order, mock_api)
        await self.listen_to_events(event)
        self.configure_full_fill_trade_response(order, mock_api)
        updates = await self.exchange._all_trade_updates_for_order(order)
        for update in updates:
            self.exchange._order_tracker.process_trade_update(update)
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(Decimal("2"), order.executed_amount_base)

    @aioresponses()
    async def test_create_timeout_remains_tracked_then_recovers_by_client_id(self, mock_api):
        self._simulate_trading_rules_initialized()
        mock_api.post(self.order_creation_url, exception=asyncio.TimeoutError())
        client_order_id = "HBOT-uncertain"
        await self.exchange._create_order(TradeType.BUY, client_order_id, self.trading_pair,
                                          Decimal("1"), OrderType.LIMIT, Decimal("10000"))
        order = self.exchange.in_flight_orders[client_order_id]
        self.assertEqual(OrderState.PENDING_CREATE, order.current_state)
        self.assertIsNone(order.exchange_order_id)
        self.assertFalse(self.order_failure_logger.event_log)
        result = self.status_response(order, "NEW")
        result["result"]["orderId"] = self.expected_exchange_order_id
        mock_api.get(self.url_pattern(self.order_creation_url), payload=result)
        update = await self.exchange._request_order_status(order)
        self.exchange._order_tracker.process_order_update(update)
        await asyncio.sleep(0.1)
        self.assertEqual(self.expected_exchange_order_id, order.exchange_order_id)
        self.assertTrue(order.is_open)
        self.assertEqual(1, len(self.buy_order_created_logger.event_log))
        lookup = self._all_executed_requests(mock_api, self.order_creation_url)[-1]
        self.assertEqual(client_order_id, lookup.kwargs["params"]["clientOrderId"])

    @aioresponses()
    async def test_create_order_fails_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        mock_api.post(self.order_creation_url, payload={"rc": 1, "mc": "ORDER_F0101", "result": None})
        await self.exchange._create_order(TradeType.BUY, "HBOT-rejected", self.trading_pair,
                                          Decimal("1"), OrderType.LIMIT, Decimal("10000"))
        await asyncio.sleep(0.1)
        self.assertNotIn("HBOT-rejected", self.exchange.in_flight_orders)
        self.assertEqual(1, len(self.order_failure_logger.event_log))

    @aioresponses()
    async def test_http_client_error_with_known_denial_fails_create_once(self, mock_api):
        self._simulate_trading_rules_initialized()
        for status, code in ((403, "AUTH_104"), (400, "ORDER_F0101")):
            with self.subTest(status=status, code=code):
                client_id = f"HBOT-rejected-{code}"
                mock_api.post(self.order_creation_url, status=status,
                              payload={"rc": 1, "mc": code, "result": None})
                await self.exchange._create_order(TradeType.BUY, client_id, self.trading_pair,
                                                  Decimal("1"), OrderType.LIMIT, Decimal("10000"))
                await asyncio.sleep(0.1)
                self.assertNotIn(client_id, self.exchange.in_flight_orders)
        self.assertEqual(2, len(self.order_failure_logger.event_log))
        self.assertEqual(2, len(self._all_executed_requests(mock_api, self.order_creation_url)))

    @aioresponses()
    async def test_http_unknown_and_server_errors_preserve_create_without_replay(self, mock_api):
        self._simulate_trading_rules_initialized()
        for index, (status, code) in enumerate(((400, "UNKNOWN"), (503, "UNKNOWN"), (500, "AUTH_104"))):
            with self.subTest(status=status, code=code):
                client_id = f"HBOT-uncertain-{index}"
                mock_api.post(self.order_creation_url, status=status,
                              payload={"rc": 1, "mc": code, "result": None})
                await self.exchange._create_order(TradeType.BUY, client_id, self.trading_pair,
                                                  Decimal("1"), OrderType.LIMIT, Decimal("10000"))
                self.assertEqual(OrderState.PENDING_CREATE,
                                 self.exchange.in_flight_orders[client_id].current_state)
        self.assertFalse(self.order_failure_logger.event_log)
        self.assertEqual(3, len(self._all_executed_requests(mock_api, self.order_creation_url)))

    @aioresponses()
    async def test_http_timestamp_denial_retries_only_after_explicit_no_execution(self, mock_api):
        self.exchange._update_time_synchronizer = AsyncMock()
        mock_api.post(self.order_creation_url, status=401,
                      payload={"rc": 1, "mc": "AUTH_105", "result": None})
        mock_api.post(self.order_creation_url, payload=self.order_creation_request_successful_mock_response)
        exchange_id, _ = await self.exchange._place_order(
            "HBOT-time-denied", self.trading_pair, Decimal("1"), TradeType.BUY, OrderType.LIMIT, Decimal("10000"))
        self.assertEqual(self.expected_exchange_order_id, exchange_id)
        self.exchange._update_time_synchronizer.assert_awaited_once()
        self.assertEqual(2, len(self._all_executed_requests(mock_api, self.order_creation_url)))

    @aioresponses()
    async def test_missing_create_ack_preserves_pending_order(self, mock_api):
        self._simulate_trading_rules_initialized()
        mock_api.post(self.order_creation_url, payload=self.response({}))
        await self.exchange._create_order(TradeType.SELL, "HBOT-missing-ack", self.trading_pair,
                                          Decimal("1"), OrderType.LIMIT, Decimal("10000"))
        self.assertEqual(OrderState.PENDING_CREATE, self.exchange.in_flight_orders["HBOT-missing-ack"].current_state)
        self.assertFalse(self.order_failure_logger.event_log)

    @aioresponses()
    async def test_trade_history_rejects_other_order_rows(self, mock_api):
        order = self.track_order()
        row = self.trade_row(order)
        row["orderId"] = "unrelated-order"
        url = web_utils.private_rest_url(CONSTANTS.TRADE_HISTORY_PATH_URL)
        mock_api.get(self.url_pattern(url), payload=self.response({"items": [row], "hasNext": False}))
        with self.assertRaises(ValueError):
            await self.exchange._all_trade_updates_for_order(order)
        self.assertFalse(self.order_filled_logger.event_log)

    async def test_private_balance_ignores_other_business_type(self):
        event = self.balance_event_websocket_update
        event["data"]["z"] = "MARGIN"
        await self.listen_to_events(event)
        self.assertEqual(Decimal("0"), self.exchange.get_balance(self.base_asset))

    @aioresponses()
    async def test_create_connection_loss_keeps_pending_order(self, mock_api):
        self._simulate_trading_rules_initialized()
        mock_api.post(self.order_creation_url, exception=ConnectionError("connection lost after dispatch"))
        await self.exchange._create_order(TradeType.BUY, "HBOT-disconnected", self.trading_pair,
                                          Decimal("1"), OrderType.LIMIT, Decimal("10000"))
        order = self.exchange.in_flight_orders["HBOT-disconnected"]
        self.assertEqual(OrderState.PENDING_CREATE, order.current_state)
        self.assertFalse(self.order_failure_logger.event_log)

    @aioresponses()
    async def test_trade_history_reads_all_pages(self, mock_api):
        order = self.track_order(amount=Decimal("2"))
        first = self.trade_row(order, partial=True)
        first["tradeId"] = "200"
        second = self.trade_row(order, partial=True)
        second["tradeId"] = "100"
        url = web_utils.private_rest_url(CONSTANTS.TRADE_HISTORY_PATH_URL)
        mock_api.get(self.url_pattern(url), payload=self.response({"items": [first], "hasNext": True}))
        mock_api.get(self.url_pattern(url), payload=self.response({"items": [second], "hasNext": False}))
        updates = await self.exchange._all_trade_updates_for_order(order)
        self.assertEqual({"200", "100"}, {update.trade_id for update in updates})
        calls = self._all_executed_requests(mock_api, url)
        self.assertEqual(2, len(calls))
        self.assertEqual("200", str(calls[1].kwargs["params"]["fromId"]))
        self.assertEqual(order.exchange_order_id, str(calls[1].kwargs["params"]["orderId"]))

    @aioresponses()
    async def test_trade_history_repeated_cursor_fails_without_emitting_fills(self, mock_api):
        order = self.track_order()
        row = self.trade_row(order, partial=True)
        url = web_utils.private_rest_url(CONSTANTS.TRADE_HISTORY_PATH_URL)
        mock_api.get(self.url_pattern(url), payload=self.response({"items": [row], "hasNext": True}), repeat=True)
        with self.assertRaises((ValueError, IOError)):
            await self.exchange._all_trade_updates_for_order(order)
        self.assertFalse(self.order_filled_logger.event_log)
        self.assertEqual(Decimal("0"), order.executed_amount_base)

    @aioresponses()
    async def test_trade_history_missing_fee_cannot_invent_zero_fee(self, mock_api):
        order = self.track_order()
        row = self.trade_row(order)
        del row["fee"]
        url = web_utils.private_rest_url(CONSTANTS.TRADE_HISTORY_PATH_URL)
        mock_api.get(self.url_pattern(url), payload=self.response({"items": [row], "hasNext": False}))
        with self.assertRaises((ValueError, IOError)):
            await self.exchange._all_trade_updates_for_order(order)
        self.assertFalse(self.order_filled_logger.event_log)

    @aioresponses()
    async def test_trade_history_nonzero_fee_requires_currency(self, mock_api):
        order = self.track_order()
        row = self.trade_row(order)
        del row["feeCurrency"]
        url = web_utils.private_rest_url(CONSTANTS.TRADE_HISTORY_PATH_URL)
        mock_api.get(self.url_pattern(url), payload=self.response({"items": [row], "hasNext": False}))
        with self.assertRaises((ValueError, IOError)):
            await self.exchange._all_trade_updates_for_order(order)

    @aioresponses()
    async def test_private_trade_without_fee_reconciles_authenticated_trade_history(self, mock_api):
        order = self.track_order()
        event = self.trade_event_for_full_fill_websocket_update(order)
        self.configure_full_fill_trade_response(order, mock_api)
        await self.listen_to_events(event)
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(self.expected_fill_fee, self.order_filled_logger.event_log[0].trade_fee)
        self.assertEqual(order.amount, order.executed_amount_base)

    async def test_unknown_private_order_and_trade_do_not_change_tracked_order(self):
        order = self.track_order()
        order_event = self.order_event_for_canceled_order_websocket_update(order)
        order_event["data"]["i"] = "other-exchange-order"
        order_event["data"]["ci"] = "other-client-order"
        trade_event = self.trade_event_for_full_fill_websocket_update(order)
        trade_event["data"]["oi"] = "other-exchange-order"
        await self.listen_to_events(order_event, trade_event)
        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertFalse(self.order_filled_logger.event_log)
        self.assertFalse(self.order_cancelled_logger.event_log)

    async def test_order_event_can_correlate_by_exchange_id(self):
        order = self.track_order()
        event = self.order_event_for_new_order_websocket_update(order)
        del event["data"]["ci"]
        await self.listen_to_events(event)
        self.assertEqual(1, len(self.buy_order_created_logger.event_log))
        self.assertTrue(order.is_open)

    @aioresponses()
    async def test_http_error_without_rejection_evidence_preserves_pending_create(self, mock_api):
        self._simulate_trading_rules_initialized()
        mock_api.post(self.order_creation_url, status=400)
        await self.exchange._create_order(TradeType.BUY, "HBOT-http-error", self.trading_pair,
                                          Decimal("1"), OrderType.LIMIT, Decimal("10000"))
        order = self.exchange.in_flight_orders["HBOT-http-error"]
        self.assertEqual(OrderState.PENDING_CREATE, order.current_state)
        self.assertIsNone(order.exchange_order_id)
        self.assertFalse(self.order_failure_logger.event_log)

    @aioresponses()
    async def test_unresolved_create_lookup_does_not_mark_order_lost(self, mock_api):
        order = self.track_order(exchange_order_id=None)
        mock_api.get(self.url_pattern(self.order_creation_url),
                     payload={"rc": 1, "mc": "ORDER_005", "result": None}, repeat=True)
        for _ in range(self.exchange._order_tracker.lost_order_count_limit + 2):
            await self.exchange._update_orders_with_error_handler(
                orders=[order], error_handler=self.exchange._handle_update_error_for_active_order)
        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertFalse(self.order_failure_logger.event_log)

    @aioresponses()
    async def test_cancel_ack_waits_for_authenticated_order_event(self, mock_api):
        order = self.track_order()
        self.configure_successful_cancelation_response(order, mock_api)
        result = await self.exchange._execute_cancel(order.trading_pair, order.client_order_id)
        await asyncio.sleep(0.1)
        self.assertEqual(order.client_order_id, result)
        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertEqual(OrderState.PENDING_CANCEL, order.current_state)
        self.assertFalse(self.order_cancelled_logger.event_log)
        self.configure_empty_trade_history(mock_api)
        await self.listen_to_events(self.order_event_for_canceled_order_websocket_update(order))
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertEqual(1, len(self.order_cancelled_logger.event_log))

    @aioresponses()
    async def test_cancel_uncertain_create_recovers_exact_id_before_delete(self, mock_api):
        order = self.track_order(exchange_order_id=None)
        response = self.status_response(order, "NEW")
        response["result"]["orderId"] = self.expected_exchange_order_id
        mock_api.get(self.url_pattern(self.order_creation_url), payload=response)
        cancel_url = web_utils.private_rest_url(CONSTANTS.ORDER_STATUS_PATH_URL.format(order_id=self.expected_exchange_order_id))
        mock_api.delete(cancel_url, payload=self.response({"orderId": self.expected_exchange_order_id}))
        result = await self.exchange._execute_cancel(order.trading_pair, order.client_order_id)
        self.assertEqual(order.client_order_id, result)
        self.assertEqual(self.expected_exchange_order_id, order.exchange_order_id)
        await asyncio.sleep(0.1)
        self.assertEqual(OrderState.PENDING_CANCEL, order.current_state)
        self.assertEqual(1, len(self._all_executed_requests(mock_api, cancel_url)))
        self.assertFalse(self.order_cancelled_logger.event_log)

    @aioresponses()
    async def test_cancel_uncertain_create_preserves_recovered_canceled_state(self, mock_api):
        order = self.track_order(exchange_order_id=None)
        response = self.status_response(order, "CANCELED")
        response["result"]["orderId"] = self.expected_exchange_order_id
        mock_api.get(self.url_pattern(self.order_creation_url), payload=response)
        self.configure_empty_trade_history(mock_api)

        result = await self.exchange._execute_cancel(order.trading_pair, order.client_order_id)
        await asyncio.sleep(0)

        self.assertEqual(order.client_order_id, result)
        self.assertEqual(OrderState.CANCELED, order.current_state)
        self.assertTrue(order.is_done)
        self.assertFalse(order.is_open)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertIs(order, self.exchange._order_tracker.fetch_cached_order(order.client_order_id))
        self.assertEqual(1, len(self.buy_order_created_logger.event_log))
        self.assertEqual(1, len(self.order_cancelled_logger.event_log))
        self.assertFalse(self.order_failure_logger.event_log)
        self.assertTrue(all(method != "DELETE" for method, url in mock_api.requests))

    @aioresponses()
    async def test_cancel_uncertain_create_preserves_recovered_failed_state(self, mock_api):
        order = self.track_order(exchange_order_id=None)
        response = self.status_response(order, "REJECTED")
        response["result"]["orderId"] = self.expected_exchange_order_id
        mock_api.get(self.url_pattern(self.order_creation_url), payload=response)

        result = await self.exchange._execute_cancel(order.trading_pair, order.client_order_id)
        await asyncio.sleep(0)

        self.assertEqual(order.client_order_id, result)
        self.assertEqual(OrderState.FAILED, order.current_state)
        self.assertTrue(order.is_done)
        self.assertFalse(order.is_open)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertIs(order, self.exchange._order_tracker.fetch_cached_order(order.client_order_id))
        self.assertFalse(self.buy_order_created_logger.event_log)
        self.assertFalse(self.order_cancelled_logger.event_log)
        self.assertEqual(1, len(self.order_failure_logger.event_log))
        self.assertTrue(all(method != "DELETE" for method, url in mock_api.requests))

    @aioresponses()
    async def test_cancel_all_reports_success_for_terminal_create_recovery(self, mock_api):
        for state in ("CANCELED", "REJECTED"):
            order = self.track_order(client_order_id=f"HBOT-{state}", exchange_order_id=None)
            response = self.status_response(order, state)
            response["result"]["orderId"] = self.expected_exchange_order_id
            mock_api.get(self.url_pattern(self.order_creation_url), payload=response)
            if state == "CANCELED":
                self.configure_empty_trade_history(mock_api)

            results = await self.exchange.cancel_all(timeout_seconds=5)
            await asyncio.sleep(0)

            self.assertEqual(1, len(results))
            self.assertEqual(order.client_order_id, results[0].order_id)
            self.assertTrue(results[0].success)
            self.assertTrue(order.is_done)
            self.assertFalse(order.is_open)
        self.assertEqual(1, len(self.order_cancelled_logger.event_log))
        self.assertEqual(1, len(self.order_failure_logger.event_log))
        self.assertTrue(all(method != "DELETE" for method, url in mock_api.requests))

    @aioresponses()
    async def test_cancel_uncertain_create_does_not_cancel_recovered_filled_order(self, mock_api):
        order = self.track_order(exchange_order_id=None)
        response = self.status_response(order, "FILLED")
        response["result"]["orderId"] = self.expected_exchange_order_id
        mock_api.get(self.url_pattern(self.order_creation_url), payload=response)
        row = self.trade_row(order)
        row["orderId"] = self.expected_exchange_order_id
        trades_url = web_utils.private_rest_url(CONSTANTS.TRADE_HISTORY_PATH_URL)
        mock_api.get(self.url_pattern(trades_url), payload=self.response({"items": [row], "hasNext": False}))

        result = await self.exchange._execute_cancel(order.trading_pair, order.client_order_id)
        await asyncio.sleep(0)

        self.assertIsNone(result)
        self.assertEqual(OrderState.FILLED, order.current_state)
        self.assertTrue(order.is_done)
        self.assertFalse(order.is_open)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertIs(order, self.exchange._order_tracker.fetch_cached_order(order.client_order_id))
        self.assertEqual(1, len(self.buy_order_completed_logger.event_log))
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertFalse(self.order_cancelled_logger.event_log)
        self.assertTrue(all(method != "DELETE" for method, url in mock_api.requests))

    @aioresponses()
    async def test_cancel_unresolved_create_preserves_tracking(self, mock_api):
        order = self.track_order(exchange_order_id=None)
        mock_api.get(self.url_pattern(self.order_creation_url),
                     payload={"rc": 1, "mc": "ORDER_005", "result": None})
        result = await self.exchange._execute_cancel(order.trading_pair, order.client_order_id)
        self.assertIsNone(result)
        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertFalse(self.order_cancelled_logger.event_log)
        self.assertFalse(self.order_failure_logger.event_log)
        self.assertTrue(all(method != "DELETE" for method, url in mock_api.requests))

    @aioresponses()
    async def test_recovery_status_rejects_mismatched_client_id(self, mock_api):
        order = self.track_order(exchange_order_id=None)
        response = self.status_response(order, "NEW")
        response["result"].update(orderId=self.expected_exchange_order_id, clientOrderId="other-client")
        mock_api.get(self.url_pattern(self.order_creation_url), payload=response)
        with self.assertRaises(ValueError):
            await self.exchange._request_order_status(order)
        self.assertIsNone(order.exchange_order_id)
        self.assertEqual(OrderState.PENDING_CREATE, order.current_state)

    @aioresponses()
    async def test_zero_fee_fill_is_valid_without_fee_currency(self, mock_api):
        order = self.track_order()
        row = self.trade_row(order)
        row["fee"] = "0"
        del row["feeCurrency"]
        url = web_utils.private_rest_url(CONSTANTS.TRADE_HISTORY_PATH_URL)
        mock_api.get(self.url_pattern(url), payload=self.response({"items": [row], "hasNext": False}))
        updates = await self.exchange._all_trade_updates_for_order(order)
        self.assertEqual(1, len(updates))
        self.assertEqual([], updates[0].fee.flat_fees)

    @aioresponses()
    async def test_conflicting_duplicate_trade_fails_without_partial_application(self, mock_api):
        order = self.track_order()
        first = self.trade_row(order, partial=True)
        conflicting = dict(first, quantity="0.25", quoteQty="2625")
        url = web_utils.private_rest_url(CONSTANTS.TRADE_HISTORY_PATH_URL)
        mock_api.get(self.url_pattern(url), payload=self.response({"items": [first, conflicting], "hasNext": False}))
        with self.assertRaises(ValueError):
            await self.exchange._all_trade_updates_for_order(order)
        self.assertFalse(self.order_filled_logger.event_log)
        self.assertEqual(Decimal("0"), order.executed_amount_base)

    @aioresponses()
    async def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)
        await self.exchange._create_order(TradeType.BUY, "HBOT-invalid-size", self.trading_pair,
                                          Decimal("0.0001"), OrderType.LIMIT, Decimal("10000"))
        await asyncio.sleep(0.1)
        self.assertNotIn("HBOT-invalid-size", self.exchange.in_flight_orders)
        self.assertEqual(1, len(self.order_failure_logger.event_log))
        self.assertEqual("HBOT-invalid-size", self.order_failure_logger.event_log[0].order_id)
        self.assertEqual(OrderType.LIMIT, self.order_failure_logger.event_log[0].order_type)
        self.assertFalse(mock_api.requests)

    @aioresponses()
    async def test_active_market_with_empty_capabilities_publishes_symbols_and_trading_rules(self, mock_api):
        offline = dict(self.symbol_info("OFFLINE", self.quote_asset), state="OFFLINE")
        disabled = dict(self.symbol_info("DISABLED", self.quote_asset), tradingEnabled=False)
        mock_api.get(self.trading_rules_url, payload=self.response({
            "symbols": [self.symbol_info(), offline, disabled],
        }))

        await self.exchange._update_trading_rules()

        self.assertEqual([self.trading_pair], await self.exchange.all_trading_pairs())
        self.assertEqual(self.exchange_trading_pair,
                         await self.exchange.exchange_symbol_associated_to_pair(self.trading_pair))
        self.assertEqual(self.trading_pair,
                         await self.exchange.trading_pair_associated_to_exchange_symbol(self.exchange_trading_pair))
        self.assertEqual({self.trading_pair}, set(self.exchange.trading_rules))
        self.assertEqual(repr(self.expected_trading_rule), repr(self.exchange.trading_rules[self.trading_pair]))

    @aioresponses()
    async def test_trading_rule_without_filters_uses_symbol_precisions(self, mock_api):
        info = self.symbol_info()
        info.pop("filters")
        mock_api.get(self.trading_rules_url, payload=self.response({"symbols": [info]}))
        await self.exchange._update_trading_rules()
        rule = self.exchange.trading_rules[self.trading_pair]
        self.assertEqual(Decimal("0.0001"), rule.min_price_increment)
        self.assertEqual(Decimal("0.001"), rule.min_base_amount_increment)
        self.assertEqual(Decimal("0.000001"), rule.min_quote_amount_increment)
        self.assertEqual(Decimal("0"), rule.min_order_size)
        self.assertEqual(Decimal("1e56"), rule.max_order_size)
        self.assertEqual(Decimal("0"), rule.min_notional_size)

    @aioresponses()
    async def test_null_filter_fields_use_symbol_precisions_and_optional_limits(self, mock_api):
        info = self.symbol_info()
        info["filters"] = [
            {"filter": "PRICE", "min": None, "max": None, "tickSize": None},
            {"filter": "QUANTITY", "min": None, "max": None, "tickSize": None},
            {"filter": "QUOTE_QTY", "min": None},
        ]
        mock_api.get(self.trading_rules_url, payload=self.response({"symbols": [info]}))
        await self.exchange._update_trading_rules()
        rule = self.exchange.trading_rules[self.trading_pair]
        self.assertEqual(Decimal("0.0001"), rule.min_price_increment)
        self.assertEqual(Decimal("0.001"), rule.min_base_amount_increment)
        self.assertEqual(Decimal("0"), rule.min_order_size)
        self.assertEqual(Decimal("1e56"), rule.max_order_size)
        self.assertEqual(Decimal("0"), rule.min_notional_size)

    @aioresponses()
    async def test_cancel_uncertain_create_reconciles_prior_partial_fill_before_finalizing(self, mock_api):
        order = self.track_order(exchange_order_id=None)
        response = self.status_response(order, "CANCELED")
        response["result"]["executedQty"] = str(self.expected_partial_fill_amount)
        response["result"]["orderId"] = self.expected_exchange_order_id
        mock_api.get(self.url_pattern(self.order_creation_url), payload=response)
        row = self.trade_row(order, partial=True)
        row["orderId"] = self.expected_exchange_order_id
        trades_url = web_utils.private_rest_url(CONSTANTS.TRADE_HISTORY_PATH_URL)
        mock_api.get(self.url_pattern(trades_url), payload=self.response({"items": [row], "hasNext": False}))
        result = await self.exchange._execute_cancel(order.trading_pair, order.client_order_id)
        await asyncio.sleep(0)
        self.assertEqual(order.client_order_id, result)
        self.assertEqual(OrderState.CANCELED, order.current_state)
        self.assertTrue(order.is_done)
        self.assertFalse(order.is_open)
        self.assertIs(order, self.exchange._order_tracker.fetch_cached_order(order.client_order_id))
        self.assertEqual(self.expected_exchange_order_id, order.exchange_order_id)
        self.assertEqual(self.expected_partial_fill_amount, order.executed_amount_base)
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(self.expected_fill_fee, self.order_filled_logger.event_log[0].trade_fee)
        self.assertEqual(1, len(self.order_cancelled_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(all(method != "DELETE" for method, url in mock_api.requests))

    @aioresponses()
    async def test_canceled_known_id_waits_for_trade_history_after_failed_fill_poll(self, mock_api):
        order = self.track_order()
        self.configure_status(order, mock_api, "CANCELED", executed_qty=self.expected_partial_fill_amount)
        trades_url = web_utils.private_rest_url(CONSTANTS.TRADE_HISTORY_PATH_URL)
        mock_api.get(self.url_pattern(trades_url), status=503)
        mock_api.get(self.url_pattern(trades_url), status=503)
        await self.exchange._update_order_status()
        await asyncio.sleep(0.1)
        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertFalse(self.order_cancelled_logger.event_log)
        self.assertFalse(self.order_filled_logger.event_log)
        self.configure_status(order, mock_api, "CANCELED", executed_qty=self.expected_partial_fill_amount)
        mock_api.get(self.url_pattern(trades_url),
                     payload=self.response({"items": [self.trade_row(order, partial=True)], "hasNext": False}), repeat=True)
        await self.exchange._update_order_status()
        await asyncio.sleep(0.1)
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(1, len(self.order_cancelled_logger.event_log))
        self.assertEqual(self.expected_partial_fill_amount, order.executed_amount_base)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

    @aioresponses()
    async def test_private_canceled_pending_create_waits_for_actual_prior_fills(self, mock_api):
        order = self.track_order(exchange_order_id=None)
        event = self.order_event_for_canceled_order_websocket_update(order)
        event["data"]["i"] = self.expected_exchange_order_id
        event["data"]["eq"] = str(self.expected_partial_fill_amount)
        trades_url = web_utils.private_rest_url(CONSTANTS.TRADE_HISTORY_PATH_URL)
        mock_api.get(self.url_pattern(trades_url), status=503)
        with self.assertRaises(IOError):
            await self.exchange._process_user_stream_order_event(event)
        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertEqual(self.expected_exchange_order_id, order.exchange_order_id)
        self.assertFalse(self.order_cancelled_logger.event_log)
        row = self.trade_row(order, partial=True)
        mock_api.get(self.url_pattern(trades_url), payload=self.response({"items": [row], "hasNext": False}))
        await self.exchange._process_user_stream_order_event(event)
        await asyncio.sleep(0.1)
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(1, len(self.order_cancelled_logger.event_log))
        self.assertEqual(self.expected_partial_fill_amount, order.executed_amount_base)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

    async def test_private_order_rejects_contradictory_client_and_exchange_ids(self):
        order = self.track_order()
        for field, value in [("ci", "other-client-id"), ("i", "other-exchange-id")]:
            with self.subTest(field=field):
                event = self.order_event_for_new_order_websocket_update(order)
                event["data"][field] = value
                with self.assertRaises(ValueError):
                    await self.exchange._process_user_stream_order_event(event)
                self.assertEqual(OrderState.PENDING_CREATE, order.current_state)
                self.assertFalse(self.buy_order_created_logger.event_log)

    def configure_empty_trade_history(self, mock_api):
        url = web_utils.private_rest_url(CONSTANTS.TRADE_HISTORY_PATH_URL)
        mock_api.get(self.url_pattern(url), payload=self.response({"items": [], "hasNext": False}), repeat=True)

    @aioresponses()
    async def test_user_stream_update_for_canceled_order(self, mock_api):
        self.configure_empty_trade_history(mock_api)
        await super().test_user_stream_update_for_canceled_order()

    @aioresponses()
    async def test_lost_order_removed_after_cancel_status_user_event_received(self, mock_api):
        self.configure_empty_trade_history(mock_api)
        await super().test_lost_order_removed_after_cancel_status_user_event_received()

    @aioresponses()
    async def test_update_order_status_when_filled_correctly_processed_even_when_trade_fill_update_fails(self, mock_api):
        order = self.track_order()
        self.configure_completely_filled_order_status_response(order, mock_api)
        trades_url = web_utils.private_rest_url(CONSTANTS.TRADE_HISTORY_PATH_URL)
        mock_api.get(self.url_pattern(trades_url), status=503, repeat=True)
        await self.exchange._update_order_status()
        await asyncio.sleep(0.1)
        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertFalse(self.order_filled_logger.event_log)
        self.assertFalse(self.buy_order_completed_logger.event_log)
        self.assertFalse(self.order_failure_logger.event_log)

    async def test_private_order_rejects_foreign_symbol_side_and_business_type(self):
        order = self.track_order()
        for field, value in [("s", "other_pair"), ("sd", "SELL"), ("z", "MARGIN"),
                             ("symbol", "other_pair"), ("side", "SELL"), ("bizType", "MARGIN")]:
            with self.subTest(field=field):
                event = self.order_event_for_new_order_websocket_update(order)
                event["data"][field] = value
                with self.assertRaises(ValueError):
                    await self.exchange._process_user_stream_order_event(event)
                self.assertEqual(OrderState.PENDING_CREATE, order.current_state)
                self.assertFalse(self.buy_order_created_logger.event_log)

    @aioresponses()
    async def test_canceled_status_waits_for_successfully_lagging_trade_history(self, mock_api):
        order = self.track_order()
        trades_url = web_utils.private_rest_url(CONSTANTS.TRADE_HISTORY_PATH_URL)
        for lagging_rows in ([], [dict(self.trade_row(order, partial=True), quantity="0.25", quoteQty="2625")]):
            self.configure_status(order, mock_api, "CANCELED", executed_qty=self.expected_partial_fill_amount)
            mock_api.get(self.url_pattern(trades_url), payload=self.response({"items": lagging_rows, "hasNext": False}))
            with self.assertRaises(IOError):
                await self.exchange._request_order_status(order)
            self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
            self.assertFalse(self.order_cancelled_logger.event_log)
            self.assertFalse(self.order_filled_logger.event_log)
        self.configure_status(order, mock_api, "CANCELED", executed_qty=self.expected_partial_fill_amount)
        mock_api.get(self.url_pattern(trades_url),
                     payload=self.response({"items": [self.trade_row(order, partial=True)], "hasNext": False}))
        update = await self.exchange._request_order_status(order)
        await self.exchange._order_tracker.process_order_update(update)
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(1, len(self.order_cancelled_logger.event_log))
        self.assertEqual(self.expected_partial_fill_amount, order.executed_amount_base)

    @aioresponses()
    async def test_canceled_rest_without_executed_quantity_retains_order(self, mock_api):
        order = self.track_order()
        response = self.status_response(order, "CANCELED")
        response["result"].pop("executedQty")
        mock_api.get(self.url_pattern(self.order_url(order)), payload=response)
        with self.assertRaises(IOError):
            await self.exchange._request_order_status(order)
        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertFalse(self.order_cancelled_logger.event_log)
        self.assertFalse(self.order_filled_logger.event_log)

    @aioresponses()
    async def test_private_canceled_without_quantity_uses_exact_rest_status(self, mock_api):
        order = self.track_order()
        event = self.order_event_for_canceled_order_websocket_update(order)
        event["data"].pop("eq")
        self.configure_status(order, mock_api, "CANCELED", executed_qty=self.expected_partial_fill_amount)
        self.configure_partial_fill_trade_response(order, mock_api)
        await self.exchange._process_user_stream_order_event(event)
        await asyncio.sleep(0.1)
        status_requests = self._all_executed_requests(mock_api, self.order_url(order))
        self.assertEqual(1, len(status_requests))
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(1, len(self.order_cancelled_logger.event_log))
        self.assertEqual(self.expected_partial_fill_amount, order.executed_amount_base)

    @aioresponses()
    async def test_private_canceled_without_quantity_does_not_override_rest_open(self, mock_api):
        order = self.track_order()
        event = self.order_event_for_canceled_order_websocket_update(order)
        event["data"].pop("eq")
        self.configure_open_order_status_response(order, mock_api)
        await self.exchange._process_user_stream_order_event(event)
        await asyncio.sleep(0.1)
        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_open)
        self.assertFalse(self.order_cancelled_logger.event_log)
