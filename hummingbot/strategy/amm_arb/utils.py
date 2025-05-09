from decimal import Decimal
from enum import Enum
from typing import List

from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

from .data_types import ArbProposal, ArbProposalSide, TokenAmount

s_decimal_nan = Decimal("NaN")


class TradeDirection(Enum):
    BUY = 1
    SELL = 0


async def create_arb_proposals(
        market_info_1: MarketTradingPairTuple,
        market_info_2: MarketTradingPairTuple,
        market_1_extra_flat_fees: List[TokenAmount],
        market_2_extra_flat_fees: List[TokenAmount],
        order_amount: Decimal
) -> List[ArbProposal]:
    order_amount = Decimal(str(order_amount))
    results = []

    tasks = []
    for trade_direction in TradeDirection:
        is_buy = trade_direction == TradeDirection.BUY
        tasks.append([
            market_info_1.market.get_quote_price(market_info_1.trading_pair, is_buy, order_amount),
            market_info_1.market.get_order_price(market_info_1.trading_pair, is_buy, order_amount),
            market_info_2.market.get_quote_price(market_info_2.trading_pair, not is_buy, order_amount),
            market_info_2.market.get_order_price(market_info_2.trading_pair, not is_buy, order_amount)
        ])

    results_raw = await safe_gather(*[safe_gather(*task_group) for task_group in tasks])

    for trade_direction, task_group_result in zip(TradeDirection, results_raw):
        is_buy = trade_direction == TradeDirection.BUY
        m_1_q_price, m_1_o_price, m_2_q_price, m_2_o_price = task_group_result

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
