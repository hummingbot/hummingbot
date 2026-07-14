"""Pure-domain building blocks for multi-account strategy routing.

The package intentionally has no exchange credentials, connector side effects,
or live deployment actions. Runtime workers consume validated ``RoutePlan``
objects in a later integration layer.
"""

from hummingbot.strategy_v2.routing.config import RoutingConfig, load_routing_config
from hummingbot.strategy_v2.routing.data_types import (
    AIRoutingSignal,
    AccountSnapshot,
    CandidateSignal,
    FixedScoreComponents,
    MarketState,
    RoutePlan,
    RouteTarget,
)
from hummingbot.strategy_v2.routing.supervisor import StrategyRoutingSupervisor

__all__ = [
    "AIRoutingSignal",
    "AccountSnapshot",
    "CandidateSignal",
    "FixedScoreComponents",
    "MarketState",
    "RoutePlan",
    "RouteTarget",
    "RoutingConfig",
    "StrategyRoutingSupervisor",
    "load_routing_config",
]
