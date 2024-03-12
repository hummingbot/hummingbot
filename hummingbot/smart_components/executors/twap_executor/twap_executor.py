import logging

from hummingbot.logger import HummingbotLogger
from hummingbot.smart_components.executors.executor_base import ExecutorBase
from hummingbot.smart_components.executors.twap_executor.data_types import TWAPExecutorConfig
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class TWAPExecutor(ExecutorBase):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, strategy: ScriptStrategyBase, config: TWAPExecutorConfig, update_interval: float = 1.0,
                 max_retries: int = 15):
        super().__init__(strategy=strategy, connectors=[config.connector_name], config=config, update_interval=update_interval)
        self._config = config
