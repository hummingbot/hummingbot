"""
Trading Rules & Fee Integration for Coins.xyz Exchange.

This module provides comprehensive trading rules and fee integration including:
- Coins.xyz fee structure implementation
- Trading rules integration (lot sizes, minimum notional values)
- Symbol-specific trading constraints
- Fee calculation utilities for different order types
- Trading rules validation before order placement
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from hummingbot.connector.exchange.coinsxyz import (
    coinsxyz_constants as CONSTANTS,
    coinsxyz_utils as utils,
    coinsxyz_web_utils as web_utils,
)
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class FeeType(Enum):
    """Fee type enumeration."""
    MAKER = "MAKER"
    TAKER = "TAKER"
    WITHDRAWAL = "WITHDRAWAL"
    DEPOSIT = "DEPOSIT"


@dataclass
class CoinsxyzFeeStructure:
    """Coins.xyz fee structure data."""
    trading_pair: str
    maker_fee_rate: Decimal
    taker_fee_rate: Decimal
    min_fee_amount: Decimal
    fee_currency: str
    volume_tier: str = "DEFAULT"
    special_conditions: Optional[Dict[str, Any]] = None


@dataclass
class CoinsxyzTradingRule:
    """Enhanced trading rule for Coins.xyz."""
    trading_pair: str
    min_order_size: Decimal
    max_order_size: Decimal
    min_price_increment: Decimal
    min_base_amount_increment: Decimal
    min_quote_amount_increment: Decimal
    min_notional_size: Decimal
    max_price_significant_digits: int
    max_base_amount_significant_digits: int
    supports_limit_orders: bool = True
    supports_market_orders: bool = True
    supports_stop_orders: bool = False
    trading_status: str = "TRADING"
    base_asset_precision: int = 8
    quote_asset_precision: int = 8


@dataclass
class OrderValidationResult:
    """Order validation result with detailed feedback."""
    is_valid: bool
    error_message: Optional[str] = None
    warnings: List[str] = None
    adjusted_amount: Optional[Decimal] = None
    adjusted_price: Optional[Decimal] = None
    estimated_fee: Optional[Decimal] = None
    fee_currency: Optional[str] = None


class CoinsxyzTradingRules:
    """
    Trading rules and fee integration for Coins.xyz exchange.

    Provides comprehensive trading rules management with:
    - Fee structure implementation and calculation
    - Trading rules validation and enforcement
    - Symbol-specific trading constraints
    - Order parameter validation and adjustment
    - Fee calculation for different order types
    """

    def __init__(self,
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        """
        Initialize trading rules and fee integration.

        Args:
            api_factory: Web assistants factory for API requests
            domain: API domain (default or testnet)
        """
        self._api_factory = api_factory
        self._domain = domain
        self._logger = None

        # Trading rules and fees cache
        self._trading_rules: Dict[str, CoinsxyzTradingRule] = {}
        self._fee_structures: Dict[str, CoinsxyzFeeStructure] = {}
        self._last_update_time = 0
        self._update_interval = 1800  # 30 minutes

        # Default fee structure (will be updated from API)
        self._default_fees = CoinsxyzFeeStructure(
            trading_pair="DEFAULT",
            maker_fee_rate=Decimal("0.001"),  # 0.1%
            taker_fee_rate=Decimal("0.002"),  # 0.2%
            min_fee_amount=Decimal("0.00001"),
            fee_currency="USDT"
        )

        # Update lock
        self._update_lock = asyncio.Lock()

    def logger(self) -> HummingbotLogger:
        """Get logger instance."""
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    async def initialize_trading_rules(self) -> bool:
        """
        Initialize trading rules and fee structures from exchange.

        Returns:
            Boolean indicating success
        """
        try:
            # Fetch exchange info
            exchange_info = await self._fetch_exchange_info()

            # Parse trading rules
            trading_rules = await self._parse_trading_rules(exchange_info)

            # Parse fee structures
            fee_structures = await self._parse_fee_structures(exchange_info)

            # Update cache
            self._trading_rules.update(trading_rules)
            self._fee_structures.update(fee_structures)
            self._last_update_time = time.time()

            self.logger().info(
                f"Initialized {len(trading_rules)} trading rules and "
                f"{len(fee_structures)} fee structures"
            )

            return True

        except Exception as e:
            self.logger().error(f"Error initializing trading rules: {e}")
            return False

    async def update_trading_rules(self) -> bool:
        """
        Update trading rules and fee structures if needed.

        Returns:
            Boolean indicating if update was performed
        """
        current_time = time.time()

        if current_time - self._last_update_time < self._update_interval:
            return False

        async with self._update_lock:
            try:
                return await self.initialize_trading_rules()
            except Exception as e:
                self.logger().error(f"Error updating trading rules: {e}")
                return False

    def get_trading_rule(self, trading_pair: str) -> Optional[CoinsxyzTradingRule]:
        """
        Get trading rule for a specific trading pair.

        Args:
            trading_pair: Trading pair (e.g., "BTC-USDT")

        Returns:
            CoinsxyzTradingRule or None if not found
        """
        return self._trading_rules.get(trading_pair)

    def get_fee_structure(self, trading_pair: str) -> CoinsxyzFeeStructure:
        """
        Get fee structure for a trading pair.

        Args:
            trading_pair: Trading pair

        Returns:
            CoinsxyzFeeStructure (default if not found)
        """
        return self._fee_structures.get(trading_pair, self._default_fees)

    def calculate_fee(self,
                      trading_pair: str,
                      order_type: OrderType,
                      trade_type: TradeType,
                      amount: Decimal,
                      price: Decimal,
                      is_maker: Optional[bool] = None) -> Dict[str, Any]:
        """
        Calculate fee for an order.

        Args:
            trading_pair: Trading pair
            order_type: Order type
            trade_type: Trade type
            amount: Order amount
            price: Order price
            is_maker: Whether order is maker (None for auto-detection)

        Returns:
            Dictionary with fee information
        """
        try:
            # Get fee structure
            fee_structure = self.get_fee_structure(trading_pair)

            # Determine if maker or taker
            if is_maker is None:
                is_maker = order_type == OrderType.LIMIT_MAKER or order_type == OrderType.LIMIT

            # Calculate fee rate
            fee_rate = fee_structure.maker_fee_rate if is_maker else fee_structure.taker_fee_rate

            # Calculate notional value
            notional_value = amount * price

            # Calculate fee amount
            fee_amount = notional_value * fee_rate

            # Apply minimum fee
            if fee_amount < fee_structure.min_fee_amount:
                fee_amount = fee_structure.min_fee_amount

            # Determine fee currency
            base_asset, quote_asset = trading_pair.split("-")
            if trade_type == TradeType.BUY:
                fee_currency = base_asset  # Fee paid in base asset for buy orders
            else:
                fee_currency = quote_asset  # Fee paid in quote asset for sell orders

            return {
                "fee_rate": fee_rate,
                "fee_amount": fee_amount,
                "fee_currency": fee_currency,
                "notional_value": notional_value,
                "is_maker": is_maker,
                "min_fee_applied": fee_amount == fee_structure.min_fee_amount,
                "volume_tier": fee_structure.volume_tier
            }

        except Exception as e:
            self.logger().error(f"Error calculating fee for {trading_pair}: {e}")
            return {
                "fee_rate": self._default_fees.taker_fee_rate,
                "fee_amount": Decimal("0.001"),
                "fee_currency": "USDT",
                "notional_value": amount * price,
                "is_maker": False,
                "error": str(e)
            }

    def validate_order_parameters(self,
                                  trading_pair: str,
                                  order_type: OrderType,
                                  trade_type: TradeType,
                                  amount: Decimal,
                                  price: Optional[Decimal] = None) -> OrderValidationResult:
        """
        Validate order parameters against trading rules.

        Args:
            trading_pair: Trading pair
            order_type: Order type
            trade_type: Trade type
            amount: Order amount
            price: Order price (required for LIMIT orders)

        Returns:
            OrderValidationResult with validation outcome
        """
        try:
            warnings = []

            # Get trading rule
            trading_rule = self.get_trading_rule(trading_pair)
            if not trading_rule:
                return OrderValidationResult(
                    is_valid=False,
                    error_message=f"Trading pair {trading_pair} not supported"
                )

            # Check trading status
            if trading_rule.trading_status != "TRADING":
                return OrderValidationResult(
                    is_valid=False,
                    error_message=f"Trading is currently {trading_rule.trading_status} for {trading_pair}"
                )

            # Check order type support
            if order_type == OrderType.LIMIT and not trading_rule.supports_limit_orders:
                return OrderValidationResult(
                    is_valid=False,
                    error_message=f"LIMIT orders not supported for {trading_pair}"
                )

            if order_type == OrderType.MARKET and not trading_rule.supports_market_orders:
                return OrderValidationResult(
                    is_valid=False,
                    error_message=f"MARKET orders not supported for {trading_pair}"
                )

            # Validate amount
            if amount < trading_rule.min_order_size:
                return OrderValidationResult(
                    is_valid=False,
                    error_message=f"Order amount {amount} below minimum {trading_rule.min_order_size}"
                )

            if amount > trading_rule.max_order_size:
                return OrderValidationResult(
                    is_valid=False,
                    error_message=f"Order amount {amount} exceeds maximum {trading_rule.max_order_size}"
                )

            # Validate price for LIMIT orders
            if order_type == OrderType.LIMIT:
                if price is None:
                    return OrderValidationResult(
                        is_valid=False,
                        error_message="Price is required for LIMIT orders"
                    )

                if price <= 0:
                    return OrderValidationResult(
                        is_valid=False,
                        error_message="Order price must be positive"
                    )

                # Check minimum notional value
                notional_value = amount * price
                if notional_value < trading_rule.min_notional_size:
                    return OrderValidationResult(
                        is_valid=False,
                        error_message=f"Order notional value {notional_value} below minimum {trading_rule.min_notional_size}"
                    )

            # Adjust precision
            adjusted_amount = self._adjust_amount_precision(amount, trading_rule)
            adjusted_price = self._adjust_price_precision(price, trading_rule) if price else None

            if adjusted_amount != amount:
                warnings.append(f"Amount adjusted from {amount} to {adjusted_amount} for precision")

            if adjusted_price and adjusted_price != price:
                warnings.append(f"Price adjusted from {price} to {adjusted_price} for precision")

            # Calculate estimated fee
            estimated_fee = None
            fee_currency = None
            if adjusted_price:
                fee_info = self.calculate_fee(trading_pair, order_type, trade_type, adjusted_amount, adjusted_price)
                estimated_fee = fee_info.get("fee_amount")
                fee_currency = fee_info.get("fee_currency")

            return OrderValidationResult(
                is_valid=True,
                warnings=warnings if warnings else None,
                adjusted_amount=adjusted_amount,
                adjusted_price=adjusted_price,
                estimated_fee=estimated_fee,
                fee_currency=fee_currency
            )

        except Exception as e:
            self.logger().error(f"Error validating order parameters: {e}")
            return OrderValidationResult(
                is_valid=False,
                error_message=f"Validation error: {e}"
            )

    def _adjust_amount_precision(self, amount: Decimal, trading_rule: CoinsxyzTradingRule) -> Decimal:
        """
        Adjust amount precision according to trading rules.

        Args:
            amount: Original amount
            trading_rule: Trading rule

        Returns:
            Adjusted amount
        """
        increment = trading_rule.min_base_amount_increment
        if increment > 0:
            return (amount / increment).quantize(Decimal("1")) * increment
        return amount

    def _adjust_price_precision(self, price: Decimal, trading_rule: CoinsxyzTradingRule) -> Decimal:
        """
        Adjust price precision according to trading rules.

        Args:
            price: Original price
            trading_rule: Trading rule

        Returns:
            Adjusted price
        """
        increment = trading_rule.min_price_increment
        if increment > 0:
            return (price / increment).quantize(Decimal("1")) * increment
        return price

    async def _fetch_exchange_info(self) -> Dict[str, Any]:
        """
        Fetch exchange information from API.

        Returns:
            Exchange information dictionary
        """
        rest_assistant = await self._api_factory.get_rest_assistant()

        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self._domain)

        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.EXCHANGE_INFO_PATH_URL
        )

        return response

    async def _parse_trading_rules(self, exchange_info: Dict[str, Any]) -> Dict[str, CoinsxyzTradingRule]:
        """
        Parse trading rules from exchange info.

        Args:
            exchange_info: Exchange information

        Returns:
            Dictionary of trading rules
        """
        trading_rules = {}

        try:
            symbols = exchange_info.get("symbols", [])

            for symbol_info in symbols:
                try:
                    symbol = symbol_info.get("symbol", "")
                    trading_pair = utils.parse_exchange_trading_pair(symbol)

                    if not trading_pair:
                        continue

                    # Parse filters
                    filters = {f["filterType"]: f for f in symbol_info.get("filters", [])}

                    # Extract trading rule parameters
                    lot_size_filter = filters.get("LOT_SIZE", {})
                    price_filter = filters.get("PRICE_FILTER", {})
                    notional_filter = filters.get("MIN_NOTIONAL", {})

                    trading_rule = CoinsxyzTradingRule(
                        trading_pair=trading_pair,
                        min_order_size=Decimal(lot_size_filter.get("minQty", "0.001")),
                        max_order_size=Decimal(lot_size_filter.get("maxQty", "1000000")),
                        min_base_amount_increment=Decimal(lot_size_filter.get("stepSize", "0.001")),
                        min_price_increment=Decimal(price_filter.get("tickSize", "0.01")),
                        min_quote_amount_increment=Decimal("0.01"),
                        min_notional_size=Decimal(notional_filter.get("minNotional", "10.0")),
                        max_price_significant_digits=8,
                        max_base_amount_significant_digits=8,
                        supports_limit_orders=True,
                        supports_market_orders=True,
                        trading_status=symbol_info.get("status", "TRADING"),
                        base_asset_precision=int(symbol_info.get("baseAssetPrecision", 8)),
                        quote_asset_precision=int(symbol_info.get("quotePrecision", 8))
                    )

                    trading_rules[trading_pair] = trading_rule

                except Exception as e:
                    self.logger().error(f"Error parsing trading rule for {symbol_info}: {e}")
                    continue

            return trading_rules

        except Exception as e:
            self.logger().error(f"Error parsing trading rules: {e}")
            return {}

    async def _parse_fee_structures(self, exchange_info: Dict[str, Any]) -> Dict[str, CoinsxyzFeeStructure]:
        """
        Parse fee structures from exchange info.

        Args:
            exchange_info: Exchange information

        Returns:
            Dictionary of fee structures
        """
        fee_structures = {}

        try:
            # Default fee structure for all pairs
            default_maker_fee = Decimal("0.001")  # 0.1%
            default_taker_fee = Decimal("0.002")  # 0.2%

            symbols = exchange_info.get("symbols", [])

            for symbol_info in symbols:
                try:
                    symbol = symbol_info.get("symbol", "")
                    trading_pair = utils.parse_exchange_trading_pair(symbol)

                    if not trading_pair:
                        continue

                    # Extract fee information (if available in symbol info)
                    maker_fee = Decimal(str(symbol_info.get("makerCommission", default_maker_fee)))
                    taker_fee = Decimal(str(symbol_info.get("takerCommission", default_taker_fee)))

                    # Determine fee currency (usually quote asset)
                    base_asset, quote_asset = trading_pair.split("-")
                    fee_currency = quote_asset

                    fee_structure = CoinsxyzFeeStructure(
                        trading_pair=trading_pair,
                        maker_fee_rate=maker_fee,
                        taker_fee_rate=taker_fee,
                        min_fee_amount=Decimal("0.00001"),
                        fee_currency=fee_currency,
                        volume_tier="DEFAULT"
                    )

                    fee_structures[trading_pair] = fee_structure

                except Exception as e:
                    self.logger().error(f"Error parsing fee structure for {symbol_info}: {e}")
                    continue

            return fee_structures

        except Exception as e:
            self.logger().error(f"Error parsing fee structures: {e}")
            return {}

    def get_all_trading_pairs(self) -> List[str]:
        """Get all available trading pairs."""
        return list(self._trading_rules.keys())

    def get_trading_rules_summary(self) -> Dict[str, Any]:
        """
        Get summary of trading rules.

        Returns:
            Dictionary with trading rules summary
        """
        return {
            "total_trading_pairs": len(self._trading_rules),
            "last_update": self._last_update_time,
            "update_interval": self._update_interval,
            "default_maker_fee": str(self._default_fees.maker_fee_rate),
            "default_taker_fee": str(self._default_fees.taker_fee_rate),
            "trading_pairs": list(self._trading_rules.keys())
        }

    def create_hummingbot_trading_rule(self, trading_pair: str) -> Optional[TradingRule]:
        """
        Create Hummingbot TradingRule from CoinsxyzTradingRule.

        Args:
            trading_pair: Trading pair

        Returns:
            TradingRule object or None if not found
        """
        coinsxyz_rule = self.get_trading_rule(trading_pair)
        if not coinsxyz_rule:
            return None

        return TradingRule(
            trading_pair=trading_pair,
            min_order_size=coinsxyz_rule.min_order_size,
            max_order_size=coinsxyz_rule.max_order_size,
            min_price_increment=coinsxyz_rule.min_price_increment,
            min_base_amount_increment=coinsxyz_rule.min_base_amount_increment,
            min_quote_amount_increment=coinsxyz_rule.min_quote_amount_increment,
            min_notional_size=coinsxyz_rule.min_notional_size
        )

    def create_trade_fee(self,
                         trading_pair: str,
                         order_type: OrderType,
                         trade_type: TradeType,
                         amount: Decimal,
                         price: Decimal,
                         is_maker: Optional[bool] = None) -> TokenAmount:
        """
        Create TokenAmount object for Hummingbot integration.

        Args:
            trading_pair: Trading pair
            order_type: Order type
            trade_type: Trade type
            amount: Order amount
            price: Order price
            is_maker: Whether order is maker

        Returns:
            TokenAmount object
        """
        fee_info = self.calculate_fee(trading_pair, order_type, trade_type, amount, price, is_maker)

        return TokenAmount(
            token=fee_info["fee_currency"],
            amount=fee_info["fee_amount"]
        )

    def get_volume_tier_fees(self, volume_30d: Decimal) -> Dict[str, Decimal]:
        """
        Get fee rates based on 30-day trading volume.

        Args:
            volume_30d: 30-day trading volume in USDT

        Returns:
            Dictionary with maker and taker fee rates
        """
        # Coins.xyz volume-based fee tiers (example structure)
        fee_tiers = [
            {"min_volume": Decimal("0"), "maker_fee": Decimal("0.001"), "taker_fee": Decimal("0.002")},
            {"min_volume": Decimal("10000"), "maker_fee": Decimal("0.0009"), "taker_fee": Decimal("0.0018")},
            {"min_volume": Decimal("50000"), "maker_fee": Decimal("0.0008"), "taker_fee": Decimal("0.0016")},
            {"min_volume": Decimal("100000"), "maker_fee": Decimal("0.0007"), "taker_fee": Decimal("0.0014")},
            {"min_volume": Decimal("500000"), "maker_fee": Decimal("0.0006"), "taker_fee": Decimal("0.0012")},
            {"min_volume": Decimal("1000000"), "maker_fee": Decimal("0.0005"), "taker_fee": Decimal("0.001")},
        ]

        # Find applicable tier
        applicable_tier = fee_tiers[0]  # Default to lowest tier
        for tier in reversed(fee_tiers):
            if volume_30d >= tier["min_volume"]:
                applicable_tier = tier
                break

        return {
            "maker_fee_rate": applicable_tier["maker_fee"],
            "taker_fee_rate": applicable_tier["taker_fee"],
            "volume_tier": f"TIER_{fee_tiers.index(applicable_tier) + 1}",
            "min_volume": applicable_tier["min_volume"]
        }

    def calculate_withdrawal_fee(self, asset: str, amount: Decimal) -> Dict[str, Any]:
        """
        Calculate withdrawal fee for an asset.

        Args:
            asset: Asset symbol (e.g., "BTC", "ETH")
            amount: Withdrawal amount

        Returns:
            Dictionary with withdrawal fee information
        """
        # Default withdrawal fees (should be updated from API)
        withdrawal_fees = {
            "BTC": Decimal("0.0005"),
            "ETH": Decimal("0.005"),
            "USDT": Decimal("1.0"),
            "USDC": Decimal("1.0"),
            "BNB": Decimal("0.001"),
        }

        base_fee = withdrawal_fees.get(asset, Decimal("0.001"))

        # Some assets have percentage-based fees
        percentage_fee_assets = {"USDT", "USDC"}
        if asset in percentage_fee_assets:
            percentage_fee = amount * Decimal("0.001")  # 0.1%
            final_fee = max(base_fee, percentage_fee)
        else:
            final_fee = base_fee

        return {
            "asset": asset,
            "withdrawal_amount": amount,
            "fee_amount": final_fee,
            "net_amount": amount - final_fee,
            "fee_type": "FIXED" if asset not in percentage_fee_assets else "PERCENTAGE",
            "minimum_withdrawal": self._get_minimum_withdrawal(asset)
        }

    def _get_minimum_withdrawal(self, asset: str) -> Decimal:
        """
        Get minimum withdrawal amount for an asset.

        Args:
            asset: Asset symbol

        Returns:
            Minimum withdrawal amount
        """
        minimum_withdrawals = {
            "BTC": Decimal("0.001"),
            "ETH": Decimal("0.01"),
            "USDT": Decimal("10.0"),
            "USDC": Decimal("10.0"),
            "BNB": Decimal("0.01"),
        }

        return minimum_withdrawals.get(asset, Decimal("0.001"))

    def validate_withdrawal(self, asset: str, amount: Decimal, available_balance: Decimal) -> Dict[str, Any]:
        """
        Validate withdrawal request.

        Args:
            asset: Asset symbol
            amount: Withdrawal amount
            available_balance: Available balance

        Returns:
            Dictionary with validation result
        """
        try:
            # Calculate withdrawal fee
            fee_info = self.calculate_withdrawal_fee(asset, amount)

            # Check minimum withdrawal
            min_withdrawal = fee_info["minimum_withdrawal"]
            if amount < min_withdrawal:
                return {
                    "is_valid": False,
                    "error": f"Withdrawal amount {amount} below minimum {min_withdrawal} for {asset}"
                }

            # Check available balance
            total_required = amount + fee_info["fee_amount"]
            if total_required > available_balance:
                return {
                    "is_valid": False,
                    "error": f"Insufficient balance: required {total_required}, available {available_balance}"
                }

            return {
                "is_valid": True,
                "fee_info": fee_info,
                "total_required": total_required,
                "remaining_balance": available_balance - total_required
            }

        except Exception as e:
            return {
                "is_valid": False,
                "error": f"Validation error: {e}"
            }

    def get_fee_discount_info(self, user_tier: str = "DEFAULT") -> Dict[str, Any]:
        """
        Get fee discount information based on user tier.

        Args:
            user_tier: User tier level

        Returns:
            Dictionary with discount information
        """
        discount_tiers = {
            "DEFAULT": {"discount": Decimal("0"), "description": "No discount"},
            "VIP1": {"discount": Decimal("0.1"), "description": "10% fee discount"},
            "VIP2": {"discount": Decimal("0.15"), "description": "15% fee discount"},
            "VIP3": {"discount": Decimal("0.2"), "description": "20% fee discount"},
            "VIP4": {"discount": Decimal("0.25"), "description": "25% fee discount"},
            "VIP5": {"discount": Decimal("0.3"), "description": "30% fee discount"},
        }

        tier_info = discount_tiers.get(user_tier, discount_tiers["DEFAULT"])

        return {
            "user_tier": user_tier,
            "discount_rate": tier_info["discount"],
            "description": tier_info["description"],
            "available_tiers": list(discount_tiers.keys())
        }

    def calculate_discounted_fee(self,
                                 trading_pair: str,
                                 order_type: OrderType,
                                 trade_type: TradeType,
                                 amount: Decimal,
                                 price: Decimal,
                                 user_tier: str = "DEFAULT",
                                 is_maker: Optional[bool] = None) -> Dict[str, Any]:
        """
        Calculate fee with user tier discount applied.

        Args:
            trading_pair: Trading pair
            order_type: Order type
            trade_type: Trade type
            amount: Order amount
            price: Order price
            user_tier: User tier level
            is_maker: Whether order is maker

        Returns:
            Dictionary with discounted fee information
        """
        # Calculate base fee
        base_fee_info = self.calculate_fee(trading_pair, order_type, trade_type, amount, price, is_maker)

        # Get discount info
        discount_info = self.get_fee_discount_info(user_tier)

        # Apply discount
        discount_rate = discount_info["discount_rate"]
        original_fee = base_fee_info["fee_amount"]
        discount_amount = original_fee * discount_rate
        final_fee = original_fee - discount_amount

        return {
            **base_fee_info,
            "original_fee": original_fee,
            "discount_rate": discount_rate,
            "discount_amount": discount_amount,
            "final_fee": final_fee,
            "user_tier": user_tier,
            "savings": discount_amount
        }


    @property
    def _rules(self) -> Dict[str, Any]:
        """Alias for _trading_rules for backward compatibility."""
        return self._trading_rules

    def get_trading_rule(self, symbol: str) -> Optional[Any]:
        """
        Get trading rule for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Trading rule or None if not found
        """
        return self._trading_rules.get(symbol)

    def is_symbol_supported(self, symbol: str) -> bool:
        """
        Check if symbol is supported.

        Args:
            symbol: Trading symbol

        Returns:
            True if supported, False otherwise
        """
        return symbol in self._trading_rules

    def get_all_symbols(self) -> List[str]:
        """
        Get all supported symbols.

        Returns:
            List of trading symbols
        """
        return list(self._trading_rules.keys())

    def _parse_lot_size_filter(self, filter_data: Dict[str, Any]) -> tuple:
        """
        Parse LOT_SIZE filter from exchange info.

        Args:
            filter_data: Filter data dictionary

        Returns:
            Tuple of (min_size, max_size, step_size)
        """
        min_qty = Decimal(str(filter_data.get("minQty", "0")))
        max_qty = Decimal(str(filter_data.get("maxQty", "0")))
        step_size = Decimal(str(filter_data.get("stepSize", "0")))
        
        return min_qty, max_qty, step_size

    def _parse_price_filter(self, filter_data: Dict[str, Any]) -> tuple:
        """
        Parse PRICE_FILTER from exchange info.

        Args:
            filter_data: Filter data dictionary

        Returns:
            Tuple of (min_price, max_price, tick_size)
        """
        min_price = Decimal(str(filter_data.get("minPrice", "0")))
        max_price = Decimal(str(filter_data.get("maxPrice", "0")))
        tick_size = Decimal(str(filter_data.get("tickSize", "0")))
        
        return min_price, max_price, tick_size
