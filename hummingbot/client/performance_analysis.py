from collections import defaultdict
from decimal import Decimal
from typing import (
    Tuple,
    Dict,
    List)
from hummingbot.core.event.events import TradeType
from hummingbot.model.trade_fill import TradeFill
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

s_float_nan = float("nan")
s_float_0 = float(0)
s_decimal_0 = Decimal(0)


def calculate_trade_asset_delta_with_fees(trade: TradeFill) -> Tuple[Decimal, Decimal]:
    trade_fee: Dict[str, any] = trade.trade_fee
    total_flat_fees: Decimal = s_decimal_0
    amount: Decimal = Decimal(str(trade.amount))
    price: Decimal = Decimal(str(trade.price))
    for flat_fee in trade_fee["flat_fees"]:
        if isinstance(flat_fee, dict):
            flat_fee_currency = flat_fee["asset"]
            flat_fee_amount = flat_fee["amount"]
        else:
            flat_fee_currency, flat_fee_amount = flat_fee
        # Flat fee is currently used only for DEX in ETH token amount, if there is a need for
        # more interchangable kinda assets, we can handle this in a more proper way (e.g. using global config)
        if flat_fee_currency == trade.quote_asset or \
                (flat_fee_currency.upper() in ("ETH", "WETH") and trade.quote_asset.upper() in ("ETH", "WETH")):
            total_flat_fees += Decimal(str(flat_fee_amount))
    if trade.trade_type == TradeType.SELL.name:
        net_base_delta: Decimal = amount
        net_quote_delta: Decimal = amount * price * (Decimal("1") - Decimal(str(trade_fee["percent"]))) - \
            total_flat_fees
    elif trade.trade_type == TradeType.BUY.name:
        net_base_delta: Decimal = amount * (Decimal("1") - Decimal(str(trade_fee["percent"]))) - total_flat_fees
        net_quote_delta: Decimal = amount * price
    else:
        raise Exception(f"Unsupported trade type {trade.trade_type}")
    return net_base_delta, net_quote_delta


def calculate_asset_delta_from_trades(current_strategy_name: str,
                                      market_trading_pair_tuples: List[MarketTradingPairTuple],
                                      raw_queried_trades: List[TradeFill],
                                      ) -> Dict[MarketTradingPairTuple, Dict[str, Decimal]]:
    """
    Calculate spent and acquired amount for each asset from trades.
    Example:
    A buy trade of ETH_USD for price 100 and amount 1, will have 1 ETH as acquired and 100 USD as spent amount.

    :param current_strategy_name: Name of the currently configured strategy
    :param market_trading_pair_tuples: Current MarketTradingPairTuple
    :param raw_queried_trades: List of queried trades
    :return: Dictionary consisting of spent and acquired amount for each assets
    """
    market_trading_pair_stats: Dict[MarketTradingPairTuple, Dict[str, Decimal]] = {}
    for market_trading_pair_tuple in market_trading_pair_tuples:
        asset_stats: Dict[str, Dict[str, Decimal]] = defaultdict(
            lambda: {"spent": s_decimal_0, "acquired": s_decimal_0}
        )
        asset_stats[market_trading_pair_tuple.base_asset.upper()] = {"spent": s_decimal_0, "acquired": s_decimal_0}
        asset_stats[market_trading_pair_tuple.quote_asset.upper()] = {"spent": s_decimal_0, "acquired": s_decimal_0}

        if raw_queried_trades is not None:
            queried_trades: List[TradeFill] = [t for t in raw_queried_trades if (
                t.strategy == current_strategy_name
                and t.market == market_trading_pair_tuple.market.display_name
                and t.symbol == market_trading_pair_tuple.trading_pair
            )]
        else:
            queried_trades = []

        if not queried_trades:
            market_trading_pair_stats[market_trading_pair_tuple] = {
                "starting_quote_rate": market_trading_pair_tuple.get_mid_price(),
                "asset": asset_stats,
                "trade_count": 0
            }
            continue

        for trade in queried_trades:
            # For each trade, calculate the spent and acquired amount of the corresponding base and quote asset
            trade_side: str = trade.trade_type
            base_asset: str = trade.base_asset.upper()
            quote_asset: str = trade.quote_asset.upper()
            base_delta, quote_delta = calculate_trade_asset_delta_with_fees(trade)
            if trade_side == TradeType.SELL.name:
                asset_stats[base_asset]["spent"] += base_delta
                asset_stats[quote_asset]["acquired"] += quote_delta
            elif trade_side == TradeType.BUY.name:
                asset_stats[base_asset]["acquired"] += base_delta
                asset_stats[quote_asset]["spent"] += quote_delta

        market_trading_pair_stats[market_trading_pair_tuple] = {
            "starting_quote_rate": Decimal(repr(queried_trades[0].price)),
            "asset": asset_stats,
            "trade_count": len(queried_trades)
        }

    return market_trading_pair_stats


def calculate_trade_performance(current_strategy_name: str,
                                market_trading_pair_tuples: List[MarketTradingPairTuple],
                                raw_queried_trades: List[TradeFill],
                                starting_balances: Dict[str, Dict[str, Decimal]],
                                secondary_market_conversion_rate: Decimal = Decimal("1")) \
        -> Tuple[Dict, Dict]:
    """
    Calculate total spent and acquired amount for the whole portfolio in quote value.

    :param current_strategy_name: Name of the currently configured strategy
    :param market_trading_pair_tuples: Current MarketTradingPairTuple
    :param raw_queried_trades: List of queried trades
    :param starting_balances: Dictionary of starting asset balance for each market, as balance_snapshot on
    history command.
    :param secondary_market_conversion_rate: A conversion rate for a secondary market if it differs from the primary.
    :return: Dictionary consisting of total spent and acquired across whole portfolio in quote value,
             as well as individual assets
    """
    trade_performance_stats: Dict[str, Decimal] = {}
    # The final stats will be in primary quote unit for arbitrage and maker quote unit for xemm
    primary_trading_pair: str = market_trading_pair_tuples[0].trading_pair
    market_trading_pair_stats: Dict[str, Dict[str, Decimal]] = calculate_asset_delta_from_trades(
        current_strategy_name,
        market_trading_pair_tuples,
        raw_queried_trades)

    # Calculate total spent and acquired amount for each trading pair in primary quote value
    for market_trading_pair_tuple, trading_pair_stats in market_trading_pair_stats.items():
        market_trading_pair_tuple: MarketTradingPairTuple
        base_asset: str = market_trading_pair_tuple.base_asset.upper()
        quote_asset: str = market_trading_pair_tuple.quote_asset.upper()
        quote_rate: Decimal = market_trading_pair_tuple.get_mid_price()
        trading_pair_stats["end_quote_rate"] = quote_rate
        asset_stats: Dict[str, Decimal] = trading_pair_stats["asset"]

        market_conversion_rate = Decimal("1")
        if market_trading_pair_tuple.trading_pair != primary_trading_pair:
            market_conversion_rate = secondary_market_conversion_rate

        # Calculate delta amount and delta percentage for each asset based on spent and acquired amount
        for asset, stats in asset_stats.items():
            stats["delta"] = stats["acquired"] - stats["spent"]

            if stats["spent"] == s_decimal_0 and stats["acquired"] > s_decimal_0:
                stats["delta_percentage"] = Decimal("100")
            elif stats["spent"] == s_decimal_0 and stats["acquired"] == s_decimal_0:
                stats["delta_percentage"] = s_decimal_0
            else:
                stats["delta_percentage"] = ((stats["acquired"] / stats["spent"]) - Decimal("1")) * Decimal("100")
        # Convert spent and acquired amount for base asset to quote asset value
        spent_base_quote_value: Decimal = asset_stats[base_asset]["spent"] * quote_rate
        acquired_base_quote_value: Decimal = asset_stats[base_asset]["acquired"] * quote_rate

        # Calculate total spent and acquired of a trading pair
        combined_spent: Decimal = spent_base_quote_value + asset_stats[quote_asset]["spent"]
        combined_acquired: Decimal = acquired_base_quote_value + asset_stats[quote_asset]["acquired"]

        market_name = market_trading_pair_tuple.market.name
        if base_asset in starting_balances and market_name in starting_balances[base_asset]:
            starting_base = Decimal(starting_balances[base_asset][market_name])
        else:
            starting_base = Decimal("0")
        if quote_asset in starting_balances and market_name in starting_balances[quote_asset]:
            starting_quote = Decimal(starting_balances[quote_asset][market_name])
        else:
            starting_quote = Decimal("0")
        if starting_base + starting_quote == 0:
            raise ValueError("Starting balances must be supplied.")
        starting_total = starting_quote + (starting_base * quote_rate)
        # Convert trading pair's spent and acquired amount into primary quote asset value
        # (primary quote asset is the quote asset of the first trading pair)
        trading_pair_stats["acquired_quote_value"] = combined_acquired * market_conversion_rate
        trading_pair_stats["spent_quote_value"] = combined_spent * market_conversion_rate
        trading_pair_stats["starting_quote_value"] = starting_total * market_conversion_rate
        trading_pair_stats["trading_pair_delta"] = combined_acquired - combined_spent

        if combined_acquired == s_decimal_0 or combined_spent == s_decimal_0:
            trading_pair_stats["trading_pair_delta_percentage"] = s_decimal_0
            continue
        trading_pair_stats["trading_pair_delta_percentage"] = \
            ((combined_acquired - combined_spent) / starting_total) * Decimal("100")

    portfolio_acquired_quote_value: Decimal = sum(
        s["acquired_quote_value"] for s in market_trading_pair_stats.values())
    portfolio_spent_quote_value: Decimal = sum(
        s["spent_quote_value"] for s in market_trading_pair_stats.values())
    portfolio_starting_quote_value: Decimal = sum(
        s["starting_quote_value"] for s in market_trading_pair_stats.values())

    if portfolio_acquired_quote_value == s_decimal_0 or portfolio_spent_quote_value == s_decimal_0:
        portfolio_delta_percentage: Decimal = s_decimal_0
    else:
        portfolio_delta_percentage: Decimal = ((portfolio_acquired_quote_value - portfolio_spent_quote_value)
                                               / portfolio_starting_quote_value) * Decimal("100")

    trade_performance_stats["portfolio_acquired_quote_value"] = portfolio_acquired_quote_value
    trade_performance_stats["portfolio_spent_quote_value"] = portfolio_spent_quote_value
    trade_performance_stats["portfolio_delta"] = portfolio_acquired_quote_value - portfolio_spent_quote_value
    trade_performance_stats["portfolio_delta_percentage"] = portfolio_delta_percentage

    return trade_performance_stats, market_trading_pair_stats
