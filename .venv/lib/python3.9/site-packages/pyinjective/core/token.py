from dataclasses import dataclass
from decimal import Decimal

from pyinjective.constant import ADDITIONAL_CHAIN_FORMAT_DECIMALS


@dataclass(eq=True, frozen=True)
class Token:
    name: str
    symbol: str
    denom: str
    address: str
    decimals: int
    logo: str
    updated: int

    @staticmethod
    def convert_value_to_extended_decimal_format(value: Decimal) -> Decimal:
        return value * Decimal(f"1e{ADDITIONAL_CHAIN_FORMAT_DECIMALS}")

    @staticmethod
    def convert_value_from_extended_decimal_format(value: Decimal) -> Decimal:
        return value / Decimal(f"1e{ADDITIONAL_CHAIN_FORMAT_DECIMALS}")

    def chain_formatted_value(self, human_readable_value: Decimal) -> Decimal:
        return human_readable_value * Decimal(f"1e{self.decimals}")
