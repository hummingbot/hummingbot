from decimal import Decimal
from typing import Any, Dict, List, Union

from hummingbot.core.data_type.common import TradeType
from hummingbot.smart_components.strategy_frameworks.data_types import OrderLevel, TripleBarrierConf
from hummingbot.smart_components.utils.distributions import DistributionFactory


class OrderLevelBuilder:
    def __init__(self, n_levels: int):
        self.n_levels = n_levels

    def _resolve_input(self, input_data: Union[Decimal, List[Decimal], Dict[str, Any]]) -> Decimal | list | list[float] | Any:
        """
        Resolve the provided input data into a list of values.

        Args:
            input_data: The input data to resolve. Can be a single value, list, or dictionary.

        Returns:
            List[Decimal]: List of resolved values.

        Raises:
            ValueError: If the input data type is unsupported.
        """
        if isinstance(input_data, Decimal):
            return [input_data] * self.n_levels
        elif isinstance(input_data, list):
            assert len(input_data) == self.n_levels, f"List length must match the number of levels: {self.n_levels}"
            return input_data
        elif isinstance(input_data, dict):
            distribution_method = input_data["method"]
            distribution = DistributionFactory.create_distribution(distribution_method)
            return distribution.distribute(n_levels=self.n_levels, params=input_data["params"])
        else:
            raise ValueError(f"Unsupported input data type: {type(input_data)}")

    def build_order_levels(self,
                           sides: List[TradeType],
                           amounts: Union[Decimal, List[Decimal], Dict[str, Any]],
                           spreads: Union[Decimal, List[Decimal], Dict[str, Any]],
                           triple_barrier_confs: Union[TripleBarrierConf, List[TripleBarrierConf]]) -> List[OrderLevel]:
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
        resolved_amounts = self._resolve_input(amounts)
        resolved_spreads = self._resolve_input(spreads)

        if not isinstance(triple_barrier_confs, list):
            triple_barrier_confs = [triple_barrier_confs] * self.n_levels

        order_levels = []
        for i in range(self.n_levels):
            for side in sides:
                order_level = OrderLevel(
                    level=i + 1,
                    side=side,
                    order_amount_usd=Decimal(resolved_amounts[i]),
                    spread_factor=Decimal(resolved_spreads[i]),
                    triple_barrier_conf=triple_barrier_confs[i]
                )
                order_levels.append(order_level)
        return order_levels
