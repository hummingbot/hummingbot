from typing import (
    List,
    Tuple,
)
from decimal import Decimal
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange.paper_trade import create_paper_trade_market
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.arbitrage.arbitrage_market_pair import ArbitrageMarketPair
from hummingbot.strategy.order_book_asset_price_delegate import OrderBookAssetPriceDelegate
from hummingbot.strategy.asset_price_delegate import AssetPriceDelegate
from hummingbot.strategy.arbitrage.arbitrage import ArbitrageStrategy
from hummingbot.strategy.arbitrage.arbitrage_config_map import arbitrage_config_map


def start(self):
    primary_market = arbitrage_config_map.get("primary_market").value.lower()
    secondary_market = arbitrage_config_map.get("secondary_market").value.lower()
    raw_primary_trading_pair = arbitrage_config_map.get("primary_market_trading_pair").value
    raw_secondary_trading_pair = arbitrage_config_map.get("secondary_market_trading_pair").value
    min_profitability = arbitrage_config_map.get("min_profitability").value / Decimal("100")
    use_oracle_conversion_rate = arbitrage_config_map.get("use_oracle_conversion_rate").value
    rate_conversion_sources = {
        'base': arbitrage_config_map.get("base_rate_conversion_source").value,
        'quote': arbitrage_config_map.get("quote_rate_conversion_source").value,
    }
    secondary_to_primary_base_conversion_rate = arbitrage_config_map["secondary_to_primary_base_conversion_rate"].value
    secondary_to_primary_quote_conversion_rate = arbitrage_config_map["secondary_to_primary_quote_conversion_rate"].value
    conversion_ext_market_price_types = {
        'base': arbitrage_config_map.get("base_conversion_ext_market_price_type").value,
        'quote': arbitrage_config_map.get("quote_conversion_ext_market_price_type").value,
    }
    conversion_ext_market_markets = {
        'base': arbitrage_config_map.get("base_conversion_ext_market_market").value,
        'quote': arbitrage_config_map.get("quote_conversion_ext_market_market").value,
    }
    conversion_ext_market_exchanges = {
        'base': arbitrage_config_map.get("base_conversion_ext_market_exchange").value,
        'quote': arbitrage_config_map.get("quote_conversion_ext_market_exchange").value,
    }

    try:
        primary_trading_pair: str = raw_primary_trading_pair
        secondary_trading_pair: str = raw_secondary_trading_pair
        primary_assets: Tuple[str, str] = self._initialize_market_assets(primary_market, [primary_trading_pair])[0]
        secondary_assets: Tuple[str, str] = self._initialize_market_assets(secondary_market,
                                                                           [secondary_trading_pair])[0]
    except ValueError as e:
        self._notify(str(e))
        return

    market_names: List[Tuple[str, List[str]]] = [(primary_market, [primary_trading_pair]),
                                                 (secondary_market, [secondary_trading_pair])]
    # Add Asset Price Delegate markets to main markets if already using the exchange.
    for asset_type in ['base', 'quote']:
        if rate_conversion_sources[asset_type] == "external_market":
            ext_exchange: str = conversion_ext_market_exchanges[asset_type]
            if ext_exchange in [primary_market, secondary_market]:
                asset_pair: str = conversion_ext_market_markets[asset_type]
                market_names.append((ext_exchange, [asset_pair]))

    self._initialize_wallet(token_trading_pairs=list(set(primary_assets + secondary_assets)))
    self._initialize_markets(market_names)
    self.assets = set(primary_assets + secondary_assets)

    primary_data = [self.markets[primary_market], primary_trading_pair] + list(primary_assets)
    secondary_data = [self.markets[secondary_market], secondary_trading_pair] + list(secondary_assets)
    self.market_trading_pair_tuples = [MarketTradingPairTuple(*primary_data), MarketTradingPairTuple(*secondary_data)]
    self.market_pair = ArbitrageMarketPair(*self.market_trading_pair_tuples)

    # Asset Price Feed Delegates
    rate_conversion_delegates = {'base': None, 'quote': None}
    shared_ext_mkt = None
    # Initialize price delegates as needed for defined price sources.
    for asset_type in ['base', 'quote']:
        price_source: str = rate_conversion_sources[asset_type]
        if price_source == "external_market":
            # For price feeds using other connectors
            ext_exchange: str = conversion_ext_market_exchanges[asset_type]
            asset_pair: str = conversion_ext_market_markets[asset_type]
            if ext_exchange in list(self.markets.keys()):
                # Use existing market if Exchange is already in markets
                ext_market = self.markets[ext_exchange]
            else:
                # Create markets otherwise
                UseSharedSource = (rate_conversion_sources['quote'] == rate_conversion_sources['base'] and
                                   conversion_ext_market_exchanges['quote'] == conversion_ext_market_exchanges['base'])
                # Use shared paper trade market if both price feeds are on the same exchange.
                if UseSharedSource and shared_ext_mkt is None and asset_type == 'base':
                    # Create Shared paper trade if not existing
                    shared_ext_mkt = create_paper_trade_market(conversion_ext_market_exchanges['base'],
                                                               [conversion_ext_market_markets['base'], conversion_ext_market_markets['quote']])
                ext_market = shared_ext_mkt if UseSharedSource else create_paper_trade_market(ext_exchange, [asset_pair])
                if ext_exchange not in list(self.markets.keys()):
                    self.markets[ext_exchange]: ExchangeBase = ext_market
            rate_conversion_delegates[asset_type]: AssetPriceDelegate = OrderBookAssetPriceDelegate(ext_market, asset_pair)

    self.strategy = ArbitrageStrategy(market_pairs=[self.market_pair],
                                      min_profitability=min_profitability,
                                      logging_options=ArbitrageStrategy.OPTION_LOG_ALL,
                                      use_oracle_conversion_rate=use_oracle_conversion_rate,
                                      secondary_to_primary_base_conversion_rate=secondary_to_primary_base_conversion_rate,
                                      secondary_to_primary_quote_conversion_rate=secondary_to_primary_quote_conversion_rate,
                                      base_rate_conversion_delegate=rate_conversion_delegates['base'],
                                      quote_rate_conversion_delegate=rate_conversion_delegates['quote'],
                                      base_conversion_ext_market_price_type=conversion_ext_market_price_types['base'],
                                      quote_conversion_ext_market_price_type=conversion_ext_market_price_types['quote'],
                                      hb_app_notification=True)
