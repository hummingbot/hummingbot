import sys
from types import ModuleType


class _DummyEventDrivenBase:
    is_event_driven = True

    def __init__(self, *_, **__):
        pass

    def on_tick(self):
        return

    async def start_event_driven(self):
        return

    async def stop_event_driven(self):
        return


module_name = "hummingbot.strategy.event_driven_strategy_v2_base"
if module_name not in sys.modules:  # pragma: no cover - testing shim
    stub = ModuleType(module_name)
    stub.EventDrivenStrategyV2Base = _DummyEventDrivenBase  # type: ignore
    sys.modules[module_name] = stub
