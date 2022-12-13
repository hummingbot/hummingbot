from decimal import Decimal

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

s_decimal_nan = Decimal("NaN")
s_decimal_0 = Decimal("0")


class ArbProposalSide:
    """
    An arbitrage proposal side which contains info needed for order submission.
    """
    def __init__(self,
                 market_info: MarketTradingPairTuple,
                 is_buy: bool,
                 order_price: Decimal
                 ):
        """
        :param market_info: The market where to submit the order
        :param is_buy: True if buy order
        :param order_price: The price required for order submission, this could differ from the quote price
        """
        self.market_info: MarketTradingPairTuple = market_info
        self.is_buy: bool = is_buy
        self.order_price: Decimal = order_price

    def __repr__(self):
        side = "Buy" if self.is_buy else "Sell"
        base, quote = self.market_info.trading_pair.split("-")
        return f"{self.market_info.market.display_name.capitalize()}: {side} {base}" \
               f" at {self.order_price} {quote}."


class ArbProposal:
    """
    An arbitrage proposal which contains 2 sides of the proposal - one on spot market and one on perpetual market.
    """
    def __init__(self,
                 spot_side: ArbProposalSide,
                 perp_side: ArbProposalSide,
                 order_amount: Decimal):
        """
        Creates ArbProposal
        :param spot_side: An ArbProposalSide on spot market
        :param perp_side: An ArbProposalSide on perpetual market
        :param order_amount: An order amount for both spot and perpetual market
        """
        if spot_side.is_buy == perp_side.is_buy:
            raise Exception("Spot and perpetual arb proposal cannot be on the same side.")
        self.spot_side: ArbProposalSide = spot_side
        self.perp_side: ArbProposalSide = perp_side
        self.order_amount: Decimal = order_amount

    def profit_pct(self) -> Decimal:
        """
        Calculates and returns arbitrage profit (in percentage value).
        """
        buy_price = self.spot_side.order_price if self.spot_side.is_buy else self.perp_side.order_price
        sell_price = self.spot_side.order_price if not self.spot_side.is_buy else self.perp_side.order_price
        if sell_price and buy_price:
            return (sell_price - buy_price) / buy_price
        return s_decimal_0

    def __repr__(self):
        return f"Spot: {self.spot_side}\nPerpetual: {self.perp_side}\nOrder amount: {self.order_amount}\n" \
               f"Profit: {self.profit_pct():.2%}"
