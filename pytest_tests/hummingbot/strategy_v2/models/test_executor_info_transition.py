# test_executor_info_transition.py
import time
from decimal import Decimal
from typing import Dict, Optional
from unittest.mock import Mock, PropertyMock

import pytest
from pydantic import BaseModel

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.strategy_v2.executors.twap_executor.data_types import TWAPExecutorConfig
from hummingbot.strategy_v2.executors.xemm_executor.data_types import XEMMExecutorConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorCustomInfoBase, ExecutorInfo


class _ExecutorInfo(BaseModel):
    id: str
    timestamp: float
    type: str
    close_timestamp: Optional[float]
    close_type: Optional[CloseType]
    status: RunnableStatus
    config: PositionExecutorConfig | XEMMExecutorConfig | ArbitrageExecutorConfig | DCAExecutorConfig | TWAPExecutorConfig | ExecutorConfigBase
    net_pnl_pct: Decimal
    net_pnl_quote: Decimal
    cum_fees_quote: Decimal
    filled_amount_quote: Decimal
    is_active: bool
    is_trading: bool
    custom_info: Dict  # TODO: Define the custom info type for each executor
    controller_id: Optional[str] = None

    @property
    def is_done(self):
        return self.status in [RunnableStatus.TERMINATED]

    @property
    def side(self) -> Optional[TradeType]:
        return self.custom_info.get("side", None)

    @property
    def trading_pair(self) -> Optional[str]:
        return self.config.trading_pair

    @property
    def connector_name(self) -> Optional[str]:
        return self.config.connector_name

    def to_dict(self):
        base_dict = self.dict()
        base_dict["side"] = self.side
        return base_dict


@pytest.fixture
def timestamp():
    return time.time()


@pytest.fixture
def config(timestamp):
    return PositionExecutorConfig(
        id="test_id",
        timestamp=timestamp,
        trading_pair="BTC-USDT",
        connector_name="binance",
        side=TradeType.BUY,
        amount=Decimal("1.0"),
        type="position_executor",
        controller_id="main",
    )


@pytest.fixture
def mock_executor(config, timestamp):
    executor = Mock()

    # Mock the config
    type(executor).config = PropertyMock(return_value=config)

    # Mock status and performance metrics
    type(executor).status = PropertyMock(return_value=RunnableStatus.RUNNING)
    type(executor).is_active = PropertyMock(return_value=True)
    type(executor).is_trading = PropertyMock(return_value=True)
    type(executor).net_pnl_pct = PropertyMock(return_value=Decimal("0.1"))
    type(executor).net_pnl_quote = PropertyMock(return_value=Decimal("100"))
    type(executor).cum_fees_quote = PropertyMock(return_value=Decimal("10"))
    type(executor).filled_amount_quote = PropertyMock(return_value=Decimal("1000"))

    # Mock close information
    type(executor).close_type = PropertyMock(return_value=CloseType.TAKE_PROFIT)
    type(executor).close_timestamp = PropertyMock(return_value=timestamp + 3600)  # 1 hour later

    return executor


def test_executor_info_complete_initialization(mock_executor, timestamp):
    """Test complete initialization of ExecutorInfo with all fields"""
    info = ExecutorInfo(
        id="test_id",
        type="position_executor",
        controller_id="main",
        timestamp=timestamp,
        close_timestamp=timestamp + 3600,
        trading_pair="BTC-USDT",
        connector_name="binance",
        status=RunnableStatus.RUNNING,
        close_type=CloseType.TAKE_PROFIT,
        is_active=True,
        is_trading=True,
        net_pnl_pct=Decimal("0.1"),
        net_pnl_quote=Decimal("100"),
        cum_fees_quote=Decimal("10"),
        filled_amount_quote=Decimal("1000"),
        custom_info=ExecutorCustomInfoBase(mock_executor),
    )

    # Test all fields are correctly set
    assert info.id == "test_id"
    assert info.type == "position_executor"
    assert info.controller_id == "main"
    assert info.timestamp == timestamp
    assert info.close_timestamp == timestamp + 3600
    assert info.trading_pair == "BTC-USDT"
    assert info.connector_name == "binance"
    assert info.status == RunnableStatus.RUNNING
    assert info.close_type == CloseType.TAKE_PROFIT
    assert info.is_active is True
    assert info.is_trading is True
    assert info.net_pnl_pct == Decimal("0.1")
    assert info.net_pnl_quote == Decimal("100")
    assert info.cum_fees_quote == Decimal("10")
    assert info.filled_amount_quote == Decimal("1000")
    assert info.side == TradeType.BUY


def test_executor_info_minimal_initialization():
    """Test initialization with only required fields"""
    timestamp = time.time()
    info = ExecutorInfo(
        id="test_id",
        type="position_executor",
        timestamp=timestamp,
        trading_pair="BTC-USDT",
        connector_name="binance",
        status=RunnableStatus.NOT_STARTED,
        is_active=False,
        is_trading=False,
        custom_info=ExecutorCustomInfoBase(Mock()),
    )

    assert info.id == "test_id"
    assert info.controller_id is None
    assert info.close_timestamp is None
    assert info.close_type is None
    assert info.net_pnl_pct == Decimal("0")
    assert info.net_pnl_quote == Decimal("0")
    assert info.cum_fees_quote == Decimal("0")
    assert info.filled_amount_quote == Decimal("0")


def test_executor_info_to_dict(mock_executor):
    """Test conversion to dictionary representation"""
    info = ExecutorInfo.from_executor(mock_executor)
    dict_repr = info.to_dict()

    assert dict_repr["id"] == mock_executor.config.id
    assert dict_repr["type"] == mock_executor.config.type
    assert dict_repr["controller_id"] == mock_executor.config.controller_id
    assert dict_repr["side"] == mock_executor.config.side
    assert isinstance(dict_repr["timestamp"], float)
    assert isinstance(dict_repr["close_timestamp"], float)
    assert dict_repr["trading_pair"] == mock_executor.config.trading_pair
    assert dict_repr["connector_name"] == mock_executor.config.connector_name
    assert dict_repr["status"] == RunnableStatus.RUNNING
    assert dict_repr["close_type"] == CloseType.TAKE_PROFIT
    assert dict_repr["is_active"] is True
    assert dict_repr["is_trading"] is True
    assert dict_repr["net_pnl_quote"] == Decimal(mock_executor.net_pnl_quote)
    assert dict_repr["net_pnl_pct"] == Decimal(mock_executor.net_pnl_pct)
    assert dict_repr["cum_fees_quote"] == Decimal(mock_executor.cum_fees_quote)
    assert dict_repr["filled_amount_quote"] == Decimal(mock_executor.filled_amount_quote)


def test_executor_info_from_executor(mock_executor):
    """Test creation from executor instance"""
    info = ExecutorInfo.from_executor(mock_executor)

    assert info.id == mock_executor.config.id
    assert info.type == mock_executor.config.type
    assert info.controller_id == mock_executor.config.controller_id
    assert info.timestamp == mock_executor.config.timestamp
    assert info.close_timestamp == mock_executor.close_timestamp
    assert info.trading_pair == mock_executor.config.trading_pair
    assert info.connector_name == mock_executor.config.connector_name
    assert info.status == mock_executor.status
    assert info.close_type == mock_executor.close_type
    assert info.is_active == mock_executor.is_active
    assert info.is_trading == mock_executor.is_trading
    assert info.net_pnl_pct == mock_executor.net_pnl_pct
    assert info.net_pnl_quote == mock_executor.net_pnl_quote
    assert info.cum_fees_quote == mock_executor.cum_fees_quote
    assert info.filled_amount_quote == mock_executor.filled_amount_quote


def test_executor_info_with_nan_values(mock_executor):
    """Test handling of NaN values in numeric fields"""
    type(mock_executor).net_pnl_quote = PropertyMock(return_value=Decimal("NaN"))
    type(mock_executor).filled_amount_quote = PropertyMock(return_value=Decimal("NaN"))

    info = ExecutorInfo.from_executor(mock_executor)
    dict_repr = info.to_dict()

    assert dict_repr["net_pnl_quote"].is_nan()
    assert dict_repr["filled_amount_quote"].is_nan()


def test_executor_info_is_done():
    """Test is_done property for different status values"""
    timestamp = time.time()
    base_info = {
        "id": "test_id",
        "type": "position_executor",
        "timestamp": timestamp,
        "trading_pair": "BTC-USDT",
        "connector_name": "binance",
        "is_active": False,
        "is_trading": False,
        "custom_info": ExecutorCustomInfoBase(Mock()),
    }

    # Test all status variations
    for status in RunnableStatus:
        info = ExecutorInfo(status=status, **base_info)
        if status == RunnableStatus.TERMINATED:
            assert info.is_done
        else:
            assert not info.is_done


def test_executor_info_edge_cases():
    """Test handling of edge cases including optional parameters"""
    timestamp = time.time()
    config = PositionExecutorConfig(
        id="test_id",
        timestamp=timestamp,
        trading_pair="BTC-USDT",
        connector_name="binance",
        side=TradeType.BUY,
        amount=Decimal("1.0"),
        type="position_executor",
    )

    # Test with optional parameters
    cases = [
        # Case 1: All optional parameters set to None
        {
            "controller_id": None,
            "close_timestamp": None,
            "close_type": None,
        },
        # Case 2: All optional parameters set
        {
            "controller_id": "main",
            "close_timestamp": timestamp + 3600,
            "close_type": CloseType.TAKE_PROFIT,
        },
        # Case 3: Mixed optional parameters
        {
            "controller_id": "main",
            "close_timestamp": None,
            "close_type": None,
        },
    ]

    for case in cases:
        legacy_info = _ExecutorInfo(
            id="test_id",
            type="position_executor",
            timestamp=timestamp,
            trading_pair="BTC-USDT",
            connector_name="binance",
            status=RunnableStatus.NOT_STARTED,
            is_active=False,
            is_trading=False,
            net_pnl_pct=Decimal("0"),
            net_pnl_quote=Decimal("0"),
            cum_fees_quote=Decimal("0"),
            filled_amount_quote=Decimal("0"),
            custom_info={},
            config=config,
            **case
        )

        new_info = ExecutorInfo(
            id="test_id",
            type="position_executor",
            timestamp=timestamp,
            trading_pair="BTC-USDT",
            connector_name="binance",
            status=RunnableStatus.NOT_STARTED,
            is_active=False,
            is_trading=False,
            net_pnl_pct=Decimal("0"),
            net_pnl_quote=Decimal("0"),
            cum_fees_quote=Decimal("0"),
            filled_amount_quote=Decimal("0"),
            custom_info=ExecutorCustomInfoBase(Mock()),
            **case
        )

        # Verify optional parameters are handled consistently
        assert legacy_info.controller_id == new_info.controller_id
        assert legacy_info.close_timestamp == new_info.close_timestamp
        assert legacy_info.close_type == new_info.close_type

        # Verify dictionary representation
        legacy_dict = legacy_info.to_dict()
        new_dict = new_info.to_dict()

        # Compare optional fields in dictionary
        assert legacy_dict.get('controller_id') == new_dict.get('controller_id')
        assert legacy_dict.get('close_timestamp') == new_dict.get('close_timestamp')
        assert legacy_dict.get('close_type') == new_dict.get('close_type')


def test_executor_info_nan_handling():
    """Test handling of NaN values"""
    timestamp = time.time()
    config = PositionExecutorConfig(
        id="test_id",
        timestamp=timestamp,
        trading_pair="BTC-USDT",
        connector_name="binance",
        side=TradeType.BUY,
        amount=Decimal("1.0"),
        type="position_executor",
    )

    nan_fields = {
        'net_pnl_pct': Decimal("NaN"),
        'net_pnl_quote': Decimal("NaN"),
        'cum_fees_quote': Decimal("NaN"),
        'filled_amount_quote': Decimal("NaN"),
    }

    legacy_info = _ExecutorInfo(
        id="test_id",
        type="position_executor",
        timestamp=timestamp,
        trading_pair="BTC-USDT",
        connector_name="binance",
        status=RunnableStatus.NOT_STARTED,
        is_active=False,
        is_trading=False,
        controller_id="main",
        custom_info={},
        config=config,
        **nan_fields
    )

    new_info = ExecutorInfo(
        id="test_id",
        type="position_executor",
        timestamp=timestamp,
        trading_pair="BTC-USDT",
        connector_name="binance",
        status=RunnableStatus.NOT_STARTED,
        is_active=False,
        is_trading=False,
        controller_id="main",
        custom_info=ExecutorCustomInfoBase(Mock()),
        **nan_fields
    )

    legacy_dict = legacy_info.to_dict()
    new_dict = new_info.to_dict()

    for field in nan_fields:
        assert legacy_dict[field].is_nan(), f"Legacy NaN handling failed for {field}"
        assert new_dict[field].is_nan(), f"New NaN handling failed for {field}"


def test_executor_info_timestamp_formatting():
    """Test timestamp formatting in dictionary representation"""
    timestamp = time.time()
    info = ExecutorInfo(
        id="test_id",
        type="position_executor",
        timestamp=timestamp,
        close_timestamp=timestamp + 3600,
        trading_pair="BTC-USDT",
        connector_name="binance",
        status=RunnableStatus.NOT_STARTED,
        is_active=False,
        is_trading=False,
        custom_info=ExecutorCustomInfoBase(Mock()),
    )

    dict_repr = info.to_dict()

    # Verify timestamps are in ISO format
    # expected_timestamp = datetime.fromtimestamp(timestamp).isoformat()
    # expected_close_timestamp = datetime.fromtimestamp(timestamp + 3600).isoformat()
    expected_timestamp = timestamp
    expected_close_timestamp = timestamp + 3600

    assert dict_repr["timestamp"] == expected_timestamp
    assert dict_repr["close_timestamp"] == expected_close_timestamp


def test_executor_info_none_timestamp_handling():
    """Test handling of None timestamps"""
    info = ExecutorInfo(
        id="test_id",
        type="position_executor",
        timestamp=time.time(),
        trading_pair="BTC-USDT",
        connector_name="binance",
        status=RunnableStatus.NOT_STARTED,
        is_active=False,
        is_trading=False,
        close_timestamp=None,  # Explicitly set to None
        custom_info=ExecutorCustomInfoBase(Mock()),
    )

    dict_repr = info.to_dict()
    assert dict_repr["close_timestamp"] is None
