"""
Test module for Gateway Transaction Handler including fee retry logic.
Tests the complete flow: GatewayLP -> GatewayHttpClient -> fee calculation -> retry logic
"""
import asyncio
import sys
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

# Add path for imports
sys.path.insert(0, '/Users/feng/hummingbot')

# Mock the problematic imports before they're used
sys.modules['hummingbot.connector.exchange_base'] = Mock()
sys.modules['hummingbot.connector.connector_base'] = Mock()

from hummingbot.connector.gateway.gateway_http_client import GatewayHttpClient  # noqa: E402
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder  # noqa: E402
from hummingbot.core.data_type.common import OrderType, TradeType  # noqa: E402
from hummingbot.core.data_type.in_flight_order import OrderState  # noqa: E402


class MockGatewaySwap:
    """Mock GatewaySwap connector for testing"""

    def __init__(self):
        self._in_flight_orders = {}
        self._native_currency = "SOL"
        self.connector_name = "raydium/clmm"
        self.chain = "solana"
        self.network = "mainnet-beta"
        self.address = "7B2UBtod3aH7nBCNhdMCVsXjHt8mcDmQxP6EfJfXEipG"
        self._tx_handler = None
        self._order_id_counter = 0
        self.logger = Mock()

    @property
    def tx_handler(self):
        if self._tx_handler is None:
            self._tx_handler = GatewayHttpClient(self._gateway_instance)
        return self._tx_handler

    def create_market_order_id(self, side, trading_pair):
        self._order_id_counter += 1
        return f"order_{self._order_id_counter}"

    def start_tracking_order(self, order_id, trading_pair, trade_type, price=None, amount=None):
        order = GatewayInFlightOrder(
            client_order_id=order_id,
            trading_pair=trading_pair,
            order_type=OrderType.MARKET,
            trade_type=trade_type,
            price=price or Decimal("0"),
            amount=amount or Decimal("0"),
            creation_timestamp=1640000000.0,
            initial_state=OrderState.PENDING_CREATE
        )
        self._in_flight_orders[order_id] = order

    def quantize_order_amount(self, trading_pair, amount):
        return amount

    def quantize_order_price(self, trading_pair, price):
        return price

    def _handle_operation_failure(self, order_id, trading_pair, operation, error):
        pass


class MockGatewayLp(MockGatewaySwap):
    """Mock GatewayLp connector for testing"""
    pass


class TestGatewayHttpClient(unittest.TestCase):
    """
    Test class for Gateway transaction handler functionality
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

        # Trading pair setup
        cls.base_asset = "USDC"
        cls.quote_asset = "SOL"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

        # Mock responses from actual tests
        cls.sell_response = {
            "signature": "5TBLtTe9wvG69kitNrpETAjjNmTw3dWcwWxGsWyNvBecPHkrZTgBaPQJMCb89v9FL9b33U3Pd9iW1trDvvbDpJCK",
            "status": 1,
            "confirmed": True,
            "data": {
                "baseAmount": "1000000",
                "quoteAmount": "8640700",
                "price": "8.6407"
            },
            "fee": 0.00215
        }

        cls.buy_response = {
            "signature": "45eeF7L7qZmWANgud8YNnwwLkJ2uZoWqZaMuNCzpUSX9qMyqrkBx2jV9LfMqWJzR5rVYhUbpFTeWvyHAg94BUSQQ",
            "status": 1,
            "confirmed": True,
            "data": {
                "baseAmount": "1000000",
                "quoteAmount": "8512000",
                "price": "8.512"
            },
            "fee": 0.00301
        }

        # Chain configuration
        cls.chain_config = {
            "defaultComputeUnits": 200000,
            "gasEstimateInterval": 60,
            "maxFee": 0.01,
            "minFee": 0.0001,
            "retryCount": 3,
            "retryFeeMultiplier": 2.0,
            "retryInterval": 0.1  # Faster for tests
        }

    def setUp(self) -> None:
        super().setUp()

        # Mock Gateway HTTP client
        self.gateway_instance_mock = AsyncMock()
        self.gateway_instance_mock.current_timestamp = 1640000000.0
        self.gateway_instance_mock.get_configuration = AsyncMock(return_value=self.chain_config)

        # Create mock swap connector
        self.swap_connector = MockGatewaySwap()
        self.swap_connector._gateway_instance = self.gateway_instance_mock

        # Create mock LP connector
        self.lp_connector = MockGatewayLp()
        self.lp_connector._gateway_instance = self.gateway_instance_mock

        # Create transaction handler
        self.tx_handler = GatewayHttpClient(self.gateway_instance_mock)

    def async_run_with_timeout(self, coroutine, timeout: float = 1):
        return self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_gateway_tx_handler_initialization(self):
        """Test that GatewayHttpClient initializes correctly"""
        self.assertIsNotNone(self.tx_handler)
        self.assertEqual(self.tx_handler.gateway_client, self.gateway_instance_mock)
        self.assertEqual(len(self.tx_handler._config_cache), 0)
        self.assertEqual(len(self.tx_handler._pending_transactions), 0)

    def test_swap_connector_tx_handler_property(self):
        """Test that swap connector properly initializes tx_handler"""
        self.assertIsNotNone(self.swap_connector.tx_handler)
        self.assertIsInstance(self.swap_connector.tx_handler, GatewayHttpClient)

    def test_lp_connector_inherits_tx_handler(self):
        """Test that LP connector inherits tx_handler from GatewaySwap"""
        self.assertIsNotNone(self.lp_connector.tx_handler)
        self.assertIsInstance(self.lp_connector.tx_handler, GatewayHttpClient)

    def test_successful_sell_order_first_attempt(self):
        """Test successful SELL order on first attempt"""
        # Mock estimate-gas response
        self.gateway_instance_mock.api_request = AsyncMock()
        self.gateway_instance_mock.api_request.side_effect = [
            # estimate-gas response
            {
                "feePerComputeUnit": 1000,  # microlamports per CU
                "denomination": "microlamports",
                "timestamp": 1640000000.0
            },
            # execute-swap response (immediate success)
            self.sell_response
        ]

        # Create order manually (simulate sell)
        order_id = self.swap_connector.create_market_order_id(TradeType.SELL, self.trading_pair)
        self.swap_connector.start_tracking_order(
            order_id=order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("8.5"),
            amount=Decimal("1")
        )

        # Execute transaction
        self.async_run_with_timeout(
            self.tx_handler.execute_transaction(
                chain="solana",
                network="mainnet-beta",
                connector="raydium/clmm",
                method="execute-swap",
                params={
                    "walletAddress": "7B2UBtod3aH7nBCNhdMCVsXjHt8mcDmQxP6EfJfXEipG",
                    "baseToken": "USDC",
                    "quoteToken": "SOL",
                    "amount": 1.0,
                    "side": "SELL",
                },
                order_id=order_id,
                tracked_order=self.swap_connector._in_flight_orders[order_id]
            )
        )

        # Let async operations complete
        self.async_run_with_timeout(asyncio.sleep(0.1))

        # Verify order was created
        self.assertIn(order_id, self.swap_connector._in_flight_orders)
        order = self.swap_connector._in_flight_orders[order_id]

        # Verify transaction hash was set
        self.assertEqual(order.creation_transaction_hash, self.sell_response["signature"])
        self.assertEqual(order.current_state, OrderState.FILLED)

        # Verify API calls
        self.assertEqual(self.gateway_instance_mock.api_request.call_count, 2)

        # Verify estimate-gas call
        estimate_call = self.gateway_instance_mock.api_request.call_args_list[0]
        self.assertEqual(estimate_call[1]["method"], "POST")
        self.assertEqual(estimate_call[1]["path_url"], "chains/solana/estimate-gas")

        # Verify execute-swap call
        swap_call = self.gateway_instance_mock.api_request.call_args_list[1]
        self.assertEqual(swap_call[1]["method"], "POST")
        self.assertEqual(swap_call[1]["path_url"], "connectors/raydium/clmm/execute-swap")

        # Verify swap parameters
        swap_params = swap_call[1]["params"]
        self.assertEqual(swap_params["walletAddress"], "7B2UBtod3aH7nBCNhdMCVsXjHt8mcDmQxP6EfJfXEipG")
        self.assertEqual(swap_params["baseToken"], "USDC")
        self.assertEqual(swap_params["quoteToken"], "SOL")
        self.assertEqual(swap_params["amount"], 1.0)
        self.assertEqual(swap_params["side"], "SELL")
        self.assertEqual(swap_params["priorityFeePerCU"], 1000)
        self.assertEqual(swap_params["computeUnits"], 200000)

    def test_successful_buy_order_first_attempt(self):
        """Test successful BUY order on first attempt"""
        # Mock estimate-gas response
        self.gateway_instance_mock.api_request = AsyncMock()
        self.gateway_instance_mock.api_request.side_effect = [
            # estimate-gas response
            {
                "feePerComputeUnit": 1500,  # microlamports per CU
                "denomination": "microlamports",
                "timestamp": 1640000000.0
            },
            # execute-swap response (immediate success)
            self.buy_response
        ]

        # Create order manually (simulate buy)
        order_id = self.swap_connector.create_market_order_id(TradeType.BUY, self.trading_pair)
        self.swap_connector.start_tracking_order(
            order_id=order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("8.6"),
            amount=Decimal("1")
        )

        # Execute transaction
        self.async_run_with_timeout(
            self.tx_handler.execute_transaction(
                chain="solana",
                network="mainnet-beta",
                connector="raydium/clmm",
                method="execute-swap",
                params={
                    "walletAddress": "7B2UBtod3aH7nBCNhdMCVsXjHt8mcDmQxP6EfJfXEipG",
                    "baseToken": "USDC",
                    "quoteToken": "SOL",
                    "amount": 1.0,
                    "side": "BUY",
                },
                order_id=order_id,
                tracked_order=self.swap_connector._in_flight_orders[order_id]
            )
        )

        # Let async operations complete
        self.async_run_with_timeout(asyncio.sleep(0.1))

        # Verify order was created
        self.assertIn(order_id, self.swap_connector._in_flight_orders)
        order = self.swap_connector._in_flight_orders[order_id]

        # Verify transaction hash was set
        self.assertEqual(order.creation_transaction_hash, self.buy_response["signature"])
        self.assertEqual(order.current_state, OrderState.FILLED)

        # Verify swap parameters
        swap_call = self.gateway_instance_mock.api_request.call_args_list[1]
        swap_params = swap_call[1]["params"]
        self.assertEqual(swap_params["side"], "BUY")
        self.assertEqual(swap_params["priorityFeePerCU"], 1500)

    def test_transaction_retry_insufficient_fee(self):
        """Test transaction retry logic when fee is insufficient"""
        # Mock responses for retry scenario
        self.gateway_instance_mock.api_request = AsyncMock()
        self.gateway_instance_mock.api_request.side_effect = [
            # estimate-gas response
            {
                "feePerComputeUnit": 500,  # Low initial fee
                "denomination": "microlamports",
                "timestamp": 1640000000.0
            },
            # First execute-swap attempt (pending)
            {
                "signature": "pendingTx1",
                "status": 0  # PENDING
            },
            # First poll (failed)
            {
                "confirmed": False,
                "failed": True
            },
            # Second execute-swap attempt with higher fee (pending)
            {
                "signature": "pendingTx2",
                "status": 0  # PENDING
            },
            # Second poll (failed)
            {
                "confirmed": False,
                "failed": True
            },
            # Third execute-swap attempt with even higher fee (success)
            self.sell_response
        ]

        # Create order manually
        order_id = self.swap_connector.create_market_order_id(TradeType.SELL, self.trading_pair)
        self.swap_connector.start_tracking_order(
            order_id=order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("8.5"),
            amount=Decimal("1")
        )

        # Execute transaction
        self.async_run_with_timeout(
            self.tx_handler.execute_transaction(
                chain="solana",
                network="mainnet-beta",
                connector="raydium/clmm",
                method="execute-swap",
                params={
                    "walletAddress": "7B2UBtod3aH7nBCNhdMCVsXjHt8mcDmQxP6EfJfXEipG",
                    "baseToken": "USDC",
                    "quoteToken": "SOL",
                    "amount": 1.0,
                    "side": "SELL",
                },
                order_id=order_id,
                tracked_order=self.swap_connector._in_flight_orders[order_id]
            )
        )

        # Let async operations complete with longer timeout for retries
        self.async_run_with_timeout(asyncio.sleep(0.5))

        # Verify order succeeded after retries
        order = self.swap_connector._in_flight_orders[order_id]
        self.assertEqual(order.creation_transaction_hash, self.sell_response["signature"])
        self.assertEqual(order.current_state, OrderState.FILLED)

        # Verify we made multiple attempts
        self.assertGreaterEqual(self.gateway_instance_mock.api_request.call_count, 5)

        # Verify fee escalation
        execute_calls = [call for call in self.gateway_instance_mock.api_request.call_args_list
                         if "execute-swap" in call[1]["path_url"]]

        # Check that fees increased with each attempt
        first_fee = execute_calls[0][1]["params"]["priorityFeePerCU"]
        second_fee = execute_calls[1][1]["params"]["priorityFeePerCU"]
        third_fee = execute_calls[2][1]["params"]["priorityFeePerCU"]

        self.assertEqual(first_fee, 500)  # Initial fee
        self.assertEqual(second_fee, 1000)  # 2x multiplier
        self.assertEqual(third_fee, 2000)  # 2x multiplier again

    def test_max_retries_exceeded(self):
        """Test behavior when maximum retries are exceeded"""
        # Mock all attempts to fail
        self.gateway_instance_mock.api_request = AsyncMock()

        # Create a list of responses for all retry attempts
        responses = [
            # estimate-gas response
            {
                "feePerComputeUnit": 1000,
                "denomination": "microlamports",
                "timestamp": 1640000000.0
            }
        ]

        # Add failed attempts (4 attempts total: initial + 3 retries)
        for i in range(4):
            responses.extend([
                # execute-swap attempt
                {
                    "signature": f"failedTx{i}",
                    "status": 0  # PENDING
                },
                # poll response (failed)
                {
                    "confirmed": False,
                    "failed": True
                }
            ])

        self.gateway_instance_mock.api_request.side_effect = responses

        # Create order manually
        order_id = self.swap_connector.create_market_order_id(TradeType.BUY, self.trading_pair)
        self.swap_connector.start_tracking_order(
            order_id=order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("8.6"),
            amount=Decimal("1")
        )

        # Execute transaction
        self.async_run_with_timeout(
            self.tx_handler.execute_transaction(
                chain="solana",
                network="mainnet-beta",
                connector="raydium/clmm",
                method="execute-swap",
                params={
                    "walletAddress": "7B2UBtod3aH7nBCNhdMCVsXjHt8mcDmQxP6EfJfXEipG",
                    "baseToken": "USDC",
                    "quoteToken": "SOL",
                    "amount": 1.0,
                    "side": "BUY",
                },
                order_id=order_id,
                tracked_order=self.swap_connector._in_flight_orders[order_id]
            )
        )

        # Let async operations complete
        self.async_run_with_timeout(asyncio.sleep(1.0))

        # Verify order failed
        order = self.swap_connector._in_flight_orders[order_id]
        self.assertEqual(order.current_state, OrderState.FAILED)

        # Verify we attempted exactly 4 times (initial + 3 retries)
        execute_calls = [call for call in self.gateway_instance_mock.api_request.call_args_list
                         if "execute-swap" in call[1]["path_url"]]
        self.assertEqual(len(execute_calls), 4)

    def test_fee_bounds_enforcement(self):
        """Test that fees respect min/max bounds"""
        # Mock very high initial fee estimate
        self.gateway_instance_mock.api_request = AsyncMock()
        self.gateway_instance_mock.api_request.side_effect = [
            # estimate-gas response with very high fee
            {
                "feePerComputeUnit": 1000000,  # Very high fee
                "denomination": "microlamports",
                "timestamp": 1640000000.0
            },
            # execute-swap response
            self.buy_response
        ]

        # Create order manually
        order_id = self.swap_connector.create_market_order_id(TradeType.BUY, self.trading_pair)
        self.swap_connector.start_tracking_order(
            order_id=order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("8.6"),
            amount=Decimal("1")
        )

        # Execute transaction
        self.async_run_with_timeout(
            self.tx_handler.execute_transaction(
                chain="solana",
                network="mainnet-beta",
                connector="raydium/clmm",
                method="execute-swap",
                params={
                    "walletAddress": "7B2UBtod3aH7nBCNhdMCVsXjHt8mcDmQxP6EfJfXEipG",
                    "baseToken": "USDC",
                    "quoteToken": "SOL",
                    "amount": 1.0,
                    "side": "BUY",
                },
                order_id=order_id,
                tracked_order=self.swap_connector._in_flight_orders[order_id]
            )
        )

        # Let async operations complete
        self.async_run_with_timeout(asyncio.sleep(0.1))

        # Verify fee was capped at max
        swap_call = self.gateway_instance_mock.api_request.call_args_list[1]
        swap_params = swap_call[1]["params"]

        # Calculate expected max fee per CU
        compute_units = 200000
        max_fee = 0.01  # SOL
        max_fee_per_cu = int((max_fee * 1e9 * 1e6) / compute_units)

        self.assertEqual(swap_params["priorityFeePerCU"], max_fee_per_cu)

    def test_compute_units_caching(self):
        """Test that compute units are cached for transaction types"""
        # First transaction
        self.gateway_instance_mock.api_request = AsyncMock(side_effect=[
            {"feePerComputeUnit": 1000, "denomination": "microlamports", "timestamp": 1640000000.0},
            self.sell_response
        ])

        order_id1 = self.swap_connector.create_market_order_id(TradeType.SELL, self.trading_pair)
        self.swap_connector.start_tracking_order(
            order_id=order_id1,
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("8.5"),
            amount=Decimal("1")
        )

        self.async_run_with_timeout(
            self.tx_handler.execute_transaction(
                chain="solana",
                network="mainnet-beta",
                connector="raydium/clmm",
                method="execute-swap",
                params={
                    "walletAddress": "7B2UBtod3aH7nBCNhdMCVsXjHt8mcDmQxP6EfJfXEipG",
                    "baseToken": "USDC",
                    "quoteToken": "SOL",
                    "amount": 1.0,
                    "side": "SELL",
                },
                order_id=order_id1,
                tracked_order=self.swap_connector._in_flight_orders[order_id1]
            )
        )
        self.async_run_with_timeout(asyncio.sleep(0.1))

        # Cache compute units
        self.tx_handler.cache_compute_units("swap", "solana", "mainnet-beta", 150000)

        # Second transaction should use cached compute units
        self.gateway_instance_mock.api_request = AsyncMock(side_effect=[
            {"feePerComputeUnit": 1000, "denomination": "microlamports", "timestamp": 1640000000.0},
            self.buy_response
        ])

        order_id2 = self.swap_connector.create_market_order_id(TradeType.BUY, self.trading_pair)
        self.swap_connector.start_tracking_order(
            order_id=order_id2,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("8.6"),
            amount=Decimal("1")
        )

        self.async_run_with_timeout(
            self.tx_handler.execute_transaction(
                chain="solana",
                network="mainnet-beta",
                connector="raydium/clmm",
                method="execute-swap",
                params={
                    "walletAddress": "7B2UBtod3aH7nBCNhdMCVsXjHt8mcDmQxP6EfJfXEipG",
                    "baseToken": "USDC",
                    "quoteToken": "SOL",
                    "amount": 1.0,
                    "side": "BUY",
                },
                order_id=order_id2,
                tracked_order=self.swap_connector._in_flight_orders[order_id2]
            )
        )
        self.async_run_with_timeout(asyncio.sleep(0.1))

        # Verify cached compute units were used
        second_swap_call = self.gateway_instance_mock.api_request.call_args_list[-1]
        self.assertEqual(second_swap_call[1]["params"]["computeUnits"], 150000)

    def test_fee_estimate_caching(self):
        """Test that fee estimates are cached and reused within interval"""
        # First transaction
        self.gateway_instance_mock.api_request = AsyncMock(side_effect=[
            {"feePerComputeUnit": 1000, "denomination": "microlamports", "timestamp": 1640000000.0},
            self.sell_response
        ])

        order_id1 = self.swap_connector.create_market_order_id(TradeType.SELL, self.trading_pair)
        self.swap_connector.start_tracking_order(
            order_id=order_id1,
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("8.5"),
            amount=Decimal("1")
        )

        self.async_run_with_timeout(
            self.tx_handler.execute_transaction(
                chain="solana",
                network="mainnet-beta",
                connector="raydium/clmm",
                method="execute-swap",
                params={
                    "walletAddress": "7B2UBtod3aH7nBCNhdMCVsXjHt8mcDmQxP6EfJfXEipG",
                    "baseToken": "USDC",
                    "quoteToken": "SOL",
                    "amount": 1.0,
                    "side": "SELL",
                },
                order_id=order_id1,
                tracked_order=self.swap_connector._in_flight_orders[order_id1]
            )
        )
        self.async_run_with_timeout(asyncio.sleep(0.1))

        # Second transaction within cache interval should not call estimate-gas again
        self.gateway_instance_mock.api_request = AsyncMock(side_effect=[
            self.buy_response  # Only execute-swap, no estimate-gas
        ])

        order_id2 = self.swap_connector.create_market_order_id(TradeType.BUY, self.trading_pair)
        self.swap_connector.start_tracking_order(
            order_id=order_id2,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("8.6"),
            amount=Decimal("1")
        )

        self.async_run_with_timeout(
            self.tx_handler.execute_transaction(
                chain="solana",
                network="mainnet-beta",
                connector="raydium/clmm",
                method="execute-swap",
                params={
                    "walletAddress": "7B2UBtod3aH7nBCNhdMCVsXjHt8mcDmQxP6EfJfXEipG",
                    "baseToken": "USDC",
                    "quoteToken": "SOL",
                    "amount": 1.0,
                    "side": "BUY",
                },
                order_id=order_id2,
                tracked_order=self.swap_connector._in_flight_orders[order_id2]
            )
        )
        self.async_run_with_timeout(asyncio.sleep(0.1))

        # Verify only one call was made (execute-swap)
        self.assertEqual(self.gateway_instance_mock.api_request.call_count, 1)

    def test_lp_open_position_transaction(self):
        """Test liquidity provision open position transaction"""
        # Mock responses for LP operation
        self.gateway_instance_mock.api_request = AsyncMock()
        self.gateway_instance_mock.api_request.side_effect = [
            # estimate-gas response
            {
                "feePerComputeUnit": 2000,
                "denomination": "microlamports",
                "timestamp": 1640000000.0
            },
            # open-position response
            {
                "signature": "lpOpenTx123",
                "status": 1,
                "confirmed": True,
                "data": {
                    "positionAddress": "somePositionAddress",
                    "lowerPrice": 7.5,
                    "upperPrice": 9.5
                },
                "fee": 0.005
            }
        ]

        # Create order manually
        order_id = self.lp_connector.create_market_order_id(TradeType.RANGE, self.trading_pair)
        self.lp_connector.start_tracking_order(
            order_id=order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.RANGE,
            price=Decimal("8.5"),
            amount=Decimal("110")  # base + quote in base terms
        )

        # Execute transaction
        self.async_run_with_timeout(
            self.tx_handler.execute_transaction(
                chain="solana",
                network="mainnet-beta",
                connector="raydium/clmm",
                method="open-position",
                params={
                    "walletAddress": "7B2UBtod3aH7nBCNhdMCVsXjHt8mcDmQxP6EfJfXEipG",
                    "baseToken": "USDC",
                    "quoteToken": "SOL",
                    "lowerPrice": 8.075,
                    "upperPrice": 8.925,
                    "baseTokenAmount": 100.0,
                    "quoteTokenAmount": 10.0,
                },
                order_id=order_id,
                tracked_order=self.lp_connector._in_flight_orders[order_id]
            )
        )

        # Let async operations complete
        self.async_run_with_timeout(asyncio.sleep(0.1))

        # Verify order was created
        self.assertIn(order_id, self.lp_connector._in_flight_orders)
        order = self.lp_connector._in_flight_orders[order_id]

        # Verify transaction details
        self.assertEqual(order.creation_transaction_hash, "lpOpenTx123")
        self.assertEqual(order.trade_type, TradeType.RANGE)

    def test_error_handling_in_transaction(self):
        """Test error handling when transaction execution fails"""
        # Mock API to raise exception
        self.gateway_instance_mock.api_request = AsyncMock()
        self.gateway_instance_mock.api_request.side_effect = [
            {"feePerComputeUnit": 1000, "denomination": "microlamports", "timestamp": 1640000000.0},
            Exception("Network error: Unable to connect to RPC endpoint")
        ]

        # Create order manually
        order_id = self.swap_connector.create_market_order_id(TradeType.SELL, self.trading_pair)
        self.swap_connector.start_tracking_order(
            order_id=order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("8.5"),
            amount=Decimal("1")
        )

        # Execute transaction
        self.async_run_with_timeout(
            self.tx_handler.execute_transaction(
                chain="solana",
                network="mainnet-beta",
                connector="raydium/clmm",
                method="execute-swap",
                params={
                    "walletAddress": "7B2UBtod3aH7nBCNhdMCVsXjHt8mcDmQxP6EfJfXEipG",
                    "baseToken": "USDC",
                    "quoteToken": "SOL",
                    "amount": 1.0,
                    "side": "SELL",
                },
                order_id=order_id,
                tracked_order=self.swap_connector._in_flight_orders[order_id]
            )
        )

        # Let async operations complete
        self.async_run_with_timeout(asyncio.sleep(0.2))

        # Verify order exists but with proper error handling
        order = self.swap_connector._in_flight_orders[order_id]
        # The order should still be tracked even if transaction failed
        self.assertIsNotNone(order)

    def test_parallel_transactions(self):
        """Test handling multiple parallel transactions"""
        # Mock responses for multiple transactions
        self.gateway_instance_mock.api_request = AsyncMock()

        # Prepare responses for 3 parallel transactions
        responses = []
        # Add estimate-gas response (shared by all due to caching)
        responses.append({"feePerComputeUnit": 1000, "denomination": "microlamports", "timestamp": 1640000000.0})

        # Add 3 successful swap responses
        for i in range(3):
            responses.append({
                "signature": f"parallelTx{i}",
                "status": 1,
                "confirmed": True,
                "data": {"baseAmount": "1000000", "quoteAmount": "8640700", "price": "8.6407"},
                "fee": 0.00215
            })

        self.gateway_instance_mock.api_request.side_effect = responses

        # Create multiple orders rapidly
        order_ids = []
        for i in range(3):
            trade_type = TradeType.SELL if i % 2 == 0 else TradeType.BUY
            order_id = self.swap_connector.create_market_order_id(trade_type, self.trading_pair)
            self.swap_connector.start_tracking_order(
                order_id=order_id,
                trading_pair=self.trading_pair,
                trade_type=trade_type,
                price=Decimal("8.5") if trade_type == TradeType.SELL else Decimal("8.6"),
                amount=Decimal("1")
            )

            # Execute transaction
            self.async_run_with_timeout(
                self.tx_handler.execute_transaction(
                    chain="solana",
                    network="mainnet-beta",
                    connector="raydium/clmm",
                    method="execute-swap",
                    params={
                        "walletAddress": "7B2UBtod3aH7nBCNhdMCVsXjHt8mcDmQxP6EfJfXEipG",
                        "baseToken": "USDC",
                        "quoteToken": "SOL",
                        "amount": 1.0,
                        "side": trade_type.name,
                    },
                    order_id=order_id,
                    tracked_order=self.swap_connector._in_flight_orders[order_id]
                )
            )
            order_ids.append(order_id)

        # Let all async operations complete
        self.async_run_with_timeout(asyncio.sleep(0.3))

        # Verify all orders completed successfully
        for i, order_id in enumerate(order_ids):
            order = self.swap_connector._in_flight_orders[order_id]
            self.assertEqual(order.creation_transaction_hash, f"parallelTx{i}")
            self.assertEqual(order.current_state, OrderState.FILLED)


if __name__ == "__main__":
    unittest.main()
