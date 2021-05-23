from decimal import Decimal
from typing import List
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from .data_types import ArbProposal, ArbProposalSide

s_decimal_nan = Decimal("NaN")


async def create_arb_proposals(markets_info: List[MarketTradingPairTuple],
                               order_amount: Decimal) -> List[ArbProposal]:
    """
    Creates base arbitrage proposals for given markets without any filtering.
    :param markets_info: The list of markets informations
    :param order_amount: The required order amount.
    :return A list of proposals
    """
    order_amount = Decimal(str(order_amount))
    results = []
    for i, market_info_1 in enumerate(markets_info):
        for j, market_info_2 in enumerate(markets_info):
            if i != j:  # Do not arbitrage market with itself
                m_1_q_price = await market_info_1.market.get_quote_price(market_info_1.trading_pair, True, order_amount)
                m_1_o_price = await market_info_1.market.get_order_price(market_info_1.trading_pair, True, order_amount)
                m_2_q_price = await market_info_2.market.get_quote_price(market_info_2.trading_pair, False, order_amount)
                m_2_o_price = await market_info_2.market.get_order_price(market_info_2.trading_pair, False, order_amount)
                if any(p is None for p in (m_1_o_price, m_1_q_price, m_2_o_price, m_2_q_price)):
                    continue
                first_side = ArbProposalSide(
                    market_info_1,
                    True,
                    m_1_q_price,
                    m_1_o_price,
                    order_amount
                )
                second_side = ArbProposalSide(
                    market_info_2,
                    False,
                    m_2_q_price,
                    m_2_o_price,
                    order_amount
                )
                results.append(ArbProposal(first_side, second_side))
    return results
