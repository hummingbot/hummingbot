import asyncio
import json
import re
import time
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.connector.derivative.reya_perpetual import (
    reya_perpetual_constants as CONSTANTS,
    reya_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.reya_perpetual.reya_perpetual_auth import wire_client_id
from hummingbot.connector.derivative.reya_perpetual.reya_perpetual_derivative import (
    ReyaAPIError,
    ReyaOrderNotFound,
    ReyaPerpetualDerivative,
)
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase

PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"  # noqa: mock
WALLET = "0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266"  # The key's own address: the owner signs.
OTHER_WALLET = "0x0000000000000000000000000000000000000001"
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
        self.exchange._max_leverage[self.trading_pair] = Decimal("20")

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
        return self.wallet_url("fundingPayments")

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
        return self.page([])

    @property
    def funding_payment_mock_response(self):
        # The entry covers the hour that ends at the target timestamp; rates are hourly percentages.
        return self.page([self.funding_payment(
            timestamp=(self.target_funding_payment_timestamp - 3600) * 1000,
            payment=str(self.target_funding_payment_payment_amount),
            funding_rate=str(self.target_funding_payment_funding_rate * 100))])

    def funding_payment(self, timestamp: int = 1640779200000, payment: str = "-1.5",
                        funding_rate: Optional[str] = "0.0125") -> Dict[str, Any]:
        entry = {"accountId": ACCOUNT_ID, "symbol": self.symbol, "timestamp": timestamp, "side": "B", "qty": "1",
                 "payment": payment}
        if funding_rate is not None:
            entry["fundingRate"] = funding_rate
        return entry

    def position_risk(self, qty: str = "1", side: str = "B", unrealized_pnl: str = "4",
                      account_id: int = ACCOUNT_ID) -> Dict[str, Any]:
        return {"accountId": account_id, "symbol": self.symbol, "side": side, "qty": qty, "avgEntryPrice": "100",
                "lastTradeSequenceNumber": 1, "markPrice": "104", "notional": str(Decimal(qty) * 104),
                "unrealizedPnl": unrealized_pnl, "fundingSinceChange": "0", "fundingSinceOpen": "0",
                "liquidationMarginRequirement": "2", "liquidationPrice": "50", "hasCorrelatedCollateral": False,
                "updatedAt": 1640780000000, "pricesUpdatedAt": 1640780000000}

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
        self.exchange._max_leverage[self.trading_pair] = Decimal("1")
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
        # The valued position after the fill, from the positionRisk channel.
        side = "B" if order.trade_type is TradeType.BUY else "A"
        row = {**self.position_risk(qty=str(order.amount), side=side, unrealized_pnl=str(unrealized_pnl)),
               "avgEntryPrice": str(order.price), "lastTradeSequenceNumber": 5001}
        return {"type": "channel_data", "timestamp": 1640780000000, "channel": f"/v2/wallet/{WALLET}/positionRisk",
                "accountId": ACCOUNT_ID, "data": [row]}

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

    @aioresponses()
    async def test_last_fee_payment_reads_the_newest_hour_for_the_account_and_market(self, mock_api):
        mock_api.get(self.funding_payment_url, body=json.dumps(self.page([self.funding_payment()])))
        timestamp, rate, payment = await self.exchange._fetch_last_fee_payment(self.trading_pair)

        request = next(iter(mock_api.requests.values()))[0]
        self.assertEqual({"accountId": ACCOUNT_ID, "symbol": self.symbol, "limit": 1}, request.kwargs["params"])
        # Reported when the hour it covers has ended; the hourly percentage rate becomes a fraction.
        self.assertEqual(1640782800, timestamp)
        self.assertEqual(Decimal("0.000125"), rate)
        self.assertEqual(Decimal("-1.5"), payment)

    @aioresponses()
    async def test_last_fee_payment_ignores_empty_hours_and_tolerates_a_missing_rate(self, mock_api):
        mock_api.get(self.funding_payment_url, body=json.dumps(self.page([self.funding_payment(payment="0")])))
        self.assertEqual((0, Decimal("-1"), Decimal("-1")),
                         await self.exchange._fetch_last_fee_payment(self.trading_pair))

        mock_api.get(self.funding_payment_url, body=json.dumps(self.page([self.funding_payment(funding_rate=None)])))
        _, rate, payment = await self.exchange._fetch_last_fee_payment(self.trading_pair)
        self.assertEqual((Decimal("0"), Decimal("-1.5")), (rate, payment))

    @aioresponses()
    async def test_rest_positions_are_valued_and_replace_the_tracked_set(self, mock_api):
        mock_api.get(self.wallet_url("positionRisk"), body=json.dumps(
            [self.position_risk(qty="2", side="A", unrealized_pnl="-3")]))
        await self.exchange._update_positions()

        request = next(iter(mock_api.requests.values()))[0]
        self.assertEqual({"accountId": ACCOUNT_ID}, request.kwargs["params"])
        position = self.exchange.account_positions[self.trading_pair]
        self.assertEqual(PositionSide.SHORT, position.position_side)
        self.assertEqual(Decimal("-2"), position.amount)
        self.assertEqual(Decimal("-3"), position.unrealized_pnl)

        mock_api.get(self.wallet_url("positionRisk"), body=json.dumps([]))
        await self.exchange._update_positions()
        self.assertEqual({}, self.exchange.account_positions)

    @aioresponses()
    async def test_rest_positions_fall_back_to_the_position_record_when_valuation_is_unavailable(self, mock_api):
        mock_api.get(self.wallet_url("positionRisk"), body=json.dumps([self.position_risk(unrealized_pnl="4")]))
        await self.exchange._update_positions()

        unavailable = {"error": "SERVICE_UNAVAILABLE_ERROR", "message": "retry after backing off"}
        mock_api.get(self.wallet_url("positionRisk"), status=503, body=json.dumps(unavailable))
        mock_api.get(self.wallet_url("positions"), body=json.dumps([
            {"exchangeId": 2, "symbol": self.symbol, "accountId": ACCOUNT_ID, "qty": "3", "side": "B",
             "avgEntryPrice": "100", "avgEntryFundingValue": "0", "lastTradeSequenceNumber": 2},
            {"exchangeId": 2, "symbol": self.symbol, "accountId": 99, "qty": "5", "side": "B",
             "avgEntryPrice": "100", "avgEntryFundingValue": "0", "lastTradeSequenceNumber": 1},
        ]))
        await self.exchange._update_positions()

        position = self.exchange.account_positions[self.trading_pair]
        self.assertEqual(Decimal("3"), position.amount)
        # Without valuation the last known unrealized PnL is kept.
        self.assertEqual(Decimal("4"), position.unrealized_pnl)

    @aioresponses()
    async def test_rest_positions_raise_other_errors(self, mock_api):
        mock_api.get(self.wallet_url("positionRisk"), status=400,
                     body=json.dumps({"error": "NO_ACCOUNTS_FOUND_ERROR", "message": "No accounts found"}))
        with self.assertRaises(ReyaAPIError):
            await self.exchange._update_positions()

    def delegated_exchange(self, wallet: str = OTHER_WALLET, trading_required: bool = True) -> ReyaPerpetualDerivative:
        # The key signs for another owner wallet: the signer must be one of its enabled API wallets.
        return ReyaPerpetualDerivative(reya_perpetual_private_key=PRIVATE_KEY, reya_perpetual_wallet_address=wallet,
                                       reya_perpetual_account_id=str(ACCOUNT_ID), trading_pairs=[self.trading_pair],
                                       trading_required=trading_required)

    @aioresponses()
    async def test_owner_signer_is_valid_without_a_request(self, mock_api):
        await self.exchange._validate_signer()
        self.assertEqual({}, dict(mock_api.requests))

    @aioresponses()
    async def test_enabled_api_wallet_signer_is_validated_once(self, mock_api):
        exchange = self.delegated_exchange()
        mock_api.get(web_utils.api_wallet_status_url(OTHER_WALLET), body=json.dumps(
            {"enabledApiWallets": [WALLET.upper().replace("0X", "0x")]}))
        await exchange._validate_signer()
        await exchange._validate_signer()
        self.assertEqual(1, sum(len(calls) for calls in mock_api.requests.values()))

    @aioresponses()
    async def test_connect_rejects_a_signer_the_owner_has_not_enabled(self, mock_api):
        # `connect` builds the connector with trading not required and reads its balance.
        exchange = self.delegated_exchange(trading_required=False)
        mock_api.get(web_utils.api_wallet_status_url(OTHER_WALLET), body=json.dumps({"enabledApiWallets": []}))
        # `connect` reads the balance; Reya's reads are public, so the signer is checked there.
        with self.assertRaisesRegex(IOError, "not an enabled API wallet"):
            await exchange._update_balances()

    async def test_trading_requires_a_signer_key(self):
        exchange = ReyaPerpetualDerivative(reya_perpetual_wallet_address=WALLET,
                                           reya_perpetual_account_id=str(ACCOUNT_ID), trading_pairs=[self.trading_pair])
        with self.assertRaisesRegex(IOError, "private key is required"):
            await exchange._validate_signer()

    @aioresponses()
    async def test_update_balances_explains_when_reya_cannot_value_the_account(self, mock_api):
        mock_api.get(url_pattern(CONSTANTS.WALLET_PATH.format(address=WALLET, resource="accountSummaries")),
                     status=503, body=json.dumps({"error": "SERVICE_UNAVAILABLE_ERROR", "message": "retry"}))
        with self.assertRaisesRegex(IOError, "cannot value the account"):
            await self.exchange._update_balances()

    async def test_leverage_is_bounded_by_the_market_maximum(self):
        # The advertised maximum can exceed 1 / initial margin, e.g. 25x with a 4.0006% initial margin.
        definition = {**self.market_definition(), "initialMarginParameter": "0.040006", "maxLeverage": 25}
        self.exchange._initialize_trading_pair_symbols_from_exchange_info([definition])
        self.assertEqual((True, ""), await self.exchange._set_trading_pair_leverage(self.trading_pair, 25))
        self.assertFalse((await self.exchange._set_trading_pair_leverage(self.trading_pair, 26))[0])
        self.assertFalse((await self.exchange._set_trading_pair_leverage("UNKNOWN-RUSD", 2))[0])

    def tracked_order(self) -> InFlightOrder:
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(order_id="HBOT-1", exchange_order_id="10001", trading_pair=self.trading_pair,
                                           trade_type=TradeType.BUY, price=Decimal("100"), amount=Decimal("1"),
                                           order_type=OrderType.LIMIT)
        return self.exchange.in_flight_orders["HBOT-1"]

    @aioresponses()
    async def test_an_order_missing_from_a_truncated_history_is_not_reported_as_not_found(self, mock_api):
        order = self.tracked_order()
        mock_api.get(self.wallet_url("openOrders"), body=json.dumps([]), repeat=True)
        mock_api.get(self.wallet_url("orderHistory"), body=json.dumps(
            {"data": [], "meta": {"limit": 100, "count": 0, "nextCursor": "more"}}), repeat=True)
        with self.assertRaises(IOError) as raised:
            await self.exchange._request_order_status(order)
        self.assertNotIsInstance(raised.exception, ReyaOrderNotFound)

    @aioresponses()
    async def test_an_active_order_missing_from_a_truncated_history_stays_active(self, mock_api):
        order = self.tracked_order()
        mock_api.get(self.wallet_url("openOrders"), body=json.dumps([]), repeat=True)
        mock_api.get(self.wallet_url("orderHistory"), body=json.dumps(
            {"data": [], "meta": {"limit": 100, "count": 0, "nextCursor": "more"}}), repeat=True)
        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 2):
            await self.exchange._update_orders()
        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)

    @aioresponses()
    async def test_a_lost_order_missing_from_a_truncated_history_is_finalized(self, mock_api):
        order = self.tracked_order()
        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            await self.exchange._order_tracker.process_order_not_found(order.client_order_id)
        self.assertIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        mock_api.get(self.wallet_url("openOrders"), body=json.dumps([]), repeat=True)
        mock_api.get(self.wallet_url("orderHistory"), body=json.dumps(
            {"data": [], "meta": {"limit": 100, "count": 0, "nextCursor": "more"}}), repeat=True)
        await self.exchange._update_lost_orders()
        await asyncio.sleep(0.1)
        self.assertTrue(order.is_failure)
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)

    @aioresponses()
    async def test_an_order_missing_from_the_whole_history_is_not_found(self, mock_api):
        order = self.tracked_order()
        mock_api.get(self.wallet_url("openOrders"), body=json.dumps([]))
        mock_api.get(self.wallet_url("orderHistory"), body=json.dumps(self.page([])))
        with self.assertRaises(ReyaOrderNotFound):
            await self.exchange._request_order_status(order)

    async def test_a_feed_reset_row_is_not_a_cancellation(self):
        order = self.tracked_order()
        row = {**self.order_row(order, "CANCELLED"), "cancelReason": "FEED_RESET"}
        await self.run_user_stream({"type": "channel_data", "channel": f"/v2/wallet/{WALLET}/orderChanges",
                                    "data": [row]})
        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertFalse(self.exchange.in_flight_orders[order.client_order_id].is_cancelled)
        self.assertTrue(self.exchange._poll_notifier.is_set())

    def position_row(self, qty: str, sequence: int, side: str = "B") -> Dict[str, Any]:
        return {"exchangeId": 2, "symbol": self.symbol, "accountId": ACCOUNT_ID, "qty": qty, "side": side,
                "avgEntryPrice": "100", "avgEntryFundingValue": "0", "lastTradeSequenceNumber": sequence}

    async def test_a_rest_snapshot_older_than_a_stream_close_does_not_reopen_the_position(self):
        await self.exchange._apply_positions([self.position_row("1", 2)], complete=False)
        await self.exchange._apply_positions([self.position_row("0", 3)], complete=False)
        await self.exchange._apply_positions([self.position_row("1", 2)], complete=True)
        self.assertEqual({}, self.exchange.account_positions)

    async def test_a_rest_snapshot_keeps_a_position_the_stream_opened_after_it_was_read(self):
        changes_before = self.exchange._position_change_count
        await self.exchange._apply_positions([self.position_row("1", 5)], complete=False)
        await self.exchange._apply_positions([], complete=True, changes_before=changes_before)
        self.assertEqual(Decimal("1"), self.exchange.account_positions[self.trading_pair].amount)

        await self.exchange._apply_positions([], complete=True, changes_before=self.exchange._position_change_count)
        self.assertEqual({}, self.exchange.account_positions)

    @aioresponses()
    async def test_funding_info_uses_the_mark_while_the_index_price_is_absent(self, mock_api):
        summary = self.market_summary(mark_price="20")
        del summary["oraclePrice"]
        mock_api.get(self.funding_info_url, body=json.dumps(summary))
        funding_info = await self.exchange._orderbook_ds.get_funding_info(self.trading_pair)
        self.assertEqual(Decimal("20"), funding_info.index_price)

    async def test_status_polling_synchronizes_time_without_a_server_time_endpoint(self):
        self.assertAlmostEqual(time.time(), await web_utils.get_current_server_time(), delta=5)
        fetch = AsyncMock(side_effect=asyncio.CancelledError)
        self.exchange._status_polling_loop_fetch_updates = fetch
        self.exchange._poll_notifier.set()
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(self.exchange._status_polling_loop(), timeout=2)
        fetch.assert_awaited_once()

    def mock_order_status(self, mock_api, row: Dict[str, Any], executions: List[Dict[str, Any]]):
        mock_api.get(self.wallet_url("openOrders"), body=json.dumps([]))
        mock_api.get(self.wallet_url("orderHistory"), body=json.dumps(self.page([row])))
        mock_api.get(self.wallet_url("perpExecutions"), body=json.dumps(self.page(executions)))

    @aioresponses()
    async def test_an_order_recovered_without_an_exchange_id_completes_with_its_fills(self, mock_api):
        # The create timed out, so the order is tracked without the exchange id that fills are matched by.
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(order_id="HBOT-2", exchange_order_id=None, trading_pair=self.trading_pair,
                                           trade_type=TradeType.BUY, price=Decimal("100"), amount=Decimal("1"),
                                           order_type=OrderType.LIMIT)
        order = self.exchange.in_flight_orders["HBOT-2"]
        row = {**self.order_row(order, "FILLED", Decimal("1")), "orderId": "10002"}
        execution = {**self.execution(order, Decimal("1"), Decimal("100")), "takerOrderId": "10002"}
        self.mock_order_status(mock_api, row, [execution])

        await self.exchange._update_orders()
        await asyncio.sleep(0.1)

        self.assertEqual("10002", order.exchange_order_id)
        self.assertEqual(Decimal("1"), order.executed_amount_base)
        self.assertTrue(order.is_filled)
        self.assertEqual(1, len(self.order_filled_logger.event_log))

    @aioresponses()
    async def test_missing_fills_are_read_from_the_orders_own_lifetime(self, mock_api):
        # Fills older than the newest history pages are found by reading the window the order lived in.
        order = self.tracked_order()
        row = {**self.order_row(order, "FILLED", Decimal("1")), "lastUpdateAt": 1640780005000}
        self.mock_order_status(mock_api, row, [self.execution(order, Decimal("1"), Decimal("100"))])

        await self.exchange._update_orders()
        await asyncio.sleep(0.1)

        executions_request = next(calls[0] for (method, url), calls in mock_api.requests.items()
                                  if "perpExecutions" in str(url))
        self.assertEqual({"limit": CONSTANTS.HISTORY_PAGE_LIMIT, "startTime": 1640780000000,
                          "endTime": 1640780005000 + CONSTANTS.ORDER_FILLS_SETTLEMENT_WINDOW * 1000},
                         executions_request.kwargs["params"])
        self.assertEqual(Decimal("1"), order.executed_amount_base)
        self.assertTrue(order.is_filled)

    @aioresponses()
    async def test_reading_a_finished_orders_fills_resumes_on_the_next_poll(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(order_id="HBOT-3", exchange_order_id="10003", trading_pair=self.trading_pair,
                                           trade_type=TradeType.BUY, price=Decimal("100"), amount=Decimal("2"),
                                           order_type=OrderType.LIMIT)
        order = self.exchange.in_flight_orders["HBOT-3"]
        row = {**self.order_row(order, "FILLED", Decimal("2")), "lastUpdateAt": 1640780005000}
        first = {**self.execution(order, Decimal("1"), Decimal("100")), "sequenceNumber": 1}
        second = {**self.execution(order, Decimal("1"), Decimal("100")), "sequenceNumber": 2}
        for _ in range(2):
            mock_api.get(self.wallet_url("openOrders"), body=json.dumps([]))
            mock_api.get(self.wallet_url("orderHistory"), body=json.dumps(self.page([row])))
        mock_api.get(self.wallet_url("perpExecutions"), body=json.dumps(
            {"data": [first], "meta": {"limit": 100, "count": 1, "nextCursor": "older"}}))
        mock_api.get(self.wallet_url("perpExecutions"), body=json.dumps(self.page([second])))

        with patch.object(CONSTANTS, "ORDER_FILLS_MAX_PAGES", 1):
            await self.exchange._update_orders()
            await asyncio.sleep(0.1)
            # The window holds more pages than one poll reads: the order stays open with what was found.
            self.assertEqual(Decimal("1"), order.executed_amount_base)
            self.assertFalse(order.is_done)

            await self.exchange._update_orders()
            await asyncio.sleep(0.1)

        executions_requests = [call for (method, url), calls in mock_api.requests.items()
                               if "perpExecutions" in str(url) for call in calls]
        self.assertEqual("older", executions_requests[-1].kwargs["params"]["cursor"])
        self.assertEqual(Decimal("2"), order.executed_amount_base)
        self.assertTrue(order.is_filled)

    async def test_a_valuation_from_before_a_snapshot_removal_does_not_reopen_the_position(self):
        await self.exchange._apply_positions([self.position_row("1", 5)], complete=False)
        # A complete REST snapshot no longer lists the position: it was closed.
        await self.exchange._apply_positions([], complete=True, changes_before=self.exchange._position_change_count)
        await self.exchange._apply_position_valuations([self.position_risk(qty="1", unrealized_pnl="3")
                                                        | {"lastTradeSequenceNumber": 5}])
        self.assertEqual({}, self.exchange.account_positions)

        # A newer trade reopens it.
        await self.exchange._apply_position_valuations([self.position_risk(qty="2", unrealized_pnl="3")
                                                        | {"lastTradeSequenceNumber": 6}])
        self.assertEqual(Decimal("2"), self.exchange.account_positions[self.trading_pair].amount)

    async def run_user_stream(self, *events: Dict[str, Any]):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [*events, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue
        with self.assertRaises(asyncio.CancelledError):
            await self.exchange._user_stream_event_listener()

    async def test_position_risk_frames_apply_only_valuations_that_include_the_latest_fill(self):
        row = {"exchangeId": 2, "symbol": self.symbol, "accountId": ACCOUNT_ID, "qty": "1", "side": "B",
               "avgEntryPrice": "100", "avgEntryFundingValue": "0", "lastTradeSequenceNumber": 1}
        positions = f"/v2/wallet/{WALLET}/positions"
        risk = f"/v2/wallet/{WALLET}/positionRisk"

        def risk_frame(account_id: int = ACCOUNT_ID, **kwargs) -> Dict[str, Any]:
            return {"type": "channel_data", "channel": risk, "accountId": account_id,
                    "data": [{**self.position_risk(account_id=account_id), **kwargs}]}

        await self.run_user_stream(
            {"type": "subscribed", "channel": positions, "contents": [row]},
            {"type": "subscribed", "channel": risk, "contents": {"data": [self.position_risk(unrealized_pnl="4")]}},
            risk_frame(account_id=99, unrealizedPnl="9"),
            # A fill arrives on the positions channel without valuation: the last PnL is kept.
            {"type": "channel_data", "channel": positions, "data": [{**row, "qty": "2", "lastTradeSequenceNumber": 2}]},
            # A valuation computed before that fill is skipped.
            risk_frame(unrealizedPnl="9", lastTradeSequenceNumber=1),
        )
        position = self.exchange.account_positions[self.trading_pair]
        self.assertEqual((Decimal("2"), Decimal("4")), (position.amount, position.unrealized_pnl))

        await self.run_user_stream(risk_frame(qty="2", unrealizedPnl="6", lastTradeSequenceNumber=2))
        position = self.exchange.account_positions[self.trading_pair]
        self.assertEqual((Decimal("2"), Decimal("6")), (position.amount, position.unrealized_pnl))

        # After a close, a valuation from before it does not reopen the position, and an empty
        # valuation frame removes nothing.
        await self.run_user_stream(
            {"type": "channel_data", "channel": positions, "data": [{**row, "qty": "0", "lastTradeSequenceNumber": 3}]},
            risk_frame(qty="2", unrealizedPnl="7", lastTradeSequenceNumber=2),
            {"type": "channel_data", "channel": risk, "accountId": ACCOUNT_ID, "data": []},
        )
        self.assertEqual({}, self.exchange.account_positions)

        # A valuation that includes a newer fill applies even before that fill's positions frame.
        await self.run_user_stream(risk_frame(qty="1", side="A", unrealizedPnl="1", lastTradeSequenceNumber=4))
        position = self.exchange.account_positions[self.trading_pair]
        self.assertEqual((PositionSide.SHORT, Decimal("-1"), Decimal("1")),
                         (position.position_side, position.amount, position.unrealized_pnl))

    async def test_position_snapshot_is_a_bare_array_and_a_zero_quantity_update_closes(self):
        row = {"exchangeId": 2, "symbol": self.symbol, "accountId": ACCOUNT_ID, "qty": "1", "side": "B",
               "avgEntryPrice": "100", "avgEntryFundingValue": "0", "lastTradeSequenceNumber": 1}
        channel = f"/v2/wallet/{WALLET}/positions"
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [
            {"type": "subscribed", "channel": channel, "contents": [row]},
            asyncio.CancelledError,
        ]
        self.exchange._user_stream_tracker._user_stream = mock_queue
        with self.assertRaises(asyncio.CancelledError):
            await self.exchange._user_stream_event_listener()
        self.assertEqual(Decimal("1"), self.exchange.account_positions[self.trading_pair].amount)

        mock_queue.get.side_effect = [{"type": "channel_data", "channel": channel, "data": [{**row, "qty": "0"}]},
                                      asyncio.CancelledError]
        with self.assertRaises(asyncio.CancelledError):
            await self.exchange._user_stream_event_listener()
        self.assertEqual({}, self.exchange.account_positions)
