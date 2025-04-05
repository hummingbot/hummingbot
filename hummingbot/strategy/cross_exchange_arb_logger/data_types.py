import dataclasses


@dataclasses.dataclass(frozen=True)
class ExchangeInstrumentPair:
    exchange_name: str
    instrument_name: str
