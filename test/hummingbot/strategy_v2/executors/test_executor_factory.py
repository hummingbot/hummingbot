import unittest
import uuid
from typing import Any
from unittest.mock import MagicMock

from hummingbot.strategy_v2.executors.executor_base import ExecutorUpdateBase
from hummingbot.strategy_v2.executors.executor_factory import ExecutorFactory
from hummingbot.strategy_v2.executors.protocols import ExecutorConfigFactoryProtocol

# ---------------------------------------------------------------------------
# Dummy classes for testing
# ---------------------------------------------------------------------------


class DummyExecutorConfig(ExecutorConfigFactoryProtocol):
    """
    Dummy executor configuration that satisfies ExecutorConfigFactoryProtocol.
    This minimal config is used for matching in the factory.
    """

    def __init__(self, id: str, controller_id: str | None = None) -> None:
        self.id = id
        self.controller_id = controller_id


@ExecutorFactory.register_executor(DummyExecutorConfig)
class DummyExecutor:
    """
    Dummy executor that satisfies the minimal ExecutorBaseFactoryProtocol.
    It uses the minimal configuration required for executor creation.
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
    Satisfies the minimal requirements but is not in the registry.
    """

    def __init__(self, id: str, controller_id: str | None = None) -> None:
        self.id = id
        self.controller_id = controller_id


# Dummy update type for testing update type registration.
class DummyUpdate(ExecutorUpdateBase):
    pass


# A new config type that is a subclass of DummyExecutorConfig and will be registered
# with an associated update type.
class DummyExecutorWithUpdateConfig(DummyExecutorConfig):
    pass


@ExecutorFactory.register_executor(DummyExecutorWithUpdateConfig, update_type=DummyUpdate)
class DummyExecutorWithUpdate:
    """
    Dummy executor that expects an update type.
    This executor also implements an update_live method.
    """

    def __init__(self, strategy: Any, config: DummyExecutorWithUpdateConfig, update_interval: float) -> None:
        self.strategy = strategy
        self.config = config  # type: DummyExecutorWithUpdateConfig
        self.update_interval = update_interval
        self.started = False
        self.last_update = None

    def start(self) -> None:
        self.started = True

    def update_live(self, update: DummyUpdate) -> None:
        self.last_update = update


# A derived configuration class to test isinstance matching.
class DerivedDummyExecutorConfig(DummyExecutorConfig):
    pass


# -----------------------------------------------------------------------------
# Test Cases
# -----------------------------------------------------------------------------

class TestExecutorFactoryThorough(unittest.TestCase):
    """
    Thorough test cases for the ExecutorFactory.
    """

    def setUp(self) -> None:
        """
        Set up the test environment with a mocked strategy and update interval.
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

    def test_duplicate_registration_raises(self) -> None:
        """
        Test that registering a duplicate executor for the same configuration type
        raises a ValueError.
        """
        with self.assertRaises(ValueError):
            @ExecutorFactory.register_executor(DummyExecutorConfig)
            class AnotherDummyExecutor:
                def __init__(self, strategy: Any, config: DummyExecutorConfig, update_interval: float) -> None:
                    pass

                def start(self) -> None:
                    pass

    def test_get_update_type_none(self) -> None:
        """
        Test that get_update_type returns None for a config type with no update type registered.
        """
        update_type = ExecutorFactory.get_update_type(DummyExecutorConfig)
        self.assertIsNone(update_type, "Expected no update type for DummyExecutorConfig.")

    def test_get_update_type_with_registration(self) -> None:
        """
        Test that get_update_type returns the correct update type for a config type that has one registered.
        """
        update_type = ExecutorFactory.get_update_type(DummyExecutorWithUpdateConfig)
        self.assertIsNotNone(update_type, "Expected an update type for DummyExecutorWithUpdateConfig.")
        self.assertEqual(update_type, DummyUpdate, "Update type does not match the registered DummyUpdate.")

    def test_subclass_config_matching(self) -> None:
        """
        Test that an executor can be created using a configuration that is a subclass of the registered type.
        """
        config = DerivedDummyExecutorConfig(id=str(uuid.uuid4()), controller_id="controller_sub")
        executor = ExecutorFactory.create_executor(self.mock_strategy, config, self.update_interval)
        # Since DerivedDummyExecutorConfig is a subclass of DummyExecutorConfig, it should match DummyExecutor.
        self.assertIsInstance(executor, DummyExecutor, "Factory did not match a subclass config to DummyExecutor.")

    def test_registry_property(self) -> None:
        """
        Test that the registry property correctly reflects the registered executor mappings.
        """
        registry = ExecutorFactory().registry
        self.assertIn(DummyExecutorConfig, registry, "DummyExecutorConfig not found in registry.")
        self.assertIn(DummyExecutorWithUpdateConfig, registry, "DummyExecutorWithUpdateConfig not found in registry.")


if __name__ == "__main__":
    unittest.main()
