from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

from .data_types import ArbSide, CrossExchangeArbProposal


def create_arb_proposals(
    market_info_1: MarketTradingPairTuple,
    market_info_2: MarketTradingPairTuple,
) -> list[CrossExchangeArbProposal]:
    return [
        create_arb_proposal(market_info_1, market_info_2),
        create_arb_proposal(market_info_2, market_info_1),
    ]


def create_arb_proposal(
    buy_market_info: MarketTradingPairTuple,
    sell_market_info: MarketTradingPairTuple,
) -> CrossExchangeArbProposal:
    best_buy = buy_market_info.get_price(is_buy=False)
    best_sell = sell_market_info.get_price(is_buy=True)
    return CrossExchangeArbProposal(
        buy=ArbSide(buy_market_info, best_buy),
        sell=ArbSide(sell_market_info, best_sell),
    )
