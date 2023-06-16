from typing import Dict, List, Optional, Tuple

from _decimal import Decimal

from hummingbot.connector.exchange.coinbase_advanced_trade import cat_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_data_converters import (
    cat_product_to_trading_rule,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_response_types import (
    CoinbaseAdvancedTradeGetMarketTradesResponse as _MarketTrades,
    CoinbaseAdvancedTradeGetProductResponse as _Product,
    CoinbaseAdvancedTradeListProductsResponse as _Products,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_exchange_protocols import (
    CoinbaseAdvancedTradeAPICallsMixinProtocol as _APICallsProto,
    CoinbaseAdvancedTradeTradingPairsMixinProtocol as _TradingPairsProto,
    CoinbaseAdvancedTradeUtilitiesMixinProtocol,
    CoinbaseAdvancedTradeUtilitiesMixinProtocol as _UtilitiesProto,
)
from hummingbot.connector.trading_rule import TradingRule


class _PairsAPILoggerProto(_TradingPairsProto, _APICallsProto, _UtilitiesProto):
    def set_last_trade_price(self, trading_pair: str, price: Decimal):
        ...

    async def _initialize_market_assets(self) -> Tuple[_Product, ...]:
        ...


class TradingPairsRulesMixin:

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pair_symbol_map_initialized = False

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def trading_pairs(self: CoinbaseAdvancedTradeUtilitiesMixinProtocol) -> List[str]:
        return self._trading_pairs

    # Overwriting this method from ExchangePyBase that seems to force mis-handling data flow
    # as well as duplicating expensive API calls (call for all products)
    async def _update_trading_rules(self: _PairsAPILoggerProto):
        self.trading_rules.clear()
        trading_pair_symbol_map: Dict[str, str] = {}
        products: Optional[Tuple[_Product, ...]] = await self._initialize_market_assets()

        if products is None:
            return

        for product in products:
            # try:
            #     trading_pair: str = await self.trading_pair_associated_to_exchange_symbol(symbol=product.product_id)
            #     trading_rule: TradingRule = cat_product_to_trading_rule(product, trading_pair=trading_pair)
            # except asyncio.TimeoutError:
            #     trading_rule: TradingRule = cat_product_to_trading_rule(product)
            # except Exception:
            #     self.logger().error(f"Error getting trading pair for {product.product_id} from Coinbase Advanced "
            #                         f"Trade. Skipping.")
            trading_rule: TradingRule = cat_product_to_trading_rule(product)

            self.trading_rules[trading_rule.trading_pair] = trading_rule

            trading_pair_symbol_map[product.product_id] = trading_rule.trading_pair
        self._set_trading_pair_symbol_map(trading_pair_symbol_map)

    async def _initialize_trading_pair_symbol_map(self):
        if not self._pair_symbol_map_initialized:
            await self._update_trading_rules()
            self._pair_symbol_map_initialized: bool = True

    async def _initialize_market_assets(self: _PairsAPILoggerProto) -> Tuple[_Product, ...]:
        """
        Fetch the list of trading pairs from the exchange and map them
        """
        try:
            products: _Products = _Products(**await self.api_get(path_url=CONSTANTS.ALL_PAIRS_EP))
            return products.tradable_products
        except Exception:
            self.logger().exception("Error getting all trading pairs from Coinbase Advanced Trade.")

    async def _get_last_traded_price(self: _PairsAPILoggerProto, trading_pair: str) -> float:
        product_id = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        trade = _MarketTrades(**await self.api_get(
            path_url=CONSTANTS.PAIR_TICKER_24HR_EP.format(product_id=product_id) + "?limit=1",
            limit_id=CONSTANTS.PAIR_TICKER_24HR_RATE_LIMIT_ID
        ))
        return float(trade.trades[0].price)

    async def get_all_pairs_prices(self: _APICallsProto) -> List[Dict[str, str]]:
        """
        Fetches the prices of all symbols in the exchange with a default quote of USD
        """
        products: _Products = _Products(**await self.api_get(path_url=CONSTANTS.ALL_PAIRS_EP))
        return [{p.product_id: p.price} for p in products.tradable_products]
