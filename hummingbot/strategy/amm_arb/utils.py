from decimal import Decimal
from typing import NamedTuple, List
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

s_decimal_nan = Decimal("NaN")


class OrderProspect(NamedTuple):
    market_pair: MarketTradingPairTuple
    is_buy: bool
    quote_price: Decimal
    order_price: Decimal


class TradeProfit(NamedTuple):
    prospects: List[OrderProspect]
    amount: Decimal

    def profit_pct(self) -> Decimal:
        buy = [p for p in self.prospects if p.is_buy][0]
        sell = [p for p in self.prospects if not p.is_buy][0]
        if buy.quote_price == 0:
            return s_decimal_nan
        return (sell.quote_price - buy.quote_price) / buy.quote_price


def create_trade_profits(market_pairs: List[MarketTradingPairTuple], order_amount: Decimal) -> List[TradeProfit]:
    order_amount = Decimal(str(order_amount))
    results = []
    for index in range(0, 1):
        is_buy = not bool(index)  # bool(0) is False, so start with buy first
        prospect_1 = OrderProspect(
            market_pairs[0].market,
            is_buy,
            market_pairs[0].market.get_quote_price(market_pairs[0].trading_pair, is_buy, order_amount),
            market_pairs[0].market.get_order_price(market_pairs[0].trading_pair, is_buy, order_amount)
        )
        prospect_2 = OrderProspect(
            market_pairs[1].market,
            not is_buy,
            market_pairs[1].market.get_quote_price(market_pairs[1].trading_pair, not is_buy, order_amount),
            market_pairs[1].market.get_order_price(market_pairs[1].trading_pair, not is_buy, order_amount)
        )
        results.append(TradeProfit([prospect_1, prospect_2], order_amount))
    return results
