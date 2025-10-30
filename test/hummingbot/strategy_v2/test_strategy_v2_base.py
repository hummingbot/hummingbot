import sys
import unittest
from decimal import Decimal
from types import ModuleType
from unittest.mock import MagicMock, patch

# Provide lightweight stubs for optional third-party dependencies used by production modules.
if "hexbytes" not in sys.modules:
    hexbytes_stub = ModuleType("hexbytes")

    class HexBytes(bytes):
        """Minimal stub used by connector utils during tests."""
        pass

    hexbytes_stub.HexBytes = HexBytes
    sys.modules["hexbytes"] = hexbytes_stub

if "cachetools" not in sys.modules:
    cachetools_stub = ModuleType("cachetools")

    class TTLCache(dict):
        def __init__(self, ttl=None, maxsize=None):
            super().__init__()

    cachetools_stub.TTLCache = TTLCache
    sys.modules["cachetools"] = cachetools_stub

if "aiohttp" not in sys.modules:
    aiohttp_stub = ModuleType("aiohttp")

    class ClientSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def close(self):
            return None

    class ClientResponse:
        def __init__(self, url=None, method="GET", status=200, headers=None, content_type="application/json"):
            self.url = url
            self.method = method
            self.status = status
            self.headers = headers or {}
            self.content_type = content_type

        async def json(self):
            return {}

        async def read(self):
            return b"{}"

        async def text(self):
            return "{}"

    aiohttp_stub.ClientResponse = ClientResponse
    aiohttp_stub.ClientSession = ClientSession
    aiohttp_stub.WebSocketError = Exception

    class _WSCloseCode:
        OK = 1000

    aiohttp_stub.WSCloseCode = _WSCloseCode
    aiohttp_stub.WSMessage = object

    class _WSMsgType:
        TEXT = 1
        BINARY = 2
        CLOSE = 3

    aiohttp_stub.WSMsgType = _WSMsgType
    sys.modules["aiohttp"] = aiohttp_stub

if "ujson" not in sys.modules:
    import json

    ujson_stub = ModuleType("ujson")
    ujson_stub.dumps = json.dumps
    ujson_stub.loads = json.loads
    sys.modules["ujson"] = ujson_stub

# Stub connector utils to avoid heavy third-party dependencies during import.
if "hummingbot.connector.utils" not in sys.modules:
    connector_utils_stub = ModuleType("hummingbot.connector.utils")

    def split_hb_trading_pair(trading_pair: str):
        base, quote = trading_pair.split("-")
        return base, quote

    def combine_to_hb_trading_pair(base: str, quote: str) -> str:
        return f"{base}-{quote}"

    connector_utils_stub.split_hb_trading_pair = split_hb_trading_pair
    connector_utils_stub.combine_to_hb_trading_pair = combine_to_hb_trading_pair
    sys.modules["hummingbot.connector.utils"] = connector_utils_stub

# Stub MarketsRecorder to avoid database dependencies.
if "hummingbot.connector.markets_recorder" not in sys.modules:
    markets_recorder_stub = ModuleType("hummingbot.connector.markets_recorder")

    class _MarketsRecorderInstance:
        def store_controller_config(self, config):
            pass

        def store_or_update_executor(self, executor):
            pass

        def store_all_executors(self):
            pass

        def get_all_executors(self):
            return []

        def get_all_positions(self):
            return []

    class MarketsRecorder:
        _instance = None

        @classmethod
        def get_instance(cls):
            if cls._instance is None:
                cls._instance = _MarketsRecorderInstance()
            return cls._instance

    markets_recorder_stub.MarketsRecorder = MarketsRecorder
    sys.modules["hummingbot.connector.markets_recorder"] = markets_recorder_stub

if "hummingbot.client.settings" not in sys.modules:
    settings_stub = ModuleType("hummingbot.client.settings")
    settings_stub.CONTROLLERS_CONF_DIR_PATH = ""
    settings_stub.CONTROLLERS_MODULE = "hummingbot.test.controllers"

    class AllConnectorSettings:
        @staticmethod
        def get_connector_settings():
            return {}

    settings_stub.AllConnectorSettings = AllConnectorSettings
    sys.modules["hummingbot.client.settings"] = settings_stub

if "hummingbot.remote_iface.mqtt" not in sys.modules:
    mqtt_stub = ModuleType("hummingbot.remote_iface.mqtt")

    class ETopicPublisher:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, msg):
            pass

    mqtt_stub.ETopicPublisher = ETopicPublisher
    sys.modules["hummingbot.remote_iface.mqtt"] = mqtt_stub

if "hummingbot.client.ui.interface_utils" not in sys.modules:
    interface_utils_stub = ModuleType("hummingbot.client.ui.interface_utils")

    def format_df_for_printout(df, table_format="psql", index=False):
        return df.to_string(index=index)

    interface_utils_stub.format_df_for_printout = format_df_for_printout
    sys.modules["hummingbot.client.ui.interface_utils"] = interface_utils_stub

if "hummingbot.connector.connector_base" not in sys.modules:
    connector_base_stub = ModuleType("hummingbot.connector.connector_base")

    class ConnectorBase:
        def __init__(self, *args, **kwargs):
            self.ready = True

        def set_leverage(self, *args, **kwargs):
            pass

        def set_position_mode(self, *args, **kwargs):
            pass

    connector_base_stub.ConnectorBase = ConnectorBase
    sys.modules["hummingbot.connector.connector_base"] = connector_base_stub

if "hummingbot.core.clock" not in sys.modules:
    clock_stub = ModuleType("hummingbot.core.clock")

    class Clock:
        def __init__(self):
            pass

    clock_stub.Clock = Clock
    sys.modules["hummingbot.core.clock"] = clock_stub

if "hummingbot.data_feed.market_data_provider" not in sys.modules:
    mdp_stub = ModuleType("hummingbot.data_feed.market_data_provider")

    class MarketDataProvider:
        def __init__(self, *args, **kwargs):
            self.ready = True

        def initialize_candles_feed_list(self, *args, **kwargs):
            pass

        def stop(self):
            pass

        def get_price_by_type(self, *args, **kwargs):
            from decimal import Decimal
            return Decimal("0")

    mdp_stub.MarketDataProvider = MarketDataProvider
    sys.modules["hummingbot.data_feed.market_data_provider"] = mdp_stub

if "hummingbot.strategy.script_strategy_base" not in sys.modules:
    script_base_stub = ModuleType("hummingbot.strategy.script_strategy_base")

    class _Logger:
        def warning(self, *args, **kwargs):
            pass

        def error(self, *args, **kwargs):
            pass

    class ScriptStrategyBase:
        markets = {}

        @classmethod
        def logger(cls):
            return _Logger()

        def __init__(self, connectors=None, config=None):
            self.connectors = connectors or {}
            self.ready_to_trade = True

        def add_markets(self, *args, **kwargs):
            pass

        def on_tick(self):
            pass

    script_base_stub.ScriptStrategyBase = ScriptStrategyBase
    sys.modules["hummingbot.strategy.script_strategy_base"] = script_base_stub

if "hummingbot.strategy_v2.controllers.controller_base" not in sys.modules:
    controller_base_stub = ModuleType("hummingbot.strategy_v2.controllers.controller_base")

    class ControllerConfigBase:
        def __init__(self, controller_name: str = "", controller_type: str = "generic", config_id: str = None,
                     candles_config=None, initial_positions=None):
            self.controller_name = controller_name
            self.controller_type = controller_type
            self.id = config_id
            self.candles_config = candles_config or []
            self.initial_positions = initial_positions or []
            self.model_fields_set = set()
            if config_id is not None:
                self.model_fields_set.add("id")

        def update_markets(self, markets):
            return markets

        def get_controller_class(self):
            return ControllerBase

    class ControllerBase:
        def __init__(self, config=None, market_data_provider=None, actions_queue=None, update_interval: float = 1.0):
            self.config = config
            self.executors_info = []
            self.positions_held = []
            self.executors_update_event = type("Event", (), {"set": lambda self: None})()

        def start(self):
            pass

        def stop(self):
            pass

        def update_config(self, new_config):
            self.config = new_config

        def determine_executor_actions(self):
            return []

        def to_format_status(self):
            return []

    controller_base_stub.ControllerBase = ControllerBase
    controller_base_stub.ControllerConfigBase = ControllerConfigBase
    sys.modules["hummingbot.strategy_v2.controllers.controller_base"] = controller_base_stub

if "hummingbot.strategy_v2.controllers.directional_trading_controller_base" not in sys.modules:
    directional_stub = ModuleType("hummingbot.strategy_v2.controllers.directional_trading_controller_base")

    class DirectionalTradingControllerConfigBase(ControllerConfigBase):
        pass

    directional_stub.DirectionalTradingControllerConfigBase = DirectionalTradingControllerConfigBase
    sys.modules["hummingbot.strategy_v2.controllers.directional_trading_controller_base"] = directional_stub

if "hummingbot.strategy_v2.controllers.market_making_controller_base" not in sys.modules:
    mm_stub = ModuleType("hummingbot.strategy_v2.controllers.market_making_controller_base")

    class MarketMakingControllerConfigBase(ControllerConfigBase):
        pass

    mm_stub.MarketMakingControllerConfigBase = MarketMakingControllerConfigBase
    sys.modules["hummingbot.strategy_v2.controllers.market_making_controller_base"] = mm_stub

if "hummingbot.model.position" not in sys.modules:
    position_stub = ModuleType("hummingbot.model.position")

    class Position:
        def __init__(self, *args, **kwargs):
            self.controller_id = kwargs.get("controller_id")
            self.connector_name = kwargs.get("connector_name", "")
            self.trading_pair = kwargs.get("trading_pair", "")
            self.side = kwargs.get("side", "")
            self.volume_traded_quote = kwargs.get("volume_traded_quote", 0)
            self.amount = kwargs.get("amount", 0)
            self.breakeven_price = kwargs.get("breakeven_price", 0)
            self.unrealized_pnl_quote = kwargs.get("unrealized_pnl_quote", 0)
            self.cum_fees_quote = kwargs.get("cum_fees_quote", 0)

    position_stub.Position = Position
    sys.modules["hummingbot.model.position"] = position_stub

def _ensure_executor_stub(module_path: str, class_name: str):
    if module_path in sys.modules:
        return
    executor_stub = ModuleType(module_path)

    class _Executor:
        def __init__(self, strategy=None, config=None, update_interval: float = 1.0, max_retries: int = 10):
            self.strategy = strategy
            self.config = config
            self.executor_info = MagicMock()
            self.is_closed = True

        def start(self):
            pass

        def early_stop(self, *args, **kwargs):
            pass

    setattr(executor_stub, class_name, _Executor)
    sys.modules[module_path] = executor_stub


_ensure_executor_stub("hummingbot.strategy_v2.executors.arbitrage_executor.arbitrage_executor", "ArbitrageExecutor")
_ensure_executor_stub("hummingbot.strategy_v2.executors.dca_executor.dca_executor", "DCAExecutor")
_ensure_executor_stub("hummingbot.strategy_v2.executors.grid_executor.grid_executor", "GridExecutor")
_ensure_executor_stub("hummingbot.strategy_v2.executors.order_executor.order_executor", "OrderExecutor")
_ensure_executor_stub("hummingbot.strategy_v2.executors.position_executor.position_executor", "PositionExecutor")
_ensure_executor_stub("hummingbot.strategy_v2.executors.twap_executor.twap_executor", "TWAPExecutor")
_ensure_executor_stub("hummingbot.strategy_v2.executors.xemm_executor.xemm_executor", "XEMMExecutor")

if "hummingbot.strategy_v2.models.executors" not in sys.modules:
    from enum import Enum

    executors_model_stub = ModuleType("hummingbot.strategy_v2.models.executors")

    class CloseType(Enum):
        NONE = 0
        NORMAL = 1

    executors_model_stub.CloseType = CloseType
    class TrackedOrder:
        pass
    executors_model_stub.TrackedOrder = TrackedOrder
    sys.modules["hummingbot.strategy_v2.models.executors"] = executors_model_stub

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy.strategy_v2_base import StrategyV2Base
from hummingbot.strategy_v2.executors.executor_orchestrator import ExecutorOrchestrator
from hummingbot.strategy_v2.models.position_config import InitialPositionConfig


class DummyControllerConfig:
    def __init__(self, controller_name: str, controller_id: str = None, initial_positions=None):
        self.controller_name = controller_name
        self.id = controller_id
        self.initial_positions = initial_positions or []
        self.model_fields_set = set()
        if controller_id is not None:
            self.model_fields_set.add("id")


class DummyStrategy:
    def __init__(self):
        self.controllers = {}
        self.markets = {}
        self.market_data_provider = MagicMock()
        self.market_data_provider.get_price_by_type.return_value = Decimal("1")


class StrategyV2BaseUnitTests(unittest.TestCase):
    def setUp(self):
        self.strategy = StrategyV2Base.__new__(StrategyV2Base)
        self.strategy._controller_id_map = {}

    def test_assign_controller_id_reuses_cached_id(self):
        first_config = DummyControllerConfig(controller_name="alpha")
        self.strategy._assign_controller_id("path_alpha.yaml", first_config)
        first_id = first_config.id

        second_config = DummyControllerConfig(controller_name="alpha")
        self.strategy._assign_controller_id("path_alpha.yaml", second_config)

        self.assertEqual(first_id, second_config.id)

        third_config = DummyControllerConfig(controller_name="alpha")
        self.strategy._assign_controller_id("path_beta.yaml", third_config)

        self.assertNotEqual(first_id, third_config.id)

    def test_assign_controller_id_respects_explicit_ids(self):
        explicit_id = "explicit-controller-id"
        config = DummyControllerConfig(controller_name="beta", controller_id=explicit_id)

        self.strategy._assign_controller_id("path_beta.yaml", config)

        self.assertEqual(explicit_id, config.id)
        self.assertEqual(explicit_id, self.strategy._controller_id_map["path_beta.yaml"])


class ExecutorOrchestratorUnitTests(unittest.TestCase):
    @patch("hummingbot.strategy_v2.executors.executor_orchestrator.MarketsRecorder")
    def test_register_controller_initial_positions_once(self, markets_recorder_mock):
        recorder_instance = MagicMock()
        recorder_instance.get_all_executors.return_value = []
        recorder_instance.get_all_positions.return_value = []
        markets_recorder_mock.get_instance.return_value = recorder_instance

        orchestrator = ExecutorOrchestrator(strategy=DummyStrategy())

        controller_id = "controller-1"
        initial_positions = [
            InitialPositionConfig(
                connector_name="binance",
                trading_pair="ETH-USDT",
                amount=Decimal("1"),
                side=TradeType.BUY,
            )
        ]

        orchestrator.register_controller(controller_id, initial_positions)

        self.assertIn(controller_id, orchestrator.cached_performance)
        self.assertIn(controller_id, orchestrator.positions_held)
        self.assertEqual(1, len(orchestrator.positions_held[controller_id]))

        # Calling register again with the same controller should not duplicate positions.
        orchestrator.register_controller(controller_id, initial_positions)

        self.assertEqual(1, len(orchestrator.positions_held[controller_id]))


if __name__ == "__main__":
    unittest.main()
