"""
Balance Parsing Utilities for Coins.xyz Exchange.

This module provides comprehensive balance parsing and conversion utilities
for seamless integration with Hummingbot's balance management system.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from hummingbot.logger import HummingbotLogger


class CoinsxyzBalanceUtils:
    """
    Balance parsing and conversion utilities for Coins.xyz exchange.

    Provides comprehensive utilities for:
    - Balance data parsing from various API response formats
    - Conversion to Hummingbot standard format
    - Balance validation and error handling
    - Multi-asset balance aggregation
    - Balance change detection and tracking
    """

    def __init__(self):
        """Initialize balance utilities."""
        self._logger = None

    def logger(self) -> HummingbotLogger:
        """Get logger instance."""
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    def parse_balance_response(self, response_data: Dict[str, Any]) -> Dict[str, Dict[str, Decimal]]:
        """
        Parse balance response from Coins.xyz API into Hummingbot format.

        Args:
            response_data: Raw balance response from API

        Returns:
            Dictionary mapping asset symbols to balance dictionaries
            Format: {asset: {"total": Decimal, "available": Decimal, "locked": Decimal}}
        """
        try:
            parsed_balances = {}

            # Handle different response formats
            balances_data = self._extract_balances_data(response_data)

            for balance_entry in balances_data:
                asset_balance = self._parse_single_balance(balance_entry)
                if asset_balance:
                    asset, balance_dict = asset_balance
                    parsed_balances[asset] = balance_dict

            self.logger().debug(f"Parsed {len(parsed_balances)} asset balances")
            return parsed_balances

        except Exception as e:
            self.logger().error(f"Error parsing balance response: {e}")
            return {}

    def _extract_balances_data(self, response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract balances data from various response formats.

        Args:
            response_data: Raw API response

        Returns:
            List of balance entries
        """
        # Handle different response structures
        if "balances" in response_data:
            return response_data["balances"]
        elif "data" in response_data and isinstance(response_data["data"], list):
            return response_data["data"]
        elif "data" in response_data and "balances" in response_data["data"]:
            return response_data["data"]["balances"]
        elif isinstance(response_data, list):
            return response_data
        elif "asset" in response_data or "coin" in response_data:
            # Single balance entry
            return [response_data]
        else:
            self.logger().warning(f"Unknown balance response format: {response_data}")
            return []

    def _parse_single_balance(self, balance_entry: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Decimal]]]:
        """
        Parse a single balance entry.

        Args:
            balance_entry: Single balance entry from API

        Returns:
            Tuple of (asset_symbol, balance_dict) or None if parsing fails
        """
        try:
            # Extract asset symbol
            asset = self._extract_asset_symbol(balance_entry)
            if not asset:
                return None

            # Extract balance amounts
            total_balance = self._extract_balance_amount(balance_entry, "total")
            available_balance = self._extract_balance_amount(balance_entry, "available")
            locked_balance = self._extract_balance_amount(balance_entry, "locked")

            # Validate and adjust balances
            total_balance, available_balance, locked_balance = self._validate_balance_amounts(
                total_balance, available_balance, locked_balance
            )

            # Only return non-zero balances
            if total_balance > Decimal("0"):
                balance_dict = {
                    "total": total_balance,
                    "available": available_balance,
                    "locked": locked_balance
                }
                return asset, balance_dict

            return None

        except Exception as e:
            self.logger().warning(f"Error parsing balance entry {balance_entry}: {e}")
            return None

    def _extract_asset_symbol(self, balance_entry: Dict[str, Any]) -> Optional[str]:
        """
        Extract asset symbol from balance entry.

        Args:
            balance_entry: Balance entry data

        Returns:
            Asset symbol or None if not found
        """
        # Try different field names for asset symbol
        asset_fields = ["asset", "coin", "currency", "symbol", "token"]

        for field in asset_fields:
            if field in balance_entry:
                asset = str(balance_entry[field]).upper().strip()
                if asset:
                    return asset

        return None

    def _extract_balance_amount(self, balance_entry: Dict[str, Any], balance_type: str) -> Decimal:
        """
        Extract balance amount from balance entry.

        Args:
            balance_entry: Balance entry data
            balance_type: Type of balance ("total", "available", "locked")

        Returns:
            Balance amount as Decimal
        """
        # Define field mappings for different balance types
        field_mappings = {
            "total": ["total", "balance", "totalBalance", "wallet_balance"],
            "available": ["free", "available", "availableBalance", "available_balance"],
            "locked": ["locked", "frozen", "lockedBalance", "locked_balance", "used"]
        }

        fields = field_mappings.get(balance_type, [balance_type])

        for field in fields:
            if field in balance_entry:
                try:
                    amount_str = str(balance_entry[field])
                    return Decimal(amount_str) if amount_str else Decimal("0")
                except (ValueError, TypeError):
                    continue

        return Decimal("0")

    def _validate_balance_amounts(self,
                                  total: Decimal,
                                  available: Decimal,
                                  locked: Decimal) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Validate and adjust balance amounts for consistency.

        Args:
            total: Total balance
            available: Available balance
            locked: Locked balance

        Returns:
            Tuple of validated (total, available, locked) balances
        """
        # Ensure all amounts are non-negative
        total = max(total, Decimal("0"))
        available = max(available, Decimal("0"))
        locked = max(locked, Decimal("0"))

        # Calculate total from available + locked (this is the correct total)
        calculated_total = available + locked

        if total == Decimal("0") and calculated_total > Decimal("0"):
            # Total not provided, calculate from available + locked
            total = calculated_total
        elif total > Decimal("0") and calculated_total == Decimal("0"):
            # Only total provided, assume all is available
            available = total
            locked = Decimal("0")
            total = available  # Recalculate total
        elif abs(total - calculated_total) > Decimal("0.00000001"):
            # Inconsistent amounts, use calculated total (free + locked)
            self.logger().warning(
                f"Inconsistent balance amounts: total={total}, "
                f"available={available}, locked={locked}, calculated_total={calculated_total}"
            )
            # Always use calculated total (free + locked) as the source of truth
            total = calculated_total

        return total, available, locked

    def convert_to_hummingbot_format(self,
                                     balances: Dict[str, Any],
                                     include_zero_balances: bool = False) -> Dict[str, Dict[str, Decimal]]:
        """
        Convert balances to Hummingbot standard format.

        Args:
            balances: Raw balance data or parsed balance objects
            include_zero_balances: Whether to include assets with zero balance

        Returns:
            Dictionary in Hummingbot format
        """
        if not balances:
            return {}

        # If already in correct format, validate and return
        if self._is_hummingbot_format(balances):
            return self._filter_balances(balances, include_zero_balances)

        # Parse raw balance data
        parsed_balances = self.parse_balance_response(balances)
        return self._filter_balances(parsed_balances, include_zero_balances)

    def _is_hummingbot_format(self, balances: Dict[str, Any]) -> bool:
        """
        Check if balances are already in Hummingbot format.

        Args:
            balances: Balance data to check

        Returns:
            True if in Hummingbot format, False otherwise
        """
        if not isinstance(balances, dict):
            return False

        # Check a sample entry
        for asset, balance_data in balances.items():
            if isinstance(balance_data, dict):
                required_keys = {"total", "available", "locked"}
                if required_keys.issubset(balance_data.keys()):
                    return True
            break

        return False

    def _filter_balances(self,
                         balances: Dict[str, Dict[str, Decimal]],
                         include_zero_balances: bool) -> Dict[str, Dict[str, Decimal]]:
        """
        Filter balances based on zero balance inclusion preference.

        Args:
            balances: Parsed balances
            include_zero_balances: Whether to include zero balances

        Returns:
            Filtered balances
        """
        if include_zero_balances:
            return balances

        return {
            asset: balance_data
            for asset, balance_data in balances.items()
            if balance_data.get("total", Decimal("0")) > Decimal("0")
        }

    def calculate_balance_changes(self,
                                  old_balances: Dict[str, Dict[str, Decimal]],
                                  new_balances: Dict[str, Dict[str, Decimal]]) -> Dict[str, Dict[str, Decimal]]:
        """
        Calculate balance changes between two balance snapshots.

        Args:
            old_balances: Previous balance snapshot
            new_balances: Current balance snapshot

        Returns:
            Dictionary of balance changes
        """
        changes = {}

        # Get all assets from both snapshots
        all_assets = set(old_balances.keys()) | set(new_balances.keys())

        for asset in all_assets:
            old_balance = old_balances.get(asset, {"total": Decimal("0"), "available": Decimal("0"), "locked": Decimal("0")})
            new_balance = new_balances.get(asset, {"total": Decimal("0"), "available": Decimal("0"), "locked": Decimal("0")})

            # Calculate changes
            total_change = new_balance["total"] - old_balance["total"]
            available_change = new_balance["available"] - old_balance["available"]
            locked_change = new_balance["locked"] - old_balance["locked"]

            # Only include assets with changes
            if any(change != Decimal("0") for change in [total_change, available_change, locked_change]):
                changes[asset] = {
                    "total": total_change,
                    "available": available_change,
                    "locked": locked_change
                }

        return changes

    def aggregate_balances(self, balance_sources: List[Dict[str, Dict[str, Decimal]]]) -> Dict[str, Dict[str, Decimal]]:
        """
        Aggregate balances from multiple sources.

        Args:
            balance_sources: List of balance dictionaries to aggregate

        Returns:
            Aggregated balance dictionary
        """
        aggregated = {}

        for balance_source in balance_sources:
            for asset, balance_data in balance_source.items():
                if asset not in aggregated:
                    aggregated[asset] = {
                        "total": Decimal("0"),
                        "available": Decimal("0"),
                        "locked": Decimal("0")
                    }

                # Add balances
                aggregated[asset]["total"] += balance_data.get("total", Decimal("0"))
                aggregated[asset]["available"] += balance_data.get("available", Decimal("0"))
                aggregated[asset]["locked"] += balance_data.get("locked", Decimal("0"))

        return aggregated

    def validate_balance_consistency(self, balances: Dict[str, Dict[str, Decimal]]) -> List[str]:
        """
        Validate balance consistency and return list of issues.

        Args:
            balances: Balance dictionary to validate

        Returns:
            List of validation error messages
        """
        issues = []

        for asset, balance_data in balances.items():
            try:
                total = balance_data.get("total", Decimal("0"))
                available = balance_data.get("available", Decimal("0"))
                locked = balance_data.get("locked", Decimal("0"))

                # Check for negative balances
                if total < Decimal("0"):
                    issues.append(f"{asset}: Negative total balance ({total})")
                if available < Decimal("0"):
                    issues.append(f"{asset}: Negative available balance ({available})")
                if locked < Decimal("0"):
                    issues.append(f"{asset}: Negative locked balance ({locked})")

                # Check balance consistency
                calculated_total = available + locked
                if abs(total - calculated_total) > Decimal("0.00000001"):
                    issues.append(
                        f"{asset}: Inconsistent balances - "
                        f"total: {total}, available: {available}, locked: {locked}, "
                        f"calculated total: {calculated_total}"
                    )

            except Exception as e:
                issues.append(f"{asset}: Error validating balance - {e}")

        return issues

    def format_balance_for_display(self,
                                   asset: str = None,
                                   balance_data: Dict[str, Decimal] = None,
                                   precision: int = 8) -> str:
        """
        Format balance data for display purposes.

        Args:
            asset: Asset symbol (or Decimal value for simple formatting)
            balance_data: Balance data dictionary (optional)
            precision: Decimal precision for display

        Returns:
            Formatted balance string
        """
        # Handle simple case: format_balance_for_display(Decimal_value, precision=X)
        if isinstance(asset, Decimal) and balance_data is None:
            balance_value = asset
            # Format with specified precision and remove trailing zeros
            formatted = f"{balance_value:.{precision}f}"
            # Remove trailing zeros after decimal point
            if '.' in formatted:
                formatted = formatted.rstrip('0').rstrip('.')
                # Ensure we have the right number of decimal places
                if '.' in formatted:
                    decimal_part = formatted.split('.')[1]
                    if len(decimal_part) < precision:
                        formatted = f"{balance_value:.{precision}f}"
            return formatted
        
        # Handle full case: format_balance_for_display(asset, balance_data, precision)
        if balance_data is not None:
            total = balance_data.get("total", Decimal("0"))
            available = balance_data.get("available", Decimal("0"))
            locked = balance_data.get("locked", Decimal("0"))

            return (
                f"{asset}: Total={total:.{precision}f}, "
                f"Available={available:.{precision}f}, "
                f"Locked={locked:.{precision}f}"
            )
        
        # Fallback
        return str(asset)

    def calculate_total_balance(self, free_balance: Decimal, locked_balance: Decimal) -> Decimal:
        """
        Calculate total balance from free and locked amounts.

        Args:
            free_balance: Free/available balance
            locked_balance: Locked balance

        Returns:
            Total balance
        """
        return free_balance + locked_balance

    def validate_balance_data(self, balance_data: Dict[str, Any]) -> bool:
        """
        Validate balance data structure.

        Args:
            balance_data: Balance data to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Check required fields
            if "asset" not in balance_data:
                return False

            # Check that at least one numeric field is present
            has_numeric_field = False
            
            # Check numeric fields
            for field in ["free", "locked", "total"]:
                if field in balance_data:
                    has_numeric_field = True
                    try:
                        value = Decimal(str(balance_data[field]))
                        if value < 0:
                            return False
                    except (ValueError, TypeError):
                        return False

            # Require at least one numeric field
            if not has_numeric_field:
                return False

            return True

        except Exception:
            return False