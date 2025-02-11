# pytest_tests/hummingbot/strategy_v2/test_data.py
import time
from decimal import Decimal

from pydantic import BaseModel

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType


class TestExecutorConfig(ExecutorConfigBase):
    """Base test config class that properly implements ExecutorConfigFactoryProtocol"""
    # Class-level attributes required by protocol
    id: str
    controller_id: str

    # Default values
    type: str = "test_executor"
    trading_pair: str = "BTC-USDT"
    connector_name: str = "binance"
    side: TradeType = TradeType.BUY
    amount: Decimal = Decimal("1.0")


class TestExecutorUpdate(BaseModel):
    """Base test update class for both executor and model tests"""
    value: str = "test"

    def validate(self) -> bool:
        return True


class TestCustomInfo(BaseModel):
    """Base test custom info class"""
    side: TradeType | None = None

    def __init__(self, executor):
        super().__init__()
        self.side = executor.config.side


class TestExecutorInfo(BaseModel):
    """Test data for ExecutorInfo testing"""
    id: str
    type: str = "test_executor"
    controller_id: str = "test_controller"
    timestamp: float = time.time()
    close_timestamp: float | None = None
    trading_pair: str = "BTC-USDT"
    connector_name: str = "binance"
    status: RunnableStatus = RunnableStatus.RUNNING
    close_type: CloseType | None = None
    is_active: bool = True
    is_trading: bool = True
    net_pnl_pct: Decimal = Decimal("0.1")
    net_pnl_quote: Decimal = Decimal("100")
    cum_fees_quote: Decimal = Decimal("10")
    filled_amount_quote: Decimal = Decimal("1000")
