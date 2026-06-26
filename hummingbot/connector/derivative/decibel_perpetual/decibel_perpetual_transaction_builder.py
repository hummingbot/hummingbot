"""
Transaction builder for Decibel Perpetual on-chain operations.

Uses Decibel Python SDK for order placement and cancellation.

SDK Return Types:
- place_order(): Returns PlaceOrderSuccess or PlaceOrderFailure (union type)
  - PlaceOrderSuccess: Has `transaction_hash` (str), `order_id` (str | None), `success` (True)
  - PlaceOrderFailure: Has `error` (str), `success` (False)
- cancel_order(): Returns dict[str, Any] - raw Aptos transaction result
  - Success: {"hash": "0x...", "success": True, "gas_used": "...", ...}
  - Failure: Raises ValueError with "Transaction failed: <vm_status>"
"""

import time
from typing import Optional, Tuple

from decibel import MAINNET_CONFIG, TESTNET_CONFIG, BaseSDKOptions, DecibelWriteDex, PlaceOrderFailure, TimeInForce

import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth
from hummingbot.logger import HummingbotLogger


class DecibelPerpetualTransactionBuilder:
    """
    Builds and submits Aptos transactions for Decibel Perpetual operations using Decibel SDK.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: DecibelPerpetualAuth,
        package_address: str,
        fullnode_url: str,
        domain: str = "decibel_perpetual",
        api_key: Optional[str] = None,
        gas_station_api_key: Optional[str] = None,
    ):
        """
        Initialize transaction builder.

        :param auth: Authentication instance
        :param package_address: Decibel package address on Aptos
        :param fullnode_url: Aptos fullnode URL for transaction submission
        :param domain: Domain (mainnet or testnet)
        :param api_key: Geomi API key for node access (required for GasPriceManager)
        :param gas_station_api_key: Optional gas station API key for sponsored transactions
        """
        self._auth = auth
        self._package_address = package_address
        self._fullnode_url = fullnode_url
        self._domain = domain
        self._api_key = api_key
        self._gas_station_api_key = gas_station_api_key
        self._write_dex: Optional[DecibelWriteDex] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            from hummingbot.logger import HummingbotLogger
            cls._logger = HummingbotLogger(__name__)
        return cls._logger

    async def _get_write_dex(self) -> DecibelWriteDex:
        """Get or create Decibel write SDK instance."""
        if self._write_dex is None:
            from dataclasses import replace

            from decibel import GasPriceManager, GasPriceManagerOptions

            base_config = TESTNET_CONFIG if "testnet" in self._domain else MAINNET_CONFIG

            self.logger().debug(f"[GAS_STATION] Initializing SDK with domain: {self._domain}")
            self.logger().debug(f"[GAS_STATION] Base config gas_station_url: {base_config.gas_station_url}")
            self.logger().debug(f"[GAS_STATION] Base config gas_station_api_key: {base_config.gas_station_api_key}")

            # Create a new config with gas_station_api_key
            if self._gas_station_api_key:
                config = replace(base_config, gas_station_api_key=self._gas_station_api_key)
            else:
                config = base_config

            self.logger().debug(f"[GAS_STATION] Final config gas_station_url: {config.gas_station_url}")
            self.logger().debug(f"[GAS_STATION] Final config gas_station_api_key: {'Provided' if config.gas_station_api_key else 'None'}")

            account = self._auth.account

            # Initialize GasPriceManager
            gas = GasPriceManager(
                config,
                opts=GasPriceManagerOptions(node_api_key=self._api_key) if self._api_key else None
            )

            await gas.initialize()

            self._write_dex = DecibelWriteDex(
                config,
                account,
                opts=BaseSDKOptions(gas_price_manager=gas)
            )
        return self._write_dex

    async def place_order(
        self,
        market_id: str,
        price: int,
        size: int,
        is_buy: bool,
        is_ioc: bool = False,
        is_post_only: bool = False,
        client_order_id: Optional[str] = None,
    ) -> Tuple[Optional[str], str, float]:
        """
        Place order on Decibel via Decibel SDK.

        Decibel orders are on-chain transactions. This method:
        1. Builds the order transaction with specified parameters
        2. Signs with the API wallet
        3. Submits to Aptos blockchain
        4. Waits for confirmation
        5. Returns transaction hash and order ID

        Market orders are implemented as IOC (Immediate or Cancel) orders.

        Example:
            >>> tx_hash, order_id, timestamp = await tx_builder.place_order(
            ...     market_id="BTC-USD",
            ...     price=50000000000,  # 50,000 in chain units (px_decimals=6)
            ...     size=1000000,       # 0.001 in chain units (sz_decimals=3)
            ...     is_buy=True,
            ...     time_in_force=TimeInForce.GoodTillCanceled,
            ... )

        :param market_id: Market identifier in BTC-USD format (converted to BTC/USD internally)
        :param price: Price in chain units (price * 10^px_decimals)
        :param size: Size in chain units (size * 10^sz_decimals)
        :param is_buy: True for buy order, False for sell order
        :param is_ioc: If True, order is Immediate or Cancel (used for market orders)
        :param is_post_only: If True, order is maker-only (LIMIT_MAKER)
        :param client_order_id: Optional client order ID for tracking
        :return: Tuple of (transaction_hash, order_id, timestamp)
                 - transaction_hash: Aptos transaction hash (str or None if order_id is used as fallback)
                 - order_id: Decibel order ID (str)
                 - timestamp: Local timestamp when order was placed (float, seconds)
        :raises Exception: If order placement fails (PlaceOrderFailure returned by SDK)
        """
        write_dex = await self._get_write_dex()

        # Convert market_id from BTC-USD to BTC/USD format for SDK
        market_name = market_id.replace("-", "/")

        # Determine time in force based on order type flags
        if is_ioc:
            time_in_force = TimeInForce.ImmediateOrCancel
        elif is_post_only:
            time_in_force = TimeInForce.PostOnly
        else:
            time_in_force = TimeInForce.GoodTillCanceled

        # Get subaccount address (main wallet address for trading)
        subaccount_addr = self._auth.get_subaccount_address(self._package_address)

        # Place order using Decibel SDK with configurable timeouts
        # SDK returns: PlaceOrderSuccess | PlaceOrderFailure
        result = await write_dex.place_order(
            market_name=market_name,
            price=price,
            size=size,
            is_buy=is_buy,
            time_in_force=time_in_force,
            is_reduce_only=False,
            client_order_id=client_order_id,
            subaccount_addr=subaccount_addr,
            txn_submit_timeout=CONSTANTS.DEFAULT_PLACE_ORDER_TIMEOUT_SECS,
            txn_confirm_timeout=CONSTANTS.DEFAULT_PLACE_ORDER_TIMEOUT_SECS,
        )

        timestamp = time.time()

        # Handle SDK result - place_order always returns PlaceOrderSuccess or PlaceOrderFailure
        if isinstance(result, PlaceOrderFailure):
            # Order failed - extract all available error details
            error_msg = getattr(result, 'error', None)
            reason = getattr(result, 'reason', None)
            message = getattr(result, 'message', None)
            success = getattr(result, 'success', None)

            # Log ALL attributes for debugging - SDK sometimes hides details
            attrs = {k: v for k, v in result.__dict__.items() if not k.startswith('_')}
            self.logger().error(f"[ORDER PLACEMENT FAILED] success={success}, error='{error_msg}', reason='{reason}', message='{message}'")
            self.logger().error(f"[ORDER PLACEMENT FAILED] Full attributes: {attrs}")
            self.logger().error(f"[ORDER PLACEMENT FAILED] Result str: {str(result)}")

            # Use most descriptive error message available
            error_detail = reason or message or error_msg or str(result) or "Unknown error (empty error message from SDK)"
            raise IOError(f"Order placement failed: {error_detail}")

        # Success - extract fields from PlaceOrderSuccess (SDK uses snake_case)
        # Fields: success=True, order_id=str|None, transaction_hash=str
        tx_hash = result.transaction_hash
        order_id = result.order_id or tx_hash  # Fallback to tx_hash if order_id is None

        self.logger().info(f"Submitted order transaction: tx_hash={tx_hash}, order_id={order_id}")

        return tx_hash, order_id, timestamp

    async def cancel_order(
        self,
        market_id: str,
        order_id: str,
    ) -> Tuple[Optional[str], float]:
        """
        Cancel order on Decibel via Decibel SDK.

        Order cancellation is an on-chain transaction. This method:
        1. Builds the cancel order transaction
        2. Signs with the API wallet
        3. Submits to Aptos blockchain
        4. Waits for confirmation
        5. Returns the transaction hash

        Note: cancel_order() always returns a dict (raw Aptos transaction result),
        not a typed SDK result like place_order().

        Example:
            >>> tx_hash, timestamp = await tx_builder.cancel_order(
            ...     market_id="BTC-USD",
            ...     order_id="170141599249866106634926395424325500928",
            ... )
            >>> # On success: tx_hash = "0xabc123...", timestamp = 1234567890.123
            >>> # On failure: Raises ValueError("Transaction failed: Move abort...")

        :param market_id: Market identifier in BTC-USD format (converted to BTC/USD internally)
        :param order_id: The Decibel order ID to cancel
        :return: Tuple of (transaction_hash, timestamp)
                 - transaction_hash: Aptos transaction hash (str or None if not available)
                 - timestamp: Local timestamp when cancellation was confirmed (float, seconds)
        :raises ValueError: If transaction fails (e.g., order not found, insufficient gas)
        :raises Exception: For other cancellation errors
        """
        write_dex = await self._get_write_dex()

        # Convert market_id from BTC-USD to BTC/USD format for SDK
        market_name = market_id.replace("-", "/")

        # Get subaccount address (main wallet address for trading)
        subaccount_addr = self._auth.get_subaccount_address(self._package_address)

        # Cancel order using Decibel SDK with configurable timeouts
        # SDK returns: dict[str, Any] - raw Aptos transaction result
        # Success: {"hash": "0x...", "success": True, "gas_used": "...", "version": "..."}
        # Failure: Raises TxnSubmitError (safe to retry) or TxnConfirmError (may be on-chain)
        result = await write_dex.cancel_order(
            market_name=market_name,
            order_id=order_id,
            subaccount_addr=subaccount_addr,
            txn_submit_timeout=CONSTANTS.DEFAULT_CANCEL_ORDER_TIMEOUT_SECS,
            txn_confirm_timeout=CONSTANTS.DEFAULT_CANCEL_ORDER_TIMEOUT_SECS,
        )

        timestamp = time.time()

        # Extract transaction hash from Aptos result dict
        # The 'hash' field contains the transaction hash (not 'tx_hash' or 'transaction_hash')
        tx_hash: Optional[str] = result.get('hash')

        self.logger().info(f"Submitted cancel transaction: tx_hash={tx_hash}")

        return tx_hash, timestamp

    async def close(self):
        """Close the SDK client."""
        if self._write_dex:
            # Decibel SDK doesn't require explicit cleanup
            self._write_dex = None
