import dataclasses
import decimal


@dataclasses.dataclass(frozen=True)
class ExchangeInstrumentPair:
    exchange_name: str
    instrument_name: str


@dataclasses.dataclass(frozen=True)
class TopOfBookPrices:
    bid: decimal.Decimal | None
    ask: decimal.Decimal | None


class ArbInfo:
    def __init__(self, exchange: ExchangeInstrumentPair):
        ...

    def profit_pct(self, with_fees, reverse: bool = False) -> decimal.Decimal:
        ...
