from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel
from pydantic.class_validators import validator

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.position_executor.data_types import TripleBarrierConfig
from hummingbot.strategy_v2.utils.distributions import Distributions


class OrderLevel(BaseModel):
    level: int
    side: TradeType
    order_amount_usd: Decimal
    spread_factor: Decimal = Decimal("0.0")
    order_refresh_time: int = 60
    cooldown_time: int = 0
    triple_barrier_conf: TripleBarrierConfig

    @property
    def level_id(self):
        return f"{self.side.name}_{self.level}"

    @validator("order_amount_usd", "spread_factor", pre=True, allow_reuse=True)
    def float_to_decimal(cls, v):
        return Decimal(v)


class OrderLevelBuilder:
    def __init__(self, n_levels: int):
        """
        Initialize the OrderLevelBuilder with the number of levels.

        Args:
            n_levels (int): The number of order levels.
        """
        self.n_levels = n_levels

    def resolve_input(self, input_data: Union[Decimal | float, List[Decimal | float], Dict[str, Any]]) -> List[Decimal | float | int]:
        """
        Resolve the provided input data into a list of Decimal values.

        Args:
            input_data: The input data to resolve. Can be a single value, list, or dictionary.

        Returns:
            List[Decimal | float | int]: List of resolved Decimal values.
        """
        if isinstance(input_data, Decimal) or isinstance(input_data, float) or isinstance(input_data, int):
            return [input_data] * self.n_levels
        elif isinstance(input_data, list):
            if len(input_data) != self.n_levels:
                raise ValueError(f"List length must match the number of levels: {self.n_levels}")
            return input_data
        elif isinstance(input_data, dict):
            distribution_method = input_data["method"]
            distribution_func = getattr(Distributions, distribution_method, None)
            if not distribution_func:
                raise ValueError(f"Unsupported distribution method: {distribution_method}")
            return distribution_func(self.n_levels, **input_data["params"])
        else:
            raise ValueError(f"Unsupported input data type: {type(input_data)}")

    def build_order_levels(self,
                           amounts: Union[Decimal, List[Decimal], Dict[str, Any]],
                           spreads: Union[Decimal, List[Decimal], Dict[str, Any]],
                           triple_barrier_confs: Union[TripleBarrierConfig, List[TripleBarrierConfig]] = TripleBarrierConfig(),
                           order_refresh_time: Union[int, List[int], Dict[str, Any]] = 60 * 5,
                           cooldown_time: Union[int, List[int], Dict[str, Any]] = 0,
                           sides: Optional[List[TradeType]] = None) -> List[OrderLevel]:
        """
        Build a list of OrderLevels based on the given parameters.

        Args:
            amounts: Amounts to be used for each order level.
            spreads: Spread factors for each order level.
            triple_barrier_confs: Triple barrier configurations.
            order_refresh_time: Time in seconds to wait before refreshing orders.
            cooldown_time: Time in seconds to wait after an order fills before placing a new one.
            sides: Trading sides, either BUY or SELL. Default is both.

        Returns:
            List[OrderLevel]: List of constructed OrderLevel objects.
        """
        if sides is None:
            sides = [TradeType.BUY, TradeType.SELL]

        resolved_amounts = self.resolve_input(amounts)
        resolved_spreads = self.resolve_input(spreads)
        resolved_order_refresh_time = self.resolve_input(order_refresh_time)
        resolved_cooldown_time = self.resolve_input(cooldown_time)

        if not isinstance(triple_barrier_confs, list):
            triple_barrier_confs = [triple_barrier_confs] * self.n_levels

        order_levels = []
        for i in range(self.n_levels):
            for side in sides:
                order_level = OrderLevel(
                    level=i + 1,
                    side=side,
                    order_amount_usd=resolved_amounts[i],
                    spread_factor=resolved_spreads[i],
                    triple_barrier_conf=triple_barrier_confs[i],
                    order_refresh_time=resolved_order_refresh_time[i],
                    cooldown_time=resolved_cooldown_time[i]
                )
                order_levels.append(order_level)

        return order_levels
