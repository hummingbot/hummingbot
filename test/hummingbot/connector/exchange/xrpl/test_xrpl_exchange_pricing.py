"""
Chunk 9 – Pricing, AMM pool, start_network, _get_fee, and misc coverage
for XrplExchange.

Covers:
  - _get_fee  (stub TODO)
  - _get_last_traded_price
  - _get_best_price
  - get_price_from_amm_pool
  - start_network
  - _initialize_trading_pair_symbol_map
  - _make_network_check_request
  - _execute_order_cancel_and_process_update (uncovered branches)
"""

import asyncio
import unittest
from decimal import Decimal
from test.hummingbot.connector.exchange.xrpl.test_xrpl_exchange_base import XRPLExchangeTestBase
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from xrpl.models import Response
from xrpl.models.response import ResponseStatus

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange
from hummingbot.connector.exchange.xrpl.xrpl_worker_pool import TransactionSubmitResult, TransactionVerifyResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OUR_ACCOUNT = "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK"
EXCHANGE_ORDER_ID = "84437895-88954510-ABCDE12345"


def _make_order(
    connector: XrplExchange,
    *,
    client_order_id: str = "hbot-1",
    exchange_order_id: str = EXCHANGE_ORDER_ID,
    trading_pair: str = "SOLO-XRP",
    order_type: OrderType = OrderType.LIMIT,
    trade_type: TradeType = TradeType.BUY,
    amount: Decimal = Decimal("100"),
    price: Decimal = Decimal("0.5"),
    state: OrderState = OrderState.OPEN,
) -> InFlightOrder:
    order = InFlightOrder(
        client_order_id=client_order_id,
        exchange_order_id=exchange_order_id,
        trading_pair=trading_pair,
        order_type=order_type,
        trade_type=trade_type,
        amount=amount,
        price=price,
        creation_timestamp=1,
        initial_state=state,
    )
    connector._order_tracker.start_tracking_order(order)
    return order


# ======================================================================
# Test: _get_fee
# ======================================================================
class TestGetFee(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):

    async def test_get_fee_returns_added_to_cost_fee(self):
        fee = self.connector._get_fee(
            base_currency="SOLO",
            quote_currency="XRP",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("100"),
            price=Decimal("0.5"),
        )
        self.assertIsInstance(fee, AddedToCostTradeFee)

    async def test_get_fee_limit_maker(self):
        fee = self.connector._get_fee(
            base_currency="SOLO",
            quote_currency="XRP",
            order_type=OrderType.LIMIT_MAKER,
            order_side=TradeType.SELL,
            amount=Decimal("50"),
            price=Decimal("1.0"),
            is_maker=True,
        )
        self.assertIsInstance(fee, AddedToCostTradeFee)


# ======================================================================
# Test: get_price_from_amm_pool
# ======================================================================
class TestGetPriceFromAmmPool(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_returns_price_with_xrp_amounts(self, _):
        """When both amounts are XRP (string drops), calculates price correctly."""
        amm_response = Response(
            status=ResponseStatus.SUCCESS,
            result={
                "amm": {
                    "account": "rAMMaccount123",
                    "amount": "1000000000",   # 1000 XRP in drops
                    "amount2": "500000000",    # 500 XRP in drops
                }
            },
        )
        account_tx_response = Response(
            status=ResponseStatus.SUCCESS,
            result={
                "transactions": [
                    {"tx_json": {"date": 784444800}}
                ]
            },
        )

        call_count = 0

        async def _mock_query(request, priority=None, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return amm_response
            return account_tx_response

        self.connector._query_xrpl = AsyncMock(side_effect=_mock_query)

        price, ts = await self.connector.get_price_from_amm_pool("SOLO-XRP")
        self.assertAlmostEqual(price, 0.5, places=5)
        self.assertGreater(ts, 0)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_returns_price_with_issued_currency_amounts(self, _):
        """When amounts are issued currencies (dicts), calculates price correctly."""
        amm_response = Response(
            status=ResponseStatus.SUCCESS,
            result={
                "amm": {
                    "account": "rAMMaccount123",
                    "amount": {"currency": "SOLO", "issuer": "rSolo...", "value": "2000"},
                    "amount2": {"currency": "USD", "issuer": "rHub...", "value": "1000"},
                }
            },
        )
        account_tx_response = Response(
            status=ResponseStatus.SUCCESS,
            result={
                "transactions": [
                    {"tx_json": {"date": 784444800}}
                ]
            },
        )

        call_count = 0

        async def _mock_query(request, priority=None, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return amm_response
            return account_tx_response

        self.connector._query_xrpl = AsyncMock(side_effect=_mock_query)

        price, ts = await self.connector.get_price_from_amm_pool("SOLO-XRP")
        self.assertAlmostEqual(price, 0.5, places=5)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_returns_zero_when_amm_pool_not_found(self, _):
        """When amm_pool_info is None, returns (0, 0)."""
        amm_response = Response(
            status=ResponseStatus.SUCCESS,
            result={},  # no "amm" key
        )
        self.connector._query_xrpl = AsyncMock(return_value=amm_response)

        price, ts = await self.connector.get_price_from_amm_pool("SOLO-XRP")
        self.assertEqual(price, 0.0)
        self.assertEqual(ts, 0)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_returns_zero_when_amounts_none(self, _):
        """When amount or amount2 is None, returns (0, 0)."""
        amm_response = Response(
            status=ResponseStatus.SUCCESS,
            result={
                "amm": {
                    "account": "rAMMaccount123",
                    "amount": None,
                    "amount2": None,
                }
            },
        )
        account_tx_response = Response(
            status=ResponseStatus.SUCCESS,
            result={"transactions": [{"tx_json": {"date": 784444800}}]},
        )

        call_count = 0

        async def _mock_query(request, priority=None, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return amm_response
            return account_tx_response

        self.connector._query_xrpl = AsyncMock(side_effect=_mock_query)

        price, ts = await self.connector.get_price_from_amm_pool("SOLO-XRP")
        self.assertEqual(price, 0.0)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_returns_zero_when_base_amount_zero(self, _):
        """When base amount is zero, price can't be calculated."""
        amm_response = Response(
            status=ResponseStatus.SUCCESS,
            result={
                "amm": {
                    "account": "rAMMaccount123",
                    "amount": "0",  # 0 drops
                    "amount2": "500000000",
                }
            },
        )
        account_tx_response = Response(
            status=ResponseStatus.SUCCESS,
            result={"transactions": [{"tx_json": {"date": 784444800}}]},
        )

        call_count = 0

        async def _mock_query(request, priority=None, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return amm_response
            return account_tx_response

        self.connector._query_xrpl = AsyncMock(side_effect=_mock_query)

        price, ts = await self.connector.get_price_from_amm_pool("SOLO-XRP")
        self.assertEqual(price, 0.0)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_exception_fetching_amm_info_returns_zero(self, _):
        """When _query_xrpl raises, returns (0, 0)."""
        self.connector._query_xrpl = AsyncMock(side_effect=Exception("connection error"))

        price, ts = await self.connector.get_price_from_amm_pool("SOLO-XRP")
        self.assertEqual(price, 0.0)
        self.assertEqual(ts, 0)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_exception_fetching_account_tx_returns_zero(self, _):
        """When fetching AccountTx raises, returns (price=0, tx_timestamp=0)."""
        amm_response = Response(
            status=ResponseStatus.SUCCESS,
            result={
                "amm": {
                    "account": "rAMMaccount123",
                    "amount": "1000000000",
                    "amount2": "500000000",
                }
            },
        )

        call_count = 0

        async def _mock_query(request, priority=None, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return amm_response
            raise Exception("account tx error")

        self.connector._query_xrpl = AsyncMock(side_effect=_mock_query)

        price, ts = await self.connector.get_price_from_amm_pool("SOLO-XRP")
        self.assertEqual(price, 0.0)
        self.assertEqual(ts, 0)


# ======================================================================
# Test: _get_last_traded_price
# ======================================================================
class TestGetLastTradedPrice(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):

    def _set_order_books(self, ob_dict):
        """Set mock order books by patching the tracker's internal dict."""
        self.connector.order_book_tracker._order_books = ob_dict

    async def test_returns_order_book_last_trade_price(self):
        """When order book has a valid last_trade_price, returns it."""
        mock_ob = MagicMock()
        mock_ob.last_trade_price = 1.5
        self._set_order_books({"SOLO-XRP": mock_ob})

        mock_data_source = MagicMock()
        mock_data_source.last_parsed_order_book_timestamp = {"SOLO-XRP": 100}

        with patch.object(self.connector.order_book_tracker, "_data_source", mock_data_source), \
             patch.object(self.connector, "get_price_from_amm_pool", new_callable=AsyncMock, return_value=(float("nan"), 0)):
            price = await self.connector._get_last_traded_price("SOLO-XRP")
            self.assertAlmostEqual(price, 1.5, places=5)

    async def test_falls_back_to_mid_price_when_last_trade_is_zero(self):
        """When last_trade_price is 0, uses mid of bid/ask."""
        mock_ob = MagicMock()
        mock_ob.last_trade_price = 0.0
        mock_ob.get_price = MagicMock(side_effect=lambda is_buy: 1.0 if is_buy else 2.0)
        self._set_order_books({"SOLO-XRP": mock_ob})

        mock_data_source = MagicMock()
        mock_data_source.last_parsed_order_book_timestamp = {"SOLO-XRP": 100}

        with patch.object(self.connector.order_book_tracker, "_data_source", mock_data_source), \
             patch.object(self.connector, "get_price_from_amm_pool", new_callable=AsyncMock, return_value=(float("nan"), 0)):
            price = await self.connector._get_last_traded_price("SOLO-XRP")
            self.assertAlmostEqual(price, 1.5, places=5)

    async def test_falls_back_to_zero_when_no_valid_bid_ask(self):
        """When bid/ask are NaN, falls back to zero."""
        mock_ob = MagicMock()
        mock_ob.last_trade_price = 0.0
        mock_ob.get_price = MagicMock(return_value=float("nan"))
        self._set_order_books({"SOLO-XRP": mock_ob})

        mock_data_source = MagicMock()
        mock_data_source.last_parsed_order_book_timestamp = {"SOLO-XRP": 100}

        with patch.object(self.connector.order_book_tracker, "_data_source", mock_data_source), \
             patch.object(self.connector, "get_price_from_amm_pool", new_callable=AsyncMock, return_value=(float("nan"), 0)):
            price = await self.connector._get_last_traded_price("SOLO-XRP")
            self.assertEqual(price, 0.0)

    async def test_prefers_amm_pool_price_when_more_recent(self):
        """When AMM pool price has a more recent timestamp, uses it."""
        mock_ob = MagicMock()
        mock_ob.last_trade_price = 1.5
        self._set_order_books({"SOLO-XRP": mock_ob})

        mock_data_source = MagicMock()
        mock_data_source.last_parsed_order_book_timestamp = {"SOLO-XRP": 100}

        with patch.object(self.connector.order_book_tracker, "_data_source", mock_data_source), \
             patch.object(self.connector, "get_price_from_amm_pool", new_callable=AsyncMock, return_value=(2.0, 200)):
            price = await self.connector._get_last_traded_price("SOLO-XRP")
            self.assertAlmostEqual(price, 2.0, places=5)

    async def test_uses_order_book_when_amm_pool_older(self):
        """When order book timestamp is more recent, uses it."""
        mock_ob = MagicMock()
        mock_ob.last_trade_price = 1.5
        self._set_order_books({"SOLO-XRP": mock_ob})

        mock_data_source = MagicMock()
        mock_data_source.last_parsed_order_book_timestamp = {"SOLO-XRP": 300}

        with patch.object(self.connector.order_book_tracker, "_data_source", mock_data_source), \
             patch.object(self.connector, "get_price_from_amm_pool", new_callable=AsyncMock, return_value=(2.0, 200)):
            price = await self.connector._get_last_traded_price("SOLO-XRP")
            self.assertAlmostEqual(price, 1.5, places=5)

    async def test_returns_zero_when_no_order_book(self):
        """When no order book exists, falls back to AMM pool."""
        self._set_order_books({})

        with patch.object(self.connector, "get_price_from_amm_pool", new_callable=AsyncMock, return_value=(3.0, 100)):
            price = await self.connector._get_last_traded_price("SOLO-XRP")
            self.assertAlmostEqual(price, 3.0, places=5)

    async def test_returns_amm_price_when_last_trade_nan(self):
        """When order book last_trade_price is NaN, uses AMM pool."""
        mock_ob = MagicMock()
        mock_ob.last_trade_price = float("nan")
        self._set_order_books({"SOLO-XRP": mock_ob})

        mock_data_source = MagicMock()
        mock_data_source.last_parsed_order_book_timestamp = {"SOLO-XRP": 100}

        with patch.object(self.connector.order_book_tracker, "_data_source", mock_data_source), \
             patch.object(self.connector, "get_price_from_amm_pool", new_callable=AsyncMock, return_value=(2.5, 200)):
            price = await self.connector._get_last_traded_price("SOLO-XRP")
            self.assertAlmostEqual(price, 2.5, places=5)

    async def test_returns_amm_price_when_order_book_zero_and_no_valid_bids(self):
        """When order book price is 0 and bids/asks invalid, uses AMM pool if available."""
        mock_ob = MagicMock()
        mock_ob.last_trade_price = 0.0
        mock_ob.get_price = MagicMock(return_value=float("nan"))
        self._set_order_books({"SOLO-XRP": mock_ob})

        mock_data_source = MagicMock()
        mock_data_source.last_parsed_order_book_timestamp = {"SOLO-XRP": 50}

        with patch.object(self.connector.order_book_tracker, "_data_source", mock_data_source), \
             patch.object(self.connector, "get_price_from_amm_pool", new_callable=AsyncMock, return_value=(4.0, 200)):
            price = await self.connector._get_last_traded_price("SOLO-XRP")
            self.assertAlmostEqual(price, 4.0, places=5)


# ======================================================================
# Test: _get_best_price
# ======================================================================
class TestGetBestPrice(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):

    def _set_order_books(self, ob_dict):
        """Set mock order books by patching the tracker's internal dict (Cython-safe)."""
        self.connector.order_book_tracker._order_books = ob_dict

    async def test_returns_order_book_best_bid(self):
        mock_ob = MagicMock()
        mock_ob.get_price = MagicMock(return_value=1.5)
        self._set_order_books({"SOLO-XRP": mock_ob})

        with patch.object(self.connector, "get_price_from_amm_pool", new_callable=AsyncMock, return_value=(float("nan"), 0)):
            price = await self.connector._get_best_price("SOLO-XRP", is_buy=True)
            self.assertAlmostEqual(price, 1.5, places=5)

    async def test_buy_prefers_lower_amm_price(self):
        """For buy, lower price is better."""
        mock_ob = MagicMock()
        mock_ob.get_price = MagicMock(return_value=2.0)
        self._set_order_books({"SOLO-XRP": mock_ob})

        with patch.object(self.connector, "get_price_from_amm_pool", new_callable=AsyncMock, return_value=(1.5, 100)):
            price = await self.connector._get_best_price("SOLO-XRP", is_buy=True)
            self.assertAlmostEqual(price, 1.5, places=5)

    async def test_sell_prefers_higher_amm_price(self):
        """For sell, higher price is better."""
        mock_ob = MagicMock()
        mock_ob.get_price = MagicMock(return_value=1.5)
        self._set_order_books({"SOLO-XRP": mock_ob})

        with patch.object(self.connector, "get_price_from_amm_pool", new_callable=AsyncMock, return_value=(2.0, 100)):
            price = await self.connector._get_best_price("SOLO-XRP", is_buy=False)
            self.assertAlmostEqual(price, 2.0, places=5)

    async def test_returns_amm_price_when_no_order_book(self):
        """When no order book, best_price starts at 0. For sell, max(0, amm) = amm."""
        self._set_order_books({})

        with patch.object(self.connector, "get_price_from_amm_pool", new_callable=AsyncMock, return_value=(3.0, 100)):
            price = await self.connector._get_best_price("SOLO-XRP", is_buy=False)
            self.assertAlmostEqual(price, 3.0, places=5)

    async def test_buy_uses_ob_when_amm_nan(self):
        mock_ob = MagicMock()
        mock_ob.get_price = MagicMock(return_value=1.8)
        self._set_order_books({"SOLO-XRP": mock_ob})

        with patch.object(self.connector, "get_price_from_amm_pool", new_callable=AsyncMock, return_value=(float("nan"), 0)):
            price = await self.connector._get_best_price("SOLO-XRP", is_buy=True)
            self.assertAlmostEqual(price, 1.8, places=5)

    async def test_sell_uses_amm_when_ob_nan(self):
        """When order book price is NaN, uses AMM price for sell."""
        mock_ob = MagicMock()
        mock_ob.get_price = MagicMock(return_value=float("nan"))
        self._set_order_books({"SOLO-XRP": mock_ob})

        with patch.object(self.connector, "get_price_from_amm_pool", new_callable=AsyncMock, return_value=(2.0, 100)):
            price = await self.connector._get_best_price("SOLO-XRP", is_buy=False)
            self.assertAlmostEqual(price, 2.0, places=5)

    async def test_buy_uses_amm_when_ob_nan(self):
        """When order book price is NaN, uses AMM price for buy."""
        mock_ob = MagicMock()
        mock_ob.get_price = MagicMock(return_value=float("nan"))
        self._set_order_books({"SOLO-XRP": mock_ob})

        with patch.object(self.connector, "get_price_from_amm_pool", new_callable=AsyncMock, return_value=(1.5, 100)):
            price = await self.connector._get_best_price("SOLO-XRP", is_buy=True)
            self.assertAlmostEqual(price, 1.5, places=5)


# ======================================================================
# Test: start_network
# ======================================================================
class TestStartNetwork(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):

    def _setup_start_network_mocks(self, healthy_side_effect=None, healthy_return=None):
        """Common setup for start_network tests."""
        mock_node_pool = MagicMock()
        if healthy_side_effect is not None:
            type(mock_node_pool).healthy_connection_count = PropertyMock(side_effect=healthy_side_effect)
        else:
            type(mock_node_pool).healthy_connection_count = PropertyMock(return_value=healthy_return or 0)
        mock_node_pool.start = AsyncMock()
        mock_node_pool._check_all_connections = AsyncMock()

        mock_worker_manager = MagicMock()
        mock_worker_manager.start = AsyncMock()

        mock_user_stream_ds = MagicMock()
        mock_user_stream_ds._initialize_ledger_index = AsyncMock()

        self.connector._node_pool = mock_node_pool
        self.connector._worker_manager = mock_worker_manager
        self.connector._init_specialized_workers = MagicMock()
        self.connector._user_stream_tracker._data_source = mock_user_stream_ds

        return mock_node_pool, mock_worker_manager, mock_user_stream_ds

    async def test_start_network_waits_for_healthy_connections(self):
        """start_network waits for healthy connections and starts pools."""
        # healthy_connection_count is accessed multiple times:
        # 1. while check (0 → enter loop), 2. while check (1 → exit loop),
        # 3. if check (1 → else branch), 4. log message (1)
        mock_node_pool, mock_worker_manager, mock_user_stream_ds = \
            self._setup_start_network_mocks(healthy_side_effect=[0, 1, 1, 1, 1, 1])

        # Patch super() at the module level so super().start_network() is a no-op
        mock_super = MagicMock()
        mock_super.return_value.start_network = AsyncMock()

        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.asyncio.sleep", new_callable=AsyncMock), \
             patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.super", mock_super):
            await self.connector.start_network()

        mock_node_pool.start.assert_awaited_once()
        mock_worker_manager.start.assert_awaited_once()
        self.connector._init_specialized_workers.assert_called_once()
        mock_user_stream_ds._initialize_ledger_index.assert_awaited_once()

    async def test_start_network_times_out_waiting_for_connections(self):
        """start_network logs error when no healthy connections after timeout."""
        mock_node_pool, mock_worker_manager, mock_user_stream_ds = \
            self._setup_start_network_mocks(healthy_return=0)

        # Patch super() at module level and asyncio.sleep so the wait loop exits quickly
        mock_super = MagicMock()
        mock_super.return_value.start_network = AsyncMock()

        call_count = 0

        async def fast_sleep(duration):
            nonlocal call_count
            call_count += 1
            if call_count > 35:
                raise Exception("safety break")

        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.asyncio.sleep", side_effect=fast_sleep), \
             patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.super", mock_super):
            await self.connector.start_network()

        # Should still start the worker manager even if no connections
        mock_worker_manager.start.assert_awaited_once()
        # Verify error was logged about no healthy connections
        self._is_logged("ERROR", "No healthy XRPL connections established")


# ======================================================================
# Test: _initialize_trading_pair_symbol_map
# ======================================================================
class TestInitTradingPairSymbolMap(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):

    async def test_initializes_symbol_map(self):
        with patch.object(self.connector, "_make_xrpl_trading_pairs_request", return_value=CONSTANTS.MARKETS), \
             patch.object(self.connector, "_initialize_trading_pair_symbols_from_exchange_info") as init_mock:
            await self.connector._initialize_trading_pair_symbol_map()
            init_mock.assert_called_once_with(exchange_info=CONSTANTS.MARKETS)

    async def test_handles_exception(self):
        with patch.object(self.connector, "_make_xrpl_trading_pairs_request", side_effect=Exception("test error")):
            # Should not raise, just log
            await self.connector._initialize_trading_pair_symbol_map()


# ======================================================================
# Test: _make_network_check_request
# ======================================================================
class TestMakeNetworkCheckRequest(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):

    async def test_calls_check_all_connections(self):
        mock_node_pool = MagicMock()
        mock_node_pool._check_all_connections = AsyncMock()
        self.connector._node_pool = mock_node_pool

        await self.connector._make_network_check_request()
        mock_node_pool._check_all_connections.assert_awaited_once()


# ======================================================================
# Test: _execute_order_cancel_and_process_update (uncovered branches)
# ======================================================================
class TestExecuteOrderCancelBranches(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_not_ready_sleeps(self, _):
        """When connector is not ready, it sleeps before proceeding."""
        order = _make_order(self.connector)

        # Make connector not ready
        with patch.object(type(self.connector), "ready", new_callable=PropertyMock, return_value=False), \
             patch.object(self.connector, "_place_cancel", new_callable=AsyncMock) as place_cancel, \
             patch.object(self.connector, "_request_order_status", new_callable=AsyncMock) as ros:
            ros.return_value = OrderUpdate(
                client_order_id=order.client_order_id,
                exchange_order_id=order.exchange_order_id,
                trading_pair=order.trading_pair,
                update_timestamp=1.0,
                new_state=OrderState.OPEN,
            )
            place_cancel.return_value = TransactionSubmitResult(
                success=False, signed_tx=None, response=None, prelim_result="tecNO_DST",
                exchange_order_id=None, tx_hash=None,
            )
            with patch.object(self.connector, "_cleanup_order_status_lock", new_callable=AsyncMock):
                result = await self.connector._execute_order_cancel_and_process_update(order)
            self.assertFalse(result)
            self.connector._sleep.assert_awaited()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_order_already_in_final_state_and_not_tracked(self, _):
        """When order is not actively tracked and is in FILLED state, processes final state."""
        order = InFlightOrder(
            client_order_id="hbot-final",
            exchange_order_id="99999-88888-FFFF",
            trading_pair="SOLO-XRP",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("100"),
            price=Decimal("0.5"),
            creation_timestamp=1,
            initial_state=OrderState.FILLED,
        )
        # Don't track the order — it's NOT in active_orders

        result = await self.connector._execute_order_cancel_and_process_update(order)
        # Order is FILLED, so cancel returns False
        self.assertFalse(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_order_already_canceled_returns_true(self, _):
        """When order is already CANCELED and not tracked, returns True."""
        order = InFlightOrder(
            client_order_id="hbot-cancel-done",
            exchange_order_id="99999-88888-FFFF",
            trading_pair="SOLO-XRP",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("100"),
            price=Decimal("0.5"),
            creation_timestamp=1,
            initial_state=OrderState.CANCELED,
        )
        # Not tracked

        result = await self.connector._execute_order_cancel_and_process_update(order)
        self.assertTrue(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_actively_tracked_order_already_filled_skips_cancel(self, _):
        """When actively tracked order is already in FILLED state, skips cancellation."""
        order = _make_order(self.connector, state=OrderState.FILLED)

        result = await self.connector._execute_order_cancel_and_process_update(order)
        self.assertFalse(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_timeout_waiting_for_exchange_order_id(self, _):
        """When exchange_order_id times out, marks order as failed."""
        order = InFlightOrder(
            client_order_id="hbot-no-eid",
            exchange_order_id=None,
            trading_pair="SOLO-XRP",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("100"),
            price=Decimal("0.5"),
            creation_timestamp=1,
            initial_state=OrderState.PENDING_CREATE,
        )
        self.connector._order_tracker.start_tracking_order(order)

        with patch.object(order, "get_exchange_order_id", new_callable=AsyncMock, side_effect=asyncio.TimeoutError), \
             patch.object(self.connector._order_tracker, "process_order_not_found", new_callable=AsyncMock) as ponf, \
             patch.object(self.connector, "_cleanup_order_status_lock", new_callable=AsyncMock):
            result = await self.connector._execute_order_cancel_and_process_update(order)
            self.assertFalse(result)
            ponf.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_fresh_status_filled_processes_fills(self, _):
        """When fresh status shows FILLED, processes fills instead of cancelling."""
        order = _make_order(self.connector)

        filled_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=2.0,
            new_state=OrderState.FILLED,
        )

        mock_trade = MagicMock()

        with patch.object(self.connector, "_request_order_status", new_callable=AsyncMock, return_value=filled_update), \
             patch.object(self.connector, "_all_trade_updates_for_order", new_callable=AsyncMock, return_value=[mock_trade]), \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            result = await self.connector._execute_order_cancel_and_process_update(order)
            self.assertFalse(result)  # Not a successful cancel — order was filled
            pfos.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_fresh_status_canceled_returns_true(self, _):
        """When fresh status shows already CANCELED, returns True."""
        order = _make_order(self.connector)

        canceled_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=2.0,
            new_state=OrderState.CANCELED,
        )

        with patch.object(self.connector, "_request_order_status", new_callable=AsyncMock, return_value=canceled_update), \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            result = await self.connector._execute_order_cancel_and_process_update(order)
            self.assertTrue(result)
            pfos.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_fresh_status_partially_filled_continues_to_cancel(self, _):
        """When fresh status shows PARTIALLY_FILLED, processes fills then cancels."""
        order = _make_order(self.connector)

        partial_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=2.0,
            new_state=OrderState.PARTIALLY_FILLED,
        )

        mock_trade = MagicMock()

        with patch.object(self.connector, "_request_order_status", new_callable=AsyncMock, return_value=partial_update), \
             patch.object(self.connector, "_all_trade_updates_for_order", new_callable=AsyncMock, return_value=[mock_trade]), \
             patch.object(self.connector, "_place_cancel", new_callable=AsyncMock) as place_cancel, \
             patch.object(self.connector, "_cleanup_order_status_lock", new_callable=AsyncMock):
            place_cancel.return_value = TransactionSubmitResult(
                success=False, signed_tx=None, response=None, prelim_result="tecNO_DST",
                exchange_order_id=None, tx_hash=None,
            )
            result = await self.connector._execute_order_cancel_and_process_update(order)
            self.assertFalse(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_status_check_exception_continues_to_cancel(self, _):
        """When _request_order_status raises, continues with cancellation."""
        order = _make_order(self.connector)

        with patch.object(self.connector, "_request_order_status", new_callable=AsyncMock, side_effect=Exception("err")), \
             patch.object(self.connector, "_place_cancel", new_callable=AsyncMock) as place_cancel, \
             patch.object(self.connector, "_cleanup_order_status_lock", new_callable=AsyncMock):
            place_cancel.return_value = TransactionSubmitResult(
                success=False, signed_tx=None, response=None, prelim_result="tecNO_DST",
                exchange_order_id=None, tx_hash=None,
            )
            result = await self.connector._execute_order_cancel_and_process_update(order)
            self.assertFalse(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_cancel_submit_fails(self, _):
        """When _place_cancel returns success=False, processes order not found."""
        order = _make_order(self.connector)

        open_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=2.0,
            new_state=OrderState.OPEN,
        )

        with patch.object(self.connector, "_request_order_status", new_callable=AsyncMock, return_value=open_update), \
             patch.object(self.connector, "_place_cancel", new_callable=AsyncMock) as place_cancel, \
             patch.object(self.connector._order_tracker, "process_order_not_found", new_callable=AsyncMock) as ponf, \
             patch.object(self.connector, "_cleanup_order_status_lock", new_callable=AsyncMock):
            place_cancel.return_value = TransactionSubmitResult(
                success=False, signed_tx=None, response=None, prelim_result="tecNO_DST",
                exchange_order_id=None, tx_hash=None,
            )
            result = await self.connector._execute_order_cancel_and_process_update(order)
            self.assertFalse(result)
            ponf.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_tem_bad_sequence_checks_status_canceled(self, _):
        """When prelim_result is temBAD_SEQUENCE and order is actually canceled."""
        order = _make_order(self.connector)

        open_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=2.0,
            new_state=OrderState.OPEN,
        )

        canceled_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=3.0,
            new_state=OrderState.CANCELED,
        )

        signed_tx = MagicMock()
        submit_result = TransactionSubmitResult(
            success=True, signed_tx=signed_tx, response=None, prelim_result="temBAD_SEQUENCE",
            exchange_order_id=EXCHANGE_ORDER_ID, tx_hash="ABCDE12345",
        )

        # First call to _request_order_status returns open, second returns canceled
        status_calls = [open_update, canceled_update]

        with patch.object(self.connector, "_request_order_status", new_callable=AsyncMock, side_effect=status_calls), \
             patch.object(self.connector, "_place_cancel", new_callable=AsyncMock, return_value=submit_result), \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            result = await self.connector._execute_order_cancel_and_process_update(order)
            self.assertTrue(result)
            pfos.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_tem_bad_sequence_checks_status_filled(self, _):
        """When prelim_result is temBAD_SEQUENCE and order is actually filled."""
        order = _make_order(self.connector)

        open_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=2.0,
            new_state=OrderState.OPEN,
        )

        filled_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=3.0,
            new_state=OrderState.FILLED,
        )

        signed_tx = MagicMock()
        submit_result = TransactionSubmitResult(
            success=True, signed_tx=signed_tx, response=None, prelim_result="temBAD_SEQUENCE",
            exchange_order_id=EXCHANGE_ORDER_ID, tx_hash="ABCDE12345",
        )

        mock_trade = MagicMock()
        status_calls = [open_update, filled_update]

        with patch.object(self.connector, "_request_order_status", new_callable=AsyncMock, side_effect=status_calls), \
             patch.object(self.connector, "_place_cancel", new_callable=AsyncMock, return_value=submit_result), \
             patch.object(self.connector, "_all_trade_updates_for_order", new_callable=AsyncMock, return_value=[mock_trade]), \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            result = await self.connector._execute_order_cancel_and_process_update(order)
            self.assertFalse(result)
            pfos.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_tem_bad_sequence_status_check_fails_assumes_canceled(self, _):
        """When temBAD_SEQUENCE and status check fails, assumes canceled."""
        order = _make_order(self.connector)

        open_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=2.0,
            new_state=OrderState.OPEN,
        )

        signed_tx = MagicMock()
        submit_result = TransactionSubmitResult(
            success=True, signed_tx=signed_tx, response=None, prelim_result="temBAD_SEQUENCE",
            exchange_order_id=EXCHANGE_ORDER_ID, tx_hash="ABCDE12345",
        )

        # First call returns open, second raises
        with patch.object(self.connector, "_request_order_status", new_callable=AsyncMock,
                          side_effect=[open_update, Exception("network error")]), \
             patch.object(self.connector, "_place_cancel", new_callable=AsyncMock, return_value=submit_result), \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            result = await self.connector._execute_order_cancel_and_process_update(order)
            self.assertTrue(result)
            pfos.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_verified_cancel_success(self, _):
        """When verification succeeds and status is 'cancelled', returns True."""
        order = _make_order(self.connector)

        open_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=2.0,
            new_state=OrderState.OPEN,
        )

        signed_tx = MagicMock()
        submit_result = TransactionSubmitResult(
            success=True, signed_tx=signed_tx, response=None, prelim_result="tesSUCCESS",
            exchange_order_id=EXCHANGE_ORDER_ID, tx_hash="ABCDE12345",
        )

        verify_response = Response(
            status=ResponseStatus.SUCCESS,
            result={
                "meta": {
                    "AffectedNodes": [],
                }
            },
        )
        verify_result = TransactionVerifyResult(
            verified=True,
            response=verify_response,
            final_result="tesSUCCESS",
        )

        mock_vp = MagicMock()
        mock_vp.submit_verification = AsyncMock(return_value=verify_result)

        with patch.object(self.connector, "_request_order_status", new_callable=AsyncMock, return_value=open_update), \
             patch.object(self.connector, "_place_cancel", new_callable=AsyncMock, return_value=submit_result), \
             patch.object(type(self.connector), "verification_pool", new_callable=PropertyMock, return_value=mock_vp), \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            result = await self.connector._execute_order_cancel_and_process_update(order)
            # changes_array is empty -> status == "cancelled"
            self.assertTrue(result)
            pfos.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_verified_cancel_with_matching_offer_changes(self, _):
        """When verification succeeds with matching offer changes showing cancelled."""
        order = _make_order(self.connector)

        open_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=2.0,
            new_state=OrderState.OPEN,
        )

        signed_tx = MagicMock()
        submit_result = TransactionSubmitResult(
            success=True, signed_tx=signed_tx, response=None, prelim_result="tesSUCCESS",
            exchange_order_id=EXCHANGE_ORDER_ID, tx_hash="ABCDE12345",
        )

        # Provide AffectedNodes with a DeletedNode for the offer
        verify_response = Response(
            status=ResponseStatus.SUCCESS,
            result={
                "meta": {
                    "AffectedNodes": [
                        {
                            "DeletedNode": {
                                "LedgerEntryType": "Offer",
                                "LedgerIndex": "ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF12345678",
                                "FinalFields": {
                                    "Account": OUR_ACCOUNT,
                                    "Sequence": 84437895,
                                    "TakerGets": "1000000",
                                    "TakerPays": {"currency": "534F4C4F00000000000000000000000000000000", "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz", "value": "100"},
                                },
                            }
                        }
                    ],
                }
            },
        )
        verify_result = TransactionVerifyResult(
            verified=True,
            response=verify_response,
            final_result="tesSUCCESS",
        )

        mock_vp = MagicMock()
        mock_vp.submit_verification = AsyncMock(return_value=verify_result)

        with patch.object(self.connector, "_request_order_status", new_callable=AsyncMock, return_value=open_update), \
             patch.object(self.connector, "_place_cancel", new_callable=AsyncMock, return_value=submit_result), \
             patch.object(type(self.connector), "verification_pool", new_callable=PropertyMock, return_value=mock_vp), \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            result = await self.connector._execute_order_cancel_and_process_update(order)
            # The DeletedNode for our offer should be recognized as "cancelled"
            self.assertTrue(result)
            pfos.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_verification_fails(self, _):
        """When verification fails, processes order not found."""
        order = _make_order(self.connector)

        open_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=2.0,
            new_state=OrderState.OPEN,
        )

        signed_tx = MagicMock()
        submit_result = TransactionSubmitResult(
            success=True, signed_tx=signed_tx, response=None, prelim_result="tesSUCCESS",
            exchange_order_id=EXCHANGE_ORDER_ID, tx_hash="ABCDE12345",
        )

        verify_result = TransactionVerifyResult(
            verified=False,
            response=None,
            final_result="tecNO_DST",
            error="verification timeout",
        )

        mock_vp = MagicMock()
        mock_vp.submit_verification = AsyncMock(return_value=verify_result)

        with patch.object(self.connector, "_request_order_status", new_callable=AsyncMock, return_value=open_update), \
             patch.object(self.connector, "_place_cancel", new_callable=AsyncMock, return_value=submit_result), \
             patch.object(type(self.connector), "verification_pool", new_callable=PropertyMock, return_value=mock_vp), \
             patch.object(self.connector._order_tracker, "process_order_not_found", new_callable=AsyncMock) as ponf, \
             patch.object(self.connector, "_cleanup_order_status_lock", new_callable=AsyncMock):
            result = await self.connector._execute_order_cancel_and_process_update(order)
            self.assertFalse(result)
            ponf.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_verified_but_not_cancelled_status_filled_race(self, _):
        """When cancel verified but offer wasn't cancelled (race: order got filled)."""
        order = _make_order(self.connector)

        open_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=2.0,
            new_state=OrderState.OPEN,
        )

        filled_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=3.0,
            new_state=OrderState.FILLED,
        )

        signed_tx = MagicMock()
        submit_result = TransactionSubmitResult(
            success=True, signed_tx=signed_tx, response=None, prelim_result="tesSUCCESS",
            exchange_order_id=EXCHANGE_ORDER_ID, tx_hash="ABCDE12345",
        )

        # Verification returns a change but status is NOT "cancelled" (e.g., "filled")
        verify_response = Response(
            status=ResponseStatus.SUCCESS,
            result={
                "meta": {
                    "AffectedNodes": [
                        {
                            "ModifiedNode": {
                                "LedgerEntryType": "Offer",
                                "LedgerIndex": "ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF12345678",
                                "FinalFields": {
                                    "Account": OUR_ACCOUNT,
                                    "Sequence": 84437895,
                                    "Flags": 0,
                                    "TakerGets": "500000",
                                    "TakerPays": {"currency": "534F4C4F00000000000000000000000000000000", "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz", "value": "50"},
                                },
                                "PreviousFields": {
                                    "TakerGets": "1000000",
                                    "TakerPays": {"currency": "534F4C4F00000000000000000000000000000000", "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz", "value": "100"},
                                },
                            }
                        }
                    ],
                }
            },
        )
        verify_result = TransactionVerifyResult(
            verified=True,
            response=verify_response,
            final_result="tesSUCCESS",
        )

        mock_vp = MagicMock()
        mock_vp.submit_verification = AsyncMock(return_value=verify_result)

        mock_trade = MagicMock()

        # First _request_order_status returns open, second returns filled
        with patch.object(self.connector, "_request_order_status", new_callable=AsyncMock,
                          side_effect=[open_update, filled_update]), \
             patch.object(self.connector, "_place_cancel", new_callable=AsyncMock, return_value=submit_result), \
             patch.object(type(self.connector), "verification_pool", new_callable=PropertyMock, return_value=mock_vp), \
             patch.object(self.connector, "_all_trade_updates_for_order", new_callable=AsyncMock, return_value=[mock_trade]), \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            result = await self.connector._execute_order_cancel_and_process_update(order)
            self.assertFalse(result)  # Cancel not successful — order filled
            pfos.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_verified_not_cancelled_final_check_exception(self, _):
        """When cancel verified but offer wasn't cancelled and final status check raises."""
        order = _make_order(self.connector)

        open_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=2.0,
            new_state=OrderState.OPEN,
        )

        signed_tx = MagicMock()
        submit_result = TransactionSubmitResult(
            success=True, signed_tx=signed_tx, response=None, prelim_result="tesSUCCESS",
            exchange_order_id=EXCHANGE_ORDER_ID, tx_hash="ABCDE12345",
        )

        # Empty AffectedNodes but we'll mock get_order_book_changes to return a non-cancelled change
        verify_response = Response(
            status=ResponseStatus.SUCCESS,
            result={
                "meta": {
                    "AffectedNodes": [
                        {
                            "ModifiedNode": {
                                "LedgerEntryType": "Offer",
                                "LedgerIndex": "ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF12345678",
                                "FinalFields": {
                                    "Account": OUR_ACCOUNT,
                                    "Sequence": 84437895,
                                    "Flags": 0,
                                    "TakerGets": "500000",
                                    "TakerPays": {"currency": "534F4C4F00000000000000000000000000000000", "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz", "value": "50"},
                                },
                                "PreviousFields": {
                                    "TakerGets": "1000000",
                                    "TakerPays": {"currency": "534F4C4F00000000000000000000000000000000", "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz", "value": "100"},
                                },
                            }
                        }
                    ],
                }
            },
        )
        verify_result = TransactionVerifyResult(
            verified=True,
            response=verify_response,
            final_result="tesSUCCESS",
        )

        mock_vp = MagicMock()
        mock_vp.submit_verification = AsyncMock(return_value=verify_result)

        # First _request_order_status returns open, second raises exception
        with patch.object(self.connector, "_request_order_status", new_callable=AsyncMock,
                          side_effect=[open_update, Exception("network error")]), \
             patch.object(self.connector, "_place_cancel", new_callable=AsyncMock, return_value=submit_result), \
             patch.object(type(self.connector), "verification_pool", new_callable=PropertyMock, return_value=mock_vp), \
             patch.object(self.connector._order_tracker, "process_order_not_found", new_callable=AsyncMock) as ponf, \
             patch.object(self.connector, "_cleanup_order_status_lock", new_callable=AsyncMock):
            result = await self.connector._execute_order_cancel_and_process_update(order)
            self.assertFalse(result)
            ponf.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_verified_but_exchange_order_id_none(self, _):
        """When verified but exchange_order_id is None during processing."""
        order = InFlightOrder(
            client_order_id="hbot-none-eid",
            exchange_order_id=None,
            trading_pair="SOLO-XRP",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("100"),
            price=Decimal("0.5"),
            creation_timestamp=1,
            initial_state=OrderState.OPEN,
        )
        self.connector._order_tracker.start_tracking_order(order)

        open_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=2.0,
            new_state=OrderState.OPEN,
        )

        signed_tx = MagicMock()
        submit_result = TransactionSubmitResult(
            success=True, signed_tx=signed_tx, response=None, prelim_result="tesSUCCESS",
            exchange_order_id=EXCHANGE_ORDER_ID, tx_hash="ABCDE12345",
        )

        verify_response = Response(
            status=ResponseStatus.SUCCESS,
            result={"meta": {"AffectedNodes": []}},
        )
        verify_result = TransactionVerifyResult(
            verified=True,
            response=verify_response,
            final_result="tesSUCCESS",
        )

        mock_vp = MagicMock()
        mock_vp.submit_verification = AsyncMock(return_value=verify_result)

        # get_exchange_order_id resolves immediately (returns the exchange_order_id that was set)
        with patch.object(order, "get_exchange_order_id", new_callable=AsyncMock, return_value=EXCHANGE_ORDER_ID), \
             patch.object(self.connector, "_request_order_status", new_callable=AsyncMock, return_value=open_update), \
             patch.object(self.connector, "_place_cancel", new_callable=AsyncMock, return_value=submit_result), \
             patch.object(type(self.connector), "verification_pool", new_callable=PropertyMock, return_value=mock_vp):
            # exchange_order_id is still None when verification runs -> logs error, returns False
            result = await self.connector._execute_order_cancel_and_process_update(order)
            self.assertFalse(result)
