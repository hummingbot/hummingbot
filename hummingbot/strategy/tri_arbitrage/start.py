from typing import (
    List,
    Tuple,
)
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.tri_arbitrage.tri_arbitrage_market_pair import ArbitrageMarketPair
from hummingbot.strategy.tri_arbitrage.tri_arbitrage import ArbitrageStrategy
from hummingbot.strategy.tri_arbitrage.tri_arbitrage_config_map import tri_arbitrage_config_map
#from csv import reader

def start(self):
    self.market_pair = []
    market_names = []
    # For using multiple tri arbitrage pairs
    #with open('hummingbot/strategy/tri_arbitrage/tri_arbitrage_pairs.csv', 'r') as csvObj:
    #    #The object having the file is passed into the reader
    #    csv_reader = reader(csvObj)
    #    #The reader object is passed into the list( ) to generate a list of lists
    #    rowList = list(csv_reader)
    primary_market_1 = tri_arbitrage_config_map.get("primary_market").value.lower()
    secondary_market_1 = tri_arbitrage_config_map.get("secondary_market").value.lower()
    tertiary_market_1 = tri_arbitrage_config_map.get("tertiary_market").value.lower()
    raw_primary_trading_pair_1 = tri_arbitrage_config_map.get("primary_market_trading_pair").value
    raw_secondary_trading_pair_1 = tri_arbitrage_config_map.get("secondary_market_trading_pair").value
    raw_tertiary_trading_pair_1 = tri_arbitrage_config_map.get("tertiary_market_trading_pair").value
    min_profitability = tri_arbitrage_config_map.get("min_profitability").value
    maxorder_amount = tri_arbitrage_config_map.get("maxorder_amount").value
    fee_amount = tri_arbitrage_config_map.get("fee_amount").value
    use_oracle_conversion_rate = tri_arbitrage_config_map.get("use_oracle_conversion_rate").value
    secondary_to_primary_base_conversion_rate = tri_arbitrage_config_map["secondary_to_primary_base_conversion_rate"].value
    secondary_to_primary_quote_conversion_rate = tri_arbitrage_config_map["secondary_to_primary_quote_conversion_rate"].value

    try:
        
        primary_trading_pair_1: str = raw_primary_trading_pair_1
        secondary_trading_pair_1: str = raw_secondary_trading_pair_1
        tertiary_trading_pair_1: str = raw_tertiary_trading_pair_1
        primary_assets_1: Tuple[str, str] = self._initialize_market_assets(primary_market_1, [primary_trading_pair_1])[0]
        secondary_assets_1: Tuple[str, str] = self._initialize_market_assets(secondary_market_1, [secondary_trading_pair_1])[0]
        tertiary_assets_1: Tuple[str, str] = self._initialize_market_assets(tertiary_market_1, [tertiary_trading_pair_1])[0]
  
    except ValueError as e:
        self._notify(str(e))
        return
    market_names.append((primary_market_1,[primary_trading_pair_1]))
    market_names.append((secondary_market_1,[secondary_trading_pair_1]))
    market_names.append((tertiary_market_1,[tertiary_trading_pair_1]))


    self._initialize_markets(market_names)
    self.assets = set(primary_assets_1 + secondary_assets_1 + tertiary_assets_1)

    primary_data_1 = [self.markets[primary_market_1], primary_trading_pair_1] + list(primary_assets_1)
    secondary_data_1 = [self.markets[secondary_market_1], secondary_trading_pair_1] + list(secondary_assets_1)
    tertiary_data_1 = [self.markets[tertiary_market_1], tertiary_trading_pair_1] + list(tertiary_assets_1)

    self.market_trading_pair_tuples_1 = [MarketTradingPairTuple(*primary_data_1), MarketTradingPairTuple(*secondary_data_1), MarketTradingPairTuple(*tertiary_data_1)]

    self.market_pair.append(ArbitrageMarketPair(*self.market_trading_pair_tuples_1))
    
    self.strategy = ArbitrageStrategy()
    self.strategy.init_params(market_pairs=[self.market_pair],
                              min_profitability=min_profitability,
							  maxorder_amount=maxorder_amount,
                              fee_amount=fee_amount,
                              logging_options=ArbitrageStrategy.OPTION_LOG_ALL,
                              use_oracle_conversion_rate=use_oracle_conversion_rate,
                              secondary_to_primary_base_conversion_rate=secondary_to_primary_base_conversion_rate,
                              secondary_to_primary_quote_conversion_rate=secondary_to_primary_quote_conversion_rate,
                              hb_app_notification=True)
