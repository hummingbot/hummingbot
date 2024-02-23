import time
from typing import List, Optional, Tuple, Union

from pydantic import Field, root_validator, validator

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.core.data_type.common import PriceType, TradeType
from hummingbot.smart_components.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.smart_components.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction


class MarketMakingControllerConfigBase(ControllerConfigBase):
    """
    This class represents the base configuration for a market making controller.
    """
    connector_name: str = Field(
        default="binance_perpetual",
        client_field=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda: "Enter the name of the exchange to trade on (e.g., binance_perpetual):"))
    trading_pair: str = Field(
        default="WLD-USDT",
        client_field=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda: "Enter the trading pair to trade on (e.g., WLD-USDT):"))
    total_amount_quote: float = Field(
        default=100,
        client_field=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda: "Enter the total amount in quote asset to use for trading (e.g., 1000):"))

    buy_spreads: Union[List[float], str] = Field(
        default="0.01, 0.02",
        client_field=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda: "Enter a comma-separated list of buy spreads (e.g., '0.01, 0.02'):"))
    buy_amounts_pct: Union[List[int], str, None] = Field(
        default=None,
        client_field=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda: "Enter a comma-separated list of buy amounts as percentages (e.g., '50, 50'), or leave blank to distribute equally:"))
    sell_spreads: Union[List[float], str] = Field(
        default="0.01,0.02",
        client_field=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda: "Enter a comma-separated list of sell spreads (e.g., '0.01, 0.02'):"))
    sell_amounts_pct: Union[List[int], str, None] = Field(
        default=None,
        client_field=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda: "Enter a comma-separated list of sell amounts as percentages (e.g., '50, 50'), or leave blank to distribute equally:"))
    executor_refresh_time: int = Field(
        default=60 * 5,
        client_field=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda: "Enter the refresh time in seconds for executors (e.g., 300 for 5 minutes):"))
    cooldown_time: int = Field(
        default=15,
        client_field=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda: "Specify the cooldown time in seconds between order placements (e.g., 15):"))
    leverage: int = Field(
        default=20,
        client_field=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda: "Set the leverage to use for trading (e.g., 20 for 20x leverage). Set it to 1 for spot trading:"))

    @validator('buy_spreads', 'sell_spreads', pre=True, always=True)
    def parse_spreads(cls, v):
        if isinstance(v, str):
            return [float(x.strip()) for x in v.split(',')]
        return v

    @validator('buy_amounts_pct', 'sell_amounts_pct', pre=True, always=True)
    def parse_and_validate_amounts(cls, v, values, field):
        if isinstance(v, str):
            v = [int(x.strip()) for x in v.split(',')]
        if v is None:
            spread_field = field.name.replace('amounts_pct', 'spreads')
            return [1 for _ in values[spread_field]]
        if len(v) != len(values[field.name.replace('amounts_pct', 'spreads')]):
            raise ValueError(
                f"The number of {field.name} must match the number of {field.name.replace('amounts_pct', 'spreads')}.")
        return v

    @root_validator
    def normalize_amounts(cls, values):
        buy_amounts_pct = values['buy_amounts_pct']
        sell_amounts_pct = values['sell_amounts_pct']

        total_buy = sum(buy_amounts_pct)
        total_sell = sum(sell_amounts_pct)

        values['buy_amounts_pct'] = [amt / total_buy for amt in buy_amounts_pct]
        values['sell_amounts_pct'] = [amt / total_sell for amt in sell_amounts_pct]

        return values

    def update_parameters(self, trade_type: TradeType, new_spreads: Union[List[float], str], new_amounts_pct: Optional[Union[List[int], str]] = None):
        spreads_field = 'buy_spreads' if trade_type == TradeType.BUY else 'sell_spreads'
        amounts_pct_field = 'buy_amounts_pct' if trade_type == TradeType.BUY else 'sell_amounts_pct'

        setattr(self, spreads_field, self.parse_spreads(new_spreads))
        if new_amounts_pct is not None:
            setattr(self, amounts_pct_field, self.parse_and_validate_amounts(new_amounts_pct, self.__dict__, amounts_pct_field))
        else:
            setattr(self, amounts_pct_field, [1 for _ in getattr(self, spreads_field)])
        self.normalize_amounts(self.__dict__)

    def get_spreads_and_amounts_in_quote(self, trade_type: TradeType) -> Tuple[List[float], List[float]]:
        spreads = getattr(self, f'{trade_type.name.lower()}_spreads')
        amounts_pct = getattr(self, f'{trade_type.name.lower()}_amounts_pct')
        return spreads, [amt_pct * self.total_amount_quote for amt_pct in amounts_pct]


class MarketMakingControllerBase(ControllerBase):
    """
    This class represents the base class for a market making controller.
    """
    def __init__(self, config: MarketMakingControllerConfigBase):
        super().__init__(config)
        self.config = config

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """
        Determine actions based on the provided executor handler report.
        """
        actions = []
        actions.extend(self.create_actions_proposal())
        actions.extend(self.stop_actions_proposal())
        actions.extend(self.store_actions_proposal())
        return actions

    def create_actions_proposal(self) -> List[ExecutorAction]:
        """
        Create actions proposal based on the current state of the controller.
        """
        create_actions = []
        active_buy_executors = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda executor: executor.trade_type == TradeType.BUY and executor.is_active)
        active_sell_executors = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda executor: executor.trade_type == TradeType.SELL and executor.is_active)
        active_levels_ids = [executor.custom_info["level_id"] for executor in active_buy_executors + active_sell_executors]
        not_active_levels = self.get_not_active_levels_ids(active_levels_ids)
        levels_to_execute = self.filter_not_active_levels(not_active_levels)
        for level_id in levels_to_execute:
            price, amount_quote = self.get_price_and_amount_in_quote(level_id)
            create_actions.append(CreateExecutorAction(
                controller_id=self.config.id,
                executor_config=self.get_executor_config(level_id, price, amount_quote)
            ))
        return create_actions

    def stop_actions_proposal(self) -> List[ExecutorAction]:
        """
        Create a list of actions to stop the executors based on order refresh and early stop conditions.
        """
        stop_actions = []
        stop_actions.extend(self.executors_to_refresh())
        stop_actions.extend(self.executors_to_early_stop())
        return stop_actions

    def executors_to_refresh(self) -> List[ExecutorAction]:
        executors_to_refresh = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda x: not x.is_trading and x.is_active and time.time() - x.timestamp > self.config.executor_refresh_time)

        return [StopExecutorAction(executor_id=executor.id) for executor in executors_to_refresh]

    async def update_market_data(self):
        """
        Update the market data for the controller. This method should be reimplemented to modify the reference price
        and spread multiplier based on the market data. By default, it will update the reference price as mid price and
        the spread multiplier as 1.
        """
        reference_price = self.market_data_provider.get_price_by_type(self.config.connector_name,
                                                                      self.config.trading_pair, PriceType.MidPrice)
        self.processed_data = {"reference_price": reference_price, "spread_multiplier": 1}

    def get_executor_config(self, level_id: str, price: float, amount_in_quote: float):
        """
        Get the executor config for a given level id.
        """
        raise NotImplementedError

    def get_price_and_amount_in_quote(self, level_id: str) -> Tuple[float, float]:
        """
        Get the spread and amount in quote for a given level id.
        """
        trade_type, level = level_id.split('_')
        spreads, amounts_quote = self.config.get_spreads_and_amounts_in_quote(TradeType[trade_type.upper()])
        reference_price = self.processed_data["reference_price"]
        spread_in_pct = spreads[int(level)] * self.processed_data["spread_multiplier"]
        side_multiplier = -1 if trade_type == TradeType.BUY else 1
        order_price = reference_price * (1 + side_multiplier * spread_in_pct)
        return order_price, amounts_quote[int(level)]

    def get_level_id_from_side(self, trade_type: TradeType, level: int) -> str:
        """
        Get the level id based on the trade type and the level.
        """
        return f"{trade_type.name.lower()}_{level}"

    def get_not_active_levels_ids(self, active_levels_ids: List[str]) -> List[str]:
        """
        Get the levels to execute based on the current state of the controller.
        """
        buy_ids_missing = [self.get_level_id_from_side(TradeType.BUY, level) for level in range(len(self.config.buy_spreads))
                           if self.get_level_id_from_side(TradeType.BUY, level) not in active_levels_ids]
        sell_ids_missing = [self.get_level_id_from_side(TradeType.SELL, level) for level in range(len(self.config.sell_spreads))
                            if self.get_level_id_from_side(TradeType.SELL, level) not in active_levels_ids]
        return buy_ids_missing + sell_ids_missing

    def filter_not_active_levels(self, not_active_levels: List[str]) -> List[str]:
        """
        Filter the not active levels based on the current state of the controller.
        This method can be overridden to implement custom behavior.
        """
        return not_active_levels
