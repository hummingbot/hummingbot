from typing import (
    List,
    Tuple,
)

from hummingbot import data_path
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.pure_market_making_as import (
    PureMarketMakingASStrategy,
    OrderBookAssetPriceDelegate,
    APIAssetPriceDelegate,
)
from hummingbot.strategy.pure_market_making_as.pure_market_making_as_config_map import pure_market_making_as_config_map as c_map
from hummingbot.connector.exchange.paper_trade import create_paper_trade_market
from hummingbot.connector.exchange_base import ExchangeBase
from decimal import Decimal


def start(self):
    try:
        order_amount = c_map.get("order_amount").value
        order_refresh_time = c_map.get("order_refresh_time").value
        exchange = c_map.get("exchange").value.lower()
        raw_trading_pair = c_map.get("market").value
        inventory_target_base_pct = 0 if c_map.get("inventory_target_base_pct").value is None else \
            c_map.get("inventory_target_base_pct").value / Decimal('100')
        price_source = c_map.get("price_source").value
        price_type = c_map.get("price_type").value
        price_source_exchange = c_map.get("price_source_exchange").value
        price_source_market = c_map.get("price_source_market").value
        price_source_custom_api = c_map.get("price_source_custom_api").value
        filled_order_delay = c_map.get("filled_order_delay").value
        order_refresh_tolerance_pct = c_map.get("order_refresh_tolerance_pct").value / Decimal('100')

        trading_pair: str = raw_trading_pair
        maker_assets: Tuple[str, str] = self._initialize_market_assets(exchange, [trading_pair])[0]
        market_names: List[Tuple[str, List[str]]] = [(exchange, [trading_pair])]
        self._initialize_wallet(token_trading_pairs=list(set(maker_assets)))
        self._initialize_markets(market_names)
        self.assets = set(maker_assets)
        maker_data = [self.markets[exchange], trading_pair] + list(maker_assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]
        asset_price_delegate = None
        if price_source == "external_market":
            asset_trading_pair: str = price_source_market
            ext_market = create_paper_trade_market(price_source_exchange, [asset_trading_pair])
            self.markets[price_source_exchange]: ExchangeBase = ext_market
            asset_price_delegate = OrderBookAssetPriceDelegate(ext_market, asset_trading_pair)
        elif price_source == "custom_api":
            asset_price_delegate = APIAssetPriceDelegate(price_source_custom_api)

        strategy_logging_options = PureMarketMakingASStrategy.OPTION_LOG_ALL
        kappa = c_map.get("kappa").value
        gamma = c_map.get("gamma").value
        closing_time = c_map.get("closing_time").value * 3600 * 24 * 1e3
        fixed_order_amount = c_map.get("fixed_order_amount").value
        buffer_size = c_map.get("buffer_size").value

        self.strategy = PureMarketMakingASStrategy(
            market_info=MarketTradingPairTuple(*maker_data),
            order_amount=order_amount,
            inventory_target_base_pct=inventory_target_base_pct,
            order_refresh_time=order_refresh_time,
            order_refresh_tolerance_pct=order_refresh_tolerance_pct,
            filled_order_delay=filled_order_delay,
            add_transaction_costs_to_orders=True,
            logging_options=strategy_logging_options,
            asset_price_delegate=asset_price_delegate,
            price_type=price_type,
            hb_app_notification=True,
            kappa=kappa,
            gamma=gamma,
            closing_time=closing_time,
            fixed_order_amount=fixed_order_amount,
            data_path=data_path(),
            buffer_size = buffer_size,
        )
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
