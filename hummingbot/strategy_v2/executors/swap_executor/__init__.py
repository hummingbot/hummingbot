"""
SwapExecutor module for executing single swaps on Gateway AMM connectors.

Import SwapExecutor directly from swap_executor.swap_executor to avoid circular imports:
    from hummingbot.strategy_v2.executors.swap_executor.swap_executor import SwapExecutor

Data types can be imported directly from this module or from data_types:
    from hummingbot.strategy_v2.executors.swap_executor import SwapExecutorConfig
"""
from hummingbot.strategy_v2.executors.swap_executor.data_types import SwapExecutorConfig, SwapExecutorStates

__all__ = [
    "SwapExecutorConfig",
    "SwapExecutorStates",
]
