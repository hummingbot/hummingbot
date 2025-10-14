"""
Account Data Source for Coins.xyz Exchange.

This module provides comprehensive account data management including:
- Account balance retrieval with multi-asset support
- Balance parsing utilities for Hummingbot format conversion
- Balance caching and update mechanisms
- Account information and trading permissions
"""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS
from hummingbot.connector.exchange.coinsxyz import coinsxyz_utils as utils
from hummingbot.connector.exchange.coinsxyz import coinsxyz_web_utils as web_utils
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.logger import HummingbotLogger


@dataclass
class AccountBalance:
    """Account balance data structure."""
    asset: str
    total_balance: Decimal
    available_balance: Decimal
    locked_balance: Decimal
    last_updated: float


@dataclass
class AccountInfo:
    """Account information data structure."""
    account_id: str
    account_type: str
    trading_enabled: bool
    withdrawal_enabled: bool
    deposit_enabled: bool
    permissions: List[str]
    last_updated: float


class CoinsxyzAccountDataSource:
    """
    Account data source for Coins.xyz exchange.

    Provides comprehensive account data management with:
    - Multi-asset balance retrieval and caching
    - Hummingbot format conversion utilities
    - Account permissions and trading status
    - Real-time balance updates
    - Error handling and retry logic
    """

    def __init__(self,
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        """
        Initialize account data source.

        Args:
            api_factory: Web assistants factory for API requests
            domain: API domain (default or testnet)
        """
        self._api_factory = api_factory
        self._domain = domain
        self._logger = None

        # Balance caching
        self._account_balances: Dict[str, AccountBalance] = {}
        self._balance_cache_timeout = 30.0  # 30 seconds
        self._last_balance_update = 0.0

        # Account information caching
        self._account_info: Optional[AccountInfo] = None
        self._account_info_cache_timeout = 300.0  # 5 minutes
        self._last_account_info_update = 0.0

        # Supported assets cache
        self._supported_assets: Set[str] = set()
        self._assets_cache_timeout = 3600.0  # 1 hour
        self._last_assets_update = 0.0

        # Update locks
        self._balance_update_lock = asyncio.Lock()
        self._account_info_update_lock = asyncio.Lock()

    def logger(self) -> HummingbotLogger:
        """Get logger instance."""
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    async def get_account_balances(self, force_update: bool = False) -> Dict[str, AccountBalance]:
        """
        Get account balances for all assets.

        Args:
            force_update: Force refresh from API even if cache is valid

        Returns:
            Dictionary mapping asset names to AccountBalance objects
        """
        current_time = time.time()

        # Check if cache is valid and not forcing update
        if (not force_update and
            self._account_balances and
                current_time - self._last_balance_update < self._balance_cache_timeout):
            return self._account_balances.copy()

        async with self._balance_update_lock:
            # Double-check after acquiring lock
            if (not force_update and
                self._account_balances and
                    current_time - self._last_balance_update < self._balance_cache_timeout):
                return self._account_balances.copy()

            try:
                # Fetch balances from API
                balances_data = await self._fetch_account_balances()

                # Parse and cache balances
                self._account_balances = self._parse_account_balances(balances_data)
                self._last_balance_update = current_time

                self.logger().info(f"Updated account balances for {len(self._account_balances)} assets")

                return self._account_balances.copy()

            except Exception as e:
                self.logger().error(f"Error fetching account balances: {e}")
                # Return cached balances if available
                return self._account_balances.copy()

    async def get_account_balance(self, asset: str, force_update: bool = False) -> Optional[AccountBalance]:
        """
        Get balance for a specific asset.

        Args:
            asset: Asset symbol (e.g., 'BTC', 'USDT')
            force_update: Force refresh from API

        Returns:
            AccountBalance object or None if asset not found
        """
        balances = await self.get_account_balances(force_update=force_update)
        return balances.get(asset.upper())

    async def get_available_balance(self, asset: str) -> Decimal:
        """
        Get available balance for a specific asset.

        Args:
            asset: Asset symbol

        Returns:
            Available balance as Decimal
        """
        balance = await self.get_account_balance(asset)
        return balance.available_balance if balance else Decimal("0")

    async def get_total_balance(self, asset: str) -> Decimal:
        """
        Get total balance for a specific asset.

        Args:
            asset: Asset symbol

        Returns:
            Total balance as Decimal
        """
        balance = await self.get_account_balance(asset)
        return balance.total_balance if balance else Decimal("0")

    async def get_account_info(self, force_update: bool = False) -> Optional[AccountInfo]:
        """
        Get account information including trading permissions.

        Args:
            force_update: Force refresh from API

        Returns:
            AccountInfo object or None if error
        """
        current_time = time.time()

        # Check if cache is valid and not forcing update
        if (not force_update and
            self._account_info and
                current_time - self._last_account_info_update < self._account_info_cache_timeout):
            return self._account_info

        async with self._account_info_update_lock:
            # Double-check after acquiring lock
            if (not force_update and
                self._account_info and
                    current_time - self._last_account_info_update < self._account_info_cache_timeout):
                return self._account_info

            try:
                # Fetch account info from API
                account_data = await self._fetch_account_info()

                # Parse and cache account info
                self._account_info = self._parse_account_info(account_data)
                self._last_account_info_update = current_time

                self.logger().info(f"Updated account info for account {self._account_info.account_id}")

                return self._account_info

            except Exception as e:
                self.logger().error(f"Error fetching account info: {e}")
                return self._account_info

    async def is_trading_enabled(self) -> bool:
        """
        Check if trading is enabled for the account.

        Returns:
            True if trading is enabled, False otherwise
        """
        account_info = await self.get_account_info()
        return account_info.trading_enabled if account_info else False

    async def get_trading_permissions(self) -> List[str]:
        """
        Get trading permissions for the account.

        Returns:
            List of permission strings
        """
        account_info = await self.get_account_info()
        return account_info.permissions if account_info else []

    async def get_supported_assets(self, force_update: bool = False) -> Set[str]:
        """
        Get list of supported assets for the account.

        Args:
            force_update: Force refresh from API

        Returns:
            Set of supported asset symbols
        """
        current_time = time.time()

        # Check if cache is valid and not forcing update
        if (not force_update and
            self._supported_assets and
                current_time - self._last_assets_update < self._assets_cache_timeout):
            return self._supported_assets.copy()

        try:
            # Get current balances to determine supported assets
            balances = await self.get_account_balances(force_update=True)
            self._supported_assets = set(balances.keys())
            self._last_assets_update = current_time

            return self._supported_assets.copy()

        except Exception as e:
            self.logger().error(f"Error fetching supported assets: {e}")
            return self._supported_assets.copy()

    async def _fetch_account_balances(self) -> Dict[str, Any]:
        """
        Fetch account balances from API.

        Returns:
            Raw balance data from API
        """
        try:
            self.logger().info("Fetching account balances from API...")

            rest_assistant = await self._api_factory.get_rest_assistant()
            url = web_utils.private_rest_url(CONSTANTS.ACCOUNTS_PATH_URL, domain=self._domain)

            self.logger().info(f"Balance API URL: {url}")

            response = await rest_assistant.execute_request(
                url=url,
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.ACCOUNTS_PATH_URL
            )

            self.logger().info(f"Balance API response: {response}")
            return response

        except Exception as e:
            self.logger().error(f"Error fetching account balances: {e}")
            import traceback
            self.logger().error(f"Traceback: {traceback.format_exc()}")
            raise

    async def _fetch_account_info(self) -> Dict[str, Any]:
        """
        Fetch account information from API.

        Returns:
            Raw account info data from API
        """
        rest_assistant = await self._api_factory.get_rest_assistant()

        url = web_utils.private_rest_url(CONSTANTS.ACCOUNT_INFO_PATH_URL, domain=self._domain)

        response = await rest_assistant.execute_request(
            url=url,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.ACCOUNT_INFO_PATH_URL
        )

        return response

    def _parse_account_balances(self, balances_data: Dict[str, Any]) -> Dict[str, AccountBalance]:
        """
        Parse account balances from API response.

        Args:
            balances_data: Raw balance data from API

        Returns:
            Dictionary mapping asset names to AccountBalance objects
        """
        parsed_balances = {}
        current_time = time.time()

        try:
            # Handle different response formats
            if "balances" in balances_data:
                balances_list = balances_data["balances"]
            elif isinstance(balances_data, list):
                balances_list = balances_data
            else:
                balances_list = [balances_data]

            for balance_entry in balances_list:
                asset = balance_entry.get("asset", balance_entry.get("coin", "")).upper()

                if not asset:
                    continue

                # Parse balance amounts
                total_str = balance_entry.get("free", balance_entry.get("total", "0"))
                available_str = balance_entry.get("free", balance_entry.get("available", "0"))
                locked_str = balance_entry.get("locked", balance_entry.get("frozen", "0"))

                try:
                    total_balance = Decimal(str(total_str))
                    available_balance = Decimal(str(available_str))
                    locked_balance = Decimal(str(locked_str))

                    # Calculate total if not provided
                    if total_balance == Decimal("0") and (available_balance > 0 or locked_balance > 0):
                        total_balance = available_balance + locked_balance

                    # Only include assets with non-zero balances
                    if total_balance > Decimal("0"):
                        parsed_balances[asset] = AccountBalance(
                            asset=asset,
                            total_balance=total_balance,
                            available_balance=available_balance,
                            locked_balance=locked_balance,
                            last_updated=current_time
                        )

                except (ValueError, TypeError) as e:
                    self.logger().warning(f"Error parsing balance for {asset}: {e}")
                    continue

        except Exception as e:
            self.logger().error(f"Error parsing account balances: {e}")

        return parsed_balances

    def _parse_account_info(self, account_data: Dict[str, Any]) -> AccountInfo:
        """
        Parse account information from API response.

        Args:
            account_data: Raw account data from API

        Returns:
            AccountInfo object
        """
        current_time = time.time()

        try:
            account_id = account_data.get("accountId", account_data.get("uid", "unknown"))
            account_type = account_data.get("accountType", "SPOT")

            # Parse permissions
            permissions = account_data.get("permissions", [])
            if isinstance(permissions, str):
                permissions = [permissions]

            # Determine trading status
            trading_enabled = "SPOT" in permissions or account_data.get("canTrade", False)
            withdrawal_enabled = "WITHDRAW" in permissions or account_data.get("canWithdraw", False)
            deposit_enabled = "DEPOSIT" in permissions or account_data.get("canDeposit", True)

            return AccountInfo(
                account_id=str(account_id),
                account_type=account_type,
                trading_enabled=trading_enabled,
                withdrawal_enabled=withdrawal_enabled,
                deposit_enabled=deposit_enabled,
                permissions=permissions,
                last_updated=current_time
            )

        except Exception as e:
            self.logger().error(f"Error parsing account info: {e}")
            # Return default account info
            return AccountInfo(
                account_id="unknown",
                account_type="SPOT",
                trading_enabled=False,
                withdrawal_enabled=False,
                deposit_enabled=False,
                permissions=[],
                last_updated=current_time
            )

    def convert_to_hummingbot_format(self, balances: Dict[str, AccountBalance]) -> Dict[str, Dict[str, Decimal]]:
        """
        Convert balances to Hummingbot format.

        Args:
            balances: AccountBalance objects

        Returns:
            Dictionary in Hummingbot format
        """
        hummingbot_balances = {}

        for asset, balance in balances.items():
            hummingbot_balances[asset] = {
                "total": balance.total_balance,
                "available": balance.available_balance,
                "locked": balance.locked_balance
            }

        return hummingbot_balances

    def clear_cache(self):
        """Clear all cached data."""
        self._account_balances.clear()
        self._account_info = None
        self._supported_assets.clear()
        self._last_balance_update = 0.0
        self._last_account_info_update = 0.0
        self._last_assets_update = 0.0

        self.logger().info("Account data cache cleared")

    def get_cache_status(self) -> Dict[str, Any]:
        """
        Get cache status information.

        Returns:
            Dictionary with cache status details
        """
        current_time = time.time()

        return {
            "balances_cached": len(self._account_balances),
            "balances_cache_age": current_time - self._last_balance_update,
            "balances_cache_valid": current_time - self._last_balance_update < self._balance_cache_timeout,
            "account_info_cached": self._account_info is not None,
            "account_info_cache_age": current_time - self._last_account_info_update,
            "account_info_cache_valid": current_time - self._last_account_info_update < self._account_info_cache_timeout,
            "supported_assets_count": len(self._supported_assets),
            "assets_cache_age": current_time - self._last_assets_update,
            "assets_cache_valid": current_time - self._last_assets_update < self._assets_cache_timeout
        }
