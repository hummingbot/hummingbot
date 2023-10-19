from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from hummingbot.core.data_type.common import TradeType
from hummingbot.smart_components.strategy_frameworks.data_types import OrderLevel, TripleBarrierConf
from hummingbot.smart_components.utils.distributions import Distribution


class OrderLevelBuilder:
    def __init__(self, n_levels: int):
        """
        Initialize the OrderLevelBuilder with the number of levels.

        Args:
            n_levels (int): The number of order levels.
        """
        self.n_levels = n_levels

    def resolve_input(self, input_data: Union[Decimal, List[Decimal], Dict[str, Any]]) -> Union[Decimal, List[Decimal], List[float], Any]:
        """
        Resolve the provided input data into a list of values.

        Args:
            input_data: The input data to resolve. Can be a single value, list, or dictionary.

        Returns:
            List[Decimal]: List of resolved values.
        """
        if isinstance(input_data, Decimal):
            return [input_data] * self.n_levels
        elif isinstance(input_data, list):
            if len(input_data) != self.n_levels:
                raise ValueError(f"List length must match the number of levels: {self.n_levels}")
            return input_data
        elif isinstance(input_data, dict):
            distribution_method = input_data["method"]
            distribution_func = getattr(Distribution, distribution_method, None)
            if not distribution_func:
                raise ValueError(f"Unsupported distribution method: {distribution_method}")
            return distribution_func(self.n_levels, **input_data["params"])
        else:
            raise ValueError(f"Unsupported input data type: {type(input_data)}")

    def build_order_levels(self,
                           amounts: Union[Decimal, List[Decimal], Dict[str, Any]],
                           spreads: Union[Decimal, List[Decimal], Dict[str, Any]],
                           triple_barrier_confs: Union[TripleBarrierConf, List[TripleBarrierConf]],
                           sides: Optional[List[TradeType]] = None) -> List[OrderLevel]:
        """
        Build a list of OrderLevels based on given parameters.

        Args:
            sides: Trading sides, either BUY or SELL.
            amounts: Amounts to be used for each order level.
            spreads: Spread factors for each order level.
            triple_barrier_confs: Triple barrier configurations.

        Returns:
            List[OrderLevel]: List of constructed OrderLevel objects.
        """

        # Default to both BUY and SELL if sides not provided
        if sides is None:
            sides = [TradeType.BUY, TradeType.SELL]

        # Resolve input data into a consistent format
        resolved_amounts = self.resolve_input(amounts)
        resolved_spreads = self.resolve_input(spreads)

        # If only one TripleBarrierConf is provided, replicate it for all levels
        if isinstance(triple_barrier_confs, TripleBarrierConf):
            triple_barrier_confs = [triple_barrier_confs] * self.n_levels

        order_levels = []
        for i, spread in enumerate(resolved_spreads):
            barrier_conf = triple_barrier_confs[i]

            for side in sides:
                order_level = OrderLevel(
                    level=i + 1,
                    side=side,
                    order_amount_usd=Decimal(resolved_amounts[i]),
                    spread_factor=Decimal(spread),
                    triple_barrier_conf=barrier_conf
                )
                order_levels.append(order_level)

        return order_levels
