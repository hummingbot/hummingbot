from typing import Any, Dict, List, Mapping, Optional, Tuple

from _decimal import Decimal

from hummingbot.connector.exchange.coinbase_advanced_trade import cat_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_exchange_protocols import (
    CATAPICallsProtocol,
    TradingPairsMixinProtocol,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utils import ProductInfo, Products, is_product_tradable
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair


class _TradingPairsMixinSuperCalls:
    """
    This class is used to call the methods of the super class of a subclass of its Mixin.
    It allows a dynamic search of the methods in the super classes of its Mixin.
    The methods must be defined in one of the super classes defined after its Mixin class.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def trading_rules(self) -> Dict[str, TradingRule]:
        # Defined in ExchangePyBase
        return super().trading_rules()

    async def exchange_symbol_associated_to_pair(self, trading_pair: str) -> str:
        # Defined in ExchangeBase
        return await super().exchange_symbol_associated_to_pair(trading_pair)

    async def trading_pair_associated_to_exchange_symbol(self, symbol: str) -> str:
        # Defined in ExchangeBase
        return await super().trading_pair_associated_to_exchange_symbol(symbol)

    def set_trading_pair_symbol_map(self, trading_pair_and_symbol_map: Optional[Mapping[str, str]]):
        # Defined in ExchangeBase
        super()._set_trading_pair_symbol_map(trading_pair_and_symbol_map)


class _LastTradePriceProtocol(TradingPairsMixinProtocol, CATAPICallsProtocol):
    async def exchange_symbol_associated_to_pair(self, trading_pair: str) -> str:
        ...

    def set_last_trade_price(self, trading_pair: str, price: Decimal):
        ...


class TradingPairsRulesMixin(_TradingPairsMixinSuperCalls):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    async def _initialize_market_assets(self: CATAPICallsProtocol) -> Tuple[ProductInfo]:
        """
        Fetch the list of trading pairs from the exchange and map them
        """
        products: Products = await self.api_get(path_url=CONSTANTS.ALL_PAIRS_EP)
        valid_products: Tuple[ProductInfo] = tuple(filter(is_product_tradable, products["products"]))
        # products: Products = {"products": valid_products, "num_products": len(valid_products)}
        return valid_products

    async def _initialize_trading_pair_symbol_map(self):
        """
        Initializes the trading pair symbols from the exchange information.
        Needs to fetch the list of trading pairs from the exchange and map them
        to the Hummingbot trading pair convention.
        """
        trading_pair_symbol_map: Dict[str, str] = {}
        for product in await self._initialize_market_assets():
            trading_pair_symbol_map[product["product_id"]] = \
                combine_to_hb_trading_pair(base=product["base_currency_id"],
                                           quote=product["quote_currency_id"])
        self.set_trading_pair_symbol_map(trading_pair_symbol_map)

    async def _get_last_traded_price(self: _LastTradePriceProtocol, trading_pair: str) -> float:
        product_id = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        resp_json = await self.api_get(
            path_url=CONSTANTS.PAIR_TICKER_24HR_EP.format(product_id=product_id) + "?limit=1",
        )

        return float(resp_json["trades"]["price"])

    async def get_all_pairs_prices(self: CATAPICallsProtocol, quote: str = "USD") -> List[Dict[str, str]]:
        """
        Fetches the prices of all symbols in the exchange with a default quote of USD
        """
        resp_json = await self.api_get(
            path_url=CONSTANTS.EXCHANGE_RATES_QUOTE_EP.format(quote_token=quote)
        )
        rates: List[Dict[str, str]] = []
        for rate in resp_json["data"]["rates"]:
            rates.append({f"{rate}-{quote}": resp_json["data"]["rates"][rate]})
        return rates

    @staticmethod
    def _convert_product_to_trading_rule(product: ProductInfo) -> TradingRule:
        """
        Converts a product to a trading rule
        """
        trading_pair: str = combine_to_hb_trading_pair(base=product["base_currency_id"],
                                                       quote=product["quote_currency_id"])
        return TradingRule(trading_pair=trading_pair,
                           min_order_size=Decimal(product["base_min_size"]),
                           min_base_amount_increment=Decimal(product["base_increment"]),
                           min_price_increment=Decimal(product["quote_increment"]))

    async def _update_trading_rules(self):
        self.trading_rules().clear()
        for product in await self._initialize_market_assets():
            trading_rule: TradingRule = self._convert_product_to_trading_rule(product)
            self.trading_rules()[trading_rule.trading_pair] = trading_rule
        await self._initialize_trading_pair_symbol_map()

    # Overriding ExchangePyBase hard-coded Exchange specific logic
    # This is to make sure they are not actually called
    @property
    def trading_rules_request_path(self) -> str:
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    @property
    def trading_pairs_request_path(self) -> str:
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    def _make_trading_rules_request(self) -> Any:
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    def _make_trading_pairs_request(self) -> Any:
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")
