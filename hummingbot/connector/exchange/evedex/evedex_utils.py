from typing import Any, Dict

from hummingbot.core.data_type.trade_fee import TradeFeeSchema


DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=0.0002,
    taker_percent_fee_decimal=0.0005,
    buy_percent_fee_deducted_from_returns=True
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    if "status" in exchange_info and exchange_info["status"] != "TRADING":
        return False
    return True
