from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from unittest.mock import MagicMock, Mock, PropertyMock, patch

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import TradeType
from hummingbot.smart_components.executors.data_types import ConnectorPair
from hummingbot.smart_components.executors.xemm_executor.data_types import XEMMExecutorConfig
from hummingbot.smart_components.executors.xemm_executor.xemm_executor import XEMMExecutor
from hummingbot.smart_components.models.base import SmartComponentStatus
from hummingbot.smart_components.models.executors import TrackedOrder
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class TestXEMMExecutor(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
    def setUp(self):
        super().setUp()
        self.strategy = self.create_mock_strategy()
        self.xemm_base_config = self.base_config
        self.update_interval = 0.5
        self.executor = XEMMExecutor(self.strategy, self.xemm_base_config, self.update_interval)
        self.set_loggers(loggers=[self.executor.logger()])

    @property
    def base_config(self) -> XEMMExecutorConfig:
        return XEMMExecutorConfig(
            timestamp=1234,
            buying_market=ConnectorPair(connector_name='binance', trading_pair='ETH-USDT'),
            selling_market=ConnectorPair(connector_name='kucoin', trading_pair='ETH-USDT'),
            maker_side=TradeType.BUY,
            order_amount=Decimal('1'),
            min_profitability=Decimal('0.01'),
            target_profitability=Decimal('0.015'),
            max_profitability=Decimal('0.02'),
        )

    @staticmethod
    def create_mock_strategy():
        market = MagicMock()
        market_info = MagicMock()
        market_info.market = market

        strategy = MagicMock(spec=ScriptStrategyBase)
        type(strategy).market_info = PropertyMock(return_value=market_info)
        type(strategy).trading_pair = PropertyMock(return_value="ETH-USDT")
        strategy.buy.side_effect = ["OID-BUY-1", "OID-BUY-2", "OID-BUY-3"]
        strategy.sell.side_effect = ["OID-SELL-1", "OID-SELL-2", "OID-SELL-3"]
        strategy.cancel.return_value = None
        strategy.connectors = {
            "binance": MagicMock(spec=ConnectorBase),
            "kucoin": MagicMock(spec=ConnectorBase),
        }
        return strategy

    def test_is_arbitrage_valid(self):
        self.assertTrue(self.executor.is_arbitrage_valid('ETH-USDT', 'ETH-USDT'))
        self.assertTrue(self.executor.is_arbitrage_valid('ETH-BUSD', 'ETH-USDT'))
        self.assertTrue(self.executor.is_arbitrage_valid('ETH-USDT', 'WETH-USDT'))
        self.assertFalse(self.executor.is_arbitrage_valid('ETH-USDT', 'BTC-USDT'))
        self.assertFalse(self.executor.is_arbitrage_valid('ETH-USDT', 'ETH-BTC'))

    def test_net_pnl_quote(self):
        self.executor._status = SmartComponentStatus.TERMINATED
        self.executor.maker_order = Mock(spec=TrackedOrder)
        self.executor.taker_order = Mock(spec=TrackedOrder)
        self.executor.maker_order.executed_amount_base = Decimal('1')
        self.executor.taker_order.executed_amount_base = Decimal('1')
        self.executor.maker_order.average_executed_price = Decimal('100')
        self.executor.taker_order.average_executed_price = Decimal('101')

    @patch.object(XEMMExecutor, 'place_order')
    def test_place_maker_order(self, mock_place_order):
        pass

    @patch.object(XEMMExecutor, 'place_order')
    def test_place_taker_order(self, mock_place_order):
        pass
