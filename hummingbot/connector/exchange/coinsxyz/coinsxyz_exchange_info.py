"""
Exchange Info Handler for Coins.ph Exchange Connector

This module handles the exchange information endpoint, parsing trading pairs metadata,
trading rules, and market constraints from the Coins.ph API.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS
from hummingbot.connector.exchange.coinsxyz import coinsxyz_utils as utils
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType


class CoinsxyzExchangeInfo:
    """
    Handler for Coins.ph exchange information and trading pairs metadata.

    This class processes exchange info responses and converts them into
    Hummingbot-compatible trading rules and pair information.
    """

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._trading_pairs_cache: Dict[str, Dict[str, Any]] = {}
        self._trading_rules_cache: Dict[str, TradingRule] = {}
        self._last_update_timestamp: float = 0.0

    def get_trading_pairs(self) -> List[str]:
        """
        Get list of available trading pairs.

        :return: List of trading pair symbols
        """
        return list(self._trading_pairs_cache.keys())

    def get_trading_rules(self) -> Dict[str, TradingRule]:
        """
        Get trading rules for all trading pairs.

        :return: Dictionary mapping trading pairs to their rules
        """
        return self._trading_rules_cache.copy()

    def get_exchange_info(self) -> Dict[str, Any]:
        """
        Get cached exchange information.

        :return: Exchange information dictionary
        """
        return {
            'trading_pairs': self.get_trading_pairs(),
            'trading_rules': self.get_trading_rules(),
            'last_update': self._last_update_timestamp
        }

    def parse_exchange_info(self, exchange_info: Dict[str, Any]) -> Tuple[List[str], Dict[str, TradingRule]]:
        """
        Parse exchange info response and extract trading pairs and rules.

        :param exchange_info: Raw exchange info response from API
        :return: Tuple of (trading_pairs_list, trading_rules_dict)
        """
        try:
            symbols_data = exchange_info.get("symbols", [])

            if not symbols_data:
                self._logger.warning("No symbols found in exchange info response")
                return [], {}

            trading_pairs = []
            trading_rules = {}

            for symbol_info in symbols_data:
                if self._is_valid_trading_pair(symbol_info):
                    # Extract trading pair
                    trading_pair = self._extract_trading_pair(symbol_info)
                    if trading_pair:
                        trading_pairs.append(trading_pair)

                        # Create trading rule
                        trading_rule = self._create_trading_rule(symbol_info, trading_pair)
                        if trading_rule:
                            trading_rules[trading_pair] = trading_rule

                            # Cache symbol info
                            self._trading_pairs_cache[trading_pair] = symbol_info

            self._trading_rules_cache = trading_rules
            self._last_update_timestamp = self._get_current_timestamp()

            self._logger.info(f"Parsed {len(trading_pairs)} trading pairs from exchange info")
            self._logger.error(f"DEBUG HEDGE: Available trading pairs: {trading_pairs}")
            btc_pairs = [pair for pair in trading_pairs if 'BTC' in pair]
            eth_pairs = [pair for pair in trading_pairs if 'ETH' in pair]
            self._logger.error(f"DEBUG HEDGE: BTC pairs: {btc_pairs}")
            self._logger.error(f"DEBUG HEDGE: ETH pairs: {eth_pairs}")
            return trading_pairs, trading_rules

        except Exception as e:
            self._logger.error(f"Error parsing exchange info: {e}")
            return [], {}

    def _is_valid_trading_pair(self, symbol_info: Dict[str, Any]) -> bool:
        """
        Check if a symbol is a valid trading pair.

        :param symbol_info: Symbol information from exchange
        :return: True if valid and tradeable
        """
        try:
            # Check required fields
            required_fields = ["symbol", "baseAsset", "quoteAsset", "status"]
            if not all(field in symbol_info for field in required_fields):
                return False

            # Check if trading is enabled (Coins.ph uses lowercase "trading")
            status = symbol_info.get("status", "").lower()
            if status != "trading":
                return False

            # Check if we have valid assets
            base_asset = symbol_info.get("baseAsset", "").strip()
            quote_asset = symbol_info.get("quoteAsset", "").strip()

            if not base_asset or not quote_asset:
                return False

            # Check if we have order types (indicates it's tradeable)
            order_types = symbol_info.get("orderTypes", [])
            if not order_types:
                return False

            # Check if we have filters (indicates proper configuration)
            filters = symbol_info.get("filters", [])
            if not filters:
                return False

            return True

        except Exception as e:
            self._logger.debug(f"Error validating trading pair: {e}")
            return False

    def _extract_trading_pair(self, symbol_info: Dict[str, Any]) -> Optional[str]:
        """
        Extract Hummingbot trading pair format from symbol info.

        :param symbol_info: Symbol information from exchange
        :return: Trading pair in BASE-QUOTE format, or None if invalid
        """
        try:
            base_asset = symbol_info.get("baseAsset", "").strip().upper()
            quote_asset = symbol_info.get("quoteAsset", "").strip().upper()

            if base_asset and quote_asset:
                return f"{base_asset}-{quote_asset}"

        except Exception as e:
            self._logger.debug(f"Error extracting trading pair: {e}")

        return None

    def _create_trading_rule(self, symbol_info: Dict[str, Any], trading_pair: str) -> Optional[TradingRule]:
        """
        Create a TradingRule from symbol information.

        :param symbol_info: Symbol information from exchange
        :param trading_pair: Trading pair in Hummingbot format
        :return: TradingRule object or None if creation failed
        """
        try:
            # Extract filters
            filters = symbol_info.get("filters", [])
            filter_dict = {f.get("filterType"): f for f in filters}

            # Extract basic info
            base_asset = symbol_info.get("baseAsset", "")
            quote_asset = symbol_info.get("quoteAsset", "")

            # Get precision info
            base_asset_precision = symbol_info.get("baseAssetPrecision", 8)
            quote_precision = symbol_info.get("quotePrecision", 8)

            # Extract LOT_SIZE filter (quantity constraints)
            lot_size_filter = filter_dict.get("LOT_SIZE", {})
            min_order_size = self._parse_decimal(lot_size_filter.get("minQty", "0"))
            max_order_size = self._parse_decimal(lot_size_filter.get("maxQty", "1000000"))
            step_size = self._parse_decimal(lot_size_filter.get("stepSize", "0.00000001"))

            # Extract PRICE_FILTER (price constraints)
            price_filter = filter_dict.get("PRICE_FILTER", {})
            min_price_increment = self._parse_decimal(price_filter.get("tickSize", "0.00000001"))
            min_price = self._parse_decimal(price_filter.get("minPrice", "0"))
            max_price = self._parse_decimal(price_filter.get("maxPrice", "1000000"))

            # Extract MIN_NOTIONAL filter (minimum order value)
            min_notional_filter = filter_dict.get("MIN_NOTIONAL", {})
            min_notional = self._parse_decimal(min_notional_filter.get("minNotional", "0"))

            # Alternative: NOTIONAL filter
            if min_notional == 0:
                notional_filter = filter_dict.get("NOTIONAL", {})
                min_notional = self._parse_decimal(notional_filter.get("minNotional", "0"))

            # Extract supported order types
            order_types = symbol_info.get("orderTypes", [])
            supports_limit = "LIMIT" in order_types
            supports_market = "MARKET" in order_types

            # Create TradingRule
            trading_rule = TradingRule(
                trading_pair=trading_pair,
                min_order_size=min_order_size,
                max_order_size=max_order_size,
                min_price_increment=min_price_increment,
                min_base_amount_increment=step_size,
                min_notional_size=min_notional,
                min_order_value=min_notional,
                supports_limit_orders=supports_limit,
                supports_market_orders=supports_market,
                buy_order_collateral_token=quote_asset,
                sell_order_collateral_token=base_asset,
            )

            self._logger.debug(f"Created trading rule for {trading_pair}: "
                               f"min_size={min_order_size}, max_size={max_order_size}, "
                               f"step_size={step_size}, min_notional={min_notional}")

            return trading_rule

        except Exception as e:
            self._logger.error(f"Error creating trading rule for {trading_pair}: {e}")
            return None

    def _parse_decimal(self, value: Any) -> Decimal:
        """
        Parse a value to Decimal, handling various input types.

        :param value: Value to parse
        :return: Decimal representation
        """
        if value is None:
            return Decimal("0")

        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return Decimal("0")

    def _get_current_timestamp(self) -> float:
        """Get current timestamp."""
        import time
        return time.time()

    def get_cached_trading_pairs(self) -> List[str]:
        """
        Get cached trading pairs list.

        :return: List of trading pairs
        """
        return list(self._trading_pairs_cache.keys())

    def get_cached_trading_rules(self) -> Dict[str, TradingRule]:
        """
        Get cached trading rules.

        :return: Dictionary of trading rules
        """
        return self._trading_rules_cache.copy()

    def get_trading_pair_info(self, trading_pair: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific trading pair.

        :param trading_pair: Trading pair in Hummingbot format
        :return: Symbol information or None if not found
        """
        return self._trading_pairs_cache.get(trading_pair)

    def is_trading_pair_supported(self, trading_pair: str) -> bool:
        """
        Check if a trading pair is supported.

        :param trading_pair: Trading pair to check
        :return: True if supported
        """
        return trading_pair in self._trading_pairs_cache

    def get_supported_order_types(self, trading_pair: str) -> List[OrderType]:
        """
        Get supported order types for a trading pair.

        :param trading_pair: Trading pair to check
        :return: List of supported order types
        """
        symbol_info = self._trading_pairs_cache.get(trading_pair)
        if not symbol_info:
            return []

        order_types = symbol_info.get("orderTypes", [])
        supported_types = []

        if "LIMIT" in order_types:
            supported_types.append(OrderType.LIMIT)
        if "MARKET" in order_types:
            supported_types.append(OrderType.MARKET)
        if "LIMIT_MAKER" in order_types:
            supported_types.append(OrderType.LIMIT_MAKER)

        return supported_types

    def get_trading_pair_base_quote(self, trading_pair: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get base and quote assets for a trading pair.

        :param trading_pair: Trading pair to check
        :return: Tuple of (base_asset, quote_asset) or (None, None) if not found
        """
        symbol_info = self._trading_pairs_cache.get(trading_pair)
        if not symbol_info:
            return None, None

        base_asset = symbol_info.get("baseAsset")
        quote_asset = symbol_info.get("quoteAsset")

        return base_asset, quote_asset

    def get_precision_info(self, trading_pair: str) -> Dict[str, int]:
        """
        Get precision information for a trading pair.

        :param trading_pair: Trading pair to check
        :return: Dictionary with precision info
        """
        symbol_info = self._trading_pairs_cache.get(trading_pair, {})

        return {
            "base_asset_precision": symbol_info.get("baseAssetPrecision", 8),
            "quote_precision": symbol_info.get("quotePrecision", 8),
            "base_commission_precision": symbol_info.get("baseCommissionPrecision", 8),
            "quote_commission_precision": symbol_info.get("quoteCommissionPrecision", 8),
        }

    def validate_order_parameters(self, trading_pair: str, order_type: OrderType,
                                  amount: Decimal, price: Optional[Decimal] = None) -> Tuple[bool, str]:
        """
        Validate order parameters against trading rules.

        :param trading_pair: Trading pair for the order
        :param order_type: Type of order
        :param amount: Order amount
        :param price: Order price (for limit orders)
        :return: Tuple of (is_valid, error_message)
        """
        trading_rule = self._trading_rules_cache.get(trading_pair)
        if not trading_rule:
            return False, f"Trading pair {trading_pair} not supported"

        # Check order type support
        if order_type == OrderType.LIMIT and not trading_rule.supports_limit_orders:
            return False, f"Limit orders not supported for {trading_pair}"

        if order_type == OrderType.MARKET and not trading_rule.supports_market_orders:
            return False, f"Market orders not supported for {trading_pair}"

        # Check amount constraints
        if amount < trading_rule.min_order_size:
            return False, f"Order amount {amount} below minimum {trading_rule.min_order_size}"

        if amount > trading_rule.max_order_size:
            return False, f"Order amount {amount} above maximum {trading_rule.max_order_size}"

        # Check step size
        if trading_rule.min_base_amount_increment > 0:
            remainder = amount % trading_rule.min_base_amount_increment
            if remainder != 0:
                return False, f"Order amount {amount} not aligned with step size {trading_rule.min_base_amount_increment}"

        # Check price constraints (for limit orders)
        if price is not None and order_type == OrderType.LIMIT:
            if price < trading_rule.min_price_increment:
                return False, f"Order price {price} below minimum increment {trading_rule.min_price_increment}"

            # Check price tick size
            if trading_rule.min_price_increment > 0:
                remainder = price % trading_rule.min_price_increment
                if remainder != 0:
                    return False, f"Order price {price} not aligned with tick size {trading_rule.min_price_increment}"

        # Check notional value
        if price is not None:
            notional_value = amount * price
            if notional_value < trading_rule.min_notional_size:
                return False, f"Order value {notional_value} below minimum notional {trading_rule.min_notional_size}"

        return True, ""

    def get_cache_age(self) -> float:
        """
        Get the age of the cached data in seconds.

        :return: Age in seconds
        """
        if self._last_update_timestamp == 0:
            return float('inf')

        return self._get_current_timestamp() - self._last_update_timestamp

    def clear_cache(self):
        """Clear all cached data."""
        self._trading_pairs_cache.clear()
        self._trading_rules_cache.clear()
        self._last_update_timestamp = 0.0
