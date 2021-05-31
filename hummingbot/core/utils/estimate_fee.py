# -*- coding: utf-8 -*-

"""
Estimate the fee of a transaction on any blockchain.
"""

from decimal import Decimal
from hummingbot.core.event.events import TradeFee, TradeFeeType
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
from hummingbot.client.settings import CONNECTOR_SETTINGS


def estimate_fee(exchange: str, is_maker: bool) -> TradeFee:
    """
    Estimate the fee of a transaction on any blockchain.
    exchange is the name of the exchange to query.
    is_maker if true look at fee from maker side, otherwise from taker side.
    """
    if exchange not in CONNECTOR_SETTINGS:
        raise Exception(f"Invalid connector. {exchange} does not exist in CONNECTOR_SETTINGS")
    fee_type = CONNECTOR_SETTINGS[exchange].fee_type
    fee_token = CONNECTOR_SETTINGS[exchange].fee_token
    default_fees = CONNECTOR_SETTINGS[exchange].default_fees
    fee_side = "maker" if is_maker else "taker"
    override_key = f"{exchange}_{fee_side}"
    if fee_type is TradeFeeType.FlatFee:
        override_key += "_fee_amount"
    elif fee_type is TradeFeeType.Percent:
        override_key += "_fee"
    fee = default_fees[0] if is_maker else default_fees[1]
    fee_config = fee_overrides_config_map.get(override_key)
    if fee_config is not None and fee_config.value is not None:
        fee = fee_config.value
    fee = Decimal(str(fee))
    if fee_type is TradeFeeType.Percent:
        return TradeFee(percent=fee / Decimal("100"), flat_fees=[])
    elif fee_type is TradeFeeType.FlatFee:
        return TradeFee(percent=0, flat_fees=[(fee_token, fee)])
