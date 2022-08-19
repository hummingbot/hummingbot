from decimal import Decimal

import cython
import numpy as np

from ..data_types import InventorySkewBidAskRatios

decimal_0 = Decimal(0)
decimal_1 = Decimal(1)
decimal_2 = Decimal(2)


def calculate_total_order_size(order_start_size: Decimal, order_step_size: Decimal = decimal_0,
                               order_levels: cython.int = 1) -> Decimal:
    order_levels_decimal: cython.int = order_levels
    return (decimal_2 *
            (order_levels_decimal * order_start_size +
             order_levels_decimal * (order_levels_decimal - decimal_1) / decimal_2 * order_step_size
             )
            )


def calculate_bid_ask_ratios_from_base_asset_ratio(
        base_asset_amount: float, quote_asset_amount: float, price: float,
        target_base_asset_ratio: float, base_asset_range: float) -> InventorySkewBidAskRatios:
    return _c_calculate_bid_ask_ratios_from_base_asset_ratio(base_asset_amount,
                                                             quote_asset_amount,
                                                             price,
                                                             target_base_asset_ratio,
                                                             base_asset_range)


@cython.cfunc
@cython.inline
def _c_calculate_bid_ask_ratios_from_base_asset_ratio(
        base_asset_amount: cython.double,
        quote_asset_amount: cython.double,
        price: cython.double,
        target_base_asset_ratio: cython.double,
        base_asset_range: cython.double) -> object:
    total_portfolio_value: cython.double = base_asset_amount * price + quote_asset_amount

    if total_portfolio_value <= 0.0 or base_asset_range <= 0.0:
        return InventorySkewBidAskRatios(0.0, 0.0)

    base_asset_value: cython.double = base_asset_amount * price
    base_asset_range_value: cython.double = min(base_asset_range * price, total_portfolio_value * 0.5)
    target_base_asset_value: cython.double = total_portfolio_value * target_base_asset_ratio
    left_base_asset_value_limit: cython.double = max(target_base_asset_value - base_asset_range_value, 0.0)
    right_base_asset_value_limit: cython.double = target_base_asset_value + base_asset_range_value

    left_inventory_ratio: cython.double = np.interp(base_asset_value,
                                                    (left_base_asset_value_limit, target_base_asset_value),
                                                    (0, 0.5))

    right_inventory_ratio: cython.double = np.interp(base_asset_value,
                                                     (target_base_asset_value, right_base_asset_value_limit),
                                                     (0.5, 1.0))
    bid_adjustment: cython.double = (np.interp(left_inventory_ratio,
                                               (0, 0.5),
                                               (2.0, 1.0))
                                     if base_asset_value < target_base_asset_value
                                     else np.interp(right_inventory_ratio,
                                                    (0.5, 1),
                                                    (1.0, 0.0)))
    ask_adjustment: cython.double = 2.0 - bid_adjustment

    return InventorySkewBidAskRatios(bid_adjustment, ask_adjustment)
