import unittest
import uuid
from typing import Any
from unittest.mock import MagicMock

from hummingbot.strategy_v2.executors.executor_factory import ExecutorFactory
from hummingbot.strategy_v2.executors.protocols import ExecutorConfigFactoryProtocol


class DummyExecutorConfig(ExecutorConfigFactoryProtocol):
    """
    Dummy executor configuration that satisfies ExecutorConfigProtocol.

    :param id: Unique identifier.
    :param controller_id: Optional controller identifier.
    """

    def __init__(self, id: str, controller_id: str | None = None) -> None:
        self.id = id
        self.controller_id = controller_id


@ExecutorFactory.register_executor(DummyExecutorConfig)
class DummyExecutor:
    """
    Dummy executor that satisfies ExecutorBaseProtocol.

    :param strategy: The strategy or context.
    :param config: The executor configuration.
    :param update_interval: The update interval.
    """

    def __init__(self, strategy: Any, config: DummyExecutorConfig, update_interval: float) -> None:
        self.strategy = strategy
        self.config = config  # type: DummyExecutorConfig
        self.update_interval = update_interval
        self.started = False

    def start(self) -> None:
        """
        Mark the executor as started.
        """
        self.started = True


class UnregisteredExecutorConfig:
    """
    Dummy configuration that is not registered with the ExecutorFactory.

    Satisfies ExecutorConfigProtocol.
    """

    def __init__(self, id: str, controller_id: str | None = None) -> None:
        self.id = id
        self.controller_id = controller_id


# -----------------------------------------------------------------------------
# Test Cases
# -----------------------------------------------------------------------------

class TestExecutorFactoryWithProtocol(unittest.TestCase):
    """
    Test cases for the ExecutorFactory using Protocols and plain Python classes.
    """

    def setUp(self) -> None:
        """
        Set up the test environment with a mocked strategy.
        """
        self.mock_strategy: Any = MagicMock(name="MockStrategy")
        self.update_interval: float = 1.0

    def test_create_dummy_executor(self) -> None:
        """
        Test that the factory correctly creates a DummyExecutor instance
        when provided with a registered configuration.
        """
        config = DummyExecutorConfig(id=str(uuid.uuid4()), controller_id="controller_1")
        executor = ExecutorFactory.create_executor(self.mock_strategy, config, self.update_interval)
        self.assertIsInstance(executor, DummyExecutor, "Factory did not create a DummyExecutor instance.")
        # Start the executor and verify that it is marked as started.
        executor.start()
        self.assertTrue(executor.started, "DummyExecutor failed to start correctly.")

    def test_create_unregistered_executor_raises(self) -> None:
        """
        Test that a ValueError is raised when trying to create an executor
        with an unregistered configuration type.
        """
        config = UnregisteredExecutorConfig(id=str(uuid.uuid4()), controller_id="controller_1")
        with self.assertRaises(ValueError):
            ExecutorFactory.create_executor(self.mock_strategy, config, self.update_interval)


if __name__ == "__main__":
    unittest.main()
