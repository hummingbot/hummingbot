"""
Decibel Perpetual Transaction Builder

Builds and submits Aptos on-chain transactions for the Decibel DEX smart contract.
Decibel order placement and cancellation happen via Aptos Entry Function calls,
NOT via REST API POST requests.

The builder uses the ``aptos_sdk`` Python package when available; when it is not
installed it falls back to manual HTTP calls to the Aptos fullnode REST API so
that the connector can still be imported and unit-tested without the SDK.
"""

import asyncio
import time
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

import aiohttp

from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth
from hummingbot.logger import HummingbotLogger


# Aptos module path inside the Decibel package
DECIBEL_MODULE = "market"
PLACE_ORDER_FUNC = "place_order"
CANCEL_ORDER_FUNC = "cancel_order"
CANCEL_ALL_FUNC = "cancel_all_orders"

# Gas parameters (conservative defaults)
DEFAULT_MAX_GAS = 10_000
DEFAULT_GAS_PRICE = 100  # octas per gas unit


class DecibelPerpetualTransactionBuilder:
    """
    Constructs and submits Aptos blockchain transactions for Decibel perpetuals.

    Order flow:
    1. Fetch the sender account sequence number from the fullnode.
    2. Build a BCS-serialised ``EntryFunction`` transaction payload.
    3. Sign with the API wallet Ed25519 private key.
    4. Submit via ``POST /transactions`` on the Aptos fullnode REST API.
    5. Return the transaction hash (used as order ID) and timestamp.
    """

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            import logging
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
        self,
        auth: DecibelPerpetualAuth,
        package_address: str,
        fullnode_url: str,
    ):
        self._auth = auth
        self._package_address = package_address
        self._fullnode_url = fullnode_url

        # Try to import the Aptos SDK; degrade gracefully if unavailable.
        self._sdk_available = False
        try:
            from aptos_sdk.account import Account
            from aptos_sdk.client import RestClient
            from aptos_sdk.transactions import EntryFunction, TransactionArgument
            self._sdk_available = True
        except ImportError:
            self.logger().warning(
                "aptos_sdk not installed. Order placement will use raw HTTP "
                "calls to the Aptos fullnode REST API. Install with: "
                "pip install aptos-sdk"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_account_sequence(self, address: str) -> int:
        """Fetch the current on-chain sequence number for the wallet."""
        async with aiohttp.ClientSession() as session:
            url = f"{self._fullnode_url}/accounts/{address}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                return int(data.get("sequence_number", 0))

    async def _submit_transaction_sdk(
        self,
        function_name: str,
        type_args: list,
        args: list,
    ) -> str:
        """Submit transaction using aptos_sdk (preferred path)."""
        from aptos_sdk.account import Account
        from aptos_sdk.client import RestClient
        from aptos_sdk.transactions import EntryFunction, TransactionArgument, Serializer

        private_key_hex = self._auth.get_private_key()
        if private_key_hex.startswith("0x"):
            private_key_hex = private_key_hex[2:]

        account = Account.load_key(private_key_hex)
        rest_client = RestClient(self._fullnode_url)

        entry_function = EntryFunction.natural(
            f"{self._package_address}::{DECIBEL_MODULE}",
            function_name,
            type_args,
            args,
        )

        txn_hash = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: rest_client.execute_entry_function(account, entry_function),
        )
        return txn_hash

    async def _submit_transaction_raw(
        self,
        function_name: str,
        type_arguments: list,
        arguments: list,
    ) -> str:
        """
        Submit transaction via raw Aptos REST API (fallback when SDK is unavailable).
        Returns the transaction hash.
        """
        sender_address = self._auth.api_wallet_address
        sequence_number = await self._get_account_sequence(sender_address)

        payload: Dict[str, Any] = {
            "type": "entry_function_payload",
            "function": f"{self._package_address}::{DECIBEL_MODULE}::{function_name}",
            "type_arguments": type_arguments,
            "arguments": [str(a) for a in arguments],
        }

        expiration_seconds = int(time.time()) + 600

        txn_request: Dict[str, Any] = {
            "sender": sender_address,
            "sequence_number": str(sequence_number),
            "max_gas_amount": str(DEFAULT_MAX_GAS),
            "gas_unit_price": str(DEFAULT_GAS_PRICE),
            "expiration_timestamp_secs": str(expiration_seconds),
            "payload": payload,
        }

        async with aiohttp.ClientSession() as session:
            # Step 1: Encode the transaction for signing
            encode_url = f"{self._fullnode_url}/transactions/encode_submission"
            async with session.post(
                encode_url,
                json=txn_request,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                signing_message: str = await resp.json()

            # Step 2: Sign the encoded bytes
            private_key_hex = self._auth.get_private_key()
            if private_key_hex.startswith("0x"):
                private_key_hex = private_key_hex[2:]

            try:
                from aptos_sdk.account import Account
                account = Account.load_key(private_key_hex)
                signature_hex = account.sign(bytes.fromhex(signing_message[2:])).hex()
                public_key_hex = account.public_key().hex()
            except ImportError:
                # Pure-python Ed25519 fallback using cryptography library
                try:
                    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
                    private_key_bytes = bytes.fromhex(private_key_hex)
                    pk = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
                    message_bytes = bytes.fromhex(signing_message[2:] if signing_message.startswith("0x") else signing_message)
                    signature_hex = pk.sign(message_bytes).hex()
                    public_key_hex = pk.public_key().public_bytes_raw().hex()
                except Exception:
                    raise RuntimeError(
                        "Cannot sign transaction: install aptos-sdk or cryptography package."
                    )

            # Step 3: Attach signature and submit
            txn_request["signature"] = {
                "type": "ed25519_signature",
                "public_key": "0x" + public_key_hex,
                "signature": "0x" + signature_hex,
            }

            submit_url = f"{self._fullnode_url}/transactions"
            async with session.post(
                submit_url,
                json=txn_request,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                result = await resp.json()
                if resp.status not in (200, 202):
                    raise RuntimeError(f"Transaction submission failed: {result}")
                return result.get("hash", "")

    async def _submit(
        self,
        function_name: str,
        type_arguments: list,
        arguments: list,
    ) -> str:
        """Dispatch to SDK path or raw HTTP path."""
        if self._sdk_available:
            try:
                return await self._submit_transaction_sdk(function_name, type_arguments, arguments)
            except Exception as e:
                self.logger().warning(f"SDK submission failed ({e}), falling back to raw HTTP")

        return await self._submit_transaction_raw(function_name, type_arguments, arguments)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def place_order(
        self,
        market_id: str,
        price: int,
        size: int,
        is_buy: bool,
        is_ioc: bool = False,
        is_post_only: bool = False,
        client_order_id: str = "",
    ) -> Tuple[str, str, float]:
        """
        Place a perpetual order on Decibel via an Aptos transaction.

        :param market_id: Exchange market identifier (e.g. ``"BTC/USD"``).
        :param price: Price in chain units (integer with px_decimals applied).
        :param size: Size in chain units (integer with sz_decimals applied).
        :param is_buy: True for buy/long, False for sell/short.
        :param is_ioc: Immediate-or-cancel flag (simulates market orders).
        :param is_post_only: Post-only/maker-only flag.
        :param client_order_id: Client-assigned order identifier (up to 32 chars).
        :return: Tuple of (tx_hash, exchange_order_id, timestamp_seconds).
        """
        self.logger().info(
            f"Placing {'BUY' if is_buy else 'SELL'} order on {market_id}: "
            f"size={size} price={price} ioc={is_ioc} post_only={is_post_only}"
        )

        arguments = [
            market_id,           # market identifier string
            str(price),          # limit price (chain units)
            str(size),           # order size (chain units)
            str(is_buy).lower(), # direction
            str(is_ioc).lower(), # time-in-force flag
            str(is_post_only).lower(),  # maker-only flag
            client_order_id,     # client order id
        ]

        tx_hash = await self._submit(PLACE_ORDER_FUNC, [], arguments)
        timestamp = time.time()

        # Derive a stable exchange order id from the tx hash
        exchange_order_id = tx_hash if tx_hash else f"local_{int(timestamp * 1000)}"

        self.logger().info(f"Order placed: tx_hash={tx_hash}")
        return tx_hash, exchange_order_id, timestamp

    async def cancel_order(
        self,
        market_id: str,
        order_id: str,
    ) -> Tuple[str, float]:
        """
        Cancel a specific order via an Aptos transaction.

        :param market_id: Exchange market identifier.
        :param order_id: Exchange order ID to cancel.
        :return: Tuple of (tx_hash, timestamp_seconds).
        """
        self.logger().info(f"Cancelling order {order_id} on {market_id}")

        arguments = [market_id, order_id]
        tx_hash = await self._submit(CANCEL_ORDER_FUNC, [], arguments)
        timestamp = time.time()

        self.logger().info(f"Order cancelled: tx_hash={tx_hash}")
        return tx_hash, timestamp

    async def cancel_all_orders(self, market_id: str) -> Tuple[str, float]:
        """
        Cancel all open orders for a market via an Aptos transaction.

        :param market_id: Exchange market identifier.
        :return: Tuple of (tx_hash, timestamp_seconds).
        """
        self.logger().info(f"Cancelling all orders on {market_id}")

        arguments = [market_id]
        tx_hash = await self._submit(CANCEL_ALL_FUNC, [], arguments)
        timestamp = time.time()

        self.logger().info(f"All orders cancelled: tx_hash={tx_hash}")
        return tx_hash, timestamp
