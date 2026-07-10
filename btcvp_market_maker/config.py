"""Configuration loader for BTCvp Market Maker Bot."""

import os
from dataclasses import dataclass
from decimal import Decimal

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # Network
    rpc_url: str = os.getenv("RPC_URL", "https://rpc.pharos.xyz")
    chain_id: int = int(os.getenv("CHAIN_ID", "1672"))
    private_key: str = os.getenv("PRIVATE_KEY", "")

    # Contracts
    router_address: str = os.getenv("ROUTER_ADDRESS", "0xd285e37678f07631f33eb99927eb3ff0591a12d7")
    factory_address: str = os.getenv("FACTORY_ADDRESS", "0x18Fab7d7027E9FB33Fa90ca607439449209F7B09")
    pool_address: str = os.getenv("POOL_ADDRESS", "0x81acc053ca20e75faed94382e297e6bad50c2c2c")
    btcvp_address: str = os.getenv("BTCVP_ADDRESS", "0x79D154287DDC77e5C10127E68c2df1a942a330BB")
    usdc_address: str = os.getenv("USDC_ADDRESS", "0xC879C018dB60520F4355C26eD1a6D572cdAC1815")
    weth_address: str = os.getenv("WETH_ADDRESS", "0x52C48d4213107b20bC583832b0d951FB9CA8F0B0")

    # Token decimals
    btcvp_decimals: int = int(os.getenv("BTCVP_DECIMALS", "8"))
    usdc_decimals: int = int(os.getenv("USDC_DECIMALS", "6"))

    # Price Oracle
    btc_price_url: str = os.getenv("BTC_PRICE_URL", "https://vault.vishwalab.com/rwa/v1/asset/btcvp")

    # Swap Strategy
    swap_price_deviation_threshold: Decimal = Decimal(os.getenv("SWAP_PRICE_DEVIATION_THRESHOLD", "0.005"))
    swap_amount_usdc: Decimal = Decimal(os.getenv("SWAP_AMOUNT_USDC", "100"))
    poll_interval: int = int(os.getenv("POLL_INTERVAL", "30"))

    # LP Strategy
    lp_position_count: int = int(os.getenv("LP_POSITION_COUNT", "3"))
    lp_range_pct: Decimal = Decimal(os.getenv("LP_RANGE_PCT", "0.03"))
    lp_rebalance_threshold: Decimal = Decimal(os.getenv("LP_REBALANCE_THRESHOLD", "0.80"))
    lp_amount_per_position: Decimal = Decimal(os.getenv("LP_AMOUNT_PER_POSITION", "1000"))

    # Trading
    slippage_tolerance: Decimal = Decimal(os.getenv("SLIPPAGE_TOLERANCE", "0.01"))

    # Gas
    gas_price_gwei: int = int(os.getenv("GAS_PRICE_GWEI", "5"))
    gas_limit: int = int(os.getenv("GAS_LIMIT", "500000"))
