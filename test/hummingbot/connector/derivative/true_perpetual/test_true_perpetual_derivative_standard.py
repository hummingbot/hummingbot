import asyncio
import json
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

import hummingbot.connector.derivative.true_perpetual.true_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.true_perpetual.true_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.derivative.true_perpetual.true_perpetual_derivative import TruePerpetualDerivative
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase

# 2021-12-29T12:13:20Z, the timestamp the generic tests set on the exchange
NOW = 1640780000
NOW_MS = NOW * 1000
COLLATERAL = "USDC"


def _regex(url: str) -> re.Pattern:
    return re.compile(f"^{re.escape(url)}")


class TruePerpetualDerivativeStandardTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):
    """
    Hummingbot's standardized perpetual connector tests run against the TRUE Bot API shapes.

    Three facts about TRUE shape the overrides at the end of the class: the account is margined in USDC only
    (there is no base asset balance), the account stream carries balances and positions but no order or fill
    events (orders and fills are polled over REST), and funding is settled into the position at the venue
    (there is no per payment feed).
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "tbk_0123456789abcdef"
        cls.api_secret = "tbs_secret_for_tests"

    # ---------------------------------------------------------------------------------------------------------
    # URLs

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(CONSTANTS.MARKETS_PATH_URL)

    @property
    def latest_prices_url(self):
        return _regex(web_utils.public_rest_url(CONSTANTS.TICKER_PATH_URL))

    @property
    def network_status_url(self):
        return web_utils.public_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)

    @property
    def trading_rules_url(self):
        return web_utils.public_rest_url(CONSTANTS.MARKETS_PATH_URL)

    @property
    def order_creation_url(self):
        return web_utils.private_rest_url(CONSTANTS.PLACE_ORDER_PATH_URL)

    @property
    def balance_url(self):
        return web_utils.private_rest_url(CONSTANTS.ACCOUNT_PATH_URL)

    @property
    def funding_info_url(self):
        return _regex(web_utils.public_rest_url(CONSTANTS.MARK_PATH_URL))

    @property
    def funding_payment_url(self):
        return ""  # no funding payment feed on the Bot API, see test_funding_payment_polling_loop_sends_update_event

    @property
    def fills_url(self) -> re.Pattern:
        return _regex(web_utils.private_rest_url(CONSTANTS.FILLS_PATH_URL))

    @property
    def leverage_url(self) -> str:
        return web_utils.private_rest_url(CONSTANTS.LEVERAGE_PATH_URL)

    def _order_url(self, order: InFlightOrder) -> re.Pattern:
        return _regex(web_utils.private_rest_url(web_utils.order_path(order.exchange_order_id)))

    # ---------------------------------------------------------------------------------------------------------
    # Mock responses (shaped after the live GET /api/bot/v1 payloads)

    def _market(self, symbol: str, base: str, quote: str = COLLATERAL, active: bool = True, **overrides) -> Dict[str, Any]:
        market = {
            "symbol": symbol, "base": base, "quote": quote, "status": "Normal", "active": active,
            "lotSize": "0.0001", "tickSize": "1", "minOrderNotionalUsd": 5, "maxOrderSize": "10",
            "maxPositionSize": "30", "maxLeverage": 50, "makerFeePct": 0.02, "takerFeePct": 0.065,
            "fundingRate8h": "0.0001", "priceBands": {"min": "38862", "max": "116586"}, "isNew": False,
        }
        market.update(overrides)
        return market

    @property
    def all_symbols_request_mock_response(self):
        return {"ok": True, "markets": [self._market(self.exchange_trading_pair, self.base_asset, self.quote_asset)]}

    @property
    def latest_prices_request_mock_response(self):
        return {"ok": True, "data": {"results": [
            {"symbol": self.exchange_trading_pair, "last_traded_price": str(self.expected_latest_price),
             "volume_24h": "1234.5", "price_change_24h": "0.5"},
            {"symbol": "ETHUSDC", "last_traded_price": None},
        ]}}

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = {"ok": True, "markets": [
            self._market(self.exchange_trading_pair, self.base_asset, self.quote_asset),
            self._market("INVALIDUSDC", "INVALID", active=False),
        ]}
        return "INVALID-USDC", response

    @property
    def network_status_request_successful_mock_response(self):
        return {"ok": True, "serverTime": NOW_MS}

    @property
    def trading_rules_request_mock_response(self):
        return {"ok": True, "markets": [self._market(
            self.exchange_trading_pair, self.base_asset, self.quote_asset,
            lotSize="0.001", tickSize="0.5", minOrderNotionalUsd="5", maxOrderSize="50",
        )]}

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return {"ok": True, "markets": [self._erroneous_market]}

    @property
    def _erroneous_market(self) -> Dict[str, Any]:
        # Active with a lot size, so it passes the validity check, then fails to parse as a number.
        return self._market(self.exchange_trading_pair, self.base_asset, self.quote_asset, lotSize="not-a-number")

    @property
    def order_creation_request_successful_mock_response(self):
        return {"ok": True, "order": {
            "id": self.expected_exchange_order_id, "market": self.exchange_trading_pair, "status": "open",
            "clientOrderId": "HBOTB1", "timestamp": NOW_MS,
        }}

    def _account_response(self, equity: str, free: str, positions: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        return {
            "ok": True,
            "accountKey": "5WYw1tt1WX5b4n965GaTQuvw8KuWU9HouePfgahuViGg",
            "account": {"equityUsd": equity, "freeCollateralUsd": free, "unrealizedPnlUsd": "0", "raw": {}},
            "balances": {}, "positionsOk": True, "positions": positions or [], "openOrders": [],
            "leverages": {self.exchange_trading_pair: 5}, "marginType": "cross",
        }

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        # Only USDC exists on a TRUE account: see the test_update_balances override
        return self._account_response(equity="2000", free="1500")

    @property
    def balance_request_mock_response_only_base(self):
        return self._account_response(equity="10", free="10")

    @property
    def balance_event_websocket_update(self):
        return {"event": "account", "data": {
            "account": {"equityUsd": "15", "freeCollateralUsd": "10", "unrealizedPnlUsd": "0"},
            "positionsOk": True, "positions": [],
        }}

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.5"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("5"),
            buy_order_collateral_token=COLLATERAL,
            sell_order_collateral_token=COLLATERAL,
            max_order_size=Decimal("50"),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        return f"Error parsing the trading rule for {self._erroneous_market}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "42599337"

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("10500")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=COLLATERAL,
            flat_fees=[TokenAmount(token=COLLATERAL, amount=Decimal("30"))],
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "177396390-1"

    @property
    def expected_supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    @property
    def funding_info_mock_response(self):
        return {"ok": True, "market": self.exchange_trading_pair, "mark": str(self.target_funding_info_mark_price),
                "ts": NOW_MS}

    @property
    def markets_for_funding_info_mock_response(self):
        return {"ok": True, "markets": [self._market(
            self.exchange_trading_pair, self.base_asset, self.quote_asset,
            fundingRate8h=str(self.target_funding_info_rate),
        )]}

    @property
    def empty_funding_payment_mock_response(self):
        return {}

    @property
    def funding_payment_mock_response(self):
        return {}

    # ---------------------------------------------------------------------------------------------------------
    # Exchange instance and request validation

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}{quote_token}"

    def create_exchange_instance(self):
        return TruePerpetualDerivative(
            true_perpetual_api_key=self.api_key,
            true_perpetual_api_secret=self.api_secret,
            trading_pairs=[self.trading_pair],
        )

    def validate_auth_credentials_present(self, request_call: RequestCall):
        headers = request_call.kwargs["headers"]
        self.assertEqual(self.api_key, headers["X-TRUE-KEY"])
        self.assertIn("X-TRUE-TS", headers)
        self.assertIn("X-TRUE-SIGN", headers)
        self.assertRegex(headers["X-TRUE-SIGN"], r"^[0-9a-f]{64}$")

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_trading_pair, request_data["market"])
        self.assertEqual("buy" if order.trade_type is TradeType.BUY else "sell", request_data["side"])
        self.assertEqual("limit", request_data["type"])
        self.assertEqual(order.amount, Decimal(request_data["size"]))
        self.assertEqual(order.price, Decimal(request_data["price"]))
        self.assertEqual(order.client_order_id, request_data["clientOrderId"])
        self.assertFalse(request_data["postOnly"])
        self.assertEqual(order.position is PositionAction.CLOSE, request_data["reduceOnly"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        # The order id travels in the path and the market in the query. The signer folds the query into the URL
        # before signing, so the recorded call carries neither a body nor separate params.
        self.assertIsNone(request_call.kwargs["data"])
        self.assertIsNone(request_call.kwargs["params"])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        self.assertIsNone(request_call.kwargs["params"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        self.assertIsNone(request_call.kwargs["params"])

    def _requested_urls(self, mock_api: aioresponses, url: re.Pattern) -> List[str]:
        return [key[1].human_repr() for key in mock_api.requests.keys() if url.search(key[1].human_repr())]

    # ---------------------------------------------------------------------------------------------------------
    # Order endpoints

    @staticmethod
    def _error_body(error: str, message: str = "") -> str:
        return json.dumps({"ok": False, "error": error, "message": message})

    def configure_successful_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> re.Pattern:
        url = self._order_url(order)
        mock_api.delete(url, body=json.dumps({"ok": True, "cancelled": order.exchange_order_id}), callback=callback)
        return url

    def configure_erroneous_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> re.Pattern:
        url = self._order_url(order)
        mock_api.delete(url, status=400, body=self._error_body("venue_refused", "cancel refused"), callback=callback)
        return url

    def configure_order_not_found_error_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> re.Pattern:
        url = self._order_url(order)
        mock_api.delete(url, status=404, body=self._error_body(CONSTANTS.ORDER_NOT_FOUND_ERROR, "not on this account"),
                        callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
            self, successful_order: InFlightOrder, erroneous_order: InFlightOrder, mock_api: aioresponses
    ) -> List[re.Pattern]:
        return [
            self.configure_successful_cancelation_response(order=successful_order, mock_api=mock_api),
            self.configure_erroneous_cancelation_response(order=erroneous_order, mock_api=mock_api),
        ]

    def _order_status_response(self, order: InFlightOrder, status: str, filled: Decimal) -> Dict[str, Any]:
        return {"ok": True, "order": {
            "id": order.exchange_order_id, "market": self.exchange_trading_pair,
            "side": "buy" if order.trade_type is TradeType.BUY else "sell", "type": "limit",
            "price": str(order.price), "size": str(order.amount), "filledSize": str(filled),
            "remainingSize": str(order.amount - filled), "status": status, "clientOrderId": order.client_order_id,
            "timestamp": NOW_MS,
        }}

    def _configure_order_status_response(self, order: InFlightOrder, mock_api: aioresponses, callback: Callable,
                                         status: str, filled: Decimal) -> re.Pattern:
        url = self._order_url(order)
        mock_api.get(url, body=json.dumps(self._order_status_response(order, status, filled)), callback=callback)
        return url

    def configure_completely_filled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> re.Pattern:
        return self._configure_order_status_response(order, mock_api, callback, "filled", order.amount)

    def configure_canceled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> re.Pattern:
        return self._configure_order_status_response(order, mock_api, callback, "cancelled", Decimal("0"))

    def configure_open_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> re.Pattern:
        return self._configure_order_status_response(order, mock_api, callback, "open", Decimal("0"))

    def configure_http_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> re.Pattern:
        url = self._order_url(order)
        mock_api.get(url, status=500, body=self._error_body("venue_error", "upstream unavailable"), callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> re.Pattern:
        return self._configure_order_status_response(
            order, mock_api, callback, "partially_filled", self.expected_partial_fill_amount)

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[re.Pattern]:
        url = self._order_url(order)
        mock_api.get(url, status=404, body=self._error_body(CONSTANTS.ORDER_NOT_FOUND_ERROR, "not on this account"),
                     callback=callback)
        return [url]

    def _fill(self, order: InFlightOrder, fill_id: str, price: Decimal, size: Decimal, fee: str = "30",
              created_at: int = NOW_MS) -> Dict[str, Any]:
        return {
            "id": fill_id, "order_id": order.exchange_order_id, "market": self.exchange_trading_pair,
            "side": "buy" if order.trade_type is TradeType.BUY else "sell", "price": str(price), "size": str(size),
            "fee": fee, "fee_currency": COLLATERAL, "liquidity": "maker", "created_at": created_at,
        }

    def _fills_page(self, fills: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"ok": True, "page": {"next": None, "results": fills}}

    def configure_partial_fill_trade_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> re.Pattern:
        fill = self._fill(order, self.expected_fill_trade_id, self.expected_partial_fill_price,
                          self.expected_partial_fill_amount)
        mock_api.get(self.fills_url, body=json.dumps(self._fills_page([fill])), callback=callback)
        return self.fills_url

    def configure_erroneous_http_fill_trade_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> re.Pattern:
        mock_api.get(self.fills_url, status=400, body=self._error_body("bad_request", "invalid"), callback=callback)
        return self.fills_url

    def configure_full_fill_trade_response(
            self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> re.Pattern:
        fill = self._fill(order, self.expected_fill_trade_id, order.price, order.amount)
        mock_api.get(self.fills_url, body=json.dumps(self._fills_page([fill])), callback=callback)
        return self.fills_url

    # ---------------------------------------------------------------------------------------------------------
    # Account stream messages. The stream carries balances and positions only; orders and fills are polled.

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return None

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return None

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return None

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return None

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        size = order.amount if order.trade_type is TradeType.BUY else -order.amount
        return {"event": "account", "data": {
            "account": {"equityUsd": "2000", "freeCollateralUsd": "1500", "unrealizedPnlUsd": str(unrealized_pnl)},
            "positionsOk": True,
            "positions": [{
                "market": self.exchange_trading_pair, "size": str(size), "entry_price": str(order.price),
                "unrealized_pnl": str(unrealized_pnl), "leverage": str(self.exchange.get_leverage(self.trading_pair)),
            }],
        }}

    def funding_info_event_for_websocket_update(self):
        return {"topic": f"mark:{self.exchange_trading_pair}", "type": "update", "ts": NOW_MS, "data": {
            "market": self.exchange_trading_pair, "mark_price": str(self.target_funding_info_mark_price_ws_updated),
        }}

    # ---------------------------------------------------------------------------------------------------------
    # Leverage and position mode

    def configure_successful_set_position_mode(self, position_mode: PositionMode, mock_api: aioresponses,
                                               callback: Optional[Callable] = lambda *args, **kwargs: None):
        return ""  # one position per market, no endpoint to call

    def configure_failed_set_position_mode(self, position_mode: PositionMode, mock_api: aioresponses,
                                           callback: Optional[Callable] = lambda *args, **kwargs: None
                                           ) -> Tuple[str, str]:
        return "", "TRUE perps run one position per market (ONEWAY); hedge mode is not available."

    def configure_successful_set_leverage(self, leverage: int, mock_api: aioresponses,
                                          callback: Optional[Callable] = lambda *args, **kwargs: None):
        url = self.leverage_url
        mock_api.post(url, body=json.dumps({"ok": True, "market": self.exchange_trading_pair, "leverage": leverage}),
                      callback=callback)
        return url

    def configure_failed_set_leverage(self, leverage: int, mock_api: aioresponses,
                                      callback: Optional[Callable] = lambda *args, **kwargs: None) -> Tuple[str, str]:
        url = self.leverage_url
        mock_api.post(url, status=400, body=json.dumps({
            "ok": False, "error": "leverage_out_of_range", "message": "Leverage must be between 1 and 50.",
            "maxLeverage": 50,
        }), callback=callback)
        return url, f"leverage_out_of_range Leverage must be between 1 and 50. (max 50x on {self.exchange_trading_pair})"

    # ---------------------------------------------------------------------------------------------------------
    # Generic tests overridden for TRUE

    def test_get_buy_and_sell_collateral_tokens(self):
        self._simulate_trading_rules_initialized()
        self.assertEqual(COLLATERAL, self.exchange.get_buy_collateral_token(self.trading_pair))
        self.assertEqual(COLLATERAL, self.exchange.get_sell_collateral_token(self.trading_pair))

    @aioresponses()
    async def test_update_balances(self, mock_api):
        # Only USDC exists: equity is the total, free collateral the available amount. Positions ride along.
        response = self._account_response(equity="2000", free="1500", positions=[{
            "market": self.exchange_trading_pair, "size": "0.5", "entry_price": "10000",
            "unrealized_pnl": "12.5", "leverage": "5",
        }])
        self._configure_balance_response(response=response, mock_api=mock_api)

        await self.exchange._update_balances()

        self.assertEqual({COLLATERAL: Decimal("2000")}, self.exchange.get_all_balances())
        self.assertEqual({COLLATERAL: Decimal("1500")}, dict(self.exchange.available_balances))
        position: Position = self.exchange.account_positions[self.trading_pair]
        self.assertEqual(PositionSide.LONG, position.position_side)
        self.assertEqual(Decimal("0.5"), position.amount)
        self.assertEqual(Decimal("10000"), position.entry_price)
        self.assertEqual(Decimal("12.5"), position.unrealized_pnl)
        self.assertEqual(Decimal("5"), position.leverage)

        self._configure_balance_response(response=self.balance_request_mock_response_only_base, mock_api=mock_api)
        await self.exchange._update_balances()

        self.assertEqual({COLLATERAL: Decimal("10")}, self.exchange.get_all_balances())
        self.assertEqual({COLLATERAL: Decimal("10")}, dict(self.exchange.available_balances))
        self.assertEqual(0, len(self.exchange.account_positions))

    async def test_user_stream_balance_update(self):
        self.exchange._set_current_timestamp(NOW)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self.balance_event_websocket_update, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            await self.exchange._user_stream_event_listener()
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10"), self.exchange.available_balances[COLLATERAL])
        self.assertEqual(Decimal("15"), self.exchange.get_balance(COLLATERAL))

    async def test_user_stream_update_for_new_order(self):
        # No order events on the account stream: an account snapshot leaves a tracked order exactly as it was.
        self.exchange._set_current_timestamp(NOW)
        order = self._track_order(trade_type=TradeType.BUY)
        await self._feed_user_stream([self.balance_event_websocket_update])

        self.assertTrue(order.is_open)
        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertEqual(0, len(self.buy_order_created_logger.event_log))

    async def test_user_stream_update_for_canceled_order(self):
        # Cancels are confirmed by the DELETE answer and the status poll, never by the stream.
        self.exchange._set_current_timestamp(NOW)
        order = self._track_order(trade_type=TradeType.BUY)
        await self._feed_user_stream([self.balance_event_websocket_update])

        self.assertFalse(order.is_cancelled)
        self.assertTrue(order.is_open)
        self.assertEqual(0, len(self.order_cancelled_logger.event_log))

    async def test_user_stream_update_for_order_full_fill(self):
        # Fills are polled from GET /fills (covered by the order status tests). The stream moves the position.
        self.exchange._set_current_timestamp(NOW)
        leverage = 2
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        order = self._track_order(trade_type=TradeType.SELL, position_action=PositionAction.OPEN)
        expected_unrealized_pnl = 12
        await self._feed_user_stream([
            self.position_event_for_full_fill_websocket_update(order=order, unrealized_pnl=expected_unrealized_pnl),
        ])

        self.assertTrue(order.is_open)
        self.assertEqual(0, len(self.order_filled_logger.event_log))
        self.assertEqual(1, len(self.exchange.account_positions))
        position: Position = self.exchange.account_positions[self.trading_pair]
        self.assertEqual(self.trading_pair, position.trading_pair)
        self.assertEqual(PositionSide.SHORT, position.position_side)
        self.assertEqual(Decimal(str(expected_unrealized_pnl)), position.unrealized_pnl)
        self.assertEqual(order.price, position.entry_price)
        self.assertEqual(-order.amount, position.amount)
        self.assertEqual(Decimal(str(leverage)), position.leverage)
        self.assertEqual(Decimal("2000"), self.exchange.get_balance(COLLATERAL))
        self.assertEqual(Decimal("1500"), self.exchange.available_balances[COLLATERAL])

    async def test_user_stream_position_closed_removes_it(self):
        self.exchange._set_current_timestamp(NOW)
        order = self._track_order(trade_type=TradeType.BUY, position_action=PositionAction.OPEN)
        await self._feed_user_stream([self.position_event_for_full_fill_websocket_update(order=order, unrealized_pnl=1)])
        self.assertEqual(1, len(self.exchange.account_positions))

        closed = self.position_event_for_full_fill_websocket_update(order=order, unrealized_pnl=0)
        closed["data"]["positions"][0]["size"] = "0"
        await self._feed_user_stream([closed])

        self.assertEqual(0, len(self.exchange.account_positions))

    async def test_lost_order_removed_after_cancel_status_user_event_received(self):
        # The stream carries no order events, so a lost order is settled by the status poll instead.
        await self._lost_order_resolved_by_rest(status="cancelled", filled=Decimal("0"))

    @aioresponses()
    async def test_lost_order_user_stream_full_fill_events_are_processed(self, mock_api):
        # Same as above for a lost order that turns out filled: the fill arrives from GET /fills on the next poll.
        self.exchange._set_current_timestamp(NOW)
        order = self._track_order(trade_type=TradeType.BUY)
        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            await self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        self.configure_full_fill_trade_response(order=order, mock_api=mock_api)
        self.configure_completely_filled_order_status_response(order=order, mock_api=mock_api)

        await self.exchange._update_lost_orders_status()
        await order.wait_until_completely_filled()
        await asyncio.sleep(0.1)

        fill_event = self.order_filled_logger.event_log[0]
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount)
        self.assertEqual(self.expected_fill_fee, fill_event.trade_fee)
        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_failure)

    def test_set_position_mode_success(self):
        success, message = self.async_run_with_timeout(
            self.exchange._trading_pair_position_mode_set(PositionMode.ONEWAY, self.trading_pair))

        self.assertTrue(success)
        self.assertEqual("", message)

    def test_set_position_mode_failure(self):
        success, message = self.async_run_with_timeout(
            self.exchange._trading_pair_position_mode_set(PositionMode.HEDGE, self.trading_pair))
        self.exchange.set_position_mode(PositionMode.HEDGE)

        self.assertFalse(success)
        self.assertEqual("TRUE perps run one position per market (ONEWAY); hedge mode is not available.", message)
        self.assertTrue(self.is_logged("ERROR", f"Position mode {PositionMode.HEDGE} is not supported. Mode not set."))

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_initializes_funding_info(self, mock_api, mock_queue_get):
        # The funding snapshot is two reads: GET /markets for the 8h rate and GET /mark for the mark price.
        # TRUE publishes one price, the mark, so the index price is the mark price.
        mock_api.get(self.trading_rules_url, body=json.dumps(self.markets_for_funding_info_mock_response))
        mock_api.get(self.funding_info_url, body=json.dumps(self.funding_info_mock_response))
        mock_queue_get.side_effect = [asyncio.CancelledError]

        try:
            self.async_run_with_timeout(self.exchange._listen_for_funding_info())
        except asyncio.CancelledError:
            pass

        funding_info = self.exchange.get_funding_info(self.trading_pair)
        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(self.target_funding_info_mark_price, funding_info.index_price)
        self.assertEqual(self.target_funding_info_mark_price, funding_info.mark_price)
        self.assertEqual(self.target_funding_info_rate, funding_info.rate)
        self.assertEqual(0, funding_info.next_funding_utc_timestamp % CONSTANTS.FUNDING_INTERVAL_SECONDS)

    @aioresponses()
    @patch("asyncio.Queue.get")
    def test_listen_for_funding_info_update_updates_funding_info(self, mock_api, mock_queue_get):
        mock_api.get(self.trading_rules_url, body=json.dumps(self.markets_for_funding_info_mock_response), repeat=True)
        mock_api.get(self.funding_info_url, body=json.dumps(self.funding_info_mock_response))
        mock_queue_get.side_effect = [self.funding_info_event_for_websocket_update(), asyncio.CancelledError]

        try:
            self.async_run_with_timeout(self.exchange._listen_for_funding_info())
        except asyncio.CancelledError:
            pass

        self.assertEqual(1, self.exchange._perpetual_trading.funding_info_stream.qsize())
        update = self.exchange._perpetual_trading.funding_info_stream.get_nowait()
        self.assertEqual(self.target_funding_info_mark_price_ws_updated, update.mark_price)
        self.assertEqual(self.target_funding_info_mark_price_ws_updated, update.index_price)
        self.assertEqual(self.target_funding_info_rate, update.rate)

    async def test_funding_payment_polling_loop_sends_update_event(self):
        # Funding is settled into the position's realized P&L at the venue; the Bot API has no payment feed,
        # so the connector reports no payment and never emits a FundingPaymentCompleted event.
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(NOW)

        timestamp, rate, amount = await self.exchange._fetch_last_fee_payment(self.trading_pair)
        self.assertEqual((0, Decimal("-1"), Decimal("-1")), (timestamp, rate, amount))

        fetched = await self.exchange._update_funding_payment(self.trading_pair, fire_event_on_new=True)
        self.assertTrue(fetched)
        self.assertEqual(0, len(self.funding_payment_logger.event_log))

    @aioresponses()
    async def test_market_and_page_size_travel_in_the_signed_query(self, mock_api):
        self.exchange._set_current_timestamp(NOW)
        order = self._track_order(trade_type=TradeType.BUY)
        self.configure_full_fill_trade_response(order=order, mock_api=mock_api)
        self.configure_open_order_status_response(order=order, mock_api=mock_api)

        await self.exchange._update_order_status()

        fills_url = self._requested_urls(mock_api, self.fills_url)[0]
        self.assertIn(f"market={self.exchange_trading_pair}", fills_url)
        self.assertIn(f"limit={TruePerpetualDerivative.FILLS_PAGE_SIZE}", fills_url)
        status_url = self._requested_urls(mock_api, self._order_url(order))[0]
        self.assertIn(f"/orders/{order.exchange_order_id}?market={self.exchange_trading_pair}", status_url)

    # ---------------------------------------------------------------------------------------------------------
    # Helpers

    def _track_order(self, trade_type: TradeType, position_action: PositionAction = PositionAction.NIL) -> InFlightOrder:
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=trade_type,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=position_action,
        )
        return self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

    async def _feed_user_stream(self, events: List[Any]):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [*events, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue
        try:
            await self.exchange._user_stream_event_listener()
        except asyncio.CancelledError:
            pass
        await asyncio.sleep(0.1)

    async def _lost_order_resolved_by_rest(self, status: str, filled: Decimal):
        with aioresponses() as mock_api:
            self.exchange._set_current_timestamp(NOW)
            order = self._track_order(trade_type=TradeType.BUY)
            for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
                await self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id)
            self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

            mock_api.get(self.fills_url, body=json.dumps(self._fills_page([])))
            self._configure_order_status_response(order, mock_api, lambda *args, **kwargs: None, status, filled)

            await self.exchange._update_lost_orders_status()
            await asyncio.sleep(0.1)

            self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
            self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
            self.assertEqual(0, len(self.order_cancelled_logger.event_log))
            self.assertFalse(order.is_cancelled)
            self.assertTrue(order.is_failure)
