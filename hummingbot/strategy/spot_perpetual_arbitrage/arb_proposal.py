from decimal import Decimal
from hummingbot.core.utils.async_utils import safe_gather
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
                 order_price: Decimal,
                 amount: Decimal
                 ):
        """
        :param market_info: The market where to submit the order
        :param is_buy: True if buy order
        :param order_price: The price required for order submission, this could differ from the quote price
        :param amount: The order amount
        """
        self.market_info: MarketTradingPairTuple = market_info
        self.is_buy: bool = is_buy
        self.order_price: Decimal = order_price
        self.amount: Decimal = amount

    def __repr__(self):
        side = "Buy" if self.is_buy else "Sell"
        base, quote = self.market_info.trading_pair.split("-")
        return f"{self.market_info.market.display_name.capitalize()}:  {side}  {self.amount} {base}" \
               f" at {self.order_price} {quote}."


class ArbProposal:
    """
    An arbitrage proposal which contains 2 sides of the proposal - one buy and one sell.
    """
    def __init__(self,
                 spot_market_info: MarketTradingPairTuple,
                 derivative_market_info: MarketTradingPairTuple,
                 order_amount: Decimal,
                 timestamp: float):
        self.spot_market_info: MarketTradingPairTuple = spot_market_info
        self.derivative_market_info: MarketTradingPairTuple = derivative_market_info
        self.spot_side: ArbProposalSide = None
        self.derivative_side: ArbProposalSide = None
        self.amount: Decimal = order_amount
        self.timestamp: float = timestamp
        self.spot_buy_sell_prices = [0, 0]
        self.deriv_buy_sell_prices = [0, 0]

    async def update_prices(self):
        """
        Update the buy and sell prices for both spot and deriv connectors.
        """
        tasks = [self.spot_market_info.market.get_order_price(self.spot_market_info.trading_pair, True, self.amount),
                 self.spot_market_info.market.get_order_price(self.spot_market_info.trading_pair, False, self.amount),
                 self.derivative_market_info.market.get_order_price(self.derivative_market_info.trading_pair, True, self.amount),
                 self.derivative_market_info.market.get_order_price(self.derivative_market_info.trading_pair, False, self.amount)]

        prices = await safe_gather(*tasks, return_exceptions=True)
        self.spot_buy_sell_prices = [prices[0], prices[1]]
        self.deriv_buy_sell_prices = [prices[2], prices[3]]

    def is_funding_payment_time(self):
        """
        Check if it's time for funding payment.
        Return True if it's time for funding payment else False.
        """
        funding_info = self.derivative_market_info.market.get_funding_info(self.derivative_market_info.trading_pair)
        funding_payment_span = self.derivative_market_info.market._funding_payment_span
        return bool(self.timestamp > (funding_info["nextFundingTime"] - funding_payment_span[0]) and \
           self.timestamp < (funding_info["nextFundingTime"] + funding_payment_span[1]))

    async def proposed_spot_deriv_arb(self):
        """
        Determine if the current situation is contango or backwardation and return a pair of buy and sell prices accordingly.
        """
        await self.update_prices()
        if (sum(self.spot_buy_sell_prices) / 2) > (sum(self.deriv_buy_sell_prices) / 2):  # Backwardation
            self.spot_side = ArbProposalSide(self.spot_market_info, False,
                                             self.spot_buy_sell_prices[1],
                                             self.amount)
            self.derivative_side = ArbProposalSide(self.derivative_market_info, True,
                                                   self.deriv_buy_sell_prices[0],
                                                   self.amount)
            return (self.spot_side, self.derivative_side)
        else:  # Contango
            self.spot_side = ArbProposalSide(self.spot_market_info, True,
                                             self.spot_buy_sell_prices[0],
                                             self.amount)
            self.derivative_side = ArbProposalSide(self.derivative_market_info, False,
                                                   self.deriv_buy_sell_prices[1],
                                                   self.amount)
            return (self.spot_side, self.derivative_side)

    def alternate_proposal_sides(self):
        """
        Alternate the sides and prices of proposed spot and derivative arb.
        """
        if self.spot_side.is_buy:
            self.spot_side.is_buy = False
            self.spot_side.order_price = self.spot_buy_sell_prices[1]
            self.derivative_side.is_buy = True
            self.derivative_side.order_price = self.deriv_buy_sell_prices[0]
        else:
            self.spot_side.is_buy = True
            self.spot_side.order_price = self.spot_buy_sell_prices[0]
            self.derivative_side.is_buy = False
            self.derivative_side.order_price = self.deriv_buy_sell_prices[1]
        return (self.spot_side, self.derivative_side)

    def spread(self):
        spread = abs(self.spot_side.order_price - self.derivative_side.order_price) / min(self.spot_side.order_price, self.derivative_side.order_price)
        return Decimal(str(spread))

    def __repr__(self):
        return f"Spot - {self.spot_market_info.market}\nDerivative - {self.derivative_market_info.market}"
