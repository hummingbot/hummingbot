from hummingbot.strategy.cross_exchange_arb_logger import CrossExchangeArbLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

from .data_types import ExchangeInstrumentPair


async def start(self, exchange_instrument_pairs: list[ExchangeInstrumentPair], with_fees: bool) -> None:
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

    supported_pairs: dict[str, set[str]] = {}

    # Check each exchange supports the pair
    for market_info in market_infos:
        if market_info.market.name not in supported_pairs:
            trading_pairs = await market_info.market.all_trading_pairs()
            supported_pairs[market_info.market.name] = set(trading_pairs)
        if market_info.trading_pair not in supported_pairs[market_info.market.name]:
            msg = f"Instrument '{market_info.trading_pair}' not supported by {market_info.market.name}."
            self.notify(msg)
            raise ValueError(msg)

    self.market_trading_pair_tuples = market_infos
    self.strategy = CrossExchangeArbLogger(market_infos, with_fees)
