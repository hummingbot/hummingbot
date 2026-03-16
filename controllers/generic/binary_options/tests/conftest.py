"""Stub hummingbot modules before any test imports trigger the real package."""
import sys
from types import ModuleType

from pydantic import BaseModel, ConfigDict


class _StubControllerConfigBase(BaseModel):
    id: str = "test"
    controller_name: str = ""
    controller_type: str = "generic"
    total_amount_quote: float = 100.0
    model_config = ConfigDict(arbitrary_types_allowed=True)


class _OrderType:
    LIMIT = "LIMIT"
    LIMIT_MAKER = "LIMIT_MAKER"
    MARKET = "MARKET"


class _TradeType:
    BUY = "BUY"
    SELL = "SELL"


class _TripleBarrierConfig:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _PositionExecutorConfig:
    _counter = 0

    def __init__(self, **kwargs):
        _PositionExecutorConfig._counter += 1
        self.id = f"pos_exec_{_PositionExecutorConfig._counter}"
        for k, v in kwargs.items():
            setattr(self, k, v)


class _ExecutorAction(BaseModel):
    controller_id: str = "main"
    model_config = ConfigDict(arbitrary_types_allowed=True)


class _CreateExecutorAction(_ExecutorAction):
    executor_config: object = None


class _StopExecutorAction(_ExecutorAction):
    executor_id: str = ""
    keep_position: bool = False


class _ControllerBase:
    def __init__(self, config, market_data_provider, actions_queue):
        self.config = config
        self.market_data_provider = market_data_provider
        self.actions_queue = actions_queue
        self.executors_info = []
        self.processed_data = {}
        self.connectors = {}


def _ensure_stub(name, mod):
    if name not in sys.modules:
        sys.modules[name] = mod


# Build module tree
_hb = ModuleType("hummingbot")
_hb_core = ModuleType("hummingbot.core")
_hb_core_dt = ModuleType("hummingbot.core.data_type")
_hb_common = ModuleType("hummingbot.core.data_type.common")
_hb_common.OrderType = _OrderType
_hb_common.TradeType = _TradeType

_hb_s = ModuleType("hummingbot.strategy_v2")
_hb_sc = ModuleType("hummingbot.strategy_v2.controllers")
_hb_scb = ModuleType("hummingbot.strategy_v2.controllers.controller_base")
_hb_scb.ControllerBase = _ControllerBase
_hb_scb.ControllerConfigBase = _StubControllerConfigBase

_hb_se = ModuleType("hummingbot.strategy_v2.executors")
_hb_sep = ModuleType("hummingbot.strategy_v2.executors.position_executor")
_hb_sepd = ModuleType("hummingbot.strategy_v2.executors.position_executor.data_types")
_hb_sepd.PositionExecutorConfig = _PositionExecutorConfig
_hb_sepd.TripleBarrierConfig = _TripleBarrierConfig
_hb_sed = ModuleType("hummingbot.strategy_v2.executors.data_types")

_hb_sm = ModuleType("hummingbot.strategy_v2.models")
_hb_sma = ModuleType("hummingbot.strategy_v2.models.executor_actions")
_hb_sma.ExecutorAction = _ExecutorAction
_hb_sma.CreateExecutorAction = _CreateExecutorAction
_hb_sma.StopExecutorAction = _StopExecutorAction

_hb_client = ModuleType("hummingbot.client")
_hb_client_config = ModuleType("hummingbot.client.config")
_hb_client_config_dt = ModuleType("hummingbot.client.config.config_data_types")

for name, mod in [
    ("hummingbot", _hb),
    ("hummingbot.core", _hb_core),
    ("hummingbot.core.data_type", _hb_core_dt),
    ("hummingbot.core.data_type.common", _hb_common),
    ("hummingbot.strategy_v2", _hb_s),
    ("hummingbot.strategy_v2.controllers", _hb_sc),
    ("hummingbot.strategy_v2.controllers.controller_base", _hb_scb),
    ("hummingbot.strategy_v2.executors", _hb_se),
    ("hummingbot.strategy_v2.executors.position_executor", _hb_sep),
    ("hummingbot.strategy_v2.executors.position_executor.data_types", _hb_sepd),
    ("hummingbot.strategy_v2.executors.data_types", _hb_sed),
    ("hummingbot.strategy_v2.models", _hb_sm),
    ("hummingbot.strategy_v2.models.executor_actions", _hb_sma),
    ("hummingbot.client", _hb_client),
    ("hummingbot.client.config", _hb_client_config),
    ("hummingbot.client.config.config_data_types", _hb_client_config_dt),
]:
    _ensure_stub(name, mod)
