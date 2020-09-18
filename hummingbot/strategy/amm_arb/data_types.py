from decimal import Decimal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

s_decimal_nan = Decimal("NaN")


class ArbProposalSide:
    def __init__(self,
                 market_info: MarketTradingPairTuple,
                 is_buy: bool,
                 quote_price: Decimal,
                 order_price: Decimal,
                 amount: Decimal
                 ):
        self.market_info: MarketTradingPairTuple = market_info
        self.is_buy: bool = is_buy
        self.quote_price: Decimal = quote_price
        self.order_price: Decimal = order_price
        self.amount: Decimal = amount

    def __repr__(self):
        side = "BUY" if self.is_buy else "SELL"
        return f"Connector: {self.market_info.market.display_name}  Side: {side}  Quote Price: {self.quote_price}  " \
               f"Order Price: {self.order_price}  Amount: {self.amount}"


class ArbProposal:
    def __init__(self, first_side: ArbProposalSide, second_side: ArbProposalSide):
        if first_side.is_buy == second_side.is_buy:
            raise Exception("first_side and second_side must be on different side of buy and sell.")
        self.first_side: ArbProposalSide = first_side
        self.second_side: ArbProposalSide = second_side

    def profit_pct(self) -> Decimal:
        buy = self.first_side if self.first_side.is_buy else self.second_side
        sell = self.first_side if not self.first_side.is_buy else self.second_side
        if buy.quote_price == 0:
            return s_decimal_nan
        return (sell.quote_price - buy.quote_price) / buy.quote_price

    def __repr__(self):
        return f"First Side - {self.first_side}\nSecond Side - {self.second_side}"
