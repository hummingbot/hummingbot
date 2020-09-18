from decimal import Decimal
from typing import List
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from .data_types import ArbProposal, ArbProposalSide

s_decimal_nan = Decimal("NaN")


def create_arb_proposals(market_info_1: MarketTradingPairTuple,
                         market_info_2: MarketTradingPairTuple,
                         order_amount: Decimal) -> List[ArbProposal]:
    order_amount = Decimal(str(order_amount))
    results = []
    for index in range(0, 2):
        is_buy = not bool(index)  # bool(0) is False, so start with buy first
        first_side = ArbProposalSide(
            market_info_1,
            is_buy,
            market_info_1.market.get_quote_price(market_info_1.trading_pair, is_buy, order_amount),
            market_info_1.market.get_order_price(market_info_1.trading_pair, is_buy, order_amount),
            order_amount
        )
        second_side = ArbProposalSide(
            market_info_2,
            not is_buy,
            market_info_2.market.get_quote_price(market_info_2.trading_pair, not is_buy, order_amount),
            market_info_2.market.get_order_price(market_info_2.trading_pair, not is_buy, order_amount),
            order_amount
        )
        results.append(ArbProposal(first_side, second_side))
    return results
