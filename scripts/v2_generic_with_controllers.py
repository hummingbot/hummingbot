import os
from typing import Dict, List, Set

from pydantic import Field

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.models.executor_actions import (
    CreateExecutorAction,
    StopExecutorAction,
    StoreExecutorAction,
)
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase


class GenericV2StrategyWithControllersConfig(StrategyV2ConfigBase):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    candles_config: List[CandlesConfig] = []
    markets: Dict[str, Set[str]] = {}


class GenericV2StrategyWithControllers(StrategyV2Base):
    account_config_set = False

    def __init__(self, connectors: Dict[str, ConnectorBase], config: GenericV2StrategyWithControllersConfig):
        super().__init__(connectors, config)
        self.config = config

    def on_tick(self):
        self.set_position_mode_and_leverage()
        super().on_tick()

    def create_actions_proposal(self) -> List[CreateExecutorAction]:
        return []

    def stop_actions_proposal(self) -> List[StopExecutorAction]:
        return []

    def store_actions_proposal(self) -> List[StoreExecutorAction]:
        return []

    def set_position_mode_and_leverage(self):
        if not self.account_config_set:
            for controller_id, controller in self.controllers.items():
                config_dict = controller.config.dict()
                if self.is_perpetual(config_dict.get("connector_name")):
                    if "position_mode" in config_dict:
                        self.connectors[config_dict["connector_name"]].set_position_mode(config_dict["position_mode"])
                    if "leverage" in config_dict:
                        self.connectors[config_dict["connector_name"]].set_leverage(leverage=config_dict["leverage"],
                                                                                    trading_pair=config_dict["trading_pair"])
            self.account_config_set = True
