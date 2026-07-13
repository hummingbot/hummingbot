"""Multi-strategy evidence-driven evolution loop.

This package coordinates research, backtest, paper observation, and manual
promotion reviews. It deliberately contains no live-order execution path.
"""

from hummingbot.strategy_v2.evolution.config import (
    EvolutionConfig,
    load_evolution_config,
)
from hummingbot.strategy_v2.evolution.engine import StrategyEvolutionEngine
from hummingbot.strategy_v2.evolution.supervisor import EvolutionSupervisor

__all__ = [
    "EvolutionConfig",
    "EvolutionSupervisor",
    "StrategyEvolutionEngine",
    "load_evolution_config",
]
