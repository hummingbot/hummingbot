from hummingbot.strategy.cross_exchange_arb_logger import CrossExchangeArbLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

from .data_types import ExchangeInstrumentPair


def start(self, exchange_instrument_pairs: list[ExchangeInstrumentPair], with_fees: bool) -> None:
    self._initialize_markets([
        (e.exchange_name, [e.instrument_name]) for e in exchange_instrument_pairs
    ])
    market_infos = [
        MarketTradingPairTuple(
            self.markets[pair.exchange_name],
            pair.instrument_name,
            *pair.instrument_name.split("-")  # This has already been sanitized
        )
        for pair in exchange_instrument_pairs
    ]
    self.market_trading_pair_tuples = market_infos
    self.strategy = CrossExchangeArbLogger(market_infos, with_fees)
