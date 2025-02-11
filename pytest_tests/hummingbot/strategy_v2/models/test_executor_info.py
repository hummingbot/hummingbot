# pytest_tests/hummingbot/strategy_v2/models/test_executor_info.py
import time
from decimal import Decimal
from unittest.mock import Mock, PropertyMock

import pytest

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorCustomInfoBase, ExecutorInfo


@pytest.fixture
def mock_executor_config():
    """Create a mock executor config with required attributes"""
    config = Mock()
    type(config).id = PropertyMock(return_value="test_id")
    type(config).type = PropertyMock(return_value="test_executor")
    type(config).controller_id = PropertyMock(return_value="test_controller")
    type(config).timestamp = PropertyMock(return_value=time.time())
    type(config).trading_pair = PropertyMock(return_value="BTC-USDT")
    type(config).connector_name = PropertyMock(return_value="binance")
    type(config).side = PropertyMock(return_value=TradeType.BUY)
    return config


@pytest.fixture
def mock_executor(mock_executor_config):
    """Create a mock executor with required attributes"""
    executor = Mock()
    type(executor).config = PropertyMock(return_value=mock_executor_config)
    type(executor).status = PropertyMock(return_value=RunnableStatus.RUNNING)
    type(executor).is_active = PropertyMock(return_value=True)
    type(executor).is_trading = PropertyMock(return_value=True)
    type(executor).net_pnl_pct = PropertyMock(return_value=Decimal("0.1"))
    type(executor).net_pnl_quote = PropertyMock(return_value=Decimal("100"))
    type(executor).cum_fees_quote = PropertyMock(return_value=Decimal("10"))
    type(executor).filled_amount_quote = PropertyMock(return_value=Decimal("1000"))
    return executor


class TestExecutorInfo:
    def test_create_basic_info(self, mock_executor):
        """Test creation with basic required fields"""
        info = ExecutorInfo.from_executor(mock_executor)

        assert info.id == mock_executor.config.id
        assert info.type == mock_executor.config.type
        assert info.controller_id == mock_executor.config.controller_id
        assert info.trading_pair == mock_executor.config.trading_pair
        assert info.connector_name == mock_executor.config.connector_name
        assert info.status == mock_executor.status
        assert info.is_active == mock_executor.is_active
        assert info.is_trading == mock_executor.is_trading

    def test_performance_metrics(self, mock_executor):
        """Test performance metrics handling"""
        info = ExecutorInfo.from_executor(mock_executor)

        assert info.net_pnl_pct == mock_executor.net_pnl_pct
        assert info.net_pnl_quote == mock_executor.net_pnl_quote
        assert info.cum_fees_quote == mock_executor.cum_fees_quote
        assert info.filled_amount_quote == mock_executor.filled_amount_quote

    def test_optional_fields(self, mock_executor):
        """Test handling of optional fields"""
        type(mock_executor).close_timestamp = PropertyMock(return_value=None)
        type(mock_executor).close_type = PropertyMock(return_value=None)

        info = ExecutorInfo.from_executor(mock_executor)

        assert info.close_timestamp is None
        assert info.close_type is None

    def test_closed_executor(self, mock_executor):
        """Test handling of closed executor state"""
        close_timestamp = time.time()
        type(mock_executor).status = PropertyMock(return_value=RunnableStatus.TERMINATED)
        type(mock_executor).close_timestamp = PropertyMock(return_value=close_timestamp)
        type(mock_executor).close_type = PropertyMock(return_value=CloseType.TAKE_PROFIT)
        type(mock_executor).is_active = PropertyMock(return_value=False)

        info = ExecutorInfo.from_executor(mock_executor)

        assert info.status == RunnableStatus.TERMINATED
        assert info.close_timestamp == close_timestamp
        assert info.close_type == CloseType.TAKE_PROFIT
        assert not info.is_active
        assert info.is_done

    def test_custom_info_integration(self, mock_executor):
        """Test custom info integration"""
        info = ExecutorInfo.from_executor(mock_executor)

        assert isinstance(info.custom_info, ExecutorCustomInfoBase)
        assert info.side == mock_executor.config.side

    def test_to_dict_conversion(self, mock_executor):
        """Test conversion to dictionary"""
        info = ExecutorInfo.from_executor(mock_executor)
        dict_repr = info.to_dict()

        assert dict_repr["id"] == mock_executor.config.id
        assert dict_repr["type"] == mock_executor.config.type
        assert dict_repr["trading_pair"] == mock_executor.config.trading_pair
        assert dict_repr["connector_name"] == mock_executor.config.connector_name
        assert dict_repr["side"] == mock_executor.config.side
        assert dict_repr["net_pnl_quote"] == str(mock_executor.net_pnl_quote)

    def test_nan_values_handling(self, mock_executor):
        """Test handling of NaN values"""
        type(mock_executor).net_pnl_quote = PropertyMock(return_value=Decimal("NaN"))
        type(mock_executor).filled_amount_quote = PropertyMock(return_value=Decimal("NaN"))

        info = ExecutorInfo.from_executor(mock_executor)
        dict_repr = info.to_dict()

        assert dict_repr["net_pnl_quote"] == "0"
        assert dict_repr["filled_amount_quote"] == "0"

    def test_none_values_handling(self, mock_executor):
        """Test handling of None values"""
        type(mock_executor.config).controller_id = PropertyMock(return_value=None)

        info = ExecutorInfo.from_executor(mock_executor)
        dict_repr = info.to_dict()

        assert dict_repr["controller_id"] is None

    def test_status_transitions(self, mock_executor):
        """Test different status states"""
        for status in RunnableStatus:
            type(mock_executor).status = PropertyMock(return_value=status)
            info = ExecutorInfo.from_executor(mock_executor)

            assert info.status == status
            assert info.is_done == (status == RunnableStatus.TERMINATED)
