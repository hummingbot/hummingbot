import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os
import requests
from web3 import Web3
from web3.exceptions import ContractLogicError

current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file_path))))
sys.path.append(project_root)

from hummingbot.fluxlayer_api.rfq import get_single_exchange_rfq

class TestGetSingleExchangeRFQ(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    @patch('hummingbot.fluxlayer_api.rfq.parse_chain_token')
    @patch('hummingbot.fluxlayer_api.rfq.get_token_price')
    @patch('hummingbot.fluxlayer_api.rfq.calculate_gas_fee')
    @patch('hummingbot.fluxlayer_api.rfq.calculate_price_impact')
    @patch('hummingbot.fluxlayer_api.rfq.cleanup')
    def test_successful_rfq(self, mock_cleanup, mock_calc_impact, mock_calc_gas, 
                          mock_get_price, mock_parse_token):
        """成功获取RFQ​"""
        # Setup mocks
        mock_parse_token.side_effect = [("ETH", "ETH"), ("BTC", "BTC")]
        mock_get_price.side_effect = [
            {"asks": [("3500", "10")]},  # src price
            {"asks": [("40000", "5")]}  # tar price
        ]
        mock_calc_gas.return_value = 0.001
        mock_calc_impact.return_value = {
            'average_price': 40000,
            'price_impact': 0.0001
        }
        mock_cleanup.return_value = AsyncMock()

        # Run test
        result = self.loop.run_until_complete(
            get_single_exchange_rfq(
                src_chain="ETH_ETH",
                src_token="ETH",
                src_amount=1.0,
                tar_chain="BTC_BTC",
                tar_token="BTC",
                exchange_name="binance"
            )
        )

        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["src_price"], 3500)
        self.assertEqual(result["tar_price"], 40000 * 1.004)  # price with small impact
        self.assertEqual(result["exchange"], "binance")
        mock_cleanup.assert_awaited()

    @patch('hummingbot.fluxlayer_api.rfq.parse_chain_token')
    @patch('hummingbot.fluxlayer_api.rfq.get_token_price')
    @patch('hummingbot.fluxlayer_api.rfq.cleanup')
    def test_no_src_price(self, mock_cleanup, mock_get_price, mock_parse_token):
        """无source token价格​"""
        # Setup mocks
        mock_parse_token.side_effect = [("ETH", "ETH"), ("BTC", "BTC")]
        mock_get_price.return_value = None  # No price data
        mock_cleanup.return_value = AsyncMock()

        # Run test
        result = self.loop.run_until_complete(
            get_single_exchange_rfq(
                src_chain="ETH_ETH",
                src_token="ETH",
                src_amount=1.0,
                tar_chain="BTC_BTC",
                tar_token="BTC"
            )
        )

        # Assertions
        self.assertIsNone(result)
        mock_cleanup.assert_awaited()

    @patch('hummingbot.fluxlayer_api.rfq.parse_chain_token')
    @patch('hummingbot.fluxlayer_api.rfq.get_token_price')
    @patch('hummingbot.fluxlayer_api.rfq.cleanup')
    def test_no_tar_price(self, mock_cleanup, mock_get_price, mock_parse_token):
        """无target token价格​"""
        # Setup mocks
        mock_parse_token.side_effect = [("ETH", "ETH"), ("BTC", "BTC")]
        mock_get_price.side_effect = [
            {"asks": [("3500", "10")]},  # src price
            None  # No tar price
        ]
        mock_cleanup.return_value = AsyncMock()

        # Run test
        result = self.loop.run_until_complete(
            get_single_exchange_rfq(
                src_chain="ETH_ETH",
                src_token="ETH",
                src_amount=1.0,
                tar_chain="BTC_BTC",
                tar_token="BTC"
            )
        )

        # Assertions
        self.assertIsNone(result)
        mock_cleanup.assert_awaited()

    @patch('hummingbot.fluxlayer_api.rfq.parse_chain_token')
    @patch('hummingbot.fluxlayer_api.rfq.get_token_price')
    @patch('hummingbot.fluxlayer_api.rfq.calculate_gas_fee')
    @patch('hummingbot.fluxlayer_api.rfq.calculate_price_impact')
    @patch('hummingbot.fluxlayer_api.rfq.cleanup')
    def test_high_price_impact(self, mock_cleanup, mock_calc_impact, mock_calc_gas,
                             mock_get_price, mock_parse_token):
        """高价格影响​"""
        # Setup mocks
        mock_parse_token.side_effect = [("ETH", "ETH"), ("BTC", "BTC")]
        mock_get_price.side_effect = [
            {"asks": [("3500", "10")]},  # src price
            {"asks": [("40000", "5")]}  # tar price
        ]
        mock_calc_gas.return_value = 0.001
        mock_calc_impact.return_value = {
            'average_price': 40000,
            'price_impact': 0.002  # High impact (0.02%)
        }
        mock_cleanup.return_value = AsyncMock()

        # Run test
        result = self.loop.run_until_complete(
            get_single_exchange_rfq(
                src_chain="ETH_ETH",
                src_token="ETH",
                src_amount=1.0,
                tar_chain="BTC_BTC",
                tar_token="BTC"
            )
        )

        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["tar_price"], 40000 * 1.01)  # price with high impact

    @patch('hummingbot.fluxlayer_api.rfq.parse_chain_token')
    @patch('hummingbot.fluxlayer_api.rfq.get_token_price')
    @patch('hummingbot.fluxlayer_api.rfq.cleanup')
    def test_exception_handling(self, mock_cleanup, mock_get_price, mock_parse_token):
        """异常处理​"""
        # Setup to raise exception
        mock_parse_token.side_effect = Exception("Parse error")
        mock_cleanup.return_value = AsyncMock()

        # Run test
        result = self.loop.run_until_complete(
            get_single_exchange_rfq(
                src_chain="ETH_ETH",
                src_token="ETH",
                src_amount=1.0,
                tar_chain="BTC_BTC",
                tar_token="BTC"
            )
        )

        # Assertions
        self.assertIsNone(result)
        mock_cleanup.assert_awaited()

from hummingbot.fluxlayer_api.rfq import calculate_price_impact

class TestCalculatePriceImpact(unittest.TestCase):
    def test_full_order_execution(self):
        """测试预算足够吃完整档位的情况"""
        asks = [("100", "10"), ("101", "5"), ("102", "3")]
        result = calculate_price_impact(asks, budget_usdt=1000)
        
        self.assertEqual(result['final_price'], 100.0)
        self.assertEqual(result['total_amount'], 10.0)
        self.assertEqual(result['average_price'], 100.0)
        self.assertEqual(result['price_impact'], 0.0)

    def test_partial_order_execution(self):
        """测试预算只能部分吃单的情况"""
        asks = [("100", "10"), ("101", "5"), ("102", "3")]
        result = calculate_price_impact(asks, budget_usdt=500)
        
        self.assertEqual(result['final_price'], 100.0)
        self.assertEqual(result['total_amount'], 5.0)
        self.assertEqual(result['average_price'], 100.0)
        self.assertEqual(result['price_impact'], 0.0)

    def test_multiple_level_execution(self):
        """测试需要吃多个档位的情况"""
        asks = [("100", "5"), ("101", "5"), ("102", "10")]
        result = calculate_price_impact(asks, budget_usdt=1395)
        
        self.assertEqual(result['final_price'], 102.0)
        self.assertAlmostEqual(result['total_amount'], 5 + 5 + 390/102, places=2)
        self.assertAlmostEqual(result['average_price'], 1395/(5 + 5 + 390/102), places=2)
        self.assertEqual(result['price_impact'], 102-100 / 100 * 100)

    def test_insufficient_budget(self):
        """测试预算不足的情况"""
        asks = [("100", "0.1")]
        result = calculate_price_impact(asks, budget_usdt=5)
        
        self.assertEqual(result['final_price'], 100.0)
        self.assertEqual(result['total_amount'], 0.05)
        self.assertEqual(result['average_price'], 100.0)
        self.assertEqual(result['price_impact'], 0.0)

    def test_empty_orderbook(self):
        """测试空订单簿的情况"""
        asks = []
        result = calculate_price_impact(asks)
        
        self.assertIsNone(result['final_price'])
        self.assertEqual(result['total_amount'], 0.0)
        self.assertIsNone(result['average_price'])
        self.assertEqual(result['price_impact'], 0.0)

    def test_zero_budget(self):
        """测试零预算的情况"""
        asks = [("100", "10"), ("101", "5")]
        result = calculate_price_impact(asks, budget_usdt=0)
        
        self.assertIsNone(result['final_price'])
        self.assertEqual(result['total_amount'], 0.0)
        self.assertIsNone(result['average_price'])
        self.assertEqual(result['price_impact'], 0.0)

from hummingbot.fluxlayer_api.get_chain_gas import get_gas_prices, get_btc_fee

class TestGetGasPrices(unittest.TestCase):
    
    @patch('requests.get')
    def test_ethereum_success(self, mock_get):
        # 模拟Etherscan成功响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "1",
            "result": {
                "ProposeGasPrice": "30",
                "FastGasPrice": "35"
            }
        }
        mock_get.return_value = mock_response

        result = get_gas_prices("Ethereum")
        
        self.assertEqual(result, {
            "base_fee": "30",
            "priority_fee": "35"
        })
        mock_get.assert_called_with(
            "https://api.etherscan.io/api",
            params={
                "module": "gastracker",
                "action": "gasoracle",
                "apikey": "R7R78C3U98KZ2MVQQE5XGRG1VCVFQSAYAU"
            }
        )

    @patch('requests.get')
    def test_ethereum_api_error(self, mock_get):
        # 模拟API返回错误状态
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "0",
            "message": "Invalid API Key"
        }
        mock_get.return_value = mock_response

        result = get_gas_prices("Ethereum")
        
        self.assertEqual(result, "Error: Invalid API Key")

    @patch('requests.get')
    def test_ethereum_http_error(self, mock_get):
        # 模拟HTTP错误
        mock_get.side_effect = requests.exceptions.HTTPError("404 Not Found")

        result = get_gas_prices("Ethereum")
    
        self.assertIn("HTTP Error", result)

    def test_unknown_chain(self):
        # 测试未知区块链
        result = get_gas_prices("Solana")
        
        self.assertEqual(result, {})

if __name__ == '__main__':
    unittest.main()