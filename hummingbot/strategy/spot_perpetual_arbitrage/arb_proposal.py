from functools import lru_cache
from decimal import Decimal
from typing import List
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
                 order_levels: List[List[Decimal, Decimal]]
                 ):
        """
        :param market_info: The market where to submit the order
        :param is_buy: True if buy order
        :param order_levels: A list of tuples, each tuple contains (order_price, order_amount)
        """
        self.market_info: MarketTradingPairTuple = market_info
        self.is_buy: bool = is_buy
        self.order_levels: List[List[Decimal, Decimal]] = order_levels

    @lru_cache()
    def get_order_price(self, order_amount: Decimal) -> Decimal:
        cum_amount = Decimal("0")
        for price, amount in self.order_levels:
            cum_amount += amount
            if cum_amount >= order_amount:
                return price
        raise ValueError(f"Order amount {order_amount} exceeds available levels.")

class ArbProposal:
    """
    An arbitrage proposal which contains 2 sides of the proposal - one on spot market and one on perpetual market.
    """
    def __init__(self,
                 spot_side: ArbProposalSide,
                 perp_side: ArbProposalSide,
                 max_possible_arbitrage_amount: Decimal):
        """
        Creates ArbProposal
        :param spot_side: An ArbProposalSide on spot market
        :param perp_side: An ArbProposalSide on perpetual market
        :param max_possible_arbitrage_amount: The maximum amount of base asset to arbitrage
        """
        if spot_side.is_buy == perp_side.is_buy:
            raise Exception("Spot and perpetual arb proposal cannot be on the same side.")
        self.spot_side: ArbProposalSide = spot_side
        self.perp_side: ArbProposalSide = perp_side
        self.max_possible_arbitrage_amount: Decimal = max_possible_arbitrage_amount

    def profit_pct(self, order_amount: Decimal) -> Decimal:
        """
        Calculates and returns arbitrage profit (in percentage value).
        """
        buy_price = self.spot_side.get_order_price(order_amount) if self.spot_side.is_buy else self.perp_side.get_order_price(order_amount)
        sell_price = self.spot_side.get_order_price(order_amount) if not self.spot_side.is_buy else self.perp_side.get_order_price(order_amount)
        if sell_price and buy_price:
            return (sell_price - buy_price) / buy_price
        return s_decimal_0

    def  get_max_profit_order_amount(self) -> Decimal:
        """
        Calculates and returns the order amount that maximises profit.
        It does this by checking the profit at each discrete liquidity level across both order books.
        """
        buy_side = self.spot_side if self.spot_side.is_buy else self.perp_side
        sell_side = self.perp_side if self.spot_side.is_buy else self.spot_side

        all_cumulative_amounts: List[Decimal] = []
        cumulative_amount = s_decimal_0
        for _, amount in buy_side.order_levels:
            cumulative_amount += amount
            if cumulative_amount > self.max_possible_arbitrage_amount:
                break
            all_cumulative_amounts.append(cumulative_amount)

        cumulative_amount = s_decimal_0
        for _, amount in sell_side.order_levels:
            cumulative_amount += amount
            if cumulative_amount > self.max_possible_arbitrage_amount:
                break
            all_cumulative_amounts.append(cumulative_amount)

        # get a unique, sorted list of all discrete amounts to check for profitability.
        # can be linear, but this is easier to understand.
        amounts_to_check: List[Decimal] = sorted(list(set(all_cumulative_amounts)))

        max_profit: Decimal = s_decimal_0
        best_amount: Decimal = s_decimal_0

        for amount in amounts_to_check:
            buy_price = buy_side.get_order_price(amount)
            sell_price = sell_side.get_order_price(amount)
            profit = (sell_price - buy_price) / buy_price * amount
            if profit <= max_profit:
                # maxima exists, exit if decreasing profit
                break
            max_profit = profit
            best_amount = amount

        return min(best_amount, self.max_possible_arbitrage_amount)
