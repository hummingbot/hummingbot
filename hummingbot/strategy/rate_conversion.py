import logging
from decimal import Decimal, InvalidOperation
from typing import Optional

from hummingbot.connector.exchange.paper_trade import create_paper_trade_market
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.order_book_asset_price_delegate import OrderBookAssetPriceDelegate

asset_equality_map = {"USDT": ("USDT", "USDC", "USDC.E", "USDM"),
                      "BTC": ("BTC", "WBTC", "BTC.b", "BTC.B", "BTCB"),
                      "ETH": ("ETH", "WETH"),
                      "BNB": ("BNB", "WBNB"),
                      "NXM": ("NXM", "WNXM"),
                      "HT": ("HT", "WHT"),
                      "TLOS": ("TLOS", "WTLOS"),
                      "AVAX": ("AVAX", "WAVAX"),
                      "ONE": ("ONE", "WONE"),
                      "CRO": ("CRO", "WCRO"),
                      "BONE": ("BONE", "WBONE", "knBONE")}


def assets_equality(asset1, asset2):
    if asset1 == asset2:
        return True
    for _, eq_set in asset_equality_map.items():
        if asset1 in eq_set and asset2 in eq_set:
            return True
    return False


def get_basis_asset(asset):
    if asset in asset_equality_map.keys():
        return asset
    for basis_asset, eq_set in asset_equality_map.items():
        if asset in eq_set:
            return basis_asset
    return asset


rate_conversion_logger: Optional[HummingbotLogger] = None


class RateConversionOracle:
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global rate_conversion_logger
        if rate_conversion_logger is None:
            rate_conversion_logger = logging.getLogger(__name__)
        return rate_conversion_logger

    """
    A class to convert rates between different asset pairs using market data.
    """

    def __init__(self, asset_set, client_config_map, paper_trade_market="binance"):
        self._paper_trade_market = paper_trade_market
        self._paper_trade_market_prio_list = [paper_trade_market, "binance", "ascend_ex", "mexc"]
        self._asset_set = asset_set
        self._rates = {}
        self._fixed_rates = {}
        self._trading_pair_fetcher = TradingPairFetcher.get_instance()
        self._legacy_rate_oracle = RateOracle.get_instance()
        self._markets = {}
        self._client_config_map = client_config_map
        self.init_rates()

    @property
    def markets(self):
        return self._markets

    @property
    def fixed_rates(self):
        return self._fixed_rates

    def init_rates(self):
        """Initializes rates for the asset set."""
        for asset in self._asset_set:
            self.add_asset_price_delegate(asset)

    def add_asset_price_delegate(self, asset):
        """Add an OrderBookAssetPriceDelegate to self._rates"""
        asset = get_basis_asset(asset)  # convert WBTC to BTC for the exchange
        asset_price_delegate = self.get_asset_price_delegate(asset)
        if asset_price_delegate:
            self._rates[f"{asset}-USDT"] = asset_price_delegate

    def get_asset_price_delegate(self, asset):
        """Fetches the price delegate for a given asset."""
        # Override CBY for Coinstore as the fetcher is not perfect here
        conversion_pair = f"{asset}-USDT"
        base, quote = conversion_pair.split("-")
        inverse_conversion_pair = f"{quote}-{base}"
        if base == quote:
            return

        use_legacy_oracle = False

        for i, exchange in enumerate(self._paper_trade_market_prio_list):
            if self._trading_pair_fetcher.ready:
                trading_pairs = self._trading_pair_fetcher.trading_pairs.get(f"{exchange}_paper_trade", [])
                if conversion_pair not in trading_pairs:
                    if inverse_conversion_pair not in trading_pairs:
                        if i == len(self._paper_trade_market_prio_list) - 1:
                            self.logger().info(f"WARNING: The conversion pair {conversion_pair} is unavailable on {exchange}. Resort to legacy Oracle.")
                            use_legacy_oracle = True
                        else:
                            self.logger().info(f"WARNING: The conversion pair {conversion_pair} is unavailable on {exchange}. Try on {self._paper_trade_market_prio_list[i + 1]}.")
                    else:
                        break
                else:
                    break

        if not use_legacy_oracle:
            ext_market = create_paper_trade_market(self._paper_trade_market, self._client_config_map, [conversion_pair])
            self._markets[conversion_pair]: ExchangeBase = ext_market
            conversion_asset_price_delegate = OrderBookAssetPriceDelegate(ext_market, conversion_pair)
            return conversion_asset_price_delegate
        else:
            return None

    def get_pair_rate(self, pair):
        return self.get_mid_price(pair)

    def get_mid_price(self, pair):
        cross_pair_price = self.get_cross_pair_price(pair)
        if not isinstance(cross_pair_price, Decimal):
            raise ValueError(f"could not fetch mid price for {pair}. value {cross_pair_price} is not a Decimal")
        return cross_pair_price

    def get_rate_price_delegate(self, pair):
        if pair in list(self._rates.keys()):
            return self._rates[pair].get_mid_price()

        # create inverse and check if exist
        base, quote = pair.split("-")
        base, quote = quote, base
        reversed_pair = quote + "-" + base
        if reversed_pair in self._rates:
            return 1 / self._rates[reversed_pair].get_mid_price()
        elif assets_equality(base, quote):
            return Decimal(1)
        else:
            raise ValueError(f"no OrderBookAssetPriceDelegate exists for pair '{pair}'.")

    def add_fixed_asset_price_delegate(self, pair, rate):
        """Add a fixed rate for a given pair to self._fixed_rates"""
        try:
            rate = Decimal(rate)
            self._fixed_rates[pair] = rate
        except InvalidOperation:
            raise ValueError(f"Cannot convert '{rate}' to Decimal.")

    def get_cross_pair_price(self, pair):
        """Calculates the cross pair price for two assets."""

        # convert to basis asset -> WBTC to BTC
        base, quote = pair.split("-")
        # pair = base + "-" + quote
        reverse_pair = quote + "-" + base

        # check first if there is a fixed rate
        if pair in self._fixed_rates:
            return self._fixed_rates[pair]
        if reverse_pair in self._fixed_rates:
            return 1 / self._fixed_rates[reverse_pair]

        # normalize and check if there is a rate
        base, quote = get_basis_asset(base), get_basis_asset(quote)
        pair = base + "-" + quote
        reverse_pair = quote + "-" + base
        if pair in self._rates:
            return self._rates[pair].get_mid_price()
        if reverse_pair in self._rates:
            return 1 / self._rates[reverse_pair].get_mid_price()

        if assets_equality(base, quote):
            return Decimal(1)
        elif pair in self._rates.keys():
            return self._rates[pair].get_mid_price()
        elif reverse_pair in self._rates.keys():
            return 1 / self._rates[reverse_pair].get_mid_price()

        base_rate_token = f"{base}-USDT"
        quote_rate_token = f"{quote}-USDT"

        if base_rate_token in self._rates and quote_rate_token in self._rates:
            base_price_in_usdt = self.get_rate_price_delegate(base_rate_token)
            quote_price_in_usdt = self.get_rate_price_delegate(quote_rate_token)
            return base_price_in_usdt / quote_price_in_usdt
        else:
            return self._legacy_rate_oracle.get_pair_rate(pair)
