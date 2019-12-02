# distutils: language=c++
import logging
import itertools
from decimal import Decimal
import pandas as pd
from typing import (
    List,
    Set,
    Tuple,
    Dict,
)

from hummingbot.core.clock cimport Clock
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.discovery.discovery_market_pair import DiscoveryMarketPair
from hummingbot.strategy.arbitrage import ArbitrageStrategy
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_base cimport StrategyBase
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.utils.async_utils import safe_ensure_future


NaN = float("nan")
s_decimal_0 = Decimal(0)
ds_logger = None


cdef class DiscoveryStrategy(StrategyBase):
    OPTION_LOG_STATUS_REPORT = 1 << 0
    OPTION_LOG_ALL = 0xfffffffffffffff

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ds_logger
        if ds_logger is None:
            ds_logger = logging.getLogger(__name__)
        return ds_logger

    def __init__(self,
                 market_pairs: List[DiscoveryMarketPair],
                 discovery_method: str = "arbitrage",
                 target_amount: float = float("inf"),
                 target_profitability: float = 0.0,
                 logging_options: int = OPTION_LOG_ALL,
                 status_report_interval: float = 900,
                 target_trading_pairs: list = [],
                 equivalent_token: list = []):
        """
        :param market_pairs: list of discovery market pairs. Currently, the strategy only supports one market pair.
        :param discovery_method: which type of opportunity to discovery. Currently, only "arbitrage" is supported.
        :param target_amount: the maximum limit of proposed order sizes
        :param target_profitability: the minimum profitability ratio required for an opportunity to be printed
        :param logging_options: select the types of logs to output
        :param status_report_interval: not used
        :param target_trading_pairs: List of token pairs, or single tokens
        :param equivalent_token: List of lists of equivalent token trading pairs
        """
        if len(market_pairs) < 0:
            raise ValueError(f"market_pairs must not be empty.")

        super().__init__()
        self._market_pairs = market_pairs
        self._target_amount = target_amount
        self._target_profitability = target_profitability
        self._logging_options = logging_options
        self._status_report_interval = status_report_interval
        self._refetch_market_info_interval = 60.0 * 60
        self._all_markets_ready = False
        self._last_timestamp = 0
        self._discovery_stats = {}
        self._discovery_method = discovery_method
        self._market_info = {}
        self._matching_pairs = set()
        self._equivalent_token = equivalent_token
        self._target_trading_pairs = target_trading_pairs
        self._equivalent_token_dict = self.parse_equivalent_token(self._equivalent_token)
        self._fetch_market_info_task_list = None

        cdef:
            set all_markets = set([market
                                   for market_pair in self._market_pairs
                                   for market in [market_pair.market_1, market_pair.market_2]])
        self.c_add_markets(list(all_markets))

    @property
    def all_markets_ready(self):
        return self._all_markets_ready

    @classmethod
    def parse_equivalent_token(cls, equivalent_token: List[List[str]]) -> Dict[str, Set[str]]:
        """
        Converts a list of lists of equivalent tokens (e.g. [['DAI', 'USDT', 'PAX', ...], ...]) into a lookup dictionary
        that maps from individual token names to their equivalent classes.

        :param equivalent_token: list of lists of equivalent tokens
        :return: mapping from token name to equivalent sets
        """
        equivalent_token_dict = {}
        for token_list in equivalent_token:
            for token in token_list:
                equivalent_token_dict[token.upper()] = {s.upper() for s in token_list}
        return equivalent_token_dict

    @classmethod
    def filter_trading_pairs(cls,
                             target_tokens: List[List[str]],
                             markets: pd.DataFrame,
                             equivalent_token: List[List[str]]) -> pd.DataFrame:
        """
        Filters down an active markets data frame, according to a set of target tokens or token pairs.

        :param target_tokens: List of token pairs, or single tokens
        :param markets: data frame of all trading pairs, of the `get_active_exchange_markets()` format
        :param equivalent_token: List of list of equivalent tokens.
        :return: filtered data frame of active markets, matching the `target_tokens` specification
        """
        if not target_tokens or (len(target_tokens) == 1 and not target_tokens[0]):
            return markets

        filtered_trading_pairs = set()
        equivalent_token = cls.parse_equivalent_token(equivalent_token)

        for trading_pair, b, q in zip(markets.index, markets.baseAsset, markets.quoteAsset):
            b, q = b.upper(), q.upper()
            for target_token_pair in target_tokens:
                # single token, any trading pair consisting the token will match
                if len(target_token_pair) == 1:
                    for equal_token in equivalent_token.get(target_token_pair[0], {target_token_pair[0]}):
                        if equal_token.upper() in {b, q}:
                            filtered_trading_pairs.add(trading_pair)
                # match base and quote with equivalent tokens
                if len(target_token_pair) == 2:
                    t_b, t_q = target_token_pair[0].upper(), target_token_pair[1].upper()
                    if b in equivalent_token.get(t_b, {t_b}) and q in equivalent_token.get(t_q, {t_q}):
                        filtered_trading_pairs.add(trading_pair)

        return markets[[i in filtered_trading_pairs for i in markets.index]].copy()

    async def fetch_market_info(self, market_pair: DiscoveryMarketPair):
        """
        Fetches and calculates all the matching trading pairs between two exchanges. Saved the fetched and processed
        market info and matched trading pairs to `self._market_info` and `self._matching_pairs`.

        :param market_pair: discovery market pair
        """
        try:
            for market, fetch_market_info in [(market_pair.market_1, market_pair.market_1_fetch_market_info),
                                              (market_pair.market_2, market_pair.market_2_fetch_market_info)]:
                markets = self.filter_trading_pairs(self._target_trading_pairs,
                                                    await fetch_market_info(),
                                                    self._equivalent_token)
                self._market_info[market] = {"markets": markets,
                                             "base_quote_to_trading_pair": {},
                                             "timestamp": self._current_timestamp}
                for trading_pair, b, q in zip(markets.index, markets.baseAsset, markets.quoteAsset):
                    self._market_info[market]["base_quote_to_trading_pair"][(b, q)] = (trading_pair, b, q)

            self._matching_pairs = self.get_matching_pairs(market_pair)

        except Exception as e:
            self.logger().network(f"Could not fetch market info for {market_pair}", exc_info=True,
                                  app_warning_msg=f"Failed to fetch market info for {market_pair}. "
                                                  f"Check network connection.")

    def get_matching_pairs(self, market_pair: DiscoveryMarketPair) -> Set[Tuple[str, str]]:
        """
        Given a discovery market pair, find out all the matching trading pairs for the two exchanges.

        XXX: this function takes O(n^2), need to optimize.

        :param market_pair: discovery market pair
        :return: all matching trading pairs in the two exchanges
        """
        market_1 = market_pair.market_1
        market_2 = market_pair.market_2
        market_1_info_df = self._market_info[market_1]["markets"]
        market_2_info_df = self._market_info[market_2]["markets"]
        market_1_base_quote = set(zip(market_1_info_df.baseAsset, market_1_info_df.quoteAsset))
        market_2_base_quote = set(zip(market_2_info_df.baseAsset, market_2_info_df.quoteAsset))
        matching_pair = set()

        for base_1, quote_1 in market_1_base_quote:
            # check for all equivalent base and quote token from market1 in market2
            for equivalent_base_1, equivalent_quote_1 in itertools.product(
                self._equivalent_token_dict.get(base_1.upper(), {base_1}),
                self._equivalent_token_dict.get(quote_1.upper(), {quote_1})
            ):
                if (equivalent_base_1.upper(), equivalent_quote_1.upper()) in market_2_base_quote:
                    matching_pair.add((
                        self._market_info[market_1]["base_quote_to_trading_pair"][(base_1, quote_1)],
                        self._market_info[market_2]["base_quote_to_trading_pair"][(equivalent_base_1.upper(),
                                                                            equivalent_quote_1.upper())]
                    ))
                elif (equivalent_base_1.lower(), equivalent_quote_1.lower()) in market_2_base_quote:
                    matching_pair.add((
                        self._market_info[market_1]["base_quote_to_trading_pair"][(base_1, quote_1)],
                        self._market_info[market_2]["base_quote_to_trading_pair"][(equivalent_base_1.lower(),
                                                                            equivalent_quote_1.lower())]
                    ))
        return matching_pair

    cdef c_tick(self, double timestamp):
        """
        Clock tick entry point.

        For the discovery strategy or tool, this function starts the fetch market info task, and waits for both the
        market info and all the markets to get ready.

        Afterwards, it delegates the processing of all discovery market pairs to c_process_market_pair().

        :param timestamp: current tick timestamp
        """
        StrategyBase.c_tick(self, timestamp)
        if not self._fetch_market_info_task_list:
            self._fetch_market_info_task_list = [safe_ensure_future(self.fetch_market_info(market_pair))
                                                 for market_pair in self._market_pairs]

        for market in self._sb_markets:
            if market not in self._market_info:
                self.log_with_clock(logging.INFO, f"Waiting to finish fetching trading pair from {market.name}.")
                return

        if not self._all_markets_ready:
            self._all_markets_ready = all([market.ready for market in self._sb_markets])
            if not self._all_markets_ready:
                # Markets not ready yet. Don't do anything.
                return
        for market_pair in self._market_pairs:
            try:
                self.c_process_market_pair(market_pair)
            except Exception:
                self.logger().error(f"Error processing market pair {market_pair}.", exc_info=True)

        self._last_timestamp = timestamp

    cdef dict c_calculate_single_arbitrage_profitability(self,
                                                         object market_pair,
                                                         tuple matching_pair,
                                                         double target_amount=float("inf"),
                                                         double target_profitability=0.0):
        """
        Given a matching trading pair and a discovery market pair, calculate the optimal order size and the buy-sell
        order of the two marktes to make the maximal arbitrage profits out of them.

        :param market_pair: discovery market pair
        :param matching_pair: a matching trading pair between the two exchanges
        :param target_amount: (optional) maximum limit for arbitrage order size
        :param target_profitability: (optional) minimum limit for the profitability ratio
        :return: a dictionary mapping from a 4-tuple of buy and sell market descriptions, to a 3-tuple of
                 (order size in base asset, expected ask order proceeds in quote asset, profitability ratio)
        :rtype: Dict[Tuple[str, str, str, str], Tuple[float, float, float]]
        """
        cdef:
            object total_bid_value = s_decimal_0                                  # total revenue
            object total_ask_value = s_decimal_0                                  # total cost
            object total_bid_value_adjusted = s_decimal_0
            object total_ask_value_adjusted = s_decimal_0
            object total_profitable_base_amount = s_decimal_0
            object step_amount = s_decimal_0
            object profitability = s_decimal_0
            object next_profitability = s_decimal_0
            OrderBook buy_market_order_book
            OrderBook sell_market_order_book
            dict ret = {}
            object market_trading_pair_1 = MarketTradingPairTuple(market_pair.market_1, *matching_pair[0])
            object market_trading_pair_2 = MarketTradingPairTuple(market_pair.market_2, *matching_pair[1])

        for buy_market_trading_pair, sell_market_trading_pair in [(market_trading_pair_1, market_trading_pair_2),
                                                                (market_trading_pair_2, market_trading_pair_1)]:
            try:
                total_bid_value, total_ask_value = s_decimal_0, s_decimal_0
                total_profitable_base_amount = s_decimal_0
                profitability, next_profitability = s_decimal_0, s_decimal_0

                profitable_orders = ArbitrageStrategy.find_profitable_arbitrage_orders(
                    target_profitability,
                    buy_market_trading_pair,
                    sell_market_trading_pair
                )
                for bid_price_adjusted, ask_price_adjusted, bid_price, ask_price, amount in profitable_orders:
                    if total_profitable_base_amount + amount >= target_amount:
                        step_amount = target_amount - total_profitable_base_amount
                    else:
                        step_amount = amount
                    # accumulated profitability
                    next_profitability = (total_bid_value_adjusted + bid_price_adjusted * step_amount) / \
                                         (total_ask_value_adjusted + ask_price_adjusted * step_amount)

                    # stop current step if profitability is lower than desired
                    if next_profitability < (1 + target_profitability):
                        break

                    total_bid_value_adjusted += bid_price_adjusted * step_amount
                    total_ask_value_adjusted += ask_price_adjusted * step_amount
                    total_bid_value += bid_price * step_amount
                    total_ask_value += ask_price * step_amount
                    total_profitable_base_amount += step_amount
                    profitability = next_profitability

                    if total_profitable_base_amount >= target_amount:
                        break

                # for non profitable pairs calculate the negative profitability for their top bid and ask
                # or for profitability lower than targeted, calculate with the best bid and ask
                if not profitable_orders or profitability == 0:
                    sell_price_adjusted = ExchangeRateConversion.get_instance().adjust_token_rate(
                        sell_market_trading_pair.quote_asset,
                        sell_market_trading_pair.get_price(False)
                    )
                    buy_price_adjusted = ExchangeRateConversion.get_instance().adjust_token_rate(
                        buy_market_trading_pair.quote_asset,
                        buy_market_trading_pair.get_price(True)
                    )
                    profitability = sell_price_adjusted / buy_price_adjusted

                ret[(buy_market_trading_pair.market.name,
                     buy_market_trading_pair.trading_pair,
                     sell_market_trading_pair.market.name,
                     sell_market_trading_pair.trading_pair)] = \
                    (total_profitable_base_amount, total_ask_value, (profitability - 1) * 100)

            except Exception:
                self.logger().debug(f"Error calculating arbitrage profitability: "
                                    f"{buy_market_trading_pair} v.s {sell_market_trading_pair}.",
                                    exc_info=True)
        return ret

    def calculate_arbitrage_discovery(self,
                                      market_pair: DiscoveryMarketPair,
                                      matching_pairs: set,
                                      target_amount: float,
                                      target_profitability: float):
        return self.c_calculate_arbitrage_discovery(market_pair, matching_pairs, target_amount, target_profitability)

    cdef object c_calculate_arbitrage_discovery(self,
                                                object market_pair,
                                                set matching_pairs,
                                                double target_amount,
                                                double target_profitability):
        """
        Given a set of matching trading pairs and a discovery market pair, calculate the optimal order sizes and the
        buy-sell orders of all the trading pairs to make the maximal arbitrage profits out of them.

        :param market_pair: discovery market pair
        :param matching_pairs: set of matching trading pairs between the two exchanges
        :param target_amount: maximum limit for arbitrage order size
        :param target_profitability: minimum limit for the profitability ratio
        :rtype: pd.DataFrame
        :return: data frame with the following columns: "buy_market", "buy_pair", "sell_market", "sell_pair",
                 "profit (quote)", "profit (%)"
        """
        cdef:
            dict arbitrage_discovery = {}
            dict discovery_dict = {}
        for matching_pair in matching_pairs:
            discovery_dict = self.c_calculate_single_arbitrage_profitability(market_pair,
                                                                             matching_pair,
                                                                             target_amount,
                                                                             target_profitability
                                                                             )
            arbitrage_discovery.update(discovery_dict)

        arbitrage_discovery_df = pd.DataFrame(
            data=[(names[0], names[1], names[2], names[3], float(stats[0]) * float(stats[1]), float(stats[2]))
                  for names, stats in arbitrage_discovery.items()],
            columns=["buy_market", "buy_pair", "sell_market", "sell_pair", "profit (quote)", "profit (%)"]
        )

        return arbitrage_discovery_df.sort_values(["profit (%)"], ascending=False)

    def calculate_market_stats(self, market_pair: DiscoveryMarketPair, exchange_market_info: List):
        return self.c_calculate_market_stats(market_pair, exchange_market_info)

    cdef c_calculate_market_stats(self, object market_pair, dict exchange_market_info):
        """
        Calculates some basic statistics of selected markets.

        :param market_pair: discovery market pair
        :param exchange_market_info: exchange market info dictionary, as generated in `fetch_market_info()`
        :return: data frame with the following columns: "market", "base", "quote", "mid_price", "spread (%)",
                 "usd_volume"
        :rtype: pd.DataFrame
        """
        cdef:
            dict market_stats = {}
            OrderBook order_book
            double spread
            double mid_price
            double ask
            double bid
            str exchange_name
        for exchange_class, market_info in exchange_market_info.items():
            trading_pairs = market_info["markets"]
            exchange_name = exchange_class.name
            for trading_pair, usd_volume, base_asset, quote_asset in zip(trading_pairs.index,
                                                                   trading_pairs.USDVolume,
                                                                   trading_pairs.baseAsset,
                                                                   trading_pairs.quoteAsset):
                try:
                    order_book = exchange_class.get_order_book(trading_pair)
                    ask, bid = order_book.get_price(True), order_book.get_price(False)
                    spread, mid_price = ask/bid, (ask + bid)/2
                    market_stats[(exchange_name, trading_pair)] = (
                        base_asset, quote_asset, mid_price, (spread - 1) * 100, float(usd_volume))
                except Exception:
                    self.logger().debug(f"Error calculating market stats: {exchange_name}, {trading_pair}.", exc_info=True)

        market_stats_discovery_df = pd.DataFrame(
            data=[(name[0], stats[0], stats[1], stats[2], stats[3], stats[4]) for name, stats in market_stats.items()],
            columns=["market", "base", "quote", "mid_price", "spread (%)", "usd_volume"]
        )

        return market_stats_discovery_df.sort_values(["usd_volume", "spread (%)"], ascending=False)

    cdef c_process_market_pair(self, object market_pair):
        """
        Calculates market stats and all the arbitrage opportunities from a discovery market pair, and save them to
        internal data structures for display later.

        :param market_pair: discovery market pair
        """
        self._discovery_stats["market_stats"] = self.c_calculate_market_stats(market_pair, self._market_info)
        if self._discovery_method == "arbitrage":
            self._discovery_stats["arbitrage"] = self.c_calculate_arbitrage_discovery(market_pair,
                                                                                      self._matching_pairs,
                                                                                      self._target_amount,
                                                                                      self._target_profitability)

    def get_status_dataframes(self) -> List[pd.DataFrame]:
        market_stats_df = self._discovery_stats["market_stats"]
        arbitrage_status_df = self._discovery_stats["arbitrage"]
        conversion_rate_df = self.get_conversion_rate_df()
        return [market_stats_df, arbitrage_status_df, conversion_rate_df]

    def format_status_arbitrage(self):
        cdef:
            list lines = []
            list df_lines = []
        if "arbitrage" not in self._discovery_stats or self._discovery_stats["arbitrage"].empty:
            lines.extend(["", "  Arbitrage discovery not ready yet."])
            return lines
        df_lines = self._discovery_stats["arbitrage"].to_string(index=False).split("\n")

        lines.extend(["", "  Arbitrage Opportunity Report:"] +
                     ["    " + line for line in df_lines])
        return lines

    def format_status_market_stats(self):
        cdef:
            list lines = []
            list df_lines = []
        if "market_stats" not in self._discovery_stats or self._discovery_stats["market_stats"].empty:
            lines.extend(["", "Market stats not ready yet."])
            return lines
        df_lines = self._discovery_stats["market_stats"].to_string(index=False).split("\n")

        lines.extend(["", "  Market Stats:"] +
                     ["    " + line for line in df_lines])
        return lines

    def format_status_discovery_config(self):
        cdef:
            list lines = []
        lines.extend(["", "  Discovery Strategy Config:"])
        lines.extend(["    Equivalent Tokens:"] +
                     [f"      {equivalent_token}" for equivalent_token in self._equivalent_token])
        return lines

    def get_conversion_rate_df(self) -> pd.DataFrame:
        cdef:
            list data = []
            list columns = ["asset", "conversion_rate"]

        asset_set = set()
        for market in self._market_info:
            market_info = self._market_info[market]
            for asset_tuple in market_info["base_quote_to_trading_pair"].keys():
                b, q = asset_tuple
                asset_set.add(b)
                asset_set.add(q)

        for asset in asset_set:
            rate = ExchangeRateConversion.get_instance().adjust_token_rate(asset, Decimal("1.0"))
            if rate != Decimal("1.0"):
                data.append([asset, rate])

        assets_df = pd.DataFrame(data=data, columns=columns)
        return assets_df

    def format_conversion_rate(self):
        cdef:
            list lines = []

        assets_df = self.get_conversion_rate_df()
        lines.extend(["", "  Conversion Rates:"] + ["    " + line for line in str(assets_df).split("\n")])
        return lines

    def format_status(self):
        """
        Status command output.
        """
        cdef:
            list lines = []
        self.logger().debug(
            str([(k, v) for k, v in self._discovery_stats.items()])
        )
        self.logger().debug(
            str([market_info["markets"].to_dict() for exchange_class, market_info in self._market_info.items()])
        )

        lines.extend(self.format_status_market_stats())
        if self._discovery_method == "arbitrage":
            lines.extend(self.format_status_arbitrage())

        lines.extend(self.format_conversion_rate())
        return "\n".join(lines)

    cdef c_stop(self, Clock clock):
        """
        Stops any ongoing background tasks and performs clean up.

        :param clock: clock driver
        """
        StrategyBase.c_stop(self, clock)
        for task in self._fetch_market_info_task_list:
            task.cancel()
