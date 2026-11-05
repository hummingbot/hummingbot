import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.connector.derivative.reya_perpetual import (
    reya_perpetual_constants as CONSTANTS,
    reya_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.reya_perpetual.reya_perpetual_auth import wire_client_id
from hummingbot.connector.derivative.reya_perpetual.reya_perpetual_derivative import ReyaPerpetualDerivative
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase

PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
WALLET = "0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266"  # The key's own address: the owner signs.
ACCOUNT_ID = 42


def url_pattern(path: str) -> re.Pattern:
    return re.compile(f"^{re.escape(web_utils.public_rest_url(path))}")


class ReyaPerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.quote_asset = CONSTANTS.COLLATERAL_TOKEN
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{CONSTANTS.SYMBOL_SUFFIX}"
        cls.client_order_id_prefix = "HBOT-"
        cls.exchange_order_id_prefix = "1000"

    def setUp(self) -> None:
        super().setUp()
        self.exchange._market_ids[self.symbol] = 1
        self.exchange._initial_margin[self.trading_pair] = Decimal("0.05")

    def create_exchange_instance(self):
        return ReyaPerpetualDerivative(
            reya_perpetual_private_key=PRIVATE_KEY,
            reya_perpetual_wallet_address=WALLET,
            reya_perpetual_account_id=str(ACCOUNT_ID),
            trading_pairs=[self.trading_pair],
        )

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}{CONSTANTS.SYMBOL_SUFFIX}"

    def wallet_url(self, resource: str) -> re.Pattern:
        return url_pattern(CONSTANTS.WALLET_PATH.format(address=WALLET, resource=resource))

    # URLs

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(CONSTANTS.MARKETS_PATH)

    @property
    def latest_prices_url(self):
        return web_utils.public_rest_url(CONSTANTS.MARKET_SUMMARY_PATH.format(symbol=self.symbol))

    @property
    def network_status_url(self):
        return web_utils.public_rest_url(CONSTANTS.MARKETS_PATH)

    @property
    def trading_rules_url(self):
        return web_utils.public_rest_url(CONSTANTS.MARKETS_PATH)

    @property
    def order_creation_url(self):
        return web_utils.public_rest_url(CONSTANTS.CREATE_ORDER_PATH)

    @property
    def balance_url(self):
        return web_utils.public_rest_url(CONSTANTS.WALLET_PATH.format(address=WALLET, resource="accountSummaries"))

    @property
    def funding_info_url(self):
        return self.latest_prices_url

    @property
    def funding_payment_url(self):
        return ""

    # Responses

    def market_definition(self, symbol: Optional[str] = None, status: str = "TRADING") -> Dict[str, Any]:
        return {"symbol": symbol or self.symbol, "marketId": 1, "minOrderQty": "0.01", "qtyStepSize": "0.000001",
                "tickSize": "0.0001", "liquidationMarginParameter": "0.025", "initialMarginParameter": "0.05",
                "maxLeverage": 20, "oiCap": "1000000", "status": status}

    def market_summary(self, mark_price: str = "10000", oracle_price: str = "1", funding_rate: str = "300"):
        return {"symbol": self.symbol, "updatedAt": 1640780000000, "oiQty": "10", "fundingRate": funding_rate,
                "longFundingValue": "0", "shortFundingValue": "0", "volume24h": "100", "markPrice": mark_price,
                "oraclePrice": oracle_price}

    def account_summary(self, margin_balance: str = "15", free_collateral: str = "10") -> Dict[str, Any]:
        return {"accountId": ACCOUNT_ID, "collateralValue": margin_balance, "unrealizedPnl": "0",
                "marginBalance": margin_balance, "initialMarginRequirement": "5",
                "liquidationMarginRequirement": "2", "freeCollateral": free_collateral, "initialMarginRatio": "0.3",
                "liquidationMarginRatio": "0.1", "updatedAt": 1640780000000, "pricesUpdatedAt": 1640780000000}

    def order_row(self, order: InFlightOrder, status: str, cum_qty: Decimal = Decimal("0")) -> Dict[str, Any]:
        return {"exchangeId": CONSTANTS.EXCHANGE_ID, "symbol": self.symbol, "accountId": ACCOUNT_ID,
                "orderId": order.exchange_order_id, "clientOrderId": wire_client_id(order.client_order_id),
                "qty": str(order.amount), "cumQty": str(cum_qty), "side": "B" if order.trade_type is TradeType.BUY else "A",
                "limitPx": str(order.price), "orderType": "LIMIT", "timeInForce": "GTC", "status": status,
                "createdAt": 1640780000000, "lastUpdateAt": 1640780000000}

    def execution(self, order: InFlightOrder, qty: Decimal, price: Decimal) -> Dict[str, Any]:
        return {"exchangeId": CONSTANTS.EXCHANGE_ID, "symbol": self.symbol, "takerAccountId": ACCOUNT_ID,
                "takerOrderId": order.exchange_order_id, "makerAccountId": 7, "makerOrderId": "999",
                "qty": str(qty), "side": "B" if order.trade_type is TradeType.BUY else "A", "price": str(price),
                "takerFee": str(self.expected_fill_fee.flat_fees[0].amount), "makerFee": "0", "type": "ORDER_MATCH",
                "timestamp": 1640780000000, "sequenceNumber": int(self.expected_fill_trade_id)}

    @staticmethod
    def page(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"data": rows, "meta": {"limit": 100, "count": len(rows), "nextCursor": None}}

    @property
    def all_symbols_request_mock_response(self):
        return [self.market_definition()]

    @property
    def latest_prices_request_mock_response(self):
        return self.market_summary(mark_price=str(self.expected_latest_price))

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        return "INVALID-RUSD", [self.market_definition(),
                                self.market_definition(symbol="INVALIDRUSDPERP", status="PREOPEN")]

    @property
    def network_status_request_successful_mock_response(self):
        return [self.market_definition()]

    @property
    def trading_rules_request_mock_response(self):
        return [self.market_definition()]

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return [{"symbol": self.symbol, "marketId": 1, "initialMarginParameter": "0.05", "status": "TRADING"}]

    @property
    def order_creation_request_successful_mock_response(self):
        return {"status": "OPEN", "orderId": self.expected_exchange_order_id}

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return [self.account_summary()]

    @property
    def balance_request_mock_response_only_base(self):
        return [self.account_summary()]

    @property
    def balance_event_websocket_update(self):
        return {"type": "channel_data", "timestamp": 1640780000000,
                "channel": f"/v2/wallet/{WALLET}/accountSummaries", "data": [self.account_summary()]}

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    @property
    def expected_trading_rule(self):
        market = self.market_definition()
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal(market["minOrderQty"]),
            min_price_increment=Decimal(market["tickSize"]),
            min_base_amount_increment=Decimal(market["qtyStepSize"]),
            buy_order_collateral_token=self.quote_asset,
            sell_order_collateral_token=self.quote_asset,
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        return f"Error parsing the trading pair rule {self.trading_rules_request_erroneous_mock_response[0]}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "1000"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("10000")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(percent_token=self.quote_asset,
                                   flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("3"))])

    @property
    def expected_fill_trade_id(self) -> str:
        return "5001"

    @property
    def funding_info_mock_response(self):
        return self.market_summary(mark_price=str(self.target_funding_info_mark_price),
                                   oracle_price=str(self.target_funding_info_index_price),
                                   funding_rate=str(self.target_funding_info_rate * 100))

    @property
    def empty_funding_payment_mock_response(self):
        return {}

    @property
    def funding_payment_mock_response(self):
        return {}

    # Request validation

    def validate_auth_credentials_present(self, request_call: RequestCall):
        # Reads are public; order entry carries the signer's EIP-712 signature in the body.
        if request_call.kwargs.get("data"):
            body = json.loads(request_call.kwargs["data"])
            self.assertTrue(body["signature"].startswith("0x"))
            self.assertEqual(len(body["signature"]), 132)

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        body = json.loads(request_call.kwargs["data"])
        self.assertEqual(ACCOUNT_ID, body["accountId"])
        self.assertEqual(self.symbol, body["symbol"])
        self.assertEqual(order.trade_type is TradeType.BUY, body["isBuy"])
        self.assertEqual(order.amount, Decimal(body["qty"]))
        self.assertEqual(order.price, Decimal(body["limitPx"]))
        self.assertEqual(wire_client_id(order.client_order_id), body["clientOrderId"])
        self.assertEqual("GTC", body["timeInForce"])
        self.assertNotIn("reduceOnly", body)

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        body = json.loads(request_call.kwargs["data"])
        self.assertEqual(ACCOUNT_ID, body["accountId"])
        self.assertEqual(self.symbol, body["symbol"])
        self.assertEqual(order.exchange_order_id, body["orderId"])
        self.assertEqual(wire_client_id(order.client_order_id), body["clientOrderId"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        params = request_call.kwargs.get("params") or {}
        if params:  # Order history; the open-orders read has no parameters.
            self.assertEqual(int(order.creation_timestamp * 1000), params["startTime"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        params = request_call.kwargs["params"]
        self.assertEqual(int(order.creation_timestamp * 1000), params["startTime"])
        self.assertEqual(CONSTANTS.HISTORY_PAGE_LIMIT, params["limit"])

    # Mocked responses

    def configure_successful_cancelation_response(self, order: InFlightOrder, mock_api: aioresponses,
                                                  callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.CANCEL_ORDER_PATH)
        mock_api.post(url, body=json.dumps({"status": "CANCELLED", "orderId": order.exchange_order_id}),
                      callback=callback)
        return url

    def configure_erroneous_cancelation_response(self, order: InFlightOrder, mock_api: aioresponses,
                                                 callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.CANCEL_ORDER_PATH)
        mock_api.post(url, status=400, callback=callback,
                      body=json.dumps({"error": "CANCEL_ORDER_OTHER_ERROR", "message": "Cancel failed"}))
        return url

    def configure_order_not_found_error_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.CANCEL_ORDER_PATH)
        mock_api.post(url, status=400, callback=callback,
                      body=json.dumps({"error": "ORDER_NOT_FOUND_ERROR", "message": "Order not found"}))
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
            self, successful_order: InFlightOrder, erroneous_order: InFlightOrder,
            mock_api: aioresponses) -> List[str]:
        return [self.configure_successful_cancelation_response(successful_order, mock_api),
                self.configure_erroneous_cancelation_response(erroneous_order, mock_api)]

    def configure_order_status(self, mock_api: aioresponses, callback: Callable,
                               open_rows: List[Dict[str, Any]], history: Optional[List[Dict[str, Any]]] = None):
        open_url = self.wallet_url("openOrders")
        mock_api.get(open_url, body=json.dumps(open_rows), callback=callback)
        if history is None:
            return [open_url]
        history_url = self.wallet_url("orderHistory")
        mock_api.get(history_url, body=json.dumps(self.page(history)), callback=callback)
        return [open_url, history_url]

    def configure_completely_filled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        return self.configure_order_status(mock_api, callback, [], [self.order_row(order, "FILLED", order.amount)])

    def configure_canceled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        return self.configure_order_status(mock_api, callback, [], [self.order_row(order, "CANCELLED")])

    def configure_open_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        return self.configure_order_status(mock_api, callback, [self.order_row(order, "OPEN")])

    def configure_http_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = self.wallet_url("openOrders")
        mock_api.get(url, status=500, callback=callback,
                     body=json.dumps({"error": "INTERNAL_SERVER_ERROR", "message": "Internal error"}))
        return url

    def configure_partially_filled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        row = self.order_row(order, "OPEN", self.expected_partial_fill_amount)
        return self.configure_order_status(mock_api, callback, [row])[0]

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        return self.configure_order_status(mock_api, callback, [], [])

    def configure_executions(self, mock_api: aioresponses, callback: Callable, rows: List[Dict[str, Any]],
                             status: int = 200) -> re.Pattern:
        url = self.wallet_url("perpExecutions")
        body = self.page(rows) if status == 200 else {"error": "INTERNAL_SERVER_ERROR", "message": "Internal error"}
        mock_api.get(url, status=status, body=json.dumps(body), callback=callback)
        return url

    def configure_partial_fill_trade_response(self, order: InFlightOrder, mock_api: aioresponses,
                                              callback: Optional[Callable] = lambda *args, **kwargs: None):
        rows = [self.execution(order, self.expected_partial_fill_amount, self.expected_partial_fill_price)]
        return self.configure_executions(mock_api, callback, rows)

    def configure_erroneous_http_fill_trade_response(self, order: InFlightOrder, mock_api: aioresponses,
                                                     callback: Optional[Callable] = lambda *args, **kwargs: None):
        return self.configure_executions(mock_api, callback, [], status=500)

    def configure_full_fill_trade_response(self, order: InFlightOrder, mock_api: aioresponses,
                                           callback: Optional[Callable] = lambda *args, **kwargs: None):
        return self.configure_executions(mock_api, callback, [self.execution(order, order.amount, order.price)])

    def configure_successful_set_position_mode(self, position_mode: PositionMode, mock_api: aioresponses,
                                               callback: Optional[Callable] = lambda *args, **kwargs: None):
        callback()

    def configure_failed_set_position_mode(self, position_mode: PositionMode, mock_api: aioresponses,
                                           callback: Optional[Callable] = lambda *args, **kwargs: None):
        callback()
        return "", "Reya supports one-way position mode only"

    def configure_failed_set_leverage(self, leverage: int, mock_api: aioresponses,
                                      callback: Optional[Callable] = lambda *args, **kwargs: None):
        self.exchange._initial_margin[self.trading_pair] = Decimal("1")
        callback()
        return "", f"Leverage for {self.trading_pair} must be between 1 and 1"

    def configure_successful_set_leverage(self, leverage: int, mock_api: aioresponses,
                                          callback: Optional[Callable] = lambda *args, **kwargs: None):
        callback()

    # Stream events

    def order_event(self, order: InFlightOrder, status: str, cum_qty: Decimal = Decimal("0")):
        return {"type": "channel_data", "timestamp": 1640780000000, "channel": f"/v2/wallet/{WALLET}/orderChanges",
                "data": [self.order_row(order, status, cum_qty)]}

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return self.order_event(order, "OPEN")

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return self.order_event(order, "CANCELLED")

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return self.order_event(order, "FILLED", order.amount)

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {"type": "channel_data", "timestamp": 1640780000000, "channel": f"/v2/wallet/{WALLET}/perpExecutions",
                "data": [self.execution(order, order.amount, order.price)]}

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        return {"type": "channel_data", "timestamp": 1640780000000, "channel": f"/v2/wallet/{WALLET}/positions",
                "data": [{"exchangeId": CONSTANTS.EXCHANGE_ID, "symbol": self.symbol, "accountId": ACCOUNT_ID,
                          "qty": str(order.amount), "side": "B" if order.trade_type is TradeType.BUY else "A",
                          "avgEntryPrice": str(order.price), "avgEntryFundingValue": "0",
                          "lastTradeSequenceNumber": 5001, "unrealizedPnl": str(unrealized_pnl)}]}

    def funding_info_event_for_websocket_update(self):
        return {"type": "channel_data", "timestamp": 1640780000000,
                "channel": f"/v2/perpMarket/{self.symbol}/summary",
                "data": self.market_summary(mark_price="20", oracle_price="10", funding_rate="3000")}

    # Reya-specific overrides of shared tests

    def test_get_buy_and_sell_collateral_tokens(self):
        self._simulate_trading_rules_initialized()
        self.assertEqual(self.quote_asset, self.exchange.get_buy_collateral_token(self.trading_pair))
        self.assertEqual(self.quote_asset, self.exchange.get_sell_collateral_token(self.trading_pair))

    @aioresponses()
    async def test_update_balances(self, mock_api):
        # Margin is held in rUSD only.
        self._configure_balance_response(response=[self.account_summary("15", "10")], mock_api=mock_api)
        await self.exchange._update_balances()
        self.assertEqual(Decimal("10"), self.exchange.available_balances[self.quote_asset])
        self.assertEqual(Decimal("15"), self.exchange.get_balance(self.quote_asset))

    @aioresponses()
    async def test_update_balances_rejects_an_account_the_wallet_does_not_own(self, mock_api):
        self._configure_balance_response(response=[], mock_api=mock_api)
        with self.assertRaises(IOError):
            await self.exchange._update_balances()

    async def test_user_stream_balance_update(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self.balance_event_websocket_update, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue
        with self.assertRaises(asyncio.CancelledError):
            await self.exchange._user_stream_event_listener()
        self.assertEqual(Decimal("10"), self.exchange.available_balances[self.quote_asset])
        self.assertEqual(Decimal("15"), self.exchange.get_balance(self.quote_asset))

    def test_available_balance_reserves_initial_margin_of_resting_orders(self):
        self.exchange._account_available_balances[self.quote_asset] = Decimal("1000")
        self.exchange.start_tracking_order(order_id="HBOT-1", exchange_order_id="1", trading_pair=self.trading_pair,
                                           trade_type=TradeType.BUY, price=Decimal("100"), amount=Decimal("10"),
                                           order_type=OrderType.LIMIT)
        # 10 * 100 notional at a 5% initial margin parameter.
        self.assertEqual(Decimal("950"), self.exchange.get_available_balance(self.quote_asset))

    @aioresponses()
    def test_set_position_mode_failure(self, mock_api):
        self.exchange.set_position_mode(PositionMode.HEDGE)
        self.async_run_with_timeout(asyncio.sleep(0.1))
        self.assertTrue(self.is_logged("ERROR", f"Position mode {PositionMode.HEDGE} is not supported. Mode not set."))

    @aioresponses()
    def test_set_position_mode_success(self, mock_api):
        self.exchange.set_position_mode(PositionMode.ONEWAY)
        self.async_run_with_timeout(asyncio.sleep(0.1))
        self.assertTrue(self.is_logged("INFO", f"Position mode switched to {PositionMode.ONEWAY}."))

    def _assert_limit_close_rejected(self, mock_api, place_order):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)
        order_id = place_order(position_action=PositionAction.CLOSE)
        self.async_run_with_timeout(asyncio.sleep(0.1))
        self.assertEqual([], self._all_executed_requests(mock_api, self.order_creation_url))
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(order_id, self.order_failure_logger.event_log[0].order_id)

    @aioresponses()
    def test_create_order_to_close_short_position(self, mock_api):
        # Reya accepts reduce-only on IOC orders only, so a LIMIT close is refused locally.
        self._assert_limit_close_rejected(mock_api, self.place_buy_order)

    @aioresponses()
    def test_create_order_to_close_long_position(self, mock_api):
        self._assert_limit_close_rejected(mock_api, self.place_sell_order)

    @aioresponses()
    def test_create_market_order_to_close_position_is_reduce_only(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.get_price = lambda trading_pair, is_buy: Decimal("10000")
        mock_api.post(self.order_creation_url, body=json.dumps(self.order_creation_request_successful_mock_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())
        self.place_sell_order(order_type=OrderType.MARKET, position_action=PositionAction.CLOSE)
        self.async_run_with_timeout(request_sent_event.wait())

        body = json.loads(self._all_executed_requests(mock_api, self.order_creation_url)[0].kwargs["data"])
        self.assertEqual("IOC", body["timeInForce"])
        self.assertTrue(body["reduceOnly"])
        self.assertEqual(Decimal("9950"), Decimal(body["limitPx"]))

    @aioresponses()
    def test_create_order_with_unknown_outcome_stays_tracked(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        mock_api.post(self.order_creation_url, status=400,
                      body=json.dumps({"error": "ORDER_OUTCOME_UNKNOWN_ERROR", "message": "Transport failed"}),
                      callback=lambda *args, **kwargs: request_sent_event.set())
        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())
        self.async_run_with_timeout(asyncio.sleep(0.1))

        self.assertIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(0, len(self.order_failure_logger.event_log))

    @aioresponses()
    def test_create_order_rejection_is_classified_by_error_code(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        mock_api.post(self.order_creation_url, status=400,
                      body=json.dumps({"error": "ACCOUNT_BELOW_INITIAL_MARGIN_ERROR", "message": "Insufficient margin"}),
                      callback=lambda *args, **kwargs: request_sent_event.set())
        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())
        self.async_run_with_timeout(asyncio.sleep(0.1))

        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(order_id, self.order_failure_logger.event_log[0].order_id)

    @aioresponses()
    def test_listen_for_funding_info_update_initializes_funding_info(self, mock_api):
        mock_api.get(self.funding_info_url, body=json.dumps(self.funding_info_mock_response))
        funding_info: FundingInfo = self.async_run_with_timeout(
            self.exchange._orderbook_ds.get_funding_info(self.trading_pair))

        self.assertEqual(Decimal(self.target_funding_info_index_price), funding_info.index_price)
        self.assertEqual(Decimal(self.target_funding_info_mark_price), funding_info.mark_price)
        # Funding accrues continuously, so there is no next funding time.
        self.assertEqual(0, funding_info.next_funding_utc_timestamp)
        self.assertEqual(Decimal(self.target_funding_info_rate), funding_info.rate)

    def test_funding_payment_polling_loop_sends_update_event(self):
        # Funding accrues continuously into the balance: there are no discrete payments to report.
        timestamp, rate, payment = self.async_run_with_timeout(
            self.exchange._fetch_last_fee_payment(self.trading_pair))
        self.assertEqual((0, Decimal("-1"), Decimal("-1")), (timestamp, rate, payment))

    @aioresponses()
    async def test_rest_positions_replace_the_tracked_set_and_tolerate_missing_valuation(self, mock_api):
        mock_api.get(self.wallet_url("positions"), body=json.dumps([
            {"exchangeId": 2, "symbol": self.symbol, "accountId": ACCOUNT_ID, "qty": "2", "side": "A",
             "avgEntryPrice": "100", "avgEntryFundingValue": "0", "lastTradeSequenceNumber": 1},
            {"exchangeId": 2, "symbol": self.symbol, "accountId": 99, "qty": "5", "side": "B",
             "avgEntryPrice": "100", "avgEntryFundingValue": "0", "lastTradeSequenceNumber": 1},
        ]))
        await self.exchange._update_positions()

        position = self.exchange.account_positions[self.trading_pair]
        self.assertEqual(PositionSide.SHORT, position.position_side)
        self.assertEqual(Decimal("-2"), position.amount)
        self.assertEqual(Decimal("0"), position.unrealized_pnl)

        mock_api.get(self.wallet_url("positions"), body=json.dumps([]))
        await self.exchange._update_positions()
        self.assertEqual({}, self.exchange.account_positions)

    async def test_position_snapshot_is_a_bare_array_and_a_zero_quantity_update_closes(self):
        row = {"exchangeId": 2, "symbol": self.symbol, "accountId": ACCOUNT_ID, "qty": "1", "side": "B",
               "avgEntryPrice": "100", "avgEntryFundingValue": "0", "lastTradeSequenceNumber": 1,
               "unrealizedPnl": "4"}
        channel = f"/v2/wallet/{WALLET}/positions"
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [
            {"type": "subscribed", "channel": channel, "contents": [row]},
            {"type": "channel_data", "channel": channel, "data": [{**row, "unrealizedPnl": None}]},
            asyncio.CancelledError,
        ]
        self.exchange._user_stream_tracker._user_stream = mock_queue
        with self.assertRaises(asyncio.CancelledError):
            await self.exchange._user_stream_event_listener()
        # An update without valuation keeps the last known unrealized PnL.
        self.assertEqual(Decimal("4"), self.exchange.account_positions[self.trading_pair].unrealized_pnl)

        mock_queue.get.side_effect = [{"type": "channel_data", "channel": channel, "data": [{**row, "qty": "0"}]},
                                      asyncio.CancelledError]
        with self.assertRaises(asyncio.CancelledError):
            await self.exchange._user_stream_event_listener()
        self.assertEqual({}, self.exchange.account_positions)
