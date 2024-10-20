import asyncio
import re
from decimal import Decimal
from typing import Awaitable, Union
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from substrateinterface.exceptions import SubstrateRequestException

from hummingbot.connector.exchange.chainflip_lp import chainflip_lp_constants as CONSTANTS
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor import RPCQueryExecutor


class RPCQueryExecutorTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_asset_dict = {"chain": "Ethereum", "asset": "ETH"}
        cls.quote_asset_dict = {"chain": "Ethereum", "asset": "USDC"}
        cls.base_asset = "ETH/Ethereum"
        cls.quote_asset = "USDC/Ethereum"

    def setUp(self) -> None:
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        self.log_records = []

    def tearDown(self) -> None:
        super().tearDown()
        self.async_loop.stop()
        self.async_loop.close()
        asyncio.set_event_loop(self._original_async_loop)
        self._logs_event = None

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.async_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def is_logged(self, log_level: str, message: Union[str, re.Pattern]) -> bool:
        expression = (
            re.compile(
                f"^{message}$".replace(".", r"\.")
                .replace("?", r"\?")
                .replace("/", r"\/")
                .replace("(", r"\(")
                .replace(")", r"\)")
                .replace("[", r"\[")
                .replace("]", r"\]")
            )
            if isinstance(message, str)
            else message
        )
        return any(
            record.levelname == log_level and expression.match(record.getMessage()) is not None
            for record in self.log_records
        )

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_execute_api_request_successful(self, mock_response: MagicMock):
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._lp_api_instance = Mock()
        response_data = [{"chain": "Ethereum", "asset": "USDT"}]
        mock_response.return_value = response_data
        response = self.async_run_with_timeout(rpc_executor._execute_api_request(MagicMock()))
        mock_response.assert_called_once()
        self.assertIn("data", response)
        self.assertIn("status", response)
        self.assertTrue(response["status"])
        self.assertEqual(response["data"], response_data)
        self.assertTrue(isinstance(response["data"], list))

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_execute_api_request_handles_exceptions(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._lp_api_instance = Mock()
        response = self.async_run_with_timeout(rpc_executor._execute_api_request(MagicMock()))
        self.assertIn("data", response)
        self.assertIn("status", response)
        self.assertFalse(response["status"])
        self.assertEqual(response["data"], return_data)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_execute_rpc_request_successful(self, mock_response: MagicMock):
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._rpc_instance = Mock()
        response_data = [{"chain": "Ethereum", "asset": "USDT"}]
        mock_response.return_value = response_data
        response = self.async_run_with_timeout(rpc_executor._execute_rpc_request(MagicMock()))
        mock_response.assert_called_once()
        self.assertIn("data", response)
        self.assertIn("status", response)
        self.assertTrue(response["status"])
        self.assertTrue(isinstance(response["data"], list))

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_execute_rpc_request_handles_exceptions(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._rpc_instance = Mock()
        response = self.async_run_with_timeout(rpc_executor._execute_rpc_request(MagicMock()))
        self.assertIn("data", response)
        self.assertIn("status", response)
        self.assertFalse(response["status"])
        self.assertEqual(response["data"], return_data)

    def test_calculate_ticks(self):
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        base_asset = {"chain": "Ethereum", "asset": "USDT"}
        quote_asset = {"chain": "Ethereum", "asset": "USDT"}
        tick = rpc_executor._calculate_tick(2000.00, base_asset, quote_asset)
        self.assertLessEqual(tick, CONSTANTS.UPPER_TICK_BOUND)
        self.assertGreaterEqual(tick, CONSTANTS.LOWER_TICK_BOUND)

    def test_listen_to_order_fills(self):
        pass

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.SubstrateInterface")
    def test_start_instance(self, mock_interface: MagicMock):
        mock_interface.return_value = MagicMock()
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._start_instance(MagicMock())
        mock_interface.assert_called_once()

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.SubstrateInterface")
    def test_start_instance_raises_error(self, mock_interface: MagicMock):
        error_data = {"code": -23000, "detail": "Method not found"}
        mock_interface.side_effect = SubstrateRequestException(error_data)

        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        with self.assertRaises(SubstrateRequestException):
            rpc_executor._start_instance(MagicMock())
            self.assertTrue(self.is_logged("ERROR", str(error_data)))

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_all_asset_successful(self, mock_response: MagicMock):
        return_data = {
            "result": [
                {"chain": "Ethereum", "asset": "ETH"},
                {"chain": "Ethereum", "asset": "FLIP"},
                {"chain": "Ethereum", "asset": "USDC"},
                {"chain": "Ethereum", "asset": "USDT"},
                {"chain": "Polkadot", "asset": "DOT"},
                {"chain": "Bitcoin", "asset": "BTC"},
                {"chain": "Arbitrum", "asset": "ETH"},
                {"chain": "Arbitrum", "asset": "USDC"},
            ]
        }
        mock_response.return_value = return_data
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._rpc_instance = Mock()
        data = self.async_run_with_timeout(rpc_executor.all_assets())
        self.assertTrue(isinstance(data, list))
        self.assertEqual(len(data), 8)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_all_asset_exception_returns_empty_list(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._rpc_instance = Mock()
        data = self.async_run_with_timeout(rpc_executor.all_assets())
        self.assertTrue(isinstance(data, list))
        self.assertEqual(len(data), 0)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_all_market_successful(self, mock_response: MagicMock):
        return_data = {
            "result": {
                "fees": {
                    "Ethereum": {
                        "ETH": {
                            "limit_order_fee_hundredth_pips": 500,
                            "range_order_fee_hundredth_pips": 500,
                            "range_order_total_fees_earned": {
                                "base": "0x3d4a754fc1d2302",  # noqa: mock
                                "quote": "0x3689782a",  # noqa: mock
                            },
                            "limit_order_total_fees_earned": {
                                "base": "0x83c94dd54804790a",  # noqa: mock
                                "quote": "0x670a76ae0",  # noqa: mock
                            },
                            "range_total_swap_inputs": {
                                "base": "0x1dc18b046dde67f2b0",  # noqa: mock
                                "quote": "0x1a774f80e62",  # noqa: mock
                            },
                            "limit_total_swap_inputs": {
                                "base": "0x369c2e5bafeffddab46",  # noqa: mock
                                "quote": "0x2be491b4d31d",  # noqa: mock
                            },
                            "quote_asset": {"chain": "Ethereum", "asset": "USDC"},
                        },
                    }
                }
            }
        }
        mock_response.return_value = return_data
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._rpc_instance = Mock()
        data = self.async_run_with_timeout(rpc_executor.all_markets())
        self.assertEqual(len(data), 1)
        self.assertEqual(type(data[0]["symbol"]), str)
        self.assertIn(self.base_asset, data[0]["symbol"].split("-"))
        self.assertIn(self.quote_asset, data[0]["symbol"].split("-"))

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_all_market_exception_returns_empty_list(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._rpc_instance = Mock()
        data = self.async_run_with_timeout(rpc_executor.all_markets())
        self.assertTrue(isinstance(data, list))
        self.assertEqual(len(data), 0)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor._execute_rpc_request")
    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor._execute_api_request")
    def test_connection_status_fail_when_one_request_is_false(self, mock_response: MagicMock, mock_rpc_response: MagicMock):
        mock_response.return_value = {"status": False, "data": []}
        mock_rpc_response.return_value = {"status": True, "data": []}
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._lp_api_instance = Mock()
        rpc_executor._rpc_instance = Mock()
        data = self.async_run_with_timeout(rpc_executor.check_connection_status())
        self.assertFalse(data)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_get_market_price_successful(self, mock_response: MagicMock):
        mock_response.return_value = {
            "result": {
                "base_asset": {"chain": "Bitcoin", "asset": "BTC"},
                "quote_asset": {"chain": "Ethereum", "asset": "USDC"},
                "sell": "0x10b09273676d13f5d254e20a20",  # noqa: mock
                "buy": "0x10b09273676d13f5d254e20a20",  # noqa: mock
                "range_order": "0x10b09273676d13f5d254e20a20",  # noqa: mock
            }
        }
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._rpc_instance = Mock()
        data = self.async_run_with_timeout(
            rpc_executor.get_market_price({"chain": "Ethereum", "asset": "ETH"}, {"chain": "Ethereum", "asset": "USDC"})
        )
        self.assertTrue(isinstance(data, dict))
        self.assertIn("price", data)
        self.assertIn("sell", data)
        self.assertIn("buy", data)
        self.assertTrue(isinstance(data["buy"], float))
        self.assertTrue(isinstance(data["sell"], float))
        self.assertTrue(isinstance(data["price"], float))

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor._execute_rpc_request")
    def test_get_market_price_exception_returns_none(self, mock_response: MagicMock):
        mock_response.return_value = {"status": False, "data": []}
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._rpc_instance = Mock()
        data = self.async_run_with_timeout(
            rpc_executor.get_market_price({"chain": "Ethereum", "asset": "ETH"}, {"chain": "Ethereum", "asset": "USDC"})
        )
        self.assertIsNone(data)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_all_balances_successful(self, mock_response: MagicMock):
        return_data = {
            "result": {
                "Ethereum": {
                    "ETH": "0x2386f26fc0bda2",  # noqa: mock
                    "FLIP": "0xde0b6b3a763ec60",  # noqa: mock
                    "USDC": "0x8bb50bca00",  # noqa: mock
                },
            }
        }
        mock_response.return_value = return_data
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._lp_api_instance = Mock()
        data = self.async_run_with_timeout(rpc_executor.get_all_balances())
        self.assertEqual(type(data), dict)
        self.assertEqual(len(data), 3)
        self.assertEqual(type(data[f"{self.base_asset}"]), Decimal)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_all_balances_exception_returns_empty_list(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._lp_api_instance = Mock()
        data = self.async_run_with_timeout(rpc_executor.get_all_balances())
        self.assertTrue(isinstance(data, list))
        self.assertEqual(len(data), 0)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_get_open_orders_exception_returns_empty_list(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._rpc_instance = Mock()
        data = self.async_run_with_timeout(rpc_executor.get_open_orders(self.base_asset_dict, self.quote_asset_dict))
        self.assertTrue(isinstance(data, list))
        self.assertEqual(len(data), 0)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_place_limit_order_successful(self, mock_response: MagicMock):
        return_data = {
            "result": {
                "tx_details": {
                    "tx_hash": "0x3cb78cdbbfc34634e33d556a94ee7438938b65a5b852ee523e4fc3c0ec3f8151",  # noqa: mock
                    "response": [
                        {
                            "base_asset": "ETH",
                            "quote_asset": "USDC",
                            "side": "buy",
                            "id": "0x11",  # noqa: mock
                            "tick": 50,
                            "sell_amount_total": "0x100000",  # noqa: mock
                            "collected_fees": "0x0",  # noqa: mock
                            "bought_amount": "0x0",  # noqa: mock
                            "sell_amount_change": {"increase": "0x100000"},  # noqa: mock
                        }
                    ],
                }
            },
        }
        mock_response.return_value = return_data
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._lp_api_instance = Mock()
        data = self.async_run_with_timeout(
            rpc_executor.place_limit_order(self.base_asset_dict, self.quote_asset_dict, "11", 122000.00, "buy", 12000)
        )
        self.assertTrue(isinstance(data, dict))
        self.assertIn("order_id", data)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_place_limit_order_exception_returns_False(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._lp_api_instance = Mock()
        data = self.async_run_with_timeout(
            rpc_executor.place_limit_order(self.base_asset_dict, self.quote_asset_dict, "11", 122000.00, "buy", 12000)
        )
        self.assertFalse(data)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_cancel_order_exception_returns_False(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._lp_api_instance = Mock()
        data = self.async_run_with_timeout(
            rpc_executor.cancel_order(self.base_asset_dict, self.quote_asset_dict, "11", "buy")
        )
        self.assertFalse(data)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_get_account_order_fills_exception_returns_empty_list(self, mock_response: MagicMock):
        return_data = {"code": -23000, "detail": "Method not found"}
        return_asset_data = [self.base_asset_dict, self.base_asset_dict]
        mock = AsyncMock()
        mock.return_value = return_asset_data
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._rpc_instance = Mock()
        data = self.async_run_with_timeout(rpc_executor.get_account_order_fills())
        self.assertTrue(isinstance(data, list))
        self.assertEqual(len(data), 0)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_get_orderbook_successful(self, mock_response: MagicMock):
        return_data = {
            "result": {
                "asks": [
                    {"amount": "0x54b2cec31723f8b04", "sqrt_price": "0x2091b342e50d7f26cdc582"},  # noqa: mock
                    {"amount": "0x5b475d13fc0374e", "sqrt_price": "0x1e38a26ccc8cad8ff5ed7d0e"},  # noqa: mock
                    {"amount": "0x625ecb4a48690", "sqrt_price": "0x1c0ae64c925b19f39a41ff17bd"},  # noqa: mock
                    {"amount": "0x6a03445844f", "sqrt_price": "0x1a055f3578ef64659516605ff66d"},  # noqa: mock
                ],
                "bids": [
                    {"amount": "0x9a488cdb615edf25fd", "sqrt_price": "0x62bac2a2b8f0b98b9ceb"},  # noqa: mock
                    {"amount": "0x1217d98319cd00bc28de", "sqrt_price": "0x349e212a7a008282ff9"},  # noqa: mock
                    {"amount": "0x21f2ffe1f3cc8bebab567", "sqrt_price": "0x1c0ae0758c0acee837"},  # noqa: mock
                    {"amount": "0x3fb3690cb0511666161b4d", "sqrt_price": "0xef1f790088e3f323"},  # noqa: mock
                ],
            },
        }
        mock_response.return_value = return_data
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        rpc_executor._lp_api_instance = Mock()
        data = self.async_run_with_timeout(
            rpc_executor.get_orderbook(self.base_asset_dict, self.quote_asset_dict)
        )
        self.assertIn("asks", data)
        self.assertIn("bids", data)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_get_order_status_successful(self, mock_response: MagicMock):
        return_data = {
            "result": {
                "limit_orders": {
                    "asks": [
                        {
                            "lp": "cFLGvPhhrribWCx9id5kLVqwiFK4QiVNjQ6ViyaRFF2Nrgq7j",  # noqa: mock
                            "id": "0x0",  # noqa: mock
                            "tick": -195623,
                            "sell_amount": "0x56d3a03776ce8ba0",  # noqa: mock
                            "fees_earned": "0x0",  # noqa: mock
                            "original_sell_amount": "0x56d3a03776ce8ba0"  # noqa: mock
                        },
                    ],
                    "bids": [
                        {
                            "lp": "cFLGvPhhrribWCx9id5kLVqwiFK4QiVNjQ6ViyaRFF2Nrgq7j",  # noqa: mock
                            "id": "0x0",  # noqa: mock
                            "tick": -195622,
                            "sell_amount": "0x4a817c800",  # noqa: mock
                            "fees_earned": "0x0",  # noqa: mock
                            "original_sell_amount": "0x4a817c800"  # noqa: mock
                        },
                    ]
                },
            }
        }
        mock_response.return_value = return_data
        rpc_executor = RPCQueryExecutor(
            MagicMock(),
            MagicMock(),
            "cFLGvPhhrribWCx9id5kLVqwiFK4QiVNjQ6ViyaRFF2Nrgq7j"  # noqa: mock
        )
        rpc_executor._rpc_instance = Mock()
        data = self.async_run_with_timeout(
            rpc_executor.get_order_status(
                "0x0",  # noqa: mock,
                "sell",
                self.base_asset_dict,
                self.quote_asset_dict
            )
        )
        self.assertIsNotNone(data)
        self.assertIsInstance(data, dict)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor.run_in_thread")
    def test_get_order_status_failure_raises_exeception(self, mock_response: MagicMock):
        mock_response.side_effect = SubstrateRequestException({"data": "Method Not Found"})
        rpc_executor = RPCQueryExecutor(
            MagicMock(),
            MagicMock(),
            "cFLGvPhhrribWCx9id5kLVqwiFK4QiVNjQ6ViyaRFF2Nrgq7j"  # noqa: mock
        )
        rpc_executor._rpc_instance = Mock()

        with self.assertRaises(RuntimeError):
            self.async_run_with_timeout(
                rpc_executor.get_order_status(
                    "0x0",  # noqa: mock,
                    "sell",
                    self.base_asset_dict,
                    self.quote_asset_dict
                )
            )
