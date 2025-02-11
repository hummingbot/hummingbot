# pytest_tests/hummingbot/strategy_v2/conftest.py
# Common fixtures used across different test modules
import time
import uuid
from decimal import Decimal
from unittest.mock import Mock

import pytest

from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.executor_factory import ExecutorFactory
from hummingbot.strategy_v2.models.base import RunnableStatus

from .test_data import TestExecutorConfig


@pytest.fixture
def mock_strategy():
    """Create a mock strategy for testing"""
    return Mock(spec=ScriptStrategyBase)


@pytest.fixture
def test_config():
    """Create a properly configured TestExecutorConfig instance"""
    return TestExecutorConfig(
        id=str(uuid.uuid4()),
        timestamp=time.time(),
        controller_id="test_controller",
    )


@pytest.fixture
def test_executor_class():
    """Create a base executor class with proper implementation"""

    class TestExecutor:
        def __init__(self, strategy: ScriptStrategyBase, config: TestExecutorConfig, update_interval: float):
            self.strategy = strategy
            self.config = config
            self.update_interval = update_interval
            self.status = RunnableStatus.NOT_STARTED
            self.is_active = False
            self.is_trading = False
            self.close_timestamp = None
            self.net_pnl_quote = Decimal("0")
            self.net_pnl_pct = Decimal("0")
            self.cum_fees_quote = Decimal("0")
            self.filled_amount_quote = Decimal("0")

        def start(self):
            self.status = RunnableStatus.RUNNING
            self.is_active = True

    return TestExecutor


@pytest.fixture(autouse=True)
def factory_registry_cleanup():
    """Clean the ExecutorFactory registry"""
    ExecutorFactory._registry.clear()
    ExecutorFactory._update_types.clear()
    ExecutorFactory._custom_info_types.clear()
    ExecutorFactory._executor_ids.clear()
    yield
