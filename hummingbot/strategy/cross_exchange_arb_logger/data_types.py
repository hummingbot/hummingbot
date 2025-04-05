import dataclasses
import decimal

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


@dataclasses.dataclass(frozen=True)
class ExchangeInstrumentPair:
    exchange_name: str
    instrument_name: str


@dataclasses.dataclass(frozen=True)
class ArbSide:
    market_info: MarketTradingPairTuple
    price: decimal.Decimal


@dataclasses.dataclass(frozen=True)
class CrossExchangeArbProposal:
    buy: ArbSide
    sell: ArbSide
