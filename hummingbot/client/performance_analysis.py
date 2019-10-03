import logging
from typing import (
    Tuple, Dict, List
)

from sqlalchemy.orm import Session

from hummingbot.client.data_type.currency_amount import CurrencyAmount
from hummingbot.core.event.events import TradeType
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion
from hummingbot.logger import HummingbotLogger
from hummingbot.model.sql_connection_manager import SQLConnectionManager
from hummingbot.model.trade_fill import TradeFill
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
ERC = ExchangeRateConversion.get_instance()
s_float_nan = float("nan")
s_float_0 = float(0)


class PerformanceAnalysis:
    def __init__(self):
        self._starting_base = CurrencyAmount()
        self._starting_quote = CurrencyAmount()
        self._current_base = CurrencyAmount()
        self._current_quote = CurrencyAmount()

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.pfa_logger is None:
            cls.pfa_logger = logging.getLogger(__name__)
        return cls.pfa_logger

    def _get_currency_amount_pair(self, is_base: bool, is_starting: bool) -> CurrencyAmount:
        """ Helper method to select the correct CurrencyAmount pair. """
        if is_base and is_starting:
            return self._starting_base
        elif not is_base and is_starting:
            return self._starting_quote
        elif is_base and not is_starting:
            return self._current_base
        else:
            return self._current_quote

    def add_balances(self, asset_name: str, amount: float, is_base: bool, is_starting: bool):
        """ Adds the balance of either the base or the quote in the given market symbol pair token to the corresponding
        CurrencyAmount object.

        NOTE: This is not to say that base / quote pairs between different markets are equivalent because that is NOT
        the case. Instead, this method will determine the current conversion rate between two stable coins before
        adding the balance to the corresponding CurrencyAmount object. Additionally, since it is possible that the
        exchange rate varies from the starting time of the bot to the current time, this conversion will always be
        performed using the SAME conversion rate - that is, the current conversion rate.

        So for example, let's say we are trading WETH/DAI and ETH/USD. Let's also assume that in  the
        hummingbot_application class, the first MarketTradingPairTuple in the market_trading_pair_tuple list is WETH/DAI. This means
        that in theory, the base and quote balances will be computed in terms of WETH and DAI, respectively. When the
        ETH and USD balances are added to those of WETH and DAI, the token conversion method - see
        erc.convert_token_value() will be called to convert the currencies using the CURRENT conversion rate. The
        current WETH/ETH conversion rate as well as the current DAI/USD conversion rates will be used for BOTH the
        starting and the current balance to ensure that any changes in the conversion rates while the bot was running
        do not affect the performance analysis feature."""
        currency_amount = self._get_currency_amount_pair(is_base, is_starting)
        if currency_amount.token is None:
            currency_amount.token = asset_name
            currency_amount.amount = amount
        else:
            if currency_amount.token == asset_name:
                currency_amount.amount += amount
            else:
                erc = ExchangeRateConversion.get_instance()
                temp_amount = erc.convert_token_value(amount, asset_name, currency_amount.token, source="default")
                currency_amount.amount += temp_amount

    def compute_starting(self, price: float) -> Tuple[str, float]:
        """ Computes the starting amount of token between both exchanges. """
        starting_amount = (self._starting_base.amount * price) + self._starting_quote.amount
        starting_token = self._starting_quote.token
        return starting_token, starting_amount

    def compute_current(self, price: float) -> Tuple[str, float]:
        """ Computes the current amount of token between both exchanges. """
        current_amount = (self._current_base.amount * price) + self._current_quote.amount
        current_token = self._current_quote.token
        return current_token, current_amount

    def compute_delta(self, price: float) -> Tuple[str, float]:
        """ Computes the delta between current amount in exchange and starting amount. """
        starting_token, starting_amount = self.compute_starting(price)
        _, current_amount = self.compute_current(price)
        delta = current_amount - starting_amount
        return starting_token, delta

    def compute_return(self, price: float) -> float:
        """ Compute the profitability of the trading bot based on the starting and current prices """
        _, starting_amount = self.compute_starting(price)
        if starting_amount == 0:
            return float('nan')
        _, delta = self.compute_delta(price)
        percent = (delta / starting_amount) * 100
        return percent

    @staticmethod
    def calculate_trade_asset_delta_with_fees(trade: TradeFill):
        trade_fee: Dict[str, any] = trade.trade_fee
        total_flat_fees: float = s_float_0
        for flat_fee_currency, flat_fee_amount in trade_fee["flat_fees"]:
            if flat_fee_currency == trade.quote_asset:
                total_flat_fees += flat_fee_amount
            else:
                # if the flat fee currency symbol does not match quote symbol, convert to quote currency value
                total_flat_fees += ExchangeRateConversion.get_instance().convert_token_value(
                    amount=flat_fee_amount,
                    from_currency=flat_fee_currency,
                    to_currency=trade.quote_asset,
                    source="default"
                )
        if trade.trade_type == TradeType.SELL.name:
            net_base_delta: float = trade.amount
            net_quote_delta: float = trade.amount * trade.price * (1 - float(trade_fee["percent"])) - total_flat_fees
        elif trade.trade_type == TradeType.BUY.name:
            net_base_delta: float = trade.amount * (1 - float(trade_fee["percent"])) - total_flat_fees
            net_quote_delta: float = trade.amount * trade.price
        else:
            raise Exception(f"Unsupported trade type {trade.trade-type}")
        return net_base_delta, net_quote_delta

    @staticmethod
    def calculate_asset_delta_from_trades(analysis_start_time: int,
                                          current_startegy_name: str,
                                          market_trading_pair_tuples: List[MarketTradingPairTuple]
                                          ) -> Dict[str, Dict[str, float]]:
        session: Session = SQLConnectionManager.get_trade_fills_instance().get_shared_session()
        market_trading_pair_stats: Dict[MarketTradingPairTuple, Dict[str, float]] = {}
        for market_trading_pair_tuple in market_trading_pair_tuples:
            asset_stats: Dict[str, float] = {
                market_trading_pair_tuple.base_asset: {"spent": s_float_0, "acquired": s_float_0},
                market_trading_pair_tuple.quote_asset: {"spent": s_float_0, "acquired": s_float_0}
            }
            queried_trades: List[TradeFill] = TradeFill.get_trades(session,
                                                                   start_time=analysis_start_time,
                                                                   market=market_trading_pair_tuple.market.display_name,
                                                                   strategy=current_startegy_name)
            if not queried_trades:
                market_trading_pair_stats[market_trading_pair_tuple] = {
                    "starting_quote_rate": market_trading_pair_tuple.get_mid_price(),
                    "asset": asset_stats
                }
                continue

            for trade in queried_trades:
                trade_side: str = trade.trade_type

                base_delta, quote_delta = PerformanceAnalysis.calculate_trade_asset_delta_with_fees(trade)
                if trade_side == TradeType.SELL.name:
                    asset_stats[trade.base_asset]["spent"] += base_delta
                    asset_stats[trade.quote_asset]["acquired"] += quote_delta
                elif trade_side == TradeType.BUY.name:
                    asset_stats[trade.base_asset]["acquired"] += base_delta
                    asset_stats[trade.quote_asset]["spent"] += quote_delta

            market_trading_pair_stats[market_trading_pair_tuple] = {
                "starting_quote_rate": queried_trades[0].price,
                "asset": asset_stats
            }

        return market_trading_pair_stats

    @staticmethod
    def calculate_trade_performance(analysis_start_time: int,
                                    current_startegy_name: str,
                                    market_trading_pair_tuples: List[MarketTradingPairTuple]) -> Tuple[Dict, Dict]:
        trade_performance_stats: Dict[str, float] = {}
        primary_quote_asset: str = market_trading_pair_tuples[0].quote_asset
        market_trading_pair_stats: Dict[str, Dict[str, float]] = PerformanceAnalysis.calculate_asset_delta_from_trades(
            analysis_start_time,
            current_startegy_name,
            market_trading_pair_tuples)

        for market_trading_pair_tuple, trading_pair_stats in market_trading_pair_stats.items():
            market_trading_pair_tuple: MarketTradingPairTuple
            base_asset = market_trading_pair_tuple.base_asset
            quote_asset = market_trading_pair_tuple.quote_asset
            quote_rate: float = market_trading_pair_tuple.get_mid_price()
            trading_pair_stats["end_quote_rate"] = quote_rate
            asset_stats = trading_pair_stats["asset"]

            for asset, stats in asset_stats.items():
                stats["delta"] = stats["acquired"] - stats["spent"]

                if stats["spent"] == s_float_0 and stats["acquired"] > s_float_0:
                    stats["delta_percentage"] = 100.0
                elif stats["spent"] == s_float_0 and stats["acquired"] == s_float_0:
                    stats["delta_percentage"] = s_float_0
                else:
                    stats["delta_percentage"] = ((stats["acquired"] / stats["spent"]) - 1) * 100

            spent_base_quote_value: float = asset_stats[base_asset]["spent"] * quote_rate
            acquired_base_quote_value: float = asset_stats[base_asset]["acquired"] * quote_rate

            combined_spent: float = spent_base_quote_value + asset_stats[quote_asset]["spent"]
            combined_acquired: float = acquired_base_quote_value + asset_stats[quote_asset]["acquired"]

            trading_pair_stats["acquired_quote_value"] = ERC.convert_token_value(
                combined_acquired, quote_asset, primary_quote_asset, source="default"
            )
            trading_pair_stats["spent_quote_value"] = ERC.convert_token_value(
                combined_spent, quote_asset, primary_quote_asset, source="default"
            )
            trading_pair_stats["trading_pair_delta"] = combined_acquired - combined_spent

            if combined_acquired == s_float_0 or combined_spent == s_float_0:
                trading_pair_stats["trading_pair_delta_percentage"] = s_float_nan
                continue
            trading_pair_stats["trading_pair_delta_percentage"] = ((combined_acquired / combined_spent) - 1) * 100

        portfolio_acquired_quote_value: float = sum(
            s["acquired_quote_value"] for s in market_trading_pair_stats.values())
        portfolio_spent_quote_value: float = sum(
            s["spent_quote_value"] for s in market_trading_pair_stats.values())
        if portfolio_acquired_quote_value == s_float_0 or portfolio_spent_quote_value == s_float_0:
            portfolio_delta_percentage: float = s_float_nan
        else:
            portfolio_delta_percentage: float = ((portfolio_acquired_quote_value / portfolio_spent_quote_value) - 1) * 100

        trade_performance_stats["portfolio_acquired_quote_value"] = portfolio_acquired_quote_value
        trade_performance_stats["portfolio_spent_quote_value"] = portfolio_spent_quote_value
        trade_performance_stats["portfolio_delta"] = portfolio_acquired_quote_value - portfolio_spent_quote_value
        trade_performance_stats["portfolio_delta_percentage"] = portfolio_delta_percentage

        return trade_performance_stats, market_trading_pair_stats
