"""
Chunk 8 – Trade Fills tests for XrplExchange.

Covers:
  - _all_trade_updates_for_order
  - _get_fee_for_order
  - _create_trade_update
  - process_trade_fills  (main entry point)
  - _process_taker_fill
  - _process_maker_fill
"""

import asyncio
import unittest
from decimal import Decimal
from test.hummingbot.connector.exchange.xrpl.test_xrpl_exchange_base import XRPLExchangeTestBase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, DeductedFromReturnsTradeFee

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OUR_ACCOUNT = "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK"
EXCHANGE_ORDER_ID = "84437895-88954510-ABCDE12345"
TX_HASH_MATCHING = "ABCDE12345deadbeef1234567890"
TX_HASH_EXTERNAL = "FFFFF99999aaaa0000bbbb1111"
TX_DATE = 784444800  # ripple time


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
# Helper: build a transaction data dict for process_trade_fills
# ======================================================================
def _tx_data(
    *,
    tx_hash: str = TX_HASH_MATCHING,
    tx_sequence: int = 84437895,
    tx_type: str = "OfferCreate",
    tx_date: int = TX_DATE,
    tx_result: str = "tesSUCCESS",
    # For balance changes via get_balance_changes mock
    balance_changes=None,
    offer_changes=None,
) -> dict:
    """Build a transaction data dict in the format process_trade_fills expects."""
    return {
        "tx": {
            "hash": tx_hash,
            "Sequence": tx_sequence,
            "TransactionType": tx_type,
            "date": tx_date,
            "Account": OUR_ACCOUNT,
        },
        "meta": {
            "TransactionResult": tx_result,
            "AffectedNodes": [],
        },
    }


# ======================================================================
# Test: _get_fee_for_order
# ======================================================================
class TestGetFeeForOrder(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):

    async def test_buy_order_uses_quote_fee(self):
        order = _make_order(self.connector, trade_type=TradeType.BUY)
        fee_rules = {
            "base_token": "SOLO",
            "quote_token": "XRP",
            "base_transfer_rate": Decimal("0.01"),
            "quote_transfer_rate": Decimal("0.02"),
        }
        fee = self.connector._get_fee_for_order(order, fee_rules)
        self.assertIsNotNone(fee)
        # For BUY, TradeFeeBase.new_spot_fee returns DeductedFromReturnsTradeFee
        self.assertIsInstance(fee, DeductedFromReturnsTradeFee)
        self.assertEqual(fee.percent, Decimal("0.02"))
        self.assertEqual(fee.percent_token, "XRP")

    async def test_sell_order_uses_base_fee(self):
        order = _make_order(self.connector, trade_type=TradeType.SELL)
        fee_rules = {
            "base_token": "SOLO",
            "quote_token": "XRP",
            "base_transfer_rate": Decimal("0.03"),
            "quote_transfer_rate": Decimal("0.02"),
        }
        fee = self.connector._get_fee_for_order(order, fee_rules)
        self.assertIsNotNone(fee)

    async def test_amm_swap_uses_amm_pool_fee(self):
        order = _make_order(self.connector, order_type=OrderType.AMM_SWAP, trade_type=TradeType.BUY)
        fee_rules = {
            "base_token": "SOLO",
            "quote_token": "XRP",
            "base_transfer_rate": Decimal("0.01"),
            "quote_transfer_rate": Decimal("0.02"),
            "amm_pool_fee": Decimal("0.003"),
        }
        fee = self.connector._get_fee_for_order(order, fee_rules)
        self.assertIsNotNone(fee)

    async def test_missing_fee_token_returns_none(self):
        order = _make_order(self.connector, trade_type=TradeType.BUY)
        fee_rules = {
            "quote_transfer_rate": Decimal("0.02"),
            # no quote_token
        }
        fee = self.connector._get_fee_for_order(order, fee_rules)
        self.assertIsNone(fee)

    async def test_missing_fee_rate_returns_none(self):
        order = _make_order(self.connector, trade_type=TradeType.BUY)
        fee_rules = {
            "quote_token": "XRP",
            # no quote_transfer_rate
        }
        fee = self.connector._get_fee_for_order(order, fee_rules)
        self.assertIsNone(fee)


# ======================================================================
# Test: _create_trade_update
# ======================================================================
class TestCreateTradeUpdate(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):

    async def test_basic_trade_update(self):
        order = _make_order(self.connector)
        fee = AddedToCostTradeFee(percent=Decimal("0.01"))
        tu = self.connector._create_trade_update(
            order=order,
            tx_hash="HASH123",
            tx_date=TX_DATE,
            base_amount=Decimal("50"),
            quote_amount=Decimal("25"),
            fee=fee,
        )
        self.assertEqual(tu.trade_id, "HASH123")
        self.assertEqual(tu.client_order_id, "hbot-1")
        self.assertEqual(tu.fill_base_amount, Decimal("50"))
        self.assertEqual(tu.fill_quote_amount, Decimal("25"))
        self.assertEqual(tu.fill_price, Decimal("0.5"))

    async def test_trade_update_with_offer_sequence(self):
        order = _make_order(self.connector)
        fee = AddedToCostTradeFee(percent=Decimal("0"))
        tu = self.connector._create_trade_update(
            order=order,
            tx_hash="HASH123",
            tx_date=TX_DATE,
            base_amount=Decimal("10"),
            quote_amount=Decimal("5"),
            fee=fee,
            offer_sequence=42,
        )
        self.assertEqual(tu.trade_id, "HASH123_42")

    async def test_zero_base_amount_yields_zero_price(self):
        order = _make_order(self.connector)
        fee = AddedToCostTradeFee(percent=Decimal("0"))
        tu = self.connector._create_trade_update(
            order=order,
            tx_hash="HASH",
            tx_date=TX_DATE,
            base_amount=Decimal("0"),
            quote_amount=Decimal("5"),
            fee=fee,
        )
        self.assertEqual(tu.fill_price, Decimal("0"))


# ======================================================================
# Test: _all_trade_updates_for_order
# ======================================================================
class TestAllTradeUpdatesForOrder(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_returns_trade_fills(self, _):
        order = _make_order(self.connector)
        mock_trade = MagicMock()  # No spec — MagicMock(spec=TradeUpdate) is falsy

        with patch.object(self.connector, "_fetch_account_transactions", new_callable=AsyncMock) as fetch_mock, \
             patch.object(self.connector, "process_trade_fills", new_callable=AsyncMock) as ptf:
            fetch_mock.return_value = [
                {"tx": {"TransactionType": "OfferCreate", "hash": "H1"}},
                {"tx": {"TransactionType": "OfferCreate", "hash": "H2"}},
            ]
            ptf.side_effect = [mock_trade, None]

            fills = await self.connector._all_trade_updates_for_order(order)
            self.assertEqual(len(fills), 1)
            self.assertIs(fills[0], mock_trade)

    async def test_timeout_waiting_for_exchange_order_id(self):
        order = InFlightOrder(
            client_order_id="hbot-timeout",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("1"),
            creation_timestamp=1,
            initial_state=OrderState.PENDING_CREATE,
        )
        self.connector._order_tracker.start_tracking_order(order)

        with patch.object(order, "get_exchange_order_id", new_callable=AsyncMock, side_effect=asyncio.TimeoutError):
            fills = await self.connector._all_trade_updates_for_order(order)
            self.assertEqual(fills, [])

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_skips_non_trade_transactions(self, _):
        order = _make_order(self.connector)

        with patch.object(self.connector, "_fetch_account_transactions", new_callable=AsyncMock) as fetch_mock, \
             patch.object(self.connector, "process_trade_fills", new_callable=AsyncMock) as ptf:
            fetch_mock.return_value = [
                {"tx": {"TransactionType": "AccountSet", "hash": "H1"}},
                {"tx": {"TransactionType": "TrustSet", "hash": "H2"}},
            ]
            # process_trade_fills should NOT be called for non-trade txs
            fills = await self.connector._all_trade_updates_for_order(order)
            self.assertEqual(fills, [])
            ptf.assert_not_awaited()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_skips_transaction_with_missing_tx(self, _):
        order = _make_order(self.connector)

        with patch.object(self.connector, "_fetch_account_transactions", new_callable=AsyncMock) as fetch_mock:
            fetch_mock.return_value = [
                {"meta": {"TransactionResult": "tesSUCCESS"}},  # no tx key
            ]
            fills = await self.connector._all_trade_updates_for_order(order)
            self.assertEqual(fills, [])


# ======================================================================
# Test: process_trade_fills
# ======================================================================
class TestProcessTradeFills(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):

    async def test_data_is_none_raises(self):
        order = _make_order(self.connector)
        with self.assertRaises(ValueError):
            await self.connector.process_trade_fills(None, order)

    async def test_timeout_waiting_for_exchange_order_id(self):
        order = InFlightOrder(
            client_order_id="hbot-timeout",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("1"),
            creation_timestamp=1,
            initial_state=OrderState.PENDING_CREATE,
        )
        self.connector._order_tracker.start_tracking_order(order)

        with patch.object(order, "get_exchange_order_id", new_callable=AsyncMock, side_effect=asyncio.TimeoutError):
            result = await self.connector.process_trade_fills({"tx": {}}, order)
            self.assertIsNone(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_non_trade_transaction_type_returns_none(self, _):
        order = _make_order(self.connector)
        data = {
            "tx": {
                "hash": "HASH1",
                "Sequence": 84437895,
                "TransactionType": "AccountSet",
                "date": TX_DATE,
            },
            "meta": {"TransactionResult": "tesSUCCESS"},
        }
        result = await self.connector.process_trade_fills(data, order)
        self.assertIsNone(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_missing_tx_hash_returns_none(self, _):
        order = _make_order(self.connector)
        data = {
            "tx": {
                "Sequence": 84437895,
                "TransactionType": "OfferCreate",
                "date": TX_DATE,
                # no hash
            },
            "meta": {"TransactionResult": "tesSUCCESS"},
        }
        result = await self.connector.process_trade_fills(data, order)
        self.assertIsNone(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_missing_tx_date_returns_none(self, _):
        order = _make_order(self.connector)
        data = {
            "tx": {
                "hash": TX_HASH_MATCHING,
                "Sequence": 84437895,
                "TransactionType": "OfferCreate",
                # no date
            },
            "meta": {"TransactionResult": "tesSUCCESS"},
        }
        result = await self.connector.process_trade_fills(data, order)
        self.assertIsNone(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_failed_transaction_returns_none(self, _):
        order = _make_order(self.connector)
        data = {
            "tx": {
                "hash": TX_HASH_MATCHING,
                "Sequence": 84437895,
                "TransactionType": "OfferCreate",
                "date": TX_DATE,
            },
            "meta": {"TransactionResult": "tecINSUFFICIENT_FUNDS"},
        }
        result = await self.connector.process_trade_fills(data, order)
        self.assertIsNone(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_fee_rules_not_found_triggers_update(self, _):
        """When fee_rules is None for trading pair, _update_trading_rules is called."""
        order = _make_order(self.connector)
        # Remove fee rules
        self.connector._trading_pair_fee_rules.clear()

        data = _tx_data()

        with patch.object(self.connector, "_update_trading_rules", new_callable=AsyncMock) as utr:
            # After _update_trading_rules, fee_rules still None -> raises
            with self.assertRaises(ValueError):
                await self.connector.process_trade_fills(data, order)
            utr.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_fee_calculation_fails_returns_none(self, _):
        """When _get_fee_for_order returns None, process_trade_fills returns None."""
        order = _make_order(self.connector)
        data = _tx_data()

        with patch.object(self.connector, "_get_fee_for_order", return_value=None):
            result = await self.connector.process_trade_fills(data, order)
            self.assertIsNone(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_taker_fill_dispatched_when_our_transaction(self, _):
        """When tx_sequence matches order_sequence and hash prefix matches, _process_taker_fill is called."""
        order = _make_order(self.connector)
        data = _tx_data(tx_hash=TX_HASH_MATCHING, tx_sequence=84437895)

        mock_trade = MagicMock()
        with patch.object(self.connector, "_process_taker_fill", new_callable=AsyncMock, return_value=mock_trade) as ptf:
            result = await self.connector.process_trade_fills(data, order)
            self.assertIs(result, mock_trade)
            ptf.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_maker_fill_dispatched_when_external_transaction(self, _):
        """When tx_sequence does NOT match order_sequence, _process_maker_fill is called."""
        order = _make_order(self.connector)
        data = _tx_data(tx_hash=TX_HASH_EXTERNAL, tx_sequence=99999)

        mock_trade = MagicMock()
        with patch.object(self.connector, "_process_maker_fill", new_callable=AsyncMock, return_value=mock_trade) as pmf:
            result = await self.connector.process_trade_fills(data, order)
            self.assertIs(result, mock_trade)
            pmf.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_extract_transaction_data_from_result_format(self, _):
        """process_trade_fills handles the 'result' wrapper format."""
        order = _make_order(self.connector)
        data = {
            "result": {
                "hash": TX_HASH_MATCHING,
                "tx_json": {
                    "Sequence": 84437895,
                    "TransactionType": "OfferCreate",
                    "date": TX_DATE,
                },
                "meta": {"TransactionResult": "tesSUCCESS", "AffectedNodes": []},
            }
        }

        mock_trade = MagicMock()
        with patch.object(self.connector, "_process_taker_fill", new_callable=AsyncMock, return_value=mock_trade):
            result = await self.connector.process_trade_fills(data, order)
            self.assertIs(result, mock_trade)


# ======================================================================
# Test: _process_taker_fill
# ======================================================================
class TestProcessTakerFill(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):

    def _fee(self):
        return AddedToCostTradeFee(percent=Decimal("0.01"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_market_order_uses_balance_changes(self, _):
        order = _make_order(self.connector, order_type=OrderType.MARKET)
        balance_changes = [
            {
                "account": OUR_ACCOUNT,
                "balances": [
                    {"currency": "SOLO", "value": "50"},
                    {"currency": "XRP", "value": "-25"},
                ],
            }
        ]

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.extract_fill_amounts_from_balance_changes",
            return_value=(Decimal("50"), Decimal("25")),
        ):
            result = await self.connector._process_taker_fill(
                order=order,
                tx={"hash": TX_HASH_MATCHING},
                tx_hash=TX_HASH_MATCHING,
                tx_date=TX_DATE,
                our_offer_changes=[],
                our_balance_changes=balance_changes,
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNotNone(result)
            self.assertEqual(result.fill_base_amount, Decimal("50"))
            self.assertEqual(result.fill_quote_amount, Decimal("25"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_market_order_no_balance_changes_returns_none(self, _):
        order = _make_order(self.connector, order_type=OrderType.MARKET)

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.extract_fill_amounts_from_balance_changes",
            return_value=(None, None),
        ):
            result = await self.connector._process_taker_fill(
                order=order,
                tx={},
                tx_hash=TX_HASH_MATCHING,
                tx_date=TX_DATE,
                our_offer_changes=[],
                our_balance_changes=[],
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNone(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_market_order_zero_base_returns_none(self, _):
        order = _make_order(self.connector, order_type=OrderType.MARKET)

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.extract_fill_amounts_from_balance_changes",
            return_value=(Decimal("0"), Decimal("25")),
        ):
            result = await self.connector._process_taker_fill(
                order=order,
                tx={},
                tx_hash=TX_HASH_MATCHING,
                tx_date=TX_DATE,
                our_offer_changes=[],
                our_balance_changes=[{"account": OUR_ACCOUNT, "balances": []}],
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNone(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_limit_order_filled_via_offer_change(self, _):
        """Limit order that crossed existing offers — offer_change status = 'filled'."""
        order = _make_order(self.connector, order_type=OrderType.LIMIT)

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.find_offer_change_for_order",
            return_value={"status": "filled", "sequence": 84437895,
                          "taker_gets": {"currency": "SOLO", "value": "-30"},
                          "taker_pays": {"currency": "XRP", "value": "-15"}},
        ), patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.extract_fill_amounts_from_offer_change",
            return_value=(Decimal("30"), Decimal("15")),
        ):
            result = await self.connector._process_taker_fill(
                order=order,
                tx={},
                tx_hash=TX_HASH_MATCHING,
                tx_date=TX_DATE,
                our_offer_changes=[],
                our_balance_changes=[],
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNotNone(result)
            self.assertEqual(result.fill_base_amount, Decimal("30"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_limit_order_partially_filled_via_offer_change(self, _):
        """Limit order partially filled — offer_change status = 'partially-filled'."""
        order = _make_order(self.connector, order_type=OrderType.LIMIT)

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.find_offer_change_for_order",
            return_value={"status": "partially-filled", "sequence": 84437895,
                          "taker_gets": {"currency": "SOLO", "value": "-10"},
                          "taker_pays": {"currency": "XRP", "value": "-5"}},
        ), patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.extract_fill_amounts_from_offer_change",
            return_value=(Decimal("10"), Decimal("5")),
        ):
            result = await self.connector._process_taker_fill(
                order=order,
                tx={},
                tx_hash=TX_HASH_MATCHING,
                tx_date=TX_DATE,
                our_offer_changes=[],
                our_balance_changes=[],
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNotNone(result)
            self.assertEqual(result.fill_base_amount, Decimal("10"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_limit_order_created_with_partial_fill_from_balance(self, _):
        """Offer created (rest on book) but partially filled on creation — uses balance changes."""
        order = _make_order(self.connector, order_type=OrderType.LIMIT)

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.find_offer_change_for_order",
            return_value={"status": "created", "sequence": 84437895},
        ), patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.extract_fill_amounts_from_balance_changes",
            return_value=(Decimal("20"), Decimal("10")),
        ):
            result = await self.connector._process_taker_fill(
                order=order,
                tx={},
                tx_hash=TX_HASH_MATCHING,
                tx_date=TX_DATE,
                our_offer_changes=[],
                our_balance_changes=[{"account": OUR_ACCOUNT, "balances": [{"currency": "SOLO", "value": "20"}]}],
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNotNone(result)
            self.assertEqual(result.fill_base_amount, Decimal("20"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_limit_order_created_no_balance_changes_returns_none(self, _):
        """Offer created on book without immediate fill — no balance changes."""
        order = _make_order(self.connector, order_type=OrderType.LIMIT)

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.find_offer_change_for_order",
            return_value={"status": "created", "sequence": 84437895},
        ):
            result = await self.connector._process_taker_fill(
                order=order,
                tx={},
                tx_hash=TX_HASH_MATCHING,
                tx_date=TX_DATE,
                our_offer_changes=[],
                our_balance_changes=[],
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNone(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_limit_order_cancelled_with_partial_fill(self, _):
        """Offer cancelled after partial fill — uses balance changes."""
        order = _make_order(self.connector, order_type=OrderType.LIMIT)

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.find_offer_change_for_order",
            return_value={"status": "cancelled", "sequence": 84437895},
        ), patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.extract_fill_amounts_from_balance_changes",
            return_value=(Decimal("5"), Decimal("2.5")),
        ):
            result = await self.connector._process_taker_fill(
                order=order,
                tx={},
                tx_hash=TX_HASH_MATCHING,
                tx_date=TX_DATE,
                our_offer_changes=[],
                our_balance_changes=[{"account": OUR_ACCOUNT, "balances": [{"currency": "SOLO", "value": "5"}]}],
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNotNone(result)
            self.assertEqual(result.fill_base_amount, Decimal("5"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_limit_order_cancelled_no_balance_changes_returns_none(self, _):
        """Offer cancelled without any fill — no balance changes."""
        order = _make_order(self.connector, order_type=OrderType.LIMIT)

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.find_offer_change_for_order",
            return_value={"status": "cancelled", "sequence": 84437895},
        ):
            result = await self.connector._process_taker_fill(
                order=order,
                tx={},
                tx_hash=TX_HASH_MATCHING,
                tx_date=TX_DATE,
                our_offer_changes=[],
                our_balance_changes=[],
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNone(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_no_matching_offer_fully_filled_from_balance(self, _):
        """No offer change for our sequence, but balance changes show a fill (fully filled, never hit book)."""
        order = _make_order(self.connector, order_type=OrderType.LIMIT)

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.find_offer_change_for_order",
            return_value=None,
        ), patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.extract_fill_amounts_from_balance_changes",
            return_value=(Decimal("100"), Decimal("50")),
        ):
            result = await self.connector._process_taker_fill(
                order=order,
                tx={},
                tx_hash=TX_HASH_MATCHING,
                tx_date=TX_DATE,
                our_offer_changes=[],
                our_balance_changes=[{"account": OUR_ACCOUNT, "balances": [{"currency": "SOLO", "value": "100"}]}],
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNotNone(result)
            self.assertEqual(result.fill_base_amount, Decimal("100"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_no_matching_offer_fallback_to_transaction(self, _):
        """No matching offer, balance changes return zero → fallback to TakerGets/TakerPays."""
        order = _make_order(self.connector, order_type=OrderType.LIMIT)

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.find_offer_change_for_order",
            return_value=None,
        ), patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.extract_fill_amounts_from_balance_changes",
            return_value=(Decimal("0"), Decimal("0")),
        ), patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.extract_fill_amounts_from_transaction",
            return_value=(Decimal("1"), Decimal("0.5")),
        ):
            result = await self.connector._process_taker_fill(
                order=order,
                tx={"TakerGets": "1000000", "TakerPays": {"currency": "SOLO", "value": "1"}},
                tx_hash=TX_HASH_MATCHING,
                tx_date=TX_DATE,
                our_offer_changes=[],
                our_balance_changes=[{"account": OUR_ACCOUNT, "balances": []}],
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNotNone(result)
            self.assertEqual(result.fill_base_amount, Decimal("1"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_no_matching_offer_all_fallbacks_fail_returns_none(self, _):
        """No matching offer, no balance changes, no TakerGets/TakerPays → None."""
        order = _make_order(self.connector, order_type=OrderType.LIMIT)

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.find_offer_change_for_order",
            return_value=None,
        ), patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.extract_fill_amounts_from_balance_changes",
            return_value=(Decimal("0"), Decimal("0")),
        ), patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.extract_fill_amounts_from_transaction",
            return_value=(None, None),
        ):
            result = await self.connector._process_taker_fill(
                order=order,
                tx={},
                tx_hash=TX_HASH_MATCHING,
                tx_date=TX_DATE,
                our_offer_changes=[],
                our_balance_changes=[{"account": OUR_ACCOUNT, "balances": []}],
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNone(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_no_matching_offer_no_balance_changes_at_all_returns_none(self, _):
        """No matching offer and empty our_balance_changes list → None."""
        order = _make_order(self.connector, order_type=OrderType.LIMIT)

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.find_offer_change_for_order",
            return_value=None,
        ):
            result = await self.connector._process_taker_fill(
                order=order,
                tx={},
                tx_hash=TX_HASH_MATCHING,
                tx_date=TX_DATE,
                our_offer_changes=[],
                our_balance_changes=[],
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNone(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_amm_swap_uses_balance_changes(self, _):
        """AMM_SWAP orders use the balance changes path like MARKET orders."""
        order = _make_order(self.connector, order_type=OrderType.AMM_SWAP)

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.extract_fill_amounts_from_balance_changes",
            return_value=(Decimal("80"), Decimal("40")),
        ):
            result = await self.connector._process_taker_fill(
                order=order,
                tx={},
                tx_hash=TX_HASH_MATCHING,
                tx_date=TX_DATE,
                our_offer_changes=[],
                our_balance_changes=[{"account": OUR_ACCOUNT, "balances": []}],
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNotNone(result)
            self.assertEqual(result.fill_base_amount, Decimal("80"))


# ======================================================================
# Test: _process_maker_fill
# ======================================================================
class TestProcessMakerFill(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):

    def _fee(self):
        return AddedToCostTradeFee(percent=Decimal("0.01"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_matching_offer_found_returns_trade_update(self, _):
        order = _make_order(self.connector)
        offer_changes = [
            {
                "maker_account": OUR_ACCOUNT,
                "offer_changes": [
                    {
                        "sequence": 84437895,
                        "status": "partially-filled",
                        "taker_gets": {"currency": "SOLO", "value": "-25"},
                        "taker_pays": {"currency": "XRP", "value": "-12.5"},
                    }
                ],
            }
        ]

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.find_offer_change_for_order",
            return_value=offer_changes[0]["offer_changes"][0],
        ), patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.extract_fill_amounts_from_offer_change",
            return_value=(Decimal("25"), Decimal("12.5")),
        ):
            result = await self.connector._process_maker_fill(
                order=order,
                tx_hash=TX_HASH_EXTERNAL,
                tx_date=TX_DATE,
                our_offer_changes=offer_changes,
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNotNone(result)
            self.assertEqual(result.fill_base_amount, Decimal("25"))
            # Maker fills use trade_id with offer_sequence
            self.assertIn("_84437895", result.trade_id)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_no_matching_offer_returns_none(self, _):
        order = _make_order(self.connector)

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.find_offer_change_for_order",
            return_value=None,
        ):
            result = await self.connector._process_maker_fill(
                order=order,
                tx_hash=TX_HASH_EXTERNAL,
                tx_date=TX_DATE,
                our_offer_changes=[],
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNone(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_zero_base_amount_returns_none(self, _):
        order = _make_order(self.connector)

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.find_offer_change_for_order",
            return_value={"status": "filled", "sequence": 84437895},
        ), patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.extract_fill_amounts_from_offer_change",
            return_value=(Decimal("0"), Decimal("5")),
        ):
            result = await self.connector._process_maker_fill(
                order=order,
                tx_hash=TX_HASH_EXTERNAL,
                tx_date=TX_DATE,
                our_offer_changes=[],
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNone(result)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_none_amounts_returns_none(self, _):
        order = _make_order(self.connector)

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.find_offer_change_for_order",
            return_value={"status": "filled", "sequence": 84437895},
        ), patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.extract_fill_amounts_from_offer_change",
            return_value=(None, None),
        ):
            result = await self.connector._process_maker_fill(
                order=order,
                tx_hash=TX_HASH_EXTERNAL,
                tx_date=TX_DATE,
                our_offer_changes=[],
                base_currency="SOLO",
                quote_currency="XRP",
                fee=self._fee(),
                order_sequence=84437895,
            )
            self.assertIsNone(result)
