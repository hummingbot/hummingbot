"""Uniswap V2 DEX client for FaroSwap on Pharos chain."""

import json
import logging
import os
import time
from decimal import Decimal
from typing import Optional, Tuple

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from .config import Config

logger = logging.getLogger(__name__)

ABI_DIR = os.path.join(os.path.dirname(__file__), "abi")


def load_abi(filename: str) -> list:
    with open(os.path.join(ABI_DIR, filename)) as f:
        return json.load(f)


class DexClient:
    """Client for interacting with FaroSwap (Uniswap V2 fork) on Pharos chain."""

    def __init__(self, config: Config):
        self.config = config
        self.w3 = Web3(Web3.HTTPProvider(config.rpc_url))
        # Add POA middleware for non-mainnet chains
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        self.account = self.w3.eth.account.from_key(config.private_key)
        self.address = self.account.address

        # Load contracts
        self.router = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.router_address),
            abi=load_abi("router_v2.json"),
        )
        self.pair = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.pool_address),
            abi=load_abi("pair_v2.json"),
        )
        self.btcvp_token = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.btcvp_address),
            abi=load_abi("erc20.json"),
        )
        self.usdc_token = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.usdc_address),
            abi=load_abi("erc20.json"),
        )

        # Determine token0 and token1 in the pair
        self._token0: Optional[str] = None
        self._token1: Optional[str] = None

    async def initialize(self):
        """Initialize token order in the pair contract."""
        self._token0 = self.pair.functions.token0().call()
        self._token1 = self.pair.functions.token1().call()
        logger.info(f"Pair token0: {self._token0}, token1: {self._token1}")
        logger.info(f"Wallet address: {self.address}")

        # Check and set allowances
        await self._ensure_allowances()

    async def _ensure_allowances(self):
        """Ensure router has sufficient token allowances."""
        max_uint = 2**256 - 1
        router_addr = Web3.to_checksum_address(self.config.router_address)

        for token, name in [(self.btcvp_token, "BTCvp"), (self.usdc_token, "USDC")]:
            allowance = token.functions.allowance(self.address, router_addr).call()
            if allowance < max_uint // 2:
                logger.info(f"Approving {name} for router...")
                tx = token.functions.approve(router_addr, max_uint).build_transaction(
                    self._build_tx_params()
                )
                self._send_transaction(tx)
                logger.info(f"{name} approved for router")

    def get_reserves(self) -> Tuple[int, int]:
        """Get pool reserves. Returns (btcvp_reserve, usdc_reserve)."""
        reserve0, reserve1, _ = self.pair.functions.getReserves().call()
        btcvp_addr = Web3.to_checksum_address(self.config.btcvp_address)

        if self._token0 and self._token0.lower() == btcvp_addr.lower():
            return reserve0, reserve1
        else:
            return reserve1, reserve0

    def get_pool_price(self) -> Decimal:
        """Get current pool price of BTCvp in USDC terms.
        
        Price = (usdc_reserve / 10^usdc_decimals) / (btcvp_reserve / 10^btcvp_decimals)
        """
        btcvp_reserve, usdc_reserve = self.get_reserves()
        if btcvp_reserve == 0:
            return Decimal("0")

        btcvp_amount = Decimal(btcvp_reserve) / Decimal(10 ** self.config.btcvp_decimals)
        usdc_amount = Decimal(usdc_reserve) / Decimal(10 ** self.config.usdc_decimals)
        return usdc_amount / btcvp_amount

    def get_lp_balance(self) -> int:
        """Get LP token balance of our wallet."""
        return self.pair.functions.balanceOf(self.address).call()

    def get_lp_total_supply(self) -> int:
        """Get total LP token supply."""
        return self.pair.functions.totalSupply().call()

    def get_position_ratio(self) -> Tuple[Decimal, Decimal]:
        """Get our share of pool reserves.
        
        Returns (btcvp_share, usdc_share) in human-readable amounts.
        """
        lp_balance = self.get_lp_balance()
        total_supply = self.get_lp_total_supply()
        if total_supply == 0:
            return Decimal("0"), Decimal("0")

        btcvp_reserve, usdc_reserve = self.get_reserves()
        share = Decimal(lp_balance) / Decimal(total_supply)

        btcvp_share = share * Decimal(btcvp_reserve) / Decimal(10 ** self.config.btcvp_decimals)
        usdc_share = share * Decimal(usdc_reserve) / Decimal(10 ** self.config.usdc_decimals)
        return btcvp_share, usdc_share

    def swap_exact_tokens(self, token_in: str, token_out: str, amount_in: int, min_amount_out: int) -> dict:
        """Execute a swap on the DEX.
        
        Args:
            token_in: Address of input token
            token_out: Address of output token
            amount_in: Amount of input token (in wei/raw units)
            min_amount_out: Minimum output amount (slippage protection)
        """
        deadline = int(time.time()) + 300  # 5 min deadline
        path = [
            Web3.to_checksum_address(token_in),
            Web3.to_checksum_address(token_out),
        ]

        tx = self.router.functions.swapExactTokensForTokens(
            amount_in,
            min_amount_out,
            path,
            self.address,
            deadline,
        ).build_transaction(self._build_tx_params())

        return self._send_transaction(tx)

    def add_liquidity(
        self,
        btcvp_amount: int,
        usdc_amount: int,
        btcvp_min: int,
        usdc_min: int,
    ) -> dict:
        """Add liquidity to the pool.
        
        Args:
            btcvp_amount: Desired amount of BTCvp (raw units)
            usdc_amount: Desired amount of USDC (raw units)
            btcvp_min: Minimum BTCvp amount (slippage protection)
            usdc_min: Minimum USDC amount (slippage protection)
        """
        deadline = int(time.time()) + 300

        tx = self.router.functions.addLiquidity(
            Web3.to_checksum_address(self.config.btcvp_address),
            Web3.to_checksum_address(self.config.usdc_address),
            btcvp_amount,
            usdc_amount,
            btcvp_min,
            usdc_min,
            self.address,
            deadline,
        ).build_transaction(self._build_tx_params())

        return self._send_transaction(tx)

    def remove_liquidity(self, lp_amount: int, btcvp_min: int, usdc_min: int) -> dict:
        """Remove liquidity from the pool.
        
        Args:
            lp_amount: Amount of LP tokens to burn
            btcvp_min: Minimum BTCvp to receive
            usdc_min: Minimum USDC to receive
        """
        # Approve pair token to router if needed
        router_addr = Web3.to_checksum_address(self.config.router_address)
        allowance = self.pair.functions.allowance(self.address, router_addr).call()
        if allowance < lp_amount:
            tx = self.pair.functions.approve(router_addr, 2**256 - 1).build_transaction(
                self._build_tx_params()
            )
            self._send_transaction(tx)

        deadline = int(time.time()) + 300

        tx = self.router.functions.removeLiquidity(
            Web3.to_checksum_address(self.config.btcvp_address),
            Web3.to_checksum_address(self.config.usdc_address),
            lp_amount,
            btcvp_min,
            usdc_min,
            self.address,
            deadline,
        ).build_transaction(self._build_tx_params())

        return self._send_transaction(tx)

    def get_amounts_out(self, amount_in: int, path: list) -> list:
        """Get expected output amounts for a given input."""
        checksum_path = [Web3.to_checksum_address(addr) for addr in path]
        return self.router.functions.getAmountsOut(amount_in, checksum_path).call()

    def get_token_balance(self, token: str) -> int:
        """Get balance of a token in our wallet."""
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(token),
            abi=load_abi("erc20.json"),
        )
        return contract.functions.balanceOf(self.address).call()

    def _build_tx_params(self) -> dict:
        return {
            "from": self.address,
            "nonce": self.w3.eth.get_transaction_count(self.address),
            "gas": self.config.gas_limit,
            "gasPrice": self.w3.to_wei(self.config.gas_price_gwei, "gwei"),
            "chainId": self.config.chain_id,
        }

    def _send_transaction(self, tx: dict) -> dict:
        """Sign and send a transaction, wait for receipt."""
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.config.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logger.info(f"Transaction sent: {tx_hash.hex()}")
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt["status"] != 1:
            raise Exception(f"Transaction failed: {tx_hash.hex()}")
        logger.info(f"Transaction confirmed: {tx_hash.hex()}, gas used: {receipt['gasUsed']}")
        return receipt
