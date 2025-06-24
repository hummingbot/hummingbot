"""
Test utilities for Gateway connector tests.
Provides mock classes, fixtures, and helper functions.
"""
import asyncio
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState


class MockGatewayHTTPClient:
    """Mock Gateway HTTP client for testing"""

    def __init__(self):
        self.api_request = AsyncMock()
        self._config = {
            "solana": {
                "defaultComputeUnits": 200000,
                "gasEstimateInterval": 60,
                "maxFee": 0.01,
                "minFee": 0.0001,
                "retryCount": 3,
                "retryFeeMultiplier": 2.0,
                "retryInterval": 0.1
            },
            "ethereum": {
                "gasEstimateInterval": 60,
                "maxFee": 100,  # Gwei
                "minFee": 1,    # Gwei
                "retryCount": 3,
                "retryFeeMultiplier": 1.5,
                "retryInterval": 0.1
            }
        }
        self._wallets = {
            "solana": [
                {
                    "walletAddresses": ["7B2UBtod3aH7nBCNhdMCVsXjHt8mcDmQxP6EfJfXEipG"],
                    "chain": "solana"
                }
            ],
            "ethereum": [
                {
                    "walletAddresses": ["0x742d35Cc6634C0532925a3b844Bc8e6e1c3E3dE8"],
                    "chain": "ethereum"
                }
            ]
        }
        self.current_timestamp = time.time()

    async def ping_gateway(self) -> bool:
        """Mock ping gateway"""
        return True

    async def get_configuration(self, chain: str) -> Dict[str, Any]:
        """Mock get configuration"""
        return self._config.get(chain, {})

    async def get_wallets(self, chain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Mock get wallets"""
        if chain:
            return self._wallets.get(chain, [])
        # Return all wallets
        all_wallets = []
        for chain_wallets in self._wallets.values():
            all_wallets.extend(chain_wallets)
        return all_wallets

    async def add_wallet(self, chain: str, private_key: str) -> Dict[str, Any]:
        """Mock add wallet"""
        # Generate a mock address from private key
        if chain == "solana":
            address = "New" + private_key[:40] + "Sol"
        else:
            address = "0xNew" + private_key[:38]

        wallet = {
            "walletAddresses": [address],
            "chain": chain
        }

        if chain not in self._wallets:
            self._wallets[chain] = []
        self._wallets[chain].append(wallet)

        return {"address": address, "chain": chain}

    async def remove_wallet(self, chain: str, address: str) -> Dict[str, Any]:
        """Mock remove wallet"""
        if chain in self._wallets:
            self._wallets[chain] = [
                w for w in self._wallets[chain]
                if address not in w.get("walletAddresses", [])
            ]
        return {"success": True}

    async def get_balances(self, chain: str, network: str, wallet_address: str,
                           token_symbols: List[str]) -> Dict[str, Any]:
        """Mock get balances"""
        # Return mock balances in gateway format
        balances = {}
        # Map of chain to native token
        native_tokens = {
            "solana": "SOL",
            "ethereum": "ETH",
            "polygon": "MATIC"
        }
        native_token = native_tokens.get(chain.lower())

        for token in token_symbols:
            if token == native_token:  # Native token
                balances[token] = "10.5"
            else:
                balances[token] = "1000.0"
        return {"balances": balances}

    async def get_allowances(self, chain: str, network: str, wallet_address: str,
                             token_symbols: List[str], spender: str, fail_silently: bool = True) -> Dict[str, Any]:
        """Mock get allowances"""
        approvals = {}
        for token in token_symbols:
            # Return varying allowances for testing
            if token.upper() == "USDC":
                approvals[token] = "999999999"  # Unlimited
            elif token.upper() == "USDT":
                approvals[token] = "1000000"    # Limited
            else:
                approvals[token] = "0"          # No allowance
        return {"approvals": approvals}

    async def approve_token(self, chain: str, network: str, wallet_address: str,
                            token: str, spender: str, amount: Decimal) -> Dict[str, Any]:
        """Mock approve token"""
        return {
            "signature": "mockApproveTx123",
            "status": 1,
            "confirmed": True
        }

    async def estimate_gas(self, chain: str, network: str) -> Dict[str, Any]:
        """Mock estimate gas"""
        if chain == "solana":
            return {
                "feePerComputeUnit": 1000,  # microlamports per CU
                "denomination": "microlamports",
                "timestamp": self.current_timestamp
            }
        else:
            return {
                "gasPrice": 50,  # Gwei
                "denomination": "gwei",
                "timestamp": self.current_timestamp
            }

    async def get_chains(self) -> List[Dict[str, Any]]:
        """Mock get chains"""
        return [
            {"chain": "solana", "networks": ["mainnet-beta", "devnet"]},
            {"chain": "ethereum", "networks": ["mainnet", "testnet"]},
            {"chain": "polygon", "networks": ["mainnet", "testnet"]}
        ]

    async def get_connectors(self) -> Dict[str, Any]:
        """Mock get connectors"""
        return {
            "connectors": [
                {"name": "uniswap", "chain": "ethereum", "networks": ["mainnet", "testnet"], "trading_types": ["swap"]},
                {"name": "pancakeswap", "chain": "bsc", "networks": ["mainnet"], "trading_types": ["swap"]},
                {"name": "raydium", "chain": "solana", "networks": ["mainnet-beta"], "trading_types": ["swap"]}
            ]
        }

    async def get_tokens(self, chain: str, network: str, fail_silently: bool = True) -> Dict[str, Any]:
        """Mock get tokens"""
        if chain.lower() == "solana":
            return {
                "tokens": [
                    {"symbol": "SOL", "address": "11111111111111111111111111111111", "decimals": 9},
                    {"symbol": "USDC", "address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "decimals": 6},
                    {"symbol": "RAY", "address": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R", "decimals": 6},
                    {"symbol": "ORCA", "address": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE", "decimals": 6}
                ]
            }
        elif chain.lower() == "ethereum":
            return {
                "tokens": [
                    {"symbol": "ETH", "address": "0x0000000000000000000000000000000000000000", "decimals": 18},
                    {"symbol": "USDC", "address": "0xA0b86a33E6C8d3b2b9D8C5E6A8B2D8", "decimals": 6},
                    {"symbol": "USDT", "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7", "decimals": 6},
                    {"symbol": "DAI", "address": "0x6B175474E89094C44Da98b954EedeAC495271d0F", "decimals": 18}
                ]
            }
        else:
            return {
                "tokens": [
                    {"symbol": "MATIC", "address": "0x0000000000000000000000000000000000001010", "decimals": 18},
                    {"symbol": "USDC", "address": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", "decimals": 6}
                ]
            }

    async def api_request(self, method: str, endpoint: str, params: Dict[str, Any] = None, fail_silently: bool = True) -> Dict[str, Any]:
        """Mock API request"""
        if endpoint == "chains":
            return {
                "chains": [
                    {"chain": "solana", "networks": ["mainnet-beta", "devnet"]},
                    {"chain": "ethereum", "networks": ["mainnet", "testnet"]}
                ]
            }
        elif endpoint == "connectors":
            return await self.get_connectors()
        return {"success": True}

    async def chain_request(self, method: str, chain: str, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Mock chain request"""
        if endpoint == "chain/tokens" or endpoint == "tokens":
            network = params.get("network", "mainnet")
            return await self.get_tokens(chain, network)
        return {"success": True}


class MockGatewayConnector:
    """Mock Gateway connector base for testing"""

    def __init__(self, connector_name: str, chain: str, network: str):
        self.connector_name = connector_name
        self.chain = chain
        self.network = network
        self._in_flight_orders = {}
        self._gateway_instance = MockGatewayHTTPClient()
        self._order_id_counter = 0
        self._wallet_cache = None
        self._wallet_cache_timestamp = 0
        self._wallet_cache_ttl = 300  # 5 minutes
        self.logger = Mock()

    @property
    def name(self) -> str:
        return f"{self.connector_name}_{self.chain}_{self.network}"

    async def get_wallet_for_chain(self) -> str:
        """Get wallet address for this chain from gateway."""
        current_time = time.time()

        # Check cache
        if self._wallet_cache and (current_time - self._wallet_cache_timestamp) < self._wallet_cache_ttl:
            return self._wallet_cache

        # Fetch from gateway
        wallets = await self._gateway_instance.get_wallets(self.chain)
        if not wallets or not wallets[0].get("walletAddresses"):
            raise ValueError(f"No wallet found for chain {self.chain}")

        wallet_address = wallets[0]["walletAddresses"][0]
        self._wallet_cache = wallet_address
        self._wallet_cache_timestamp = current_time
        return wallet_address

    def create_market_order_id(self, side: TradeType, trading_pair: str) -> str:
        """Create a unique order ID"""
        self._order_id_counter += 1
        return f"order_{self._order_id_counter}_{side.name.lower()}_{trading_pair}"

    def start_tracking_order(self, order_id: str, trading_pair: str, trade_type: TradeType,
                             price: Decimal = None, amount: Decimal = None) -> InFlightOrder:
        """Start tracking an order"""
        order = InFlightOrder(
            client_order_id=order_id,
            trading_pair=trading_pair,
            order_type=OrderType.MARKET,
            trade_type=trade_type,
            price=price or Decimal("0"),
            amount=amount or Decimal("0"),
            creation_timestamp=time.time(),
            initial_state=OrderState.PENDING_CREATE
        )
        self._in_flight_orders[order_id] = order
        return order


class MockGatewaySwap(MockGatewayConnector):
    """Mock Gateway swap connector for testing"""

    async def get_quote_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        """Mock get quote price"""
        # Simple mock pricing
        base_price = Decimal("100.0")
        if is_buy:
            return base_price * Decimal("1.01")  # 1% higher for buys
        else:
            return base_price * Decimal("0.99")  # 1% lower for sells

    def place_order(self, is_buy: bool, trading_pair: str, amount: Decimal, price: Decimal) -> str:
        """Mock place order"""
        trade_type = TradeType.BUY if is_buy else TradeType.SELL
        order_id = self.create_market_order_id(trade_type, trading_pair)
        self.start_tracking_order(order_id, trading_pair, trade_type, price, amount)
        return order_id


class MockGatewayLP(MockGatewayConnector):
    """Mock Gateway LP connector for testing"""

    async def open_position(self, trading_pair: str, lower_price: Decimal, upper_price: Decimal,
                            base_amount: Decimal = None, quote_amount: Decimal = None) -> Dict[str, Any]:
        """Mock open position"""
        position_id = f"position_{int(time.time())}"
        return {
            "positionAddress": position_id,
            "lowerPrice": float(lower_price),
            "upperPrice": float(upper_price),
            "baseAmount": float(base_amount) if base_amount else 0,
            "quoteAmount": float(quote_amount) if quote_amount else 0
        }

    async def close_position(self, position_id: str) -> Dict[str, Any]:
        """Mock close position"""
        return {
            "success": True,
            "baseAmount": 100.0,
            "quoteAmount": 10.0
        }

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Mock get positions"""
        return [
            {
                "positionAddress": "position_123",
                "lowerPrice": 90.0,
                "upperPrice": 110.0,
                "baseAmount": 100.0,
                "quoteAmount": 10.0,
                "uncollectedFees": {"base": 0.1, "quote": 0.01}
            }
        ]


class TestDataFactory:
    """Factory for creating test data"""

    @staticmethod
    def create_trade_fill_event(order_id: str, trading_pair: str, trade_type: TradeType,
                                price: Decimal, amount: Decimal):
        """Create a mock trade fill event"""
        return Mock(
            order_id=order_id,
            trading_pair=trading_pair,
            trade_type=trade_type,
            price=price,
            amount=amount,
            timestamp=time.time()
        )

    @staticmethod
    def create_order_cancelled_event(order_id: str):
        """Create a mock order cancelled event"""
        return Mock(
            order_id=order_id,
            timestamp=time.time()
        )

    @staticmethod
    def create_order_failure_event(order_id: str, reason: str):
        """Create a mock order failure event"""
        return Mock(
            order_id=order_id,
            reason=reason,
            timestamp=time.time()
        )


# Test wallet addresses
TEST_WALLETS = {
    "solana": {
        "address": "7B2UBtod3aH7nBCNhdMCVsXjHt8mcDmQxP6EfJfXEipG",
        "private_key": "5JcHW3bXxVPfKLmPCCaAi1CSZqnpZRxGYKwNDhTCvMcP3Lr4VQKVtUYFSVVJqEEuZGhNXDvkXJyKGYqCidEKmdfAhe3V"  # noqa: mock
    },
    "ethereum": {
        "address": "0x742d35Cc6634C0532925a3b844Bc8e6e1c3E3dE8",
        "private_key": "0x4c0883a69102937d6231471b5dbb6204fe512961708279fbbee1c5d8c8a43b5d"  # noqa: mock
    },
    "polygon": {
        "address": "0x9fB2C52b4B1B3f29e3e5e095f8f92C94cD31A2a7",
        "private_key": "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"  # noqa: mock
    }
}

# Test trading pairs
TEST_TRADING_PAIRS = {
    "solana": ["SOL-USDC", "RAY-USDC", "ORCA-SOL"],
    "ethereum": ["WETH-USDC", "WETH-DAI", "UNI-WETH"],
    "polygon": ["MATIC-USDC", "WETH-MATIC", "QUICK-MATIC"]
}

# Test transaction signatures
TEST_TX_SIGNATURES = {
    "success": "5TBLtTe9wvG69kitNrpETAjjNmTw3dWcwWxGsWyNvBecPHkrZTgBaPQJMCb89v9FL9b33U3Pd9iW1trDvvbDpJCK",
    "pending": "3xPq7Kz9wvG69kitNrpETAjjNmTw3dWcwWxGsWyNvBecPHkrZTgBaPQJMCb89v9FL9b33U3Pd9iW1trDvvbDpPEN",
    "failed": "2FAiLeDwvG69kitNrpETAjjNmTw3dWcwWxGsWyNvBecPHkrZTgBaPQJMCb89v9FL9b33U3Pd9iW1trDvvbDpFAIL"
}


def create_mock_gateway_response(success: bool = True, data: Dict[str, Any] = None,
                                 error: str = None) -> Dict[str, Any]:
    """Create a standardized mock gateway response"""
    if success:
        return {
            "success": True,
            "data": data or {},
            "timestamp": time.time()
        }
    else:
        return {
            "success": False,
            "error": error or "Unknown error",
            "timestamp": time.time()
        }


async def wait_for_condition(condition_func, timeout: float = 1.0, interval: float = 0.1) -> bool:
    """Wait for a condition to become true"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition_func():
            return True
        await asyncio.sleep(interval)
    return False
