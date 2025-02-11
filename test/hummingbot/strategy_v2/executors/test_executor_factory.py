import unittest
import uuid
from typing import Any
from unittest.mock import MagicMock

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.executor_base import ExecutorUpdateBase
from hummingbot.strategy_v2.executors.executor_factory import ExecutorFactory
from hummingbot.strategy_v2.executors.protocols import ExecutorConfigFactoryProtocol, ExecutorCustomInfoFactoryProtocol
from hummingbot.strategy_v2.models.executors_info import ExecutorCustomInfoBase

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

    def test_protocol_validation(self):
        """Test validation of protocol requirements"""

        # Test missing id attribute
        class InvalidConfig1:
            def __init__(self):
                self.controller_id = "test"

        with self.assertRaises(ValueError, match="must have 'id' and 'controller_id' attributes"):
            @ExecutorFactory.register_executor(InvalidConfig1)
            class InvalidExecutor1:
                pass

        # Test missing controller_id attribute
        class InvalidConfig2:
            def __init__(self):
                self.id = "test"

        with self.assertRaises(ValueError, match="must have 'id' and 'controller_id' attributes"):
            @ExecutorFactory.register_executor(InvalidConfig2)
            class InvalidExecutor2:
                pass

        # Test invalid update type
        class InvalidUpdateType:
            pass  # Missing validate method

        with self.assertRaises(ValueError, match="must have 'validate' method"):
            @ExecutorFactory.register_executor(
                self.CustomInfoConfig,
                update_type=InvalidUpdateType,
            )
            class InvalidExecutor3:
                pass

        # Test invalid custom info type
        class InvalidCustomInfo:
            pass  # Missing side attribute

        with self.assertRaises(ValueError, match="must have 'side' attribute"):
            @ExecutorFactory.register_executor(
                self.CustomInfoConfig,
                custom_info_type=InvalidCustomInfo,
            )
            class InvalidExecutor4:
                pass

    def test_custom_info_error_handling(self):
        """Test custom info graceful error handling"""

        class ProblematicCustomInfo:
            side = None

            def __init__(self, executor):
                raise RuntimeError("Simulated error")

        class ProblemConfig:
            def __init__(self, id: str, controller_id: str | None = None) -> None:
                self.id = id
                self.controller_id = controller_id
                self.side = TradeType.BUY

        @ExecutorFactory.register_executor(
            ProblemConfig,
            custom_info_type=ProblematicCustomInfo,
        )
        class ProblemExecutor:
            def __init__(self, strategy, config, update_interval):
                self.config = config

            def start(self):
                pass

        executor = ProblemExecutor(self.mock_strategy, ProblemConfig("test", "test"), 1.0)

        # Should fall back to base custom info
        custom_info = ExecutorFactory.get_custom_info(executor)
        self.assertIsInstance(custom_info, ExecutorCustomInfoBase)

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


class CustomDummyInfo(ExecutorCustomInfoBase):
    """Custom info implementation for DummyExecutor"""

    def __init__(self, executor):
        super().__init__(executor)
        self.extra_field = "custom_value"


class TestExecutorFactoryCustomInfo(unittest.TestCase):
    """Test cases for CustomInfo handling in ExecutorFactory"""

    def setUp(self):
        self.mock_strategy = MagicMock(name="MockStrategy")
        self.update_interval = 1.0

        # Create new config type for custom info testing
        class CustomInfoConfig(ExecutorConfigFactoryProtocol):
            def __init__(self, id: str, controller_id: str | None = None) -> None:
                self.id = id
                self.controller_id = controller_id
                self.side = TradeType.BUY  # Add required side attribute

        # Create custom info that doesn't rely on parent class initialization
        class CustomDummyInfo(ExecutorCustomInfoFactoryProtocol):
            def __init__(self, executor):
                self.side = executor.config.side
                self.extra_field = "custom_value"

        @ExecutorFactory.register_executor(
            CustomInfoConfig,
            custom_info_type=CustomDummyInfo,
        )
        class ExecutorWithCustomInfo:
            def __init__(self, strategy: Any, config: CustomInfoConfig, update_interval: float) -> None:
                self.strategy = strategy
                self.config = config
                self.update_interval = update_interval

            def start(self) -> None:
                pass

        self.CustomInfoConfig = CustomInfoConfig
        self.CustomDummyInfo = CustomDummyInfo
        self.ExecutorWithCustomInfo = ExecutorWithCustomInfo

    def test_get_custom_info_registered(self):
        """Test that registered executor returns correct custom info type"""
        config = self.CustomInfoConfig(id=str(uuid.uuid4()), controller_id="controller_1")
        executor = self.ExecutorWithCustomInfo(self.mock_strategy, config, self.update_interval)

        custom_info = ExecutorFactory.get_custom_info(executor)

        self.assertIsInstance(custom_info, self.CustomDummyInfo)
        self.assertEqual(custom_info.extra_field, "custom_value")
        self.assertEqual(custom_info.side, TradeType.BUY)

    def test_get_custom_info_unregistered(self):
        """Test that unregistered executor returns default custom info"""

        # Create a config with required side attribute
        class UnregisteredConfig(ExecutorConfigFactoryProtocol):
            def __init__(self, id: str, controller_id: str | None = None) -> None:
                self.id = id
                self.controller_id = controller_id
                self.side = TradeType.BUY

        config = UnregisteredConfig(id=str(uuid.uuid4()), controller_id="controller_1")
        executor = MagicMock()
        executor.config = config

        custom_info = ExecutorFactory.get_custom_info(executor)

        self.assertIsInstance(custom_info, ExecutorCustomInfoBase)
        self.assertNotIsInstance(custom_info, self.CustomDummyInfo)
        self.assertEqual(custom_info.side, TradeType.BUY)

    def test_custom_info_registration_validation(self):
        """Test validation of custom info type during registration"""

        class InvalidCustomInfo:  # Not implementing ExecutorCustomInfoFactoryProtocol
            def __init__(self, executor):
                pass

        class ValidConfig(ExecutorConfigFactoryProtocol):
            def __init__(self, id: str, controller_id: str | None = None) -> None:
                self.id = id
                self.controller_id = controller_id
                self.side = TradeType.BUY

        with self.assertRaises(ValueError):
            @ExecutorFactory.register_executor(
                ValidConfig,
                custom_info_type=InvalidCustomInfo,
            )
            class InvalidCustomInfoExecutor:
                pass

    def test_get_custom_info_unknown_config(self):
        """Test get_custom_info with unknown config type"""

        class UnknownConfig:
            def __init__(self):
                self.side = TradeType.BUY

        mock_executor = MagicMock()
        mock_executor.config = UnknownConfig()

        custom_info = ExecutorFactory.get_custom_info(mock_executor)
        self.assertIsInstance(custom_info, ExecutorCustomInfoBase)
        self.assertEqual(custom_info.side, TradeType.BUY)

    def test_custom_info_inheritance(self):
        """Test custom info with inherited executor configs"""

        class DerivedCustomInfoConfig(self.CustomInfoConfig):
            pass

        config = DerivedCustomInfoConfig(id=str(uuid.uuid4()), controller_id="controller_sub")
        executor = self.ExecutorWithCustomInfo(self.mock_strategy, config, self.update_interval)

        custom_info = ExecutorFactory.get_custom_info(executor)

        # Should use the parent config's custom info type
        self.assertIsInstance(custom_info, self.CustomDummyInfo)
        self.assertEqual(custom_info.side, TradeType.BUY)


if __name__ == "__main__":
    unittest.main()
