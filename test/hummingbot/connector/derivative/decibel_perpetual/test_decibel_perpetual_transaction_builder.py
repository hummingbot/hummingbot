from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_transaction_builder import (
    DecibelPerpetualTransactionBuilder,
)

# DecibelWriteDex is imported at module level in transaction_builder
TX_BUILDER_MODULE = "hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_transaction_builder"


class TestDecibelPerpetualTransactionBuilder(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = CONSTANTS.DEFAULT_DOMAIN
        cls.package_address = "0xpackage123"
        cls.fullnode_url = "https://api.mainnet.aptoslabs.com/v1"
        cls.api_key = "test_api_key"
        cls.gas_station_key = "test_gas_station_key"

    def setUp(self):
        super().setUp()
        self.log_records = []

        self.mock_auth = MagicMock(spec=DecibelPerpetualAuth)
        self.mock_auth.get_subaccount_address.return_value = "0xsubaccount123"
        self.mock_auth.account = MagicMock()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str):
        return any(record.levelname == log_level and message in record.getMessage() for record in self.log_records)

    def _create_builder(self, domain=None, gas_station_key=None):
        return DecibelPerpetualTransactionBuilder(
            auth=self.mock_auth,
            package_address=self.package_address,
            fullnode_url=self.fullnode_url,
            domain=domain or self.domain,
            api_key=self.api_key,
            gas_station_api_key=gas_station_key or self.gas_station_key,
        )

    def test_init(self):
        builder = self._create_builder()
        self.assertEqual(self.mock_auth, builder._auth)
        self.assertEqual(self.package_address, builder._package_address)
        self.assertEqual(self.fullnode_url, builder._fullnode_url)
        self.assertEqual(self.domain, builder._domain)
        self.assertEqual(self.api_key, builder._api_key)
        self.assertEqual(self.gas_station_key, builder._gas_station_api_key)
        self.assertIsNone(builder._write_dex)

    def test_logger(self):
        logger = DecibelPerpetualTransactionBuilder.logger()
        self.assertIsNotNone(logger)

    @patch("decibel.GasPriceManager")
    @patch(f"{TX_BUILDER_MODULE}.DecibelWriteDex")
    async def test_get_write_dex_mainnet(self, mock_write_dex, mock_gas_price_manager):
        mock_gas_instance = AsyncMock()
        mock_gas_price_manager.return_value = mock_gas_instance

        mock_dex_instance = AsyncMock()
        mock_write_dex.return_value = mock_dex_instance

        builder = self._create_builder(domain=CONSTANTS.DEFAULT_DOMAIN)
        DecibelPerpetualTransactionBuilder._logger = None

        result = await builder._get_write_dex()

        self.assertEqual(mock_dex_instance, result)
        mock_gas_price_manager.assert_called_once()
        mock_gas_instance.initialize.assert_awaited_once()
        mock_write_dex.assert_called_once()

    @patch("decibel.GasPriceManager")
    @patch(f"{TX_BUILDER_MODULE}.DecibelWriteDex")
    async def test_get_write_dex_testnet(self, mock_write_dex, mock_gas_price_manager):
        mock_gas_instance = AsyncMock()
        mock_gas_price_manager.return_value = mock_gas_instance

        mock_dex_instance = AsyncMock()
        mock_write_dex.return_value = mock_dex_instance

        builder = self._create_builder(domain=CONSTANTS.TESTNET_DOMAIN)
        DecibelPerpetualTransactionBuilder._logger = None

        result = await builder._get_write_dex()

        self.assertEqual(mock_dex_instance, result)
        call_args = mock_gas_price_manager.call_args
        self.assertIsNotNone(call_args)

    @patch("decibel.GasPriceManager")
    @patch(f"{TX_BUILDER_MODULE}.DecibelWriteDex")
    async def test_get_write_dex_without_gas_station_key(self, mock_write_dex, mock_gas_price_manager):
        mock_gas_instance = AsyncMock()
        mock_gas_price_manager.return_value = mock_gas_instance

        mock_dex_instance = AsyncMock()
        mock_write_dex.return_value = mock_dex_instance

        builder = self._create_builder(gas_station_key=None)
        DecibelPerpetualTransactionBuilder._logger = None

        result = await builder._get_write_dex()

        self.assertEqual(mock_dex_instance, result)

    @patch("decibel.GasPriceManager")
    @patch(f"{TX_BUILDER_MODULE}.DecibelWriteDex")
    async def test_get_write_dex_cached(self, mock_write_dex, mock_gas_price_manager):
        mock_gas_instance = AsyncMock()
        mock_gas_price_manager.return_value = mock_gas_instance

        mock_dex_instance = AsyncMock()
        mock_write_dex.return_value = mock_dex_instance

        builder = self._create_builder()
        DecibelPerpetualTransactionBuilder._logger = None

        result1 = await builder._get_write_dex()
        result2 = await builder._get_write_dex()

        self.assertEqual(result1, result2)
        mock_write_dex.assert_called_once()

    @patch("decibel.GasPriceManager")
    @patch(f"{TX_BUILDER_MODULE}.DecibelWriteDex")
    async def test_place_order_success(self, mock_write_dex_cls, mock_gas_price_manager):
        mock_gas_instance = AsyncMock()
        mock_gas_price_manager.return_value = mock_gas_instance

        mock_result = MagicMock()
        mock_result.transaction_hash = "0xtxhash123"
        mock_result.order_id = "order_456"
        mock_result.success = True

        mock_dex = AsyncMock()
        mock_dex.place_order.return_value = mock_result
        mock_write_dex_cls.return_value = mock_dex

        builder = self._create_builder()
        DecibelPerpetualTransactionBuilder._logger = None

        tx_hash, order_id, timestamp = await builder.place_order(
            market_id="BTC-USD",
            price=50000000000,
            size=1000000,
            is_buy=True,
        )

        self.assertEqual("0xtxhash123", tx_hash)
        self.assertEqual("order_456", order_id)
        self.assertIsInstance(timestamp, float)

        call_kwargs = mock_dex.place_order.call_args.kwargs
        self.assertEqual("BTC/USD", call_kwargs["market_name"])
        self.assertEqual(50000000000, call_kwargs["price"])
        self.assertEqual(1000000, call_kwargs["size"])
        self.assertTrue(call_kwargs["is_buy"])
        self.assertFalse(call_kwargs["is_reduce_only"])

    @patch("decibel.GasPriceManager")
    @patch(f"{TX_BUILDER_MODULE}.DecibelWriteDex")
    async def test_place_order_ioc(self, mock_write_dex_cls, mock_gas_price_manager):
        mock_gas_instance = AsyncMock()
        mock_gas_price_manager.return_value = mock_gas_instance

        mock_result = MagicMock()
        mock_result.transaction_hash = "0xtxhash"
        mock_result.order_id = "order_ioc"
        mock_result.success = True

        mock_dex = AsyncMock()
        mock_dex.place_order.return_value = mock_result
        mock_write_dex_cls.return_value = mock_dex

        builder = self._create_builder()
        DecibelPerpetualTransactionBuilder._logger = None

        await builder.place_order(
            market_id="ETH-USD",
            price=3000000000,
            size=500000,
            is_buy=False,
            is_ioc=True,
        )

        call_kwargs = mock_dex.place_order.call_args.kwargs
        tif = call_kwargs["time_in_force"]
        # TimeInForce.ImmediateOrCancel has value 2
        self.assertIn(tif, [2, "ImmediateOrCancel"])

    @patch("decibel.GasPriceManager")
    @patch(f"{TX_BUILDER_MODULE}.DecibelWriteDex")
    async def test_place_order_post_only(self, mock_write_dex_cls, mock_gas_price_manager):
        mock_gas_instance = AsyncMock()
        mock_gas_price_manager.return_value = mock_gas_instance

        mock_result = MagicMock()
        mock_result.transaction_hash = "0xtxhash"
        mock_result.order_id = "order_post"
        mock_result.success = True

        mock_dex = AsyncMock()
        mock_dex.place_order.return_value = mock_result
        mock_write_dex_cls.return_value = mock_dex

        builder = self._create_builder()
        DecibelPerpetualTransactionBuilder._logger = None

        await builder.place_order(
            market_id="ETH-USD",
            price=3000000000,
            size=500000,
            is_buy=True,
            is_post_only=True,
        )

        call_kwargs = mock_dex.place_order.call_args.kwargs
        tif = call_kwargs["time_in_force"]
        # TimeInForce.PostOnly has value 1
        self.assertIn(tif, [1, "PostOnly"])

    @patch("decibel.GasPriceManager")
    @patch(f"{TX_BUILDER_MODULE}.DecibelWriteDex")
    async def test_place_order_failure(self, mock_write_dex_cls, mock_gas_price_manager):
        mock_gas_instance = AsyncMock()
        mock_gas_price_manager.return_value = mock_gas_instance

        # Use PlaceOrderFailure from decibel SDK
        from decibel import PlaceOrderFailure
        mock_result = PlaceOrderFailure(error="Insufficient balance")

        mock_dex = AsyncMock()
        mock_dex.place_order.return_value = mock_result
        mock_write_dex_cls.return_value = mock_dex

        builder = self._create_builder()
        DecibelPerpetualTransactionBuilder._logger = None

        with self.assertRaises(IOError) as ctx:
            await builder.place_order(
                market_id="BTC-USD",
                price=50000000000,
                size=1000000,
                is_buy=True,
            )

        self.assertIn("Order placement failed", str(ctx.exception))
        self.assertIn("Insufficient balance", str(ctx.exception))

    @patch("decibel.GasPriceManager")
    @patch(f"{TX_BUILDER_MODULE}.DecibelWriteDex")
    async def test_place_order_failure_with_reason(self, mock_write_dex_cls, mock_gas_price_manager):
        mock_gas_instance = AsyncMock()
        mock_gas_price_manager.return_value = mock_gas_instance

        from decibel import PlaceOrderFailure
        mock_result = PlaceOrderFailure(error="Market not found", reason="Market not found")

        mock_dex = AsyncMock()
        mock_dex.place_order.return_value = mock_result
        mock_write_dex_cls.return_value = mock_dex

        builder = self._create_builder()
        DecibelPerpetualTransactionBuilder._logger = None

        with self.assertRaises(IOError) as ctx:
            await builder.place_order(
                market_id="BTC-USD",
                price=50000000000,
                size=1000000,
                is_buy=True,
            )

        self.assertIn("Market not found", str(ctx.exception))

    @patch("decibel.GasPriceManager")
    @patch(f"{TX_BUILDER_MODULE}.DecibelWriteDex")
    async def test_place_order_fallback_to_tx_hash(self, mock_write_dex_cls, mock_gas_price_manager):
        mock_gas_instance = AsyncMock()
        mock_gas_price_manager.return_value = mock_gas_instance

        mock_result = MagicMock()
        mock_result.transaction_hash = "0xtxhash789"
        mock_result.order_id = None
        mock_result.success = True

        mock_dex = AsyncMock()
        mock_dex.place_order.return_value = mock_result
        mock_write_dex_cls.return_value = mock_dex

        builder = self._create_builder()
        DecibelPerpetualTransactionBuilder._logger = None

        tx_hash, order_id, _ = await builder.place_order(
            market_id="BTC-USD",
            price=50000000000,
            size=1000000,
            is_buy=True,
        )

        self.assertEqual("0xtxhash789", tx_hash)
        self.assertEqual("0xtxhash789", order_id)

    @patch("decibel.GasPriceManager")
    @patch(f"{TX_BUILDER_MODULE}.DecibelWriteDex")
    async def test_cancel_order_success(self, mock_write_dex_cls, mock_gas_price_manager):
        mock_gas_instance = AsyncMock()
        mock_gas_price_manager.return_value = mock_gas_instance

        mock_dex = AsyncMock()
        mock_dex.cancel_order.return_value = {
            "hash": "0xcancelhash123",
            "success": True,
            "gas_used": "1000",
        }
        mock_write_dex_cls.return_value = mock_dex

        builder = self._create_builder()
        DecibelPerpetualTransactionBuilder._logger = None

        tx_hash, timestamp = await builder.cancel_order(
            market_id="BTC-USD",
            order_id="order_456",
        )

        self.assertEqual("0xcancelhash123", tx_hash)
        self.assertIsInstance(timestamp, float)

        call_kwargs = mock_dex.cancel_order.call_args.kwargs
        self.assertEqual("BTC/USD", call_kwargs["market_name"])
        self.assertEqual("order_456", call_kwargs["order_id"])

    @patch("decibel.GasPriceManager")
    @patch(f"{TX_BUILDER_MODULE}.DecibelWriteDex")
    async def test_cancel_order_no_hash(self, mock_write_dex_cls, mock_gas_price_manager):
        mock_gas_instance = AsyncMock()
        mock_gas_price_manager.return_value = mock_gas_instance

        mock_dex = AsyncMock()
        mock_dex.cancel_order.return_value = {
            "hash": None,
            "success": True,
        }
        mock_write_dex_cls.return_value = mock_dex

        builder = self._create_builder()
        DecibelPerpetualTransactionBuilder._logger = None

        tx_hash, _ = await builder.cancel_order(
            market_id="BTC-USD",
            order_id="order_456",
        )

        self.assertIsNone(tx_hash)

    async def test_close(self):
        builder = self._create_builder()
        builder._write_dex = MagicMock()

        await builder.close()

        self.assertIsNone(builder._write_dex)

    async def test_close_no_write_dex(self):
        builder = self._create_builder()
        await builder.close()
