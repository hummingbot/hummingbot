import asyncio
import re

from typing import Awaitable, Union
from unittest import TestCase
from unittest.mock import MagicMock, patch, AsyncMock

from substrateinterface.exceptions import SubstrateRequestException, ConfigurationError

from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor import RPCQueryExecutor

class RPCQueryExecutorTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        self.log_records = []

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.async_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret
    def is_logged(self, log_level: str, message: Union[str, re.Pattern]) -> bool:
        expression = (
            re.compile(
                f"^{message}$"
                .replace(".", r"\.")
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
    
    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor._rpc_instance")
    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor._execute_api_request.response")
    def test_execute_api_request_successful(self, mock_response: MagicMock,mock_api_instance:MagicMock):
        return_data = [{"chain": "Ethereum", "asset":"ETH"}]
        mock_response.return_value = return_data
        mock_api_instance.return_value = MagicMock()
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        response = self.async_run_with_timeout(rpc_executor._execute_api_request(MagicMock()))
        
        self.assertTrue(response["status"])
        self.assertEqual(response["data"], return_data)

    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor._rpc_instance")
    @patch("hummingbot.connector.exchange.chainflip_lp.chainflip_lp_rpc_executor.RPCQueryExecutor._execute_api_request.response")
    def test_execute_api_query_handles_exceptions(self,mock_response: MagicMock,mock_api_instance:MagicMock):
        return_data = {"code":-23000,"detail":"Method not found"}
        mock_api_instance.return_value = MagicMock()
        mock_response.side_effect = SubstrateRequestException(return_data)
        rpc_executor = RPCQueryExecutor(MagicMock(), MagicMock(), MagicMock())
        response = self.async_run_with_timeout(rpc_executor._execute_api_request(MagicMock()))
        self.assertFalse(response["status"])
        self.assertEqual(response["data"], return_data)
        
    def test_execute_rpc_request(self):
        pass
    def test_subscribe_to_api_event(self):
        pass
    def test_subscribe_to_rpc_events(self):
        pass
    def test_calculate_ticks(self):
        pass
    def test_listen_to_order_fills(self):
        pass
    def test_listen_to_market_price_updates(self):
        pass