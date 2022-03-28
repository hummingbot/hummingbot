from decimal import Decimal
from typing import List, Optional

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from .data_types import (
    ArbProposal,
    ArbProposalSide,
    TokenAmount,
)

s_decimal_nan = Decimal("NaN")


async def create_arb_proposals(
        market_info_1: MarketTradingPairTuple,
        market_info_2: MarketTradingPairTuple,
        market_1_extra_flat_fees: List[TokenAmount],
        market_2_extra_flat_fees: List[TokenAmount],
        order_amount: Decimal,
) -> List[ArbProposal]:
    """
    Creates base arbitrage proposals for given markets without any filtering.
    :param market_info_1: The first market
    :param market_info_2: The second market
    :param order_amount: The required order amount.
    :param market_1_extra_flat_fees: Gas fees for market 1, if appropriate.
    :param market_2_extra_flat_fees: Gas fees for market 2, if appropriate.
    :return A list of at most 2 proposal - (market_1 buy, market_2 sell) and (market_1 sell, market_2 buy)
    """
    order_amount = Decimal(str(order_amount))
    results = []
    for index in range(0, 2):
        is_buy: bool = not bool(index)  # bool(0) is False, so start with buy first
        m_1_q_price: Optional[Decimal] = await market_info_1.market.get_quote_price(
            market_info_1.trading_pair, is_buy, order_amount
        )
        m_1_o_price: Optional[Decimal] = await market_info_1.market.get_order_price(
            market_info_1.trading_pair, is_buy, order_amount
        )
        m_2_q_price: Optional[Decimal] = await market_info_2.market.get_quote_price(
            market_info_2.trading_pair, not is_buy, order_amount
        )
        m_2_o_price: Optional[Decimal] = await market_info_2.market.get_order_price(
            market_info_2.trading_pair, not is_buy, order_amount
        )
        if any(p is None for p in (m_1_o_price, m_1_q_price, m_2_o_price, m_2_q_price)):
            continue
        first_side = ArbProposalSide(
            market_info=market_info_1,
            is_buy=is_buy,
            quote_price=m_1_q_price,
            order_price=m_1_o_price,
            amount=order_amount,
            extra_flat_fees=market_1_extra_flat_fees,
        )
        second_side = ArbProposalSide(
            market_info=market_info_2,
            is_buy=not is_buy,
            quote_price=m_2_q_price,
            order_price=m_2_o_price,
            amount=order_amount,
            extra_flat_fees=market_2_extra_flat_fees
        )

        results.append(ArbProposal(first_side, second_side))
    return results
