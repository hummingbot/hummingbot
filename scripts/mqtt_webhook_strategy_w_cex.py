"""
Enhanced MQTT Webhook Strategy for Hummingbot with Gateway 2.9.0

GATEWAY 2.9.0
- JSON pool files instead of YAML
- Simplified flat structure for pools
- Updated API endpoints with /chains/ prefix
- Pool type explicitly specified in routes
Author: Todd Griggs
Date: Sept 19, 2025

"""
import asyncio
import json
import os
import re
import ssl
import time
import traceback
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlencode

import aiohttp
import pandas as pd

# Try importing MQTT with error handling
try:
    import paho.mqtt.client as mqtt

    MQTT_AVAILABLE = True
except ImportError:
    mqtt = None
    MQTT_AVAILABLE = False

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.gateway.core.gateway_network_adapter import GatewayNetworkAdapter
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.core.data_type.common import OrderType, PositionAction
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class ConfigurationError(Exception):
    """Specific exception for Gateway configuration errors - Phase 9.5 Single Source of Truth"""
    pass


class EnhancedMQTTWebhookStrategy(ScriptStrategyBase):
    """Enhanced MQTT webhook strategy with Gateway 2.9 configuration integration"""

    # Required framework attributes - CEX and DEX connectors
    # Gateway connectors use format: "{name}/{type}" (e.g., "jupiter/router", "uniswap/amm")
    # These are registered by GatewayHttpClient when it connects to Gateway (see gateway_http_client.py:212)
    # Network configuration is handled by Gateway internally
    markets = {
        # CEX connector
        os.getenv("HBOT_CEX_DEFAULT_EXCHANGE", "hyperliquid_perpetual"): os.getenv(
            "HBOT_CEX_TRADING_PAIRS",
            "ETH-USD,BTC-USD,HYPE-USD,SOL-USD,AVAX-USD,ATOM-USD,LINK-USD,DOT-USD,XRP-USD"
        ).split(","),

        # Gateway DEX connectors - Use format: {name}/{type}
        # These names must match what Gateway returns via /config/connectors endpoint
        "jupiter/router": set(),     # Jupiter (Solana router)
        "raydium/amm": set(),        # Raydium AMM
        "raydium/clmm": set(),       # Raydium CLMM
        "meteora/clmm": set(),       # Meteora CLMM
        "uniswap/amm": set(),        # Uniswap V2-style AMM
        "uniswap/clmm": set(),       # Uniswap V3 CLMM
    }

    def __init__(self, connectors: Optional[Dict] = None):
        """Initialize strategy with Gateway-first architecture"""
        super().__init__(connectors or {})
        self._pending_balances = {}
        self._initialized: bool = False
        self._initializing: bool = False

        # MQTT Configuration
        self.mqtt_host: str = os.getenv("HBOT_MQTT_HOST", "localhost")
        self.mqtt_port: int = int(os.getenv("HBOT_MQTT_PORT", "1883"))
        self.mqtt_namespace: str = os.getenv("HBOT_WEBHOOK_MQTT_NAMESPACE", "hbot")
        self.mqtt_topics: List[str] = [f"{self.mqtt_namespace}/signals/+/+"]
        self.mqtt_client: Optional[mqtt.Client] = None
        self.mqtt_connected: bool = False

        # Trading Configuration with Environment Variables
        self.trade_amount: Decimal = Decimal(str(os.getenv("HBOT_TRADE_AMOUNT", "1.0")))
        self.max_daily_trades: int = int(os.getenv("HBOT_MAX_DAILY_TRADES", "50"))
        self.max_daily_volume: Decimal = Decimal(str(os.getenv("HBOT_MAX_DAILY_VOLUME", "100.0")))

        # sell configuration using environment variables
        self.sell_percentage: float = float(os.getenv("HBOT_SELL_PERCENTAGE", "99.999"))
        self.min_sell_amount: Decimal = Decimal(str(os.getenv("HBOT_MIN_SELL_AMOUNT", "0.001")))
        self.balance_cache_ttl: int = int(os.getenv("HBOT_BALANCE_CACHE_TTL", "10"))

        # SOL minimum balance protection (for gas fees)
        self.min_sol_balance: float = float(os.getenv("HBOT_MIN_SOL_BALANCE", "0.02"))

        # CEX Configuration
        self.cex_enabled: bool = os.getenv("HBOT_CEX_ENABLED", "false").lower() == "true"
        self.cex_exchange_name: str = os.getenv("HBOT_CEX_DEFAULT_EXCHANGE", "coinbase_advanced_trade")
        self.cex_order_type: str = os.getenv("HBOT_CEX_ORDER_TYPE", "market").lower()
        self.cex_max_order_size: float = float(os.getenv("HBOT_CEX_MAX_ORDER_SIZE", "100.0"))
        self.cex_min_order_size: float = float(os.getenv("HBOT_CEX_MIN_ORDER_SIZE", "1.2"))
        self.cex_daily_limit: float = float(os.getenv("HBOT_CEX_DAILY_LIMIT", "1000.0"))
        self.cex_connector = None
        self.cex_ready: bool = False
        self.cex_daily_volume: float = 0.0
        self.cex_supported_pairs: List[str] = []
        self._cex_init_completed = False

        # CEX routing configuration
        self.cex_preferred_tokens: List[str] = os.getenv("HBOT_CEX_PREFERRED_TOKENS", "ETH,BTC").split(",")
        self.use_cex_for_large_orders: bool = os.getenv("HBOT_USE_CEX_FOR_LARGE_ORDERS", "true").lower() == "true"
        self.cex_threshold_amount: float = float(os.getenv("HBOT_CEX_THRESHOLD_AMOUNT", "50.0"))

        # Gateway Configuration
        self.gateway_host: str = os.getenv("HBOT_GATEWAY_HOST", "localhost")
        self.gateway_port: int = int(os.getenv("HBOT_GATEWAY_PORT", "15888"))
        self.gateway_https: bool = os.getenv("HBOT_GATEWAY_HTTPS", "true").lower() == "true"
        self.gateway_cert_path: str = os.getenv("HBOT_GATEWAY_CERT_PATH")
        self.gateway_key_path: str = os.getenv("HBOT_GATEWAY_KEY_PATH")
        self.gateway_conf_path: str = os.getenv("HBOT_GATEWAY_CONF_PATH")
        # Validate certificate paths are configured
        if not self.gateway_cert_path:
            raise ValueError("Gateway certificate path not configured. Set HBOT_GATEWAY_CERT_PATH in .env.hummingbot")
        if not self.gateway_key_path:
            raise ValueError("Gateway key path not configured. Set HBOT_GATEWAY_KEY_PATH in .env.hummingbot")

        # Log certificate configuration (without exposing full paths)
        self.logger().info(f"🔐 Gateway certificates configured: cert={os.path.basename(self.gateway_cert_path)}")

        # Wallet Configuration
        # Used to ensure we have a wallet to trade with
        self.arbitrum_wallet: str = os.getenv("HBOT_ARBITRUM_WALLET", "")
        self.solana_wallet: str = os.getenv("HBOT_SOLANA_WALLET", "")

        # Gateway-based configuration caches
        self.gateway_config_cache: Dict = {}
        self.supported_networks: Dict[str, Dict] = {}
        self.supported_tokens: Dict[str, List[str]] = {}
        self.pool_configurations: Dict[str, Dict] = {}
        self.connector_sources = {}  # Track which connector provided which pools

        # Gateway 2.9 simplified configuration caches
        self.pool_configurations: Dict[str, Dict] = {}  # Simplified structure for 2.9
        self.supported_networks: Dict[str, Dict] = {}
        self.supported_tokens: Dict[str, List[str]] = {}

        # Trading state tracking
        self.signal_queue: List[Tuple[Dict[str, Any], str]] = []
        self.daily_trade_count: int = 0
        self.daily_volume: Decimal = Decimal("0")
        self.last_reset_date = datetime.now(timezone.utc).date()
        self.request_timeout: int = 30

        # Cache configuration with environment variables
        self.gateway_config_cache_ttl: int = int(os.getenv("HBOT_GATEWAY_CONFIG_CACHE_TTL", "300"))  # 5 minutes default
        self.rate_oracle_update_interval: int = int(os.getenv("HBOT_RATE_ORACLE_UPDATE_INTERVAL", "10"))  # 10 seconds default
        self.config_refresh_interval: int = int(os.getenv("HBOT_CONFIG_REFRESH_INTERVAL", "300"))  # 5 minutes default
        self.predictive_stats_log_interval: int = int(os.getenv("HBOT_PREDICTIVE_STATS_LOG_INTERVAL", "300"))  # 5 minutes default

        self._gateway_config_cache: Dict = {}
        self._balance_cache: Dict = {}
        self._last_gateway_refresh = 0
        self._last_balance_refresh = 0

        # Trading Configuration Attributes
        self.slippage_tolerance: float = float(os.getenv("HBOT_SLIPPAGE_TOLERANCE", "1.0"))  # 1% default
        self.sell_percentage: float = float(os.getenv("HBOT_SELL_PERCENTAGE", "99.999"))  # Sell 99.999% by default

        # Transaction history tracking
        self.transaction_history: List[Dict[str, Any]] = []

        # DEX order tracking for event handling
        # Maps order_id -> {signal_data, exchange, pool_type, trading_pair, timestamp}
        self._dex_order_tracking: Dict[str, Dict[str, Any]] = {}
        self.balance_cache: Dict[str, Tuple[float, float]] = {}  # {token: (balance, timestamp)}

        # transaction hash response
        self._last_trade_response: Optional[Dict] = None

        # Specific token addresses
        self.token_details_cache = {}

        # active positions
        self.active_positions = {}

        # Performance tracking attributes
        self.successful_trades: int = 0
        self.failed_trades: int = 0
        self.avg_execution_time: float = 0.0
        self.last_signal_time: Optional[datetime] = None

        # Store app reference for CEX connector access
        self.app = HummingbotApplication.main_application()

        # Dynamic network-specific connector cache
        # Format: {f"{exchange}/{pool_type}/{network}": connector_instance}
        # self._network_connectors: Dict[str, Any] = {}

        """Add these configuration options to __init__"""
        # Predictive selling configuration.  This is experimental and is used for very quick unintended buy/sell cycles
        self.cex_predictive_enabled = os.getenv("HBOT_CEX_PREDICTIVE_SELL", "true").lower() == "true"
        self.cex_predictive_window = int(os.getenv("HBOT_CEX_PREDICTIVE_WINDOW", "60"))  # seconds
        self.cex_fee_estimate = float(os.getenv("HBOT_CEX_FEE_ESTIMATE", "1.5"))  # 0.6% default

        # Track predictive sell results for monitoring
        self.predictive_stats = {
            'attempts': 0,
            'successes': 0,
            'failures': 0,
            'fallback_success': 0  # When 99% retry works
        }

        # Gas Configuration - Adaptive Strategy
        self.gas_strategy = os.getenv("HBOT_GAS_STRATEGY", "adaptive").lower()  # "adaptive" or "fixed"
        self.gas_buffer = float(os.getenv("HBOT_GAS_BUFFER", "1.10"))  # 10% buffer by default
        self.gas_urgency_multiplier = float(os.getenv("HBOT_GAS_URGENCY", "1.25"))  # 25% for urgent trades
        self.gas_max_price_gwei = float(os.getenv("HBOT_GAS_MAX_GWEI", "0"))  # 0 = no limit
        self.gas_retry_multiplier = float(os.getenv("HBOT_GAS_RETRY_MULTIPLIER", "0.15"))

        # Log gas strategy on startup
        if self.gas_strategy == "adaptive":
            self.logger().info(
                f"⛽ Gas Strategy: ADAPTIVE (always execute at market price + {(self.gas_buffer - 1) * 100:.0f}% buffer)")
            if self.gas_max_price_gwei > 0:
                self.logger().info(f"⛽ Max gas price: {self.gas_max_price_gwei} Gwei")
            else:
                self.logger().info("⛽ Max gas price: UNLIMITED (execution guaranteed)")
        else:
            self.logger().info(f"⛽ Gas Strategy: FIXED (buffer={self.gas_buffer}x)")

        # Transaction failure tracking and retry configuration
        self.failed_orders: Dict[str, Dict[str, Any]] = {}  # order_id -> failure details
        self.retry_attempts: Dict[str, int] = {}  # order_id -> retry count
        self.max_retry_attempts: int = int(os.getenv("HBOT_MAX_RETRY_ATTEMPTS", "3"))
        self.retry_delay_base: float = float(os.getenv("HBOT_RETRY_DELAY_BASE", "2.0"))  # seconds
        self.order_timeout: int = int(os.getenv("HBOT_ORDER_TIMEOUT", "120"))  # seconds

        # Gas-related error tracking
        self.gas_errors: List[Dict[str, Any]] = []
        self.gas_error_count: int = 0
        self.last_gas_error_time: Optional[float] = None

        # Order status monitoring
        self.pending_orders: Dict[str, Dict[str, Any]] = {}  # order_id -> {timestamp, details}

        # Gas price monitoring and alerting
        self.gas_price_history: List[Dict[str, Any]] = []  # Historical gas prices
        self.gas_price_warning_threshold: float = float(os.getenv("HBOT_GAS_WARNING_GWEI", "1.0"))  # Gwei
        self.gas_price_critical_threshold: float = float(os.getenv("HBOT_GAS_CRITICAL_GWEI", "2.0"))  # Gwei
        self.last_gas_alert_time: Optional[float] = None
        self.gas_alert_cooldown: int = int(os.getenv("HBOT_GAS_ALERT_COOLDOWN", "300"))  # seconds

        # Network-specific gas thresholds (Gwei)
        self.network_gas_thresholds: Dict[str, Dict[str, float]] = {
            'arbitrum': {'warning': 0.5, 'critical': 1.0},
            'ethereum': {'warning': 30.0, 'critical': 50.0},
            'base': {'warning': 0.5, 'critical': 1.0},
            'optimism': {'warning': 0.5, 'critical': 1.0},
            'polygon': {'warning': 50.0, 'critical': 100.0},
            'bsc': {'warning': 3.0, 'critical': 5.0},
            'avalanche': {'warning': 25.0, 'critical': 40.0},
            'celo': {'warning': 0.5, 'critical': 1.0}
        }

        self.logger().info(f"🔄 Retry configuration: max_attempts={self.max_retry_attempts}, base_delay={self.retry_delay_base}s, order_timeout={self.order_timeout}s")
        self.logger().info(f"⛽ Gas monitoring: warning={self.gas_price_warning_threshold} GWEI, critical={self.gas_price_critical_threshold} GWEI, alert_cooldown={self.gas_alert_cooldown}s")

    @classmethod
    def init_markets(cls, config=None):
        """
        Optional: Can be used to modify markets at config load time.
        The markets dict is already set as a class attribute above, so this is optional.
        If you need to dynamically configure markets based on config, you can do it here.
        """
        pass  # markets already set as class attribute

    def _get_dex_connector(self, exchange: str, pool_type: str = None, network: str = None) -> Optional[Any]:
        """
        Get DEX connector from pre-declared framework-managed connectors with network adapter.
        The framework creates, starts (with clock), and registers all connectors
        declared in init_markets() with MarketsRecorder automatically.

        This method wraps connectors with GatewayNetworkAdapter to enable dynamic
        network switching based on MQTT signal network parameter.

        Args:
            exchange: Exchange name (e.g., 'jupiter', 'raydium', 'uniswap')
            pool_type: Pool type ('router', 'amm', 'clmm'). If None, tries to infer.
            network: Network name (e.g., 'arbitrum', 'mainnet', 'base'). Used for network override.

        Returns:
            GatewayNetworkAdapter wrapping the connector, or None if connector not found
        """
        try:
            # Auto-detect pool type for router-based exchanges
            if exchange.lower() in ['jupiter', '0x']:
                pool_type = 'router'

            # If still no pool type, default to 'amm'
            if not pool_type:
                pool_type = 'amm'

            # Build connector key in format "exchange/type" (WITHOUT network)
            # Network is NOT part of the connector key - it's a parameter for Gateway API calls
            # Gateway connectors are registered as "jupiter/router", "uniswap/clmm", etc.
            connector_key = f"{exchange.lower()}/{pool_type}"

            # Look up connector in framework-managed connectors
            if connector_key in self.connectors:
                base_connector = self.connectors[connector_key]

                # Wrap with network adapter to enable dynamic network switching
                adapter = GatewayNetworkAdapter(base_connector, network)

                self.logger().debug(
                    f"✅ Found connector: {connector_key} "
                    f"(network: {network or 'default'}, adapter: {adapter.network})"
                )

                return adapter
            else:
                self.logger().warning(f"⚠️ Connector not found: {connector_key}")
                self.logger().debug(f"Available connectors: {list(self.connectors.keys())}")
                return None

        except Exception as e:
            self.logger().error(f"❌ Error getting connector for {exchange}/{pool_type}: {e}")
            return None

    def did_fill_order(self, event: OrderFilledEvent):
        """
        Event handler called when a DEX order is filled.
        This method is automatically triggered by the connector framework when trades complete.
        The MarketsRecorder will automatically persist this event to the TradeFill database table.

        Args:
            event: OrderFilledEvent containing trade details (price, amount, fees, tx hash, etc.)
        """
        try:
            # Check if this is one of our tracked DEX orders
            if event.order_id not in self._dex_order_tracking:
                # Not our order, ignore (might be CEX order or from another strategy)
                return

            # Retrieve trade context
            order_info = self._dex_order_tracking[event.order_id]
            exchange = order_info.get("exchange")
            pool_type = order_info.get("pool_type")
            signal_data = order_info.get("signal_data", {})
            base_token = order_info.get("base_token")
            trading_pair = event.trading_pair

            # Record gas price for EVM transactions (if available)
            try:
                connector = self._get_dex_connector(exchange, pool_type)
                if connector and hasattr(connector, 'in_flight_orders'):
                    # Get the in-flight order to extract gas price
                    in_flight_order = connector.in_flight_orders.get(event.order_id)
                    if in_flight_order and hasattr(in_flight_order, 'gas_price'):
                        gas_price_wei = float(in_flight_order.gas_price)
                        if gas_price_wei > 0:
                            # Convert from Wei to Gwei (1 Gwei = 1e9 Wei)
                            gas_price_gwei = gas_price_wei / 1e9

                            # Determine network from exchange name
                            network = exchange.lower() if exchange else 'unknown'

                            # Record gas price for monitoring
                            self._record_gas_price(
                                gas_price_gwei=gas_price_gwei,
                                network=network,
                                tx_hash=event.exchange_trade_id,
                                symbol=trading_pair,
                                action=event.trade_type.name
                            )
            except Exception as gas_err:
                # Don't fail the order handler if gas recording fails
                self.logger().debug(f"⚠️ Could not record gas price: {gas_err}")

            # Build log message
            log_msg = (
                f"✅ DEX Order Filled: {event.trade_type.name} {trading_pair} on {exchange}/{pool_type}\n"
                f"   Order ID: {event.order_id}\n"
                f"   Amount: {event.amount}\n"
                f"   Price: {event.price}\n"
                f"   Fee: {event.trade_fee}\n"
                f"   TX Hash: {event.exchange_trade_id}"
            )

            # Only add signal info if we have valid signal data
            if signal_data and signal_data.get('action') and signal_data.get('token'):
                log_msg += f"\n   Signal: {signal_data['action']} {signal_data['token']}"

            self.logger().info(log_msg)

            # Clean up position tracking for SELL orders
            if event.trade_type.name == "SELL" and base_token:
                if base_token in self.active_positions:
                    del self.active_positions[base_token]
                    self.logger().info(f"📝 Position closed: {base_token}")

            # Inject DEX price into rate oracle BEFORE MarketsRecorder calculates fees/PnL
            # This prevents "Could not find exchange rate" warnings for DEX-only pairs like RAY-USDC
            try:
                rate_oracle = RateOracle.get_instance()
                # trading_pair is in format "RAY-USDC" - perfect for rate oracle
                rate_oracle.set_price(trading_pair, Decimal(str(event.price)))
                self.logger().debug(f"📊 Injected {trading_pair} = ${event.price:.6f} into rate oracle")
            except Exception as oracle_err:
                self.logger().debug(f"⚠️ Could not inject price into rate oracle: {oracle_err}")

            # Clean up tracking entry
            del self._dex_order_tracking[event.order_id]

            # Note: MarketsRecorder automatically persists this event to database
            # No manual database writes needed - the framework handles it

            # Fetch and update gas fees for EVM transactions (async, non-blocking)
            if event.exchange_trade_id and exchange:
                safe_ensure_future(self._fetch_and_update_gas_fee(
                    tx_hash=event.exchange_trade_id,
                    exchange=exchange,
                    trading_pair=trading_pair
                ))

        except Exception as e:
            self.logger().error(f"❌ Error in did_fill_order handler: {e}", exc_info=True)

    async def _fetch_and_update_gas_fee(self, tx_hash: str, exchange: str, trading_pair: str):
        """
        Fetch actual gas cost from blockchain and update TradeFill record.
        Supports both EVM (Ethereum, Arbitrum, etc.) and Solana chains.

        Args:
            tx_hash: Transaction hash / exchange_trade_id
            exchange: Exchange name (e.g., 'uniswap', 'jupiter')
            trading_pair: Trading pair for logging
        """
        try:
            # Give the transaction time to confirm and MarketsRecorder to save
            await asyncio.sleep(5)

            # Determine if this is a Solana DEX
            is_solana = any(sol_dex in exchange.lower() for sol_dex in ['jupiter', 'raydium', 'orca', 'meteora'])

            # Get the connector to access Gateway
            connector = self._get_dex_connector(exchange, 'clmm')  # Type doesn't matter for provider access
            if not connector or not hasattr(connector, '_get_gateway_instance'):
                return

            # Use Gateway to poll transaction status
            gateway = connector._get_gateway_instance()
            network = connector.network if hasattr(connector, 'network') else ('mainnet-beta' if is_solana else 'arbitrum')

            # Poll transaction to get receipt with gas info
            # For Solana, we need to pass tokens and wallet address to get accurate fee calculation
            if is_solana:
                # Extract tokens from trading pair (e.g., "WBTC-USDC" -> ["WBTC", "USDC"])
                tokens = trading_pair.split('-') if '-' in trading_pair else []
                wallet_address = connector.address if hasattr(connector, 'address') else None

                tx_status = await gateway.get_transaction_status(
                    chain=connector.chain,
                    network=network,
                    tx_hash=tx_hash,
                    tokens=tokens,
                    walletAddress=wallet_address
                )
            else:
                # EVM chains don't need tokens/wallet for fee calculation
                tx_status = await gateway.get_transaction_status(
                    chain=connector.chain,
                    network=network,
                    tx_hash=tx_hash
                )

            # Extract gas fee if available
            gas_fee = tx_status.get('fee')
            if gas_fee and float(gas_fee) > 0:
                # Determine native currency
                native_currency = 'SOL' if is_solana else (connector._native_currency if hasattr(connector, '_native_currency') else 'ETH')

                # Update the TradeFill record in database
                await self._update_trade_fill_gas_fee(tx_hash, gas_fee, native_currency)
                self.logger().info(
                    f"💰 Updated gas fee for {trading_pair}: {gas_fee} {native_currency} (tx: {tx_hash[:10]}...)"
                )
            else:
                self.logger().debug(f"⚠️ No gas fee returned for tx {tx_hash[:10]}...")

        except Exception as e:
            self.logger().debug(f"⚠️ Could not fetch gas fee for {tx_hash[:10]}...: {e}")

    async def _update_trade_fill_gas_fee(self, tx_hash: str, gas_fee: float, fee_token: str):
        """
        Update TradeFill record with actual gas fee.

        Args:
            tx_hash: Transaction hash (exchange_trade_id)
            gas_fee: Gas fee in native token (e.g., ETH)
            fee_token: Token symbol (e.g., 'ETH')
        """
        try:
            from hummingbot.client.hummingbot_application import HummingbotApplication
            from hummingbot.model.trade_fill import TradeFill

            # Get database session
            app = HummingbotApplication.main_application()
            if not app or not hasattr(app, 'markets_recorder'):
                return

            sql_manager = app.markets_recorder.sql_manager

            with sql_manager.get_new_session() as session:
                # Find the TradeFill record by exchange_trade_id
                trade_fill = session.query(TradeFill).filter(
                    TradeFill.exchange_trade_id == tx_hash
                ).first()

                if trade_fill:
                    # Update trade_fee JSON to include gas cost
                    try:
                        fee_data = json.loads(trade_fill.trade_fee) if trade_fill.trade_fee else {}
                    except Exception:
                        fee_data = {}

                    # Add or update flat_fees with gas cost
                    if 'flat_fees' not in fee_data:
                        fee_data['flat_fees'] = []

                    # Add gas fee as a flat fee
                    fee_data['flat_fees'].append({
                        'token': fee_token,
                        'amount': str(gas_fee)
                    })

                    # Update the record
                    trade_fill.trade_fee = json.dumps(fee_data)
                    session.commit()

                    self.logger().debug(f"✅ Updated TradeFill record with gas fee: {gas_fee} {fee_token}")
                else:
                    self.logger().debug(f"⚠️ TradeFill record not found for tx {tx_hash[:10]}...")

        except Exception as e:
            self.logger().error(f"❌ Error updating TradeFill gas fee: {e}", exc_info=True)

    async def _update_rate_oracle_for_dex_positions(self):
        """
        Update RateOracle with current DEX prices for active positions.
        This fixes the rate oracle warnings by injecting DEX prices so the performance
        module can calculate PNL correctly.

        Called periodically in on_tick() to keep prices fresh.
        """
        try:
            if not self.active_positions:
                return

            rate_oracle = RateOracle.get_instance()

            for base_token, position in self.active_positions.items():
                try:
                    quote_token = position.get('quote_token', 'USDC')
                    network = position.get('network')

                    # Get current price from DEX
                    price = None
                    if self._is_solana_network(network):
                        price = await self._get_solana_token_price(base_token, network)
                    else:
                        exchange = position.get('exchange', 'uniswap')
                        price = await self._get_token_price_in_usd(base_token, network, exchange)

                    if price:
                        # Inject price into rate oracle
                        # Format: "BASE-QUOTE" (e.g., "RAY-USDC")
                        pair = f"{base_token}-{quote_token}"
                        rate_oracle.set_price(pair, Decimal(str(price)))
                        self.logger().debug(f"📊 Updated rate oracle: {pair} = ${price:.6f}")

                except Exception as e:
                    self.logger().debug(f"⚠️ Could not update rate oracle for {base_token}: {e}")

        except Exception as e:
            self.logger().debug(f"⚠️ Rate oracle update error: {e}")

    def on_tick(self):
        """
        Main strategy event loop - FIXED to not spam ready checks
        """
        try:
            # Skip everything during initialization phase
            # This prevents the framework from checking CEX readiness repeatedly
            if not self._initialized:
                if not self._initializing:
                    self._initializing = True
                    safe_ensure_future(self._initialize_strategy())
                # Always return during initialization to prevent any checks
                return

            # Step 2: Reset daily counters if needed
            self._reset_daily_counters_if_needed()

            # Step 3: Process queued trading signals
            while self.signal_queue:
                signal_data, topic = self.signal_queue.pop(0)
                action = signal_data.get("action", "UNKNOWN")
                symbol = signal_data.get("symbol", "UNKNOWN")
                network = signal_data.get("network", "UNKNOWN")

                self.logger().debug(f"🔄 Processing signal: {action} {symbol} on {network}")
                safe_ensure_future(self._process_trading_signal(signal_data, topic))

            # Step 4: Periodic maintenance (only after initialization)
            self._perform_periodic_maintenance()

        except Exception as tick_error:
            self.logger().error(f"❌ Strategy tick error: {tick_error}")

    def _perform_periodic_maintenance(self):
        """
        Perform periodic maintenance tasks during tick cycles
        Keeps configuration fresh without blocking main loop
        """
        try:
            # Only perform maintenance occasionally to avoid overhead
            current_time = time.time()

            # Clean up old pending balances (older than 60 seconds)
            if self._pending_balances:  # Now safe to check since it's always a dict
                tokens_to_remove = []
                for token, pending in self._pending_balances.items():
                    if current_time - pending['timestamp'] > 60:
                        tokens_to_remove.append(token)

                for token in tokens_to_remove:
                    del self._pending_balances[token]

                if tokens_to_remove:
                    self.logger().debug(f"🧹 Cleaned up {len(tokens_to_remove)} old pending balances")

            # Refresh configuration every 5 minutes
            if not hasattr(self, '_last_config_refresh'):
                self._last_config_refresh = current_time

            if not hasattr(self, '_last_predictive_stats_log'):
                self._last_predictive_stats_log = current_time

            if current_time - self._last_predictive_stats_log > self.predictive_stats_log_interval:
                if self.predictive_stats['attempts'] > 0:
                    self.log_predictive_stats()
                self._last_predictive_stats_log = current_time

            # Update rate oracle with DEX prices for active positions (configurable interval)
            if not hasattr(self, '_last_rate_oracle_update'):
                self._last_rate_oracle_update = current_time

            if current_time - self._last_rate_oracle_update > self.rate_oracle_update_interval:
                safe_ensure_future(self._update_rate_oracle_for_dex_positions())
                self._last_rate_oracle_update = current_time

            # Periodic configuration refresh (configurable interval)
            time_since_refresh = current_time - self._last_config_refresh
            if time_since_refresh > self.config_refresh_interval:
                self.logger().debug("🔄 Performing periodic configuration refresh...")
                safe_ensure_future(self._refresh_configuration())
                self._last_config_refresh = current_time

            # Monitor pending orders for timeouts (check every tick)
            self._check_pending_order_timeouts(current_time)

            # Monitor gas prices (check every tick, alerts with cooldown)
            self._monitor_gas_prices(current_time)

            # Clean up old gas errors (keep last hour only)
            if self.gas_errors:
                one_hour_ago = current_time - 3600
                self.gas_errors = [err for err in self.gas_errors if err.get('timestamp', 0) > one_hour_ago]

            # Clean up old gas price history (keep last 24 hours)
            if self.gas_price_history:
                one_day_ago = current_time - 86400
                self.gas_price_history = [
                    entry for entry in self.gas_price_history
                    if entry.get('timestamp', 0) > one_day_ago
                ]

        except Exception as maintenance_error:
            self.logger().debug(f"⚠️ Maintenance error (non-critical): {maintenance_error}")

    def _check_pending_order_timeouts(self, current_time: float):
        """
        Check for pending orders that have exceeded timeout threshold
        Log warnings and clean up stale orders
        """
        try:
            if not self.pending_orders:
                return

            timed_out_orders = []

            for order_id, order_info in self.pending_orders.items():
                order_timestamp = order_info.get('timestamp', current_time)
                time_elapsed = current_time - order_timestamp

                if time_elapsed > self.order_timeout:
                    timed_out_orders.append(order_id)

                    # Log timeout warning
                    order_details = order_info.get('details', {})
                    symbol = order_details.get('symbol', 'UNKNOWN')
                    action = order_details.get('action', 'UNKNOWN')
                    network = order_details.get('network', 'UNKNOWN')

                    self.logger().warning(
                        f"⏰ Order timeout detected: {order_id}\n"
                        f"   Action: {action} {symbol} on {network}\n"
                        f"   Time elapsed: {time_elapsed:.1f}s (timeout: {self.order_timeout}s)"
                    )

                    # Track gas errors if this appears to be a gas-related timeout
                    if 'gas' in str(order_info.get('error', '')).lower():
                        self.gas_error_count += 1
                        self.last_gas_error_time = current_time
                        self.gas_errors.append({
                            'timestamp': current_time,
                            'order_id': order_id,
                            'details': order_details,
                            'error': order_info.get('error', 'Timeout')
                        })

            # Clean up timed out orders
            for order_id in timed_out_orders:
                del self.pending_orders[order_id]

            if timed_out_orders:
                self.logger().info(f"🧹 Cleaned up {len(timed_out_orders)} timed out orders")

        except Exception as e:
            self.logger().debug(f"⚠️ Error checking order timeouts: {e}")

    def _monitor_gas_prices(self, current_time: float):
        """
        Monitor gas prices from recent transactions and alert on anomalies
        Tracks gas price history and detects unusually high gas prices
        """
        try:
            # Skip if no gas price history to analyze
            if not self.gas_price_history:
                return

            # Clean up old gas price entries (keep last 24 hours)
            one_day_ago = current_time - 86400
            self.gas_price_history = [
                entry for entry in self.gas_price_history
                if entry.get('timestamp', 0) > one_day_ago
            ]

            # Get recent gas prices (last hour)
            one_hour_ago = current_time - 3600
            recent_prices = [
                entry for entry in self.gas_price_history
                if entry.get('timestamp', 0) > one_hour_ago
            ]

            if not recent_prices:
                return

            # Calculate statistics
            gas_prices_gwei = [entry['gas_price_gwei'] for entry in recent_prices if 'gas_price_gwei' in entry]

            if not gas_prices_gwei:
                return

            avg_gas = sum(gas_prices_gwei) / len(gas_prices_gwei)
            max_gas = max(gas_prices_gwei)
            min_gas = min(gas_prices_gwei)

            # Get latest gas price
            latest_entry = recent_prices[-1]
            latest_gas = latest_entry.get('gas_price_gwei', 0)
            network = latest_entry.get('network', 'unknown')

            # Get network-specific thresholds
            thresholds = self.network_gas_thresholds.get(
                network,
                {'warning': self.gas_price_warning_threshold, 'critical': self.gas_price_critical_threshold}
            )

            warning_threshold = thresholds['warning']
            critical_threshold = thresholds['critical']

            # Check for alerts (with cooldown to avoid spam)
            should_alert = False
            alert_level = None

            if latest_gas >= critical_threshold:
                alert_level = 'CRITICAL'
                should_alert = True
            elif latest_gas >= warning_threshold:
                alert_level = 'WARNING'
                should_alert = True

            # Apply alert cooldown
            if should_alert:
                if self.last_gas_alert_time is None or (current_time - self.last_gas_alert_time) >= self.gas_alert_cooldown:
                    self.last_gas_alert_time = current_time

                    # Generate alert message
                    self.logger().warning(
                        f"⛽ GAS PRICE {alert_level}: {network.upper()}\n"
                        f"   Current: {latest_gas:.4f} GWEI\n"
                        f"   Average (1h): {avg_gas:.4f} GWEI\n"
                        f"   Range (1h): {min_gas:.4f} - {max_gas:.4f} GWEI\n"
                        f"   Threshold: {warning_threshold:.4f} GWEI (warning), {critical_threshold:.4f} GWEI (critical)"
                    )

                    # Log recent transaction context
                    tx_hash = latest_entry.get('tx_hash', 'N/A')
                    symbol = latest_entry.get('symbol', 'N/A')
                    action = latest_entry.get('action', 'N/A')

                    if tx_hash != 'N/A':
                        explorer_url = self._get_blockchain_explorer_url(tx_hash, network)
                        self.logger().info(
                            f"   Transaction: {action} {symbol}\n"
                            f"   Explorer: {explorer_url}"
                        )

            # Periodic status update (every 5 minutes if we have data)
            if not hasattr(self, '_last_gas_status_log'):
                self._last_gas_status_log = current_time

            if current_time - self._last_gas_status_log > 300:  # 5 minutes
                self._last_gas_status_log = current_time

                # Log summary of recent gas prices by network
                networks_summary = {}
                for entry in recent_prices:
                    net = entry.get('network', 'unknown')
                    gas_gwei = entry.get('gas_price_gwei', 0)

                    if net not in networks_summary:
                        networks_summary[net] = []
                    networks_summary[net].append(gas_gwei)

                if networks_summary:
                    self.logger().info("⛽ Gas Price Summary (Last Hour):")
                    for net, prices in networks_summary.items():
                        net_avg = sum(prices) / len(prices)
                        net_max = max(prices)
                        net_thresholds = self.network_gas_thresholds.get(
                            net,
                            {'warning': self.gas_price_warning_threshold, 'critical': self.gas_price_critical_threshold}
                        )

                        status_icon = "✅"
                        if net_avg >= net_thresholds['critical']:
                            status_icon = "🔴"
                        elif net_avg >= net_thresholds['warning']:
                            status_icon = "⚠️"

                        self.logger().info(
                            f"   {status_icon} {net}: Avg {net_avg:.4f} GWEI, Max {net_max:.4f} GWEI "
                            f"(threshold: {net_thresholds['warning']:.4f}/{net_thresholds['critical']:.4f})"
                        )

        except Exception as e:
            self.logger().debug(f"⚠️ Error monitoring gas prices: {e}")

    def _record_gas_price(self, gas_price_gwei: float, network: str, tx_hash: str = None,
                          symbol: str = None, action: str = None):
        """
        Record a gas price from a transaction for monitoring

        Args:
            gas_price_gwei: Gas price in Gwei
            network: Network name (e.g., 'arbitrum', 'ethereum')
            tx_hash: Transaction hash (optional)
            symbol: Trading symbol (optional)
            action: Trade action (BUY/SELL) (optional)
        """
        try:
            self.gas_price_history.append({
                'timestamp': time.time(),
                'gas_price_gwei': gas_price_gwei,
                'network': network,
                'tx_hash': tx_hash,
                'symbol': symbol,
                'action': action
            })

            self.logger().debug(
                f"📊 Recorded gas price: {gas_price_gwei:.4f} GWEI on {network} "
                f"({'(' + action + ' ' + symbol + ')' if action and symbol else ''})"
            )

        except Exception as e:
            self.logger().debug(f"⚠️ Error recording gas price: {e}")

    async def _refresh_configuration(self):
        """Refresh Gateway configuration periodically"""
        try:
            await self._refresh_gateway_configuration()
            self.logger().debug("✅ Periodic configuration refresh completed")
        except Exception as refresh_error:
            self.logger().warning(f"⚠️ Configuration refresh error: {refresh_error}")

    async def _initialize_strategy(self) -> None:
        """Initialize strategy with Gateway 2.9 configuration"""
        try:
            if self._initialized:
                self._initializing = False
                return

            self.logger().info("🚀 Initializing MQTT Webhook Strategy with Gateway 2.9 architecture")

            if self.cex_enabled:
                num_pairs = len(self.markets.get(self.cex_exchange_name, []))
                self.logger().info(f"📊 CEX Mode: Subscribing to {num_pairs} trading pairs on {self.cex_exchange_name}")

            # Step 1: Initialize supported networks
            self.supported_networks = self._get_supported_networks()
            self.logger().info(f"📋 Target networks: {', '.join(self.supported_networks)}")

            # Step 2: Load Gateway 2.9 pool configurations
            self.logger().info("🏊 Loading Gateway 2.9 pool configurations...")
            await self._refresh_gateway_configuration()

            # Step 3: Dynamic token discovery
            self.logger().info("🔍 Starting dynamic token discovery...")
            await self._initialize_dynamic_token_discovery()

            self.logger().info("🔢 Loading token decimals...")
            await self._load_token_decimals()

            # Step 4: Initialize CEX connector if enabled
            if self.cex_enabled:
                self.logger().info("📈 Initializing CEX connector...")
                await self._initialize_cex_connector()

            # Step 5: Setup MQTT if available
            if MQTT_AVAILABLE:
                self.logger().info("📡 Setting up MQTT connection...")
                self._setup_mqtt()
            else:
                self.logger().warning("⚠️ MQTT not available - webhook-only mode")

            # Step 6: Log configuration summary
            self._log_configuration_summary()

            # Step 7: Mark as initialized
            self._initialized = True
            self._initializing = False
            self.logger().info("✅ Strategy initialization complete with Gateway 2.9")

        except Exception as init_error:
            self.logger().error(f"❌ Strategy initialization error: {init_error}")
            self._initializing = False
            self._initialized = False

    async def _refresh_gateway_configuration(self) -> None:
        """
        Gateway 2.9 Configuration Refresh
        SIMPLIFIED: Uses JSON pool files directly
        """
        try:
            current_time = datetime.now().timestamp()

            # Check cache validity
            if hasattr(self, '_last_gateway_refresh') and (
                    current_time - self._last_gateway_refresh) < self.gateway_config_cache_ttl:
                self.logger().debug("🔄 Using cached Gateway 2.9 configuration")
                return

            self.logger().info("🔄 Loading Gateway 2.9 configuration from JSON files...")

            # Clear existing configuration
            self.pool_configurations = {}
            self.supported_networks = {}

            # Read Gateway 2.9 JSON configuration
            config_response = await self._read_gateway_config_files()

            # Parse Gateway 2.9 pools
            if "pools" in config_response:
                self._parse_pool_configurations(config_response["pools"])
            else:
                raise ConfigurationError("No pools found in Gateway 2.9 configuration")

            # Validate configuration
            total_networks = len(self.supported_networks)
            total_pools = sum(
                len(pools)
                for connector_pools in self.pool_configurations.values()
                for connector_config in connector_pools.values()
                for pools in connector_config.values()
            )

            if total_networks == 0:
                raise ConfigurationError("No networks with pools found")

            # Update cache timestamp
            self._last_gateway_refresh = current_time

            self.logger().info(f"✅ Gateway 2.9 configuration loaded: {total_networks} networks, {total_pools} pools")

        except Exception as e:
            self.logger().error(f"❌ Gateway 2.9 configuration error: {e}")

    async def _read_gateway_config_files(self) -> Dict:
        """
        Read Gateway 2.9.0 JSON pool configurations
        SIMPLIFIED: Direct JSON loading instead of YAML parsing
        """
        try:
            gateway_conf_path = self.gateway_conf_path
            pools_path = os.path.join(gateway_conf_path, "pools")

            if not os.path.exists(pools_path):
                raise ConfigurationError(f"Pools directory not found: {pools_path}")

            config_response = {
                "pools": {},
                "configUpdate": datetime.now().isoformat(),
                "source": "gateway_2.9.0_json_files"
            }

            # Read JSON pool files (Gateway 2.9 format)
            # Note: Jupiter router doesn't use pool files - it finds routes dynamically
            pool_files = [
                ("uniswap", "uniswap.json"),
                ("raydium", "raydium.json"),
                ("meteora", "meteora.json")
            ]

            for connector_name, filename in pool_files:
                pool_file = os.path.join(pools_path, filename)

                if not os.path.exists(pool_file):
                    self.logger().debug(f"Pool file not found: {filename}")
                    continue

                try:
                    with open(pool_file, 'r') as file:
                        pools = json.load(file)

                    config_response["pools"][connector_name] = pools
                    self.logger().info(f"✅ Loaded {len(pools)} pools from {filename}")

                except json.JSONDecodeError as e:
                    self.logger().error(f"❌ JSON error in {filename}: {e}")
                    continue

            return config_response

        except Exception as e:
            self.logger().error(f"❌ Error reading pool files: {e}")
            raise ConfigurationError(f"Failed to read Gateway 2.9.0 pool files: {e}")

    def _parse_pool_configurations(self, pools_config: Dict) -> None:
        """
        Parse Gateway 2.9.0 flat JSON pool structure
        """
        try:
            self.pool_configurations = {}
            self.supported_networks = {}

            for connector_name, pools in pools_config.items():
                if not isinstance(pools, list):
                    continue

                for pool in pools:
                    network = pool.get("network")
                    pool_type = pool.get("type")
                    base_symbol = pool.get("baseSymbol")
                    quote_symbol = pool.get("quoteSymbol")
                    address = pool.get("address")

                    if not all([network, pool_type, base_symbol, quote_symbol, address]):
                        continue

                    # Initialize network if needed
                    if network not in self.pool_configurations:
                        self.pool_configurations[network] = {}
                        self.supported_networks[network] = {"pools": 0}

                    # Initialize connector if needed
                    if connector_name not in self.pool_configurations[network]:
                        self.pool_configurations[network][connector_name] = {"amm": {}, "clmm": {}}

                    # Store pool with hyphenated key
                    pool_key = f"{base_symbol}-{quote_symbol}"
                    self.pool_configurations[network][connector_name][pool_type][pool_key] = address
                    self.supported_networks[network]["pools"] += 1

            self.logger().info(f"✅ Parsed {len(self.supported_networks)} networks from pools")

        except Exception as e:
            self.logger().error(f"❌ Error parsing pool configurations: {e}")

    def _validate_trading_signal(self, signal_data: Dict[str, Any]) -> bool:
        """
        Validate incoming trading signals - Gateway 2.9 simplified json
        """
        try:
            # Required fields validation
            required_fields = ["action", "symbol", "network", "exchange"]
            for field in required_fields:
                if field not in signal_data or not signal_data[field]:
                    self.logger().warning(f"⚠️ Missing required field: {field}")
                    return False

            action = signal_data.get("action", "").upper()
            network = signal_data.get("network", "")
            exchange = signal_data.get("exchange", "").lower()
            symbol = signal_data.get("symbol", "")

            # Action validation
            if action not in ["BUY", "SELL"]:
                self.logger().warning(f"⚠️ Invalid action: {action}")
                return False

            # Network validation
            if network not in self.supported_networks:
                self.logger().warning(f"⚠️ Unsupported network: {network}")
                self.logger().info(f"📋 Supported: {', '.join(self.supported_networks)}")
                return False

            # Exchange validation
            if self._is_cex_exchange(exchange):
                # CEX validation - simple symbol check
                if not symbol or len(symbol) < 2:
                    self.logger().warning(f"⚠️ Invalid CEX symbol: {symbol}")
                    return False
            else:
                # DEX validation
                exchange = signal_data.get("exchange", "").lower()

                # Jupiter router doesn't need pool configuration - it finds routes dynamically
                if exchange == "jupiter":
                    # Basic symbol format check for Jupiter
                    if not symbol or len(symbol) < 3:
                        self.logger().warning(f"⚠️ Invalid DEX symbol: {symbol}")
                        return False
                    self.logger().debug(f"✅ Jupiter router validation passed: {symbol}")
                else:
                    # Other DEXs need pool configuration
                    if network not in self.pool_configurations:
                        self.logger().warning(f"⚠️ No pools configured for {network}")
                        return False

                    # Basic symbol format check
                    if not symbol or len(symbol) < 3:
                        self.logger().warning(f"⚠️ Invalid DEX symbol: {symbol}")
                        return False

                    # For traditional DEXs, verify pool exists (simplified check)
                    if not self._has_pool_configured(signal_data):
                        self.logger().warning(f"⚠️ No pool available for {symbol} on {network}")
                        return False

            # Daily limits validation
            if self.daily_trade_count >= self.max_daily_trades:
                self.logger().warning(f"⚠️ Daily trade limit reached: {self.daily_trade_count}/{self.max_daily_trades}")
                return False

            if self.daily_volume >= self.max_daily_volume:
                self.logger().warning(f"⚠️ Daily volume limit reached: ${self.daily_volume}/${self.max_daily_volume}")
                return False

            self.logger().debug(f"✅ Valid signal: {action} {symbol} on {network}/{exchange}")
            return True

        except Exception as e:
            self.logger().error(f"❌ Validation error: {e}")
            return False

    @staticmethod
    def _is_cex_exchange(exchange: str) -> bool:
        """Check if exchange is CEX"""
        return exchange in ["coinbase", "coinbase_advanced_trade", "cex", "hyperliquid", "hyperliquid_perpetual"]

    def _has_pool_configured(self, signal_data: Dict[str, Any]) -> bool:
        """
        Check if pool exists in configuration (synchronous)
        Gateway 2.9 - checks loaded configuration only
        """
        try:
            network = signal_data.get("network")
            exchange = signal_data.get("exchange", "").lower()
            symbol = signal_data.get("symbol")

            # Parse symbol to get pool key
            base_token, quote_token = self._parse_symbol_tokens(symbol, network)
            pool_key = f"{base_token}-{quote_token}"

            # Check configuration directly (no API call)
            if network in self.pool_configurations:
                network_pools = self.pool_configurations[network]

                # Check specific exchange if provided
                if exchange and exchange in network_pools:
                    exchange_pools = network_pools[exchange]
                    for pool_type in ['clmm', 'amm']:
                        if pool_type in exchange_pools and pool_key in exchange_pools[pool_type]:
                            return True

                # Check all exchanges
                for connector, pools in network_pools.items():
                    for pool_type in ['clmm', 'amm']:
                        if pool_type in pools and pool_key in pools[pool_type]:
                            return True

            return False

        except Exception:
            return False  # Let Gateway handle unknown cases

    def _validate_symbol_format(self, symbol: str) -> bool:
        """
        Validate trading symbol format
        Accepts various formats: ETHUSDC, ETH-USDC, ETH/USDC
        """
        try:
            if not symbol or len(symbol) < 3:
                return False

            # Allow alphanumeric characters, hyphens, slashes, and underscores

            if not re.match(r'^[A-Za-z0-9\-/_]+$', symbol):
                return False

            # Try to parse the symbol to see if it makes sense
            if "-" in symbol or "/" in symbol or "_" in symbol:
                # Already has separator, should have exactly 2 parts
                for separator in ["-", "/", "_"]:
                    if separator in symbol:
                        parts = symbol.split(separator)
                        if len(parts) == 2 and all(len(part) >= 2 for part in parts):
                            return True
            else:
                # Combined format like ETHUSDC - should be at least 6 characters
                if len(symbol) >= 6:
                    return True

            return False

        except Exception as format_error:
            self.logger().error(f"❌ Symbol format validation error: {format_error}")
            return False

    class ConfigurationError(Exception):
        """
        Specific exception for Gateway configuration errors
        Provides detailed context about configuration failures
        """

        def __init__(self, message: str, error_code: str = "CONFIG_ERROR", details: Dict = None):
            """
            Initialize configuration error with context

            Args:
                message: Error message
                error_code: Error code for categorization (default: CONFIG_ERROR)
                details: Additional error details as dictionary
            """
            super().__init__(message)
            self.message = message
            self.error_code = error_code
            self.details = details or {}
            self.timestamp = datetime.now().isoformat()

        def __str__(self):
            """String representation with full context"""
            base_msg = f"[{self.error_code}] {self.message}"

            if self.details:
                details_str = "\nDetails:"
                for key, value in self.details.items():
                    details_str += f"\n  - {key}: {value}"
                base_msg += details_str

            return base_msg

    def _setup_mqtt(self) -> None:
        """Set up MQTT client connection"""
        try:
            if not MQTT_AVAILABLE:
                self.logger().error("❌ MQTT not available - install paho-mqtt")
                return

            # Try modern paho-mqtt first, fallback for older versions
            try:
                self.mqtt_client = mqtt.Client()
            except (TypeError, AttributeError):
                self.mqtt_client = mqtt.Client()

            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            self.mqtt_client.on_message = self._on_mqtt_message

            self.logger().info(f"🔗 Connecting to MQTT broker at {self.mqtt_host}:{self.mqtt_port}")
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, 60)
            self.mqtt_client.loop_start()

        except Exception as mqtt_error:
            self.logger().error(f"❌ MQTT setup failed: {mqtt_error}")

    def _on_mqtt_connect(self, _client, _userdata, _flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.mqtt_connected = True
            self.logger().info("✅ MQTT client connected successfully")

            for topic in self.mqtt_topics:
                self.mqtt_client.subscribe(topic)
                self.logger().info(f"📡 Subscribing to topic: {topic}")
        else:
            self.logger().error(f"❌ MQTT connection failed with code: {rc}")

    def _on_mqtt_disconnect(self, _client, _userdata, rc):
        """MQTT disconnection callback"""
        self.mqtt_connected = False
        self.logger().warning(f"⚠️ MQTT broker disconnected with code: {rc}")

    def _on_mqtt_message(self, _client, _userdata, msg):
        """MQTT message callback - updated to use consolidated method"""
        try:
            _topic = msg.topic
            payload = msg.payload.decode('utf-8')

            self.logger().info(f"📨 Received MQTT message on {_topic}")

            signal_data = json.loads(payload)
            self.logger().info(f"📊 Signal data: {signal_data}")

            # Enhanced validation with Gateway configuration
            if self._validate_signal_with_gateway(signal_data):
                self.signal_queue.append((signal_data, _topic))
                self.logger().info(
                    f"✅ Valid trading signal queued: {signal_data.get('action')} {signal_data.get('symbol')}")
            else:
                self.logger().warning(f"⚠️ Invalid signal format: {signal_data}")

        except json.JSONDecodeError:
            self.logger().error(f"❌ Invalid JSON in MQTT message: {msg.payload.decode('utf-8', errors='ignore')}")
        except Exception as msg_error:
            self.logger().error(f"❌ MQTT message processing error: {msg_error}")

    def _validate_signal_with_gateway(self, signal_data: Dict[str, Any]) -> bool:
        """Enhanced signal validation using Gateway configuration"""
        try:
            # Basic field validation
            required_fields = ["action", "symbol", "exchange", "network"]
            for field in required_fields:
                if field not in signal_data:
                    self.logger().error(f"❌ Missing required field: {field} in signal: {signal_data}")
                    return False

            # Action validation
            action = signal_data.get("action", "").upper()
            if action not in ["BUY", "SELL"]:
                self.logger().error(f"❌ Invalid action: {action}")
                return False

            # Network validation
            network = signal_data.get("network", "")
            if network not in self.supported_networks:
                self.logger().error(f"❌ Unsupported network: {network}")
                return False

            # symbol validation for CEX vs DEX
            symbol = signal_data.get("symbol", "")
            exchange = signal_data.get("exchange", "").lower()

            if not symbol:
                self.logger().error("❌ Empty symbol in signal")
                return False

            # CEX-specific validation (more lenient)
            if exchange in ["coinbase", "coinbase_advanced_trade", "cex"]:
                # For CEX, allow simple symbols like "ETH" or "BTC"
                if len(symbol) >= 2 and symbol.isalpha():
                    self.logger().debug(f"✅ CEX symbol validation passed: {symbol}")
                    return True
                else:
                    self.logger().error(f"❌ Invalid CEX symbol format: {symbol}")
                    return False
            else:
                # DEX validation (existing logic)
                if not self._validate_symbol_format(symbol):
                    self.logger().error(f"❌ Invalid DEX symbol format: {symbol}")
                    return False

            self.logger().info(f"✅ Signal validation passed: {action} {symbol} on {network}")
            return True

        except Exception as validation_error:
            self.logger().error(f"❌ Signal validation error: {validation_error}")
            return False

    async def _initialize_cex_connector(self):
        """
        CEX initialization that just works without connector spam
        """
        try:
            # Skip if already initialized
            if hasattr(self, '_cex_init_completed') and self._cex_init_completed:
                return

            self.logger().info(f"🔍 Looking for CEX connector: {self.cex_exchange_name}")

            # Find the connector
            if self.cex_exchange_name in self.connectors:
                self.cex_connector = self.connectors[self.cex_exchange_name]
                self.logger().info(f"✅ Found {self.cex_exchange_name} in connectors")
            elif self.app and hasattr(self.app, '_markets') and self.app._markets:
                if self.cex_exchange_name in self.app._markets:
                    self.cex_connector = self.app._markets[self.cex_exchange_name]
                    self.connectors[self.cex_exchange_name] = self.cex_connector
                    self.logger().info(f"✅ Found {self.cex_exchange_name} in app._markets")

            if not self.cex_connector:
                self.logger().warning("⚠️ CEX connector not found - CEX trading disabled")
                self.cex_enabled = False
                self._cex_init_completed = True
                return

            # Wait a fixed time for order book subscriptions
            self.logger().info("⏳ Waiting for CEX order book subscriptions...")
            await asyncio.sleep(1)

            # Mark as ready
            self.cex_ready = True
            self.cex_enabled = True
            self._cex_init_completed = True
            self.logger().info(f"✅ CEX connector ready for trading: {self.cex_exchange_name}")

            # Test basic functionality
            await self._test_cex_functionality()

        except Exception as cex_error:
            self.logger().error(f"❌ CEX initialization error: {cex_error}")
            self.cex_enabled = False
            self._cex_init_completed = True

    async def _ensure_cex_ready(self, timeout: float = 10.0) -> bool:
        """
        Ensure CEX connector is fully ready before trading

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if ready, False if timeout
        """
        if not self.cex_connector:
            self.logger().error("❌ CEX connector not available")
            return False

        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check basic readiness flag
            if not self.cex_ready:
                await asyncio.sleep(0.5)
                continue

            # Try to get balances as a readiness test
            try:
                balances = self.cex_connector.get_all_balances()
                if asyncio.iscoroutine(balances):
                    balances = await balances

                # If we get a valid response (even empty dict), we're ready
                if balances is not None and isinstance(balances, dict):
                    self.logger().debug("✅ CEX connector verified ready")
                    return True

            except Exception as e:
                self.logger().debug(f"CEX readiness check failed: {e}")

            await asyncio.sleep(0.5)

        self.logger().warning(f"⚠️ CEX connector not ready after {timeout}s")
        return False

    async def _test_cex_functionality(self):
        """Quick test to confirm CEX is working"""
        try:
            # Test balances
            balances = self.cex_connector.get_all_balances()
            if asyncio.iscoroutine(balances):
                balances = await balances

            if balances:
                non_zero_balances = {k: v for k, v in balances.items() if v > 0}
                if non_zero_balances:
                    balance_tokens = list(non_zero_balances.keys())[:5]
                    self.logger().info(f"💰 CEX Balances available: {balance_tokens}")
                else:
                    self.logger().info("💰 CEX connected (ready for funding)")

            # Test order book
            order_book = self.cex_connector.get_order_book("ETH-USD")
            if order_book:
                bid = order_book.get_price(False)
                ask = order_book.get_price(True)
                if bid > 0 and ask > 0:
                    self.logger().info(f"📊 Order book test: ETH ${float(bid):.2f} / ${float(ask):.2f}")
                    return True

            self.logger().info("📊 CEX connected successfully")
            return True

        except Exception as test_error:
            self.logger().info(f"💰 CEX connected (test deferred: {str(test_error)[:30]}...)")
            return True  # Don't fail on test errors

    def _count_active_order_books(self) -> int:
        """Count active order book subscriptions"""
        try:
            if not self.cex_connector:
                return 0

            if hasattr(self.cex_connector, 'order_book_tracker'):
                tracker = getattr(self.cex_connector, 'order_book_tracker', None)
                if tracker and hasattr(tracker, '_order_books'):
                    order_books = getattr(tracker, '_order_books', {})
                    return len(order_books)

            return 0
        except Exception:
            return 0

    def _should_use_cex(self, signal_data: Dict[str, Any]) -> bool:
        """
        Determine whether to route order to CEX or DEX
        Returns True if CEX should be used, False for DEX
        """
        # If CEX is not enabled or not ready, always use DEX
        if not self.cex_enabled or not self.cex_ready or not self.cex_connector:
            return False

        # Check if signal explicitly specifies CEX
        if signal_data.get("use_cex", False):
            return True

        # Check if exchange is explicitly set to CEX or is a direct connector (like Hyperliquid)
        exchange = signal_data.get("exchange", "").lower()
        if self._is_cex_exchange(exchange):
            return True

        # Get symbol and check if it's a CEX preferred token
        symbol = signal_data.get("symbol", "").upper()
        base_token = symbol.replace("USDC", "").replace("USD", "").replace("-", "")

        # Route to CEX for preferred tokens
        if base_token in self.cex_preferred_tokens:
            self.logger().info(f"📊 Routing {base_token} to CEX (preferred token)")
            return True

        # Route large orders to CEX if configured
        if self.use_cex_for_large_orders:
            amount = float(signal_data.get("amount", self.trade_amount))
            if amount >= self.cex_threshold_amount:
                self.logger().info(f"📊 Routing ${amount} order to CEX (above threshold)")
                return True

        # Check daily CEX limit
        if self.cex_daily_volume >= self.cex_daily_limit:
            self.logger().warning(f"⚠️ CEX daily limit reached (${self.cex_daily_limit}), using DEX")
            return False

        # Default to DEX
        return False

    def _get_supported_networks(self) -> List[str]:
        """
        Get supported networks from environment or use intelligent defaults
        """
        # Try environment variable first
        env_networks = os.getenv("HBOT_SUPPORTED_NETWORKS", "")
        if env_networks:
            networks = [network.strip() for network in env_networks.split(",")]
            self.logger().info(f"📋 Using networks from environment: {networks}")
            return networks

        # Default networks for multi-chain support
        default_networks = ["arbitrum", "polygon", "base", "mainnet", "mainnet-beta"]
        self.logger().info(f"📋 Using default networks: {default_networks}")
        return default_networks

    def _log_configuration_summary(self) -> None:
        """
        Log comprehensive configuration summary for debugging and monitoring
        Enhanced with CEX trading status and Gateway 2.9 pool details
        """
        try:
            self.logger().info("📊 === CONFIGURATION SUMMARY (Gateway 2.9) ===")
            # Gas Strategy Summary
            self.logger().info("⛽ Gas Strategy Configuration:")
            if self.gas_strategy == "adaptive":
                self.logger().info("  📈 Strategy: ADAPTIVE (always execute at market price)")
                self.logger().info(f"  📊 Buffer: +{(self.gas_buffer - 1) * 100:.0f}% above current gas")
                self.logger().info(f"  🚨 Urgency: +{(self.gas_urgency_multiplier - 1) * 100:.0f}% for critical retries")
                if self.gas_max_price_gwei > 0:
                    self.logger().info(f"  💰 Max Price: {self.gas_max_price_gwei} Gwei")
                else:
                    self.logger().info("  💰 Max Price: UNLIMITED (guaranteed execution)")
                self.logger().info("  💡 Trades will ALWAYS execute regardless of gas price")
            else:
                self.logger().info("  📈 Strategy: FIXED")
                self.logger().info(f"  📊 Buffer: {self.gas_buffer}x")
                self.logger().info(f"  📈 Retry: +{self.gas_retry_multiplier}x per attempt")

            # Token discovery summary (DEX)
            self.logger().info("💎 DEX Token Discovery Results:")
            total_tokens = 0
            for network in self.supported_networks:
                token_count = len(self.supported_tokens.get(network, []))
                total_tokens += token_count

                if token_count > 0:
                    sample_tokens = self.supported_tokens[network][:5]
                    self.logger().info(f"  🌐 {network}: {token_count} tokens (sample: {', '.join(sample_tokens)})")
                else:
                    self.logger().warning(f"  ⚠️ {network}: No tokens discovered")

            # Pool configuration summary (DEX) - Gateway 2.9 structure
            self.logger().info("🏊 DEX Pool Configuration Results (Gateway 2.9):")
            pool_total = 0
            for network in self.pool_configurations:
                network_pools = 0
                for connector_name, connector_config in self.pool_configurations[network].items():
                    if isinstance(connector_config, dict):
                        for pool_type in ["amm", "clmm"]:
                            if pool_type in connector_config:
                                pools = connector_config[pool_type]
                                if isinstance(pools, dict):
                                    network_pools += len(pools)

                if network_pools > 0:
                    self.logger().info(f"  🌐 {network}: {network_pools} pools configured")
                    pool_total += network_pools
                else:
                    self.logger().debug(f"  📋 {network}: No pools configured")

            # CEX Configuration Summary
            self.logger().info("📈 CEX Trading Configuration:")
            if self.cex_enabled:
                # Basic CEX config
                self.logger().info(f"  🏛️ Exchange: {self.cex_exchange_name}")

                # Trading pairs from environment variable
                cex_pairs = self.markets.get(self.cex_exchange_name, [])
                self.logger().info(f"  💱 Trading Pairs: {len(cex_pairs)} configured")
                if len(cex_pairs) <= 5:
                    self.logger().info(f"  💱 Pairs: {cex_pairs}")
                else:
                    self.logger().info(f"  💱 Pairs: {cex_pairs[:5]} (and {len(cex_pairs) - 5} more)")

                # Routing configuration
                self.logger().info(f"  🎯 Preferred Tokens: {self.cex_preferred_tokens}")
                self.logger().info(f"  💰 Daily Limit: ${self.cex_daily_limit}")
                self.logger().info(f"  📊 Large Order Threshold: ${self.cex_threshold_amount} -> CEX")

                # Predictive selling configuration
                self.logger().info("🎯 CEX Predictive Selling:")
                if self.cex_predictive_enabled:
                    self.logger().info("  ✅ Enabled")
                    self.logger().info(f"  ⏱️ Window: {self.cex_predictive_window} seconds")
                    self.logger().info(f"  💰 Fee Estimate: {self.cex_fee_estimate}%")
                else:
                    self.logger().info("  ❌ Disabled")

                # Connection status
                if self.cex_connector:
                    connection_status = self._get_cex_connection_status()
                    ready_status = "✅ Ready" if self.cex_ready else "⏳ Initializing"
                    self.logger().info(f"  🔌 Connection: {connection_status} ({ready_status})")

                    # Order book status
                    order_book_count = 0
                    if hasattr(self.cex_connector, 'order_book_tracker'):
                        tracker = getattr(self.cex_connector, 'order_book_tracker', None)
                        if tracker and hasattr(tracker, '_order_books'):
                            order_books = getattr(tracker, '_order_books', {})
                            order_book_count = len(order_books)

                    if order_book_count > 0:
                        self.logger().info(f"  📊 Order Books: {order_book_count} active subscriptions")
                    else:
                        self.logger().info("  📊 Order Books: Initializing...")

                    # Environment variables source
                    self.logger().info("  📋 Config Source: HBOT_CEX_TRADING_PAIRS environment variable")

                else:
                    self.logger().info("  🔌 Connection: Connector not found")
            else:
                cex_disabled_reason = "HBOT_CEX_ENABLED=false" if not self.cex_enabled else "Connector unavailable"
                self.logger().info(f"  ❌ CEX Trading Disabled ({cex_disabled_reason})")

            # Trading configuration summary (Universal)
            self.logger().info("💰 Universal Trading Configuration:")
            self.logger().info(f"  📈 BUY Amount: ${self.trade_amount} (from HBOT_TRADE_AMOUNT)")
            self.logger().info(f"  📉 SELL Percentage: {self.sell_percentage}% (from HBOT_SELL_PERCENTAGE)")
            self.logger().info(f"  🛡️ SOL Minimum Balance: {self.min_sol_balance} SOL (from HBOT_MIN_SOL_BALANCE)")
            self.logger().info(f"  🚦 Daily Limits: {self.max_daily_trades} trades, ${self.max_daily_volume} volume")
            self.logger().info(f"  ⚡ Slippage Tolerance: {self.slippage_tolerance}% (DEX only)")

            # Routing Logic Summary
            self.logger().info("🔄 Trade Routing Logic:")
            if self.cex_enabled:
                self.logger().info(f"  📊 CEX for preferred tokens: {self.cex_preferred_tokens}")
                if self.use_cex_for_large_orders:
                    self.logger().info(f"  📊 CEX for orders ≥ ${self.cex_threshold_amount}")
                self.logger().info("  🌊 DEX for all other trades")
            else:
                self.logger().info("  🌊 DEX only (CEX disabled)")

            # Overall capability summary
            cex_capability = f"{len(self.markets.get(self.cex_exchange_name, []))} CEX pairs" if self.cex_enabled else "CEX disabled"
            self.logger().info(
                f"🎯 TOTAL CAPABILITY: {total_tokens} DEX tokens across {len(self.supported_networks)} networks "
                f"with {pool_total} pools + {cex_capability}")

            # Daily activity summary
            if hasattr(self, 'daily_trade_count') and hasattr(self, 'daily_volume'):
                self.logger().info(f"📈 Today's Activity: {self.daily_trade_count} trades, ${self.daily_volume} volume")

            self.logger().info("📊 === END SUMMARY ===")

        except Exception as summary_error:
            self.logger().warning(f"⚠️ Error logging configuration summary: {summary_error}")

    def _get_cex_connection_status(self) -> str:
        """Enhanced connection status"""
        if not self.cex_connector:
            return "Not Found"

        # Count order books
        order_book_count = self._count_active_order_books()

        # Check network status
        status = "Connected"
        if hasattr(self.cex_connector, '_network_status'):
            network_status = getattr(self.cex_connector, '_network_status', None)
            if network_status:
                status = str(network_status).replace('NetworkStatus.', '')

        if order_book_count > 0:
            return f"{status} ({order_book_count} order books)"
        else:
            return status

    async def _process_trading_signal(self, signal_data: Dict[str, Any], topic: str = None) -> None:
        """
        Process trading signal - Gateway 2.9 OPTIMIZED
        Routes to CEX or DEX based on configuration
        """
        try:
            # Extract signal details
            action = signal_data.get("action", "").upper()
            symbol = signal_data.get("symbol", "")
            network = signal_data.get("network", "arbitrum")
            exchange = signal_data.get("exchange", "uniswap")

            self.logger().info(f"🎯 Processing: {action} {symbol} on {network}/{exchange}")

            # Core validations
            if not self._initialized:
                self.logger().warning("⚠️ Strategy not initialized")
                return

            if not self._validate_trading_signal(signal_data):
                self.logger().warning("⚠️ Invalid signal")
                return

            if not self._check_daily_limits():
                self.logger().warning("⚠️ Daily limits reached")
                return

            # Route to CEX or DEX
            if self._should_use_cex(signal_data):
                success = await self._route_to_cex(action, symbol, signal_data)
            else:
                success = await self._route_to_dex(action, symbol, network, exchange, signal_data)

            # Update statistics
            if success:
                self._update_daily_statistics(action)
                self.successful_trades += 1
                self.logger().debug(f"✅ Trade success recorded. Total successful: {self.successful_trades}")
            else:
                self.failed_trades += 1
                self.logger().debug(f"❌ Trade failure recorded. Total failed: {self.failed_trades}")

        except Exception as e:
            self.logger().error(f"❌ Signal processing error: {e}")

            self.logger().error(traceback.format_exc())

    async def _route_to_cex(self, action: str, symbol: str, signal_data: Dict) -> bool:
        """Helper: Route trade to CEX"""
        self.logger().info(f"📈 CEX routing: {self.cex_exchange_name}")

        if action == "BUY":
            return await self._execute_cex_buy(
                symbol,
                float(signal_data.get("amount", self.trade_amount))
            )
        elif action == "SELL":
            return await self._execute_cex_sell(
                symbol,
                float(signal_data.get("percentage", self.sell_percentage))
            )
        else:
            self.logger().error(f"❌ Unsupported CEX action: {action}")
            return False

    async def _route_to_dex(self, action: str, symbol: str, network: str,
                            exchange: str, signal_data: Dict) -> bool:
        """Helper: Route trade to DEX with Gateway 2.9 pool resolution"""
        self.logger().info(f"🌊 DEX routing: {network}/{exchange}")

        # Parse tokens
        base_token, quote_token = self._parse_symbol_tokens(symbol, network)
        pool_key = f"{base_token}-{quote_token}"

        # Extract pool_type from signal if provided
        pool_type = signal_data.get("pool_type")  # Get pool type from webhook

        # Gateway 2.9: Get pool info with type
        pool_info = await self._get_pool_info(
            network,
            exchange,
            pool_key,
            signal_data.get("pool"),  # Use provided pool if any
            pool_type  # Pass pool type from webhook
        )

        pool_address = pool_info['address'] if pool_info else None

        if pool_address:
            self.logger().info(f"✅ Pool found: {pool_address[:10]}... ({pool_info['type']})")
        else:
            self.logger().info("🔄 No pool configured, Gateway will auto-select")

        # Execute trade
        if action == "BUY":
            return await self._execute_buy_trade(
                symbol=symbol,
                amount=signal_data.get("amount", self.trade_amount),
                network=network,
                exchange=exchange,
                pool=pool_address
            )
        elif action == "SELL":
            return await self._execute_sell_trade(
                symbol=symbol,
                percentage=signal_data.get("percentage", self.sell_percentage),
                network=network,
                exchange=exchange,
                pool=pool_address,
                pool_type=pool_type  # Pass pool_type from webhook
            )
        else:
            self.logger().error(f"❌ Unsupported action: {action}")
            return False

    def _update_daily_statistics(self, action: str):
        """Helper: Update daily trade statistics"""
        self.daily_trade_count += 1
        if action == "BUY":
            self.daily_volume += self.trade_amount
        self.logger().info(f"📊 Daily: {self.daily_trade_count} trades, ${self.daily_volume} volume")

    async def _execute_cex_buy(self, symbol: str, usd_amount: float) -> bool:
        """
        Execute buy order on CEX with enhanced tracking for predictive selling
        """
        try:
            if not await self._ensure_cex_ready():
                self.logger().error("❌ CEX connector not ready for trading")
                return False

            base_token = self._extract_base_token_from_symbol(symbol)
            trading_pair = f"{base_token}-USD"

            self.logger().info(f"📈 CEX BUY: ${usd_amount:.2f} worth of {trading_pair}")

            # Ensure minimum order size
            if usd_amount < self.cex_min_order_size:
                usd_amount = self.cex_min_order_size
                self.logger().info(f"📊 Adjusted to minimum order size: ${usd_amount:.2f}")

            # Get order book
            order_book = self.cex_connector.get_order_book(trading_pair)
            if not order_book:
                self.logger().error(f"❌ No order book available for {trading_pair}")
                return False

            ask_price_raw = order_book.get_price(True)
            ask_price_decimal = Decimal(str(ask_price_raw)) if not isinstance(ask_price_raw, Decimal) else ask_price_raw

            # Calculate expected amount
            usd_amount_decimal = Decimal(str(usd_amount))
            expected_amount = usd_amount_decimal / ask_price_decimal

            # Account for fees (Coinbase typically 0.5-0.6% for market orders)
            fee_multiplier = Decimal("1.0")  # 1.5% safety margin
            expected_amount_after_fees = expected_amount * fee_multiplier
            expected_amount_after_fees = expected_amount_after_fees.quantize(Decimal('0.00000001'))

            # Place the buy order
            order_id = self.cex_connector.buy(
                trading_pair=trading_pair,
                amount=expected_amount,  # Order the full amount (fees taken from USD)
                order_type=OrderType.MARKET,
                price=ask_price_decimal,
                position_action=PositionAction.OPEN  # Required for perpetual contracts
            )

            self.logger().info(f"✅ CEX BUY order placed: {order_id}")

            # Inject price into rate oracle to help with fee calculations
            try:
                rate_oracle = RateOracle.get_instance()
                rate_oracle.set_price(trading_pair, ask_price_decimal)
                self.logger().debug(f"📊 Injected {trading_pair} = ${ask_price_decimal:.2f} into rate oracle")
            except Exception as oracle_err:
                self.logger().debug(f"⚠️ Could not inject price into rate oracle: {oracle_err}")

            # Enhanced tracking for predictive selling
            self._pending_balances[base_token] = {
                'order_id': order_id,
                'timestamp': time.time(),
                'expected_amount': float(expected_amount),
                'expected_after_fees': float(expected_amount_after_fees),
                'usd_amount': usd_amount,
                'price': float(ask_price_decimal),
                'trading_pair': trading_pair
            }

            self.logger().info(
                f"📊 Expected to receive: {float(expected_amount_after_fees):.8f} {base_token} "
                f"(after ~0.6% fees)"
            )

            self.cex_daily_volume += usd_amount
            return True

        except Exception as e:
            self.logger().error(f"❌ CEX BUY order failed: {e}")
            return False

    async def _execute_cex_sell(self, symbol: str, percentage: float) -> bool:
        """
        Execute CEX sell
        """
        try:
            if not self.cex_connector or not self.cex_ready:
                self.logger().error("❌ CEX connector not ready")
                return False

            base_token = self._extract_base_token_from_symbol(symbol)
            trading_pair = f"{base_token}-USD"

            # CHECK: Is there a recent buy we can use for predictive selling?
            use_predictive = False
            predictive_amount = Decimal("0")

            if base_token in self._pending_balances:
                pending = self._pending_balances[base_token]
                time_since_buy = time.time() - pending['timestamp']

                # If buy was less than predictive window, use PREDICTIVE SELLING
                if time_since_buy < self.cex_predictive_window:
                    use_predictive = True
                    # Use the conservative expected amount
                    expected = Decimal(str(pending['expected_after_fees']))

                    # EXTRA SAFETY: Take 99.5% of expected to account for rounding
                    safety_factor = Decimal("0.995")
                    safe_expected = expected * safety_factor

                    predictive_amount = safe_expected * Decimal(str(percentage / 100.0))
                    predictive_amount = predictive_amount.quantize(Decimal('0.00000001'))

                    self.logger().info(
                        f"🎯 PREDICTIVE SELL: Using conservative estimate from buy {time_since_buy:.1f}s ago"
                    )
                    self.logger().info(
                        f"📊 Conservative estimate: {float(safe_expected):.8f} {base_token}, "
                        f"selling {percentage}% = {float(predictive_amount):.8f}"
                    )

                    # INCREMENT PREDICTIVE ATTEMPTS
                    self.predictive_stats['attempts'] += 1

            # Determine sell amount
            if use_predictive:
                sell_amount = predictive_amount
                self.logger().info("⚡ Using predictive amount (conservative estimate)")

            else:
                # Normal balance check for older trades
                self.logger().info(f"📊 Buy is older than {self.cex_predictive_window}s, checking actual balance...")

                try:
                    # Detect if this is a perpetual connector (positions) or spot connector (balances)
                    if isinstance(self.cex_connector, PerpetualDerivativePyBase):
                        # PERPETUAL CONNECTOR: Check positions instead of balances
                        self.logger().info("📊 Perpetual connector detected - checking positions...")

                        positions = self.cex_connector.account_positions

                        # Sum up all positions for this trading pair (LONG + SHORT if needed)
                        total_position = Decimal("0")
                        for pos_key, position in positions.items():
                            if position.trading_pair == trading_pair:
                                # For perpetual, use absolute value of position amount
                                total_position += abs(position.amount)
                                self.logger().info(
                                    f"📊 Found position: {position.trading_pair} "
                                    f"side={position.position_side} amount={abs(position.amount)}"
                                )

                        if total_position <= 0:
                            self.logger().warning(f"⚠️ No {base_token} position to sell")
                            return False

                        sell_amount = total_position * Decimal(str(percentage / 100.0))
                        sell_amount = sell_amount.quantize(Decimal('0.00000001'))

                        self.logger().info(
                            f"📊 Total position: {float(total_position):.8f} {base_token}, "
                            f"selling {percentage}% = {float(sell_amount):.8f}"
                        )

                    else:
                        # SPOT CONNECTOR: Check balances (existing logic)
                        self.logger().info("📊 Spot connector detected - checking balances...")

                        balances = self.cex_connector.get_all_balances()
                        if asyncio.iscoroutine(balances):
                            balances = await balances

                        if not balances or not isinstance(balances, dict):
                            self.logger().error("❌ Could not get balances")
                            return False

                        base_balance = balances.get(base_token, Decimal("0"))

                        if base_balance <= 0:
                            self.logger().warning(f"⚠️ No {base_token} balance to sell")
                            return False

                        sell_amount = base_balance * Decimal(str(percentage / 100.0))
                        sell_amount = sell_amount.quantize(Decimal('0.00000001'))

                        self.logger().info(
                            f"📊 Actual balance: {float(base_balance):.8f} {base_token}, "
                            f"selling {percentage}% = {float(sell_amount):.8f}"
                        )

                except Exception as e:
                    self.logger().error(f"❌ Balance check failed: {e}")
                    return False

            # Get current price
            order_book = self.cex_connector.get_order_book(trading_pair)
            if not order_book:
                self.logger().error("❌ No order book available")
                return False

            bid_price = order_book.get_price(False)
            if not isinstance(bid_price, Decimal):
                bid_price = Decimal(str(bid_price))

            # Validate minimum order size
            usd_value = sell_amount * bid_price
            min_order_size = Decimal(str(self.cex_min_order_size))

            if usd_value < min_order_size:
                if use_predictive:
                    self.logger().warning(
                        f"⚠️ Predictive amount too small (${float(usd_value):.2f} < ${self.cex_min_order_size})"
                    )
                else:
                    self.logger().warning("⚠️ Order too small for minimum size")
                return False

            # EXECUTE THE SELL ORDER
            self.logger().info(
                f"📉 CEX SELL: {float(sell_amount):.8f} {base_token} "
                f"(${float(usd_value):.2f}) {'[PREDICTIVE]' if use_predictive else '[CONFIRMED]'}"
            )

            try:
                order_id = self.cex_connector.sell(
                    trading_pair=trading_pair,
                    amount=sell_amount,
                    order_type=OrderType.MARKET,
                    price=bid_price,
                    position_action=PositionAction.CLOSE  # Required for perpetual contracts
                )

                self.logger().info(f"✅ CEX SELL order placed: {order_id}")

                # Inject price into rate oracle to help with fee calculations
                try:
                    rate_oracle = RateOracle.get_instance()
                    rate_oracle.set_price(trading_pair, bid_price)
                    self.logger().debug(f"📊 Injected {trading_pair} = ${bid_price:.2f} into rate oracle")
                except Exception as oracle_err:
                    self.logger().debug(f"⚠️ Could not inject price into rate oracle: {oracle_err}")

                # TRACK SUCCESS
                if use_predictive:
                    self.predictive_stats['successes'] += 1

                    # Log stats every 10 predictive trades
                    if self.predictive_stats['attempts'] % 10 == 0:
                        self.log_predictive_stats()

                # Clean up
                if base_token in self._pending_balances:
                    del self._pending_balances[base_token]

                # Clean up position tracking
                if base_token in self.active_positions:
                    del self.active_positions[base_token]
                    self.logger().info(f"📝 CEX Position closed: {base_token}")

                self.cex_daily_volume += float(usd_value)
                return True

            except Exception as order_error:
                if use_predictive:
                    self.predictive_stats['failures'] += 1

                    self.logger().error(
                        f"❌ Predictive sell failed: {order_error}"
                    )

                    # Log what we tried vs what might be available
                    self.logger().info(f"📊 Debug: Tried to sell {float(sell_amount):.8f}")
                    self.logger().info("📊 Debug: Check actual balance to see discrepancy")

                    # Log stats after failure
                    self.log_predictive_stats()

                else:
                    self.logger().error(f"❌ CEX SELL order failed: {order_error}")

                return False

        except Exception as e:
            self.logger().error(f"❌ CEX SELL error: {e}")
            return False

    def log_predictive_stats(self):
        """Log statistics about predictive selling performance"""
        if self.predictive_stats['attempts'] > 0:
            success_rate = (self.predictive_stats['successes'] / self.predictive_stats['attempts']) * 100

            self.logger().info(
                "📊 === PREDICTIVE SELLING STATS ==="
            )
            self.logger().info(
                f"   Total Attempts: {self.predictive_stats['attempts']}"
            )
            self.logger().info(
                f"   Successes: {self.predictive_stats['successes']} ({success_rate:.1f}%)"
            )
            self.logger().info(
                f"   Failures: {self.predictive_stats['failures']}"
            )

            if self.predictive_stats['fallback_success'] > 0:
                fallback_rate = (self.predictive_stats['fallback_success'] /
                                 (self.predictive_stats['failures'] + self.predictive_stats['fallback_success'])) * 100
                self.logger().info(
                    f"   99% Fallback Success: {self.predictive_stats['fallback_success']} "
                    f"({fallback_rate:.1f}% recovery rate)"
                )

            # Performance assessment
            if success_rate >= 95:
                self.logger().info("   🎯 Performance: EXCELLENT")
            elif success_rate >= 90:
                self.logger().info("   ✅ Performance: GOOD")
            elif success_rate >= 80:
                self.logger().info("   ⚠️ Performance: NEEDS TUNING (consider adjusting fee estimate)")
            else:
                self.logger().info("   ❌ Performance: POOR (check fee settings)")

            self.logger().info("   =========================")

    def _extract_base_token_from_symbol(self, symbol: str) -> str:
        """
        Extract base token from any symbol format - OPTIMIZED for all Coinbase tokens
        Supports any token symbol, not just ETH/BTC
        """
        try:
            # Remove common suffixes to get the base token
            symbol_upper = symbol.upper()

            # Handle different symbol formats
            if "-" in symbol_upper:
                # Format: ETH-USD, BTC-USD, SOL-USD, etc.
                return symbol_upper.split("-")[0]
            elif "/" in symbol_upper:
                # Format: ETH/USD, BTC/USD, SOL/USD, etc.
                return symbol_upper.split("/")[0]
            elif symbol_upper.endswith("USD"):
                # Format: ETHUSD, BTCUSD, SOLUSD, etc.
                return symbol_upper[:-3]
            elif symbol_upper.endswith("USDC"):
                # Format: ETHUSDC, BTCUSDC, SOLUSDC, etc.
                return symbol_upper[:-4]
            else:
                # Assume it's already the base token (ETH, BTC, SOL, ADA, etc.)
                return symbol_upper

        except Exception as e:
            self.logger().error(f"❌ Error extracting base token from {symbol}: {e}")
            # Fallback to original symbol
            return symbol.upper()

    def _update_trade_statistics(self, trade_request: Dict):
        """Update daily trading statistics"""
        try:
            # Update volume based on trade direction
            amount = Decimal(str(trade_request.get("amount", 0)))
            base_token = trade_request.get("baseToken", "")

            # For USDC/USDT trades, amount is already in USD
            if base_token in ["USDC", "USDT", "DAI"]:
                self.daily_volume += amount
            else:
                # For other tokens, we'd need price data for accurate volume
                # For now, just log that we executed a trade
                self.logger().debug(f"📊 Trade executed: {amount} {base_token}")

            # Increment trade counter
            self.daily_trade_count += 1

        except Exception as e:
            self.logger().debug(f"Could not update statistics: {e}")

    def _reset_daily_counters_if_needed(self):
        """
        Reset daily trading counters if new day started
        ENHANCED to log and reset predictive stats
        """
        try:
            current_date = datetime.now(timezone.utc).date()

            if not hasattr(self, '_current_date'):
                self._current_date = current_date

            if current_date != self._current_date:
                self.logger().info(f"📅 New day started: {current_date}")
                self.logger().info(
                    f"📊 Previous day stats: {self.daily_trade_count} trades, ${self.daily_volume} volume")

                # Log final predictive stats for the day
                if self.predictive_stats['attempts'] > 0:
                    self.logger().info("📊 Daily Predictive Selling Summary:")
                    self.log_predictive_stats()

                    # Reset predictive stats for new day
                    self.predictive_stats = {
                        'attempts': 0,
                        'successes': 0,
                        'failures': 0,
                        'fallback_success': 0
                    }

                # Reset counters
                self.daily_trade_count = 0
                self.daily_volume = Decimal("0")
                self._current_date = current_date

                self.logger().info("🔄 Daily counters reset")

        except Exception as reset_error:
            self.logger().error(f"❌ Error resetting daily counters: {reset_error}")

    async def _execute_buy_trade(self, symbol: str, amount: Decimal, network: str, exchange: str,
                                 pool: str = None) -> bool:
        """
        Execute BUY trade - Gateway 2.9 SIMPLIFIED version
        Leverages flat pool structure and explicit pool types
        """
        try:
            # Parse symbol ONCE using existing method
            base_token, quote_token = self._parse_symbol_tokens(symbol, network)
            pool_key = f"{base_token}-{quote_token}"

            self.logger().info(f"📊 BUY: {pool_key} on {network}/{exchange}")

            # Determine trade amount in quote currency
            original_usd_amount = float(amount)

            if quote_token in ["USDC", "USDT", "DAI"]:
                # Already in USD equivalent
                trade_amount = float(amount)
            else:
                # Need to convert USD to quote token
                self.logger().info(f"🔄 Converting ${original_usd_amount} to {quote_token}")

                # Get quote token price
                quote_price = await self._get_token_price(quote_token, network, exchange)
                if not quote_price or quote_price <= 0:
                    self.logger().error(f"❌ Could not get {quote_token} price")
                    return False

                trade_amount = original_usd_amount / float(quote_price)
                self.logger().info(f"💱 ${original_usd_amount} = {trade_amount:.6f} {quote_token}")

            # Gateway 2.9: Simple pool lookup from flat structure
            pool_info = await self._get_pool_info(network, exchange, pool_key, pool)

            if not pool_info:
                self.logger().error(f"❌ No pool found for {pool_key}")
                return False

            pool_address = pool_info.get('address')
            pool_type = pool_info.get('type', 'amm')  # Safe access with fallback

            # Log pool info safely
            if pool_address:
                self.logger().info(f"✅ Using {pool_type.upper()} pool: {pool_address[:10]}...")
            else:
                self.logger().info(f"✅ Using {pool_type.upper()} routing (no specific pool address)")

            # Execute trade based on network
            if self._is_solana_network(network):
                success = await self._execute_solana_buy_trade(
                    base_token=base_token,
                    quote_token=quote_token,
                    network=network,
                    exchange=exchange,
                    amount=trade_amount,
                    pool_address=pool_address,
                    pool_type=pool_type,
                    original_usd_amount=original_usd_amount
                )
            else:
                success = await self._execute_evm_buy_trade(
                    base_token, network, exchange, trade_amount, pool_address
                )

            # ⭐ Track position for sell trade
            if success:
                self._track_buy_position(
                    base_token=base_token,
                    quote_token=quote_token,
                    amount_spent=trade_amount,
                    usd_value=original_usd_amount,
                    pool=pool_address,
                    pool_type=pool_type,  # Store Gateway 2.9 pool type
                    network=network,
                    exchange=exchange
                )
                self.logger().info("✅ BUY trade successful!")

            return success

        except Exception as e:
            self.logger().error(f"❌ Error executing BUY trade: {e}")
            return False

    def _track_buy_position(self, base_token: str, quote_token: str, amount_spent: float,
                            usd_value: float, pool: str, pool_type: str,
                            network: str, exchange: str):
        """
        Helper: Track buy position for intelligent sell trades
        Stores Gateway 2.9 pool type for reuse in sells
        """
        self.active_positions[base_token] = {
            'quote_token': quote_token,
            'amount_spent': amount_spent,
            'usd_value': usd_value,
            'pool': pool,
            'pool_type': pool_type,  # Gateway 2.9: Explicit pool type
            'network': network,
            'exchange': exchange,
            'timestamp': time.time(),
            'tx_signature': self._last_trade_response.get('signature') if self._last_trade_response else None
        }
        self.logger().debug(f"📝 Position tracked: {base_token} with {pool_type} pool")

    async def _get_pool_info(self, network: str, exchange: str, pool_key: str = None,
                             pool_address: str = None, pool_type: str = None) -> Optional[Dict]:
        """
        Gateway 2.9 HELPER: Get pool info from local configuration
        Accept pool_type from webhook to eliminate guessing

        Args:
            network: Network name (e.g., 'mainnet-beta', 'arbitrum')
            exchange: Exchange name (e.g., 'raydium', 'uniswap')
            pool_key: Trading pair key (e.g., 'WETH-USDC')
            pool_address: Direct pool address if known
            pool_type: Pool type from webhook ('amm' or 'clmm') - NEW PARAMETER

        Returns:
            {'address': str, 'type': 'amm'|'clmm', 'base_token': str, 'quote_token': str}
        """

        # Case 1: Pool address provided directly - just return it with type
        if pool_address:
            # If pool_type provided from webhook, use it directly
            if pool_type and pool_type in ['amm', 'clmm']:
                tokens = pool_key.split("-") if pool_key else [None, None]
                self.logger().debug(f"📊 Using provided pool {pool_address[:10]}... as {pool_type}")
                return {
                    'address': pool_address,
                    'type': pool_type,
                    'base_token': tokens[0] if len(tokens) >= 2 else None,
                    'quote_token': tokens[1] if len(tokens) >= 2 else None,
                    'pair_key': pool_key,
                    'connector': exchange
                }

            # Fallback: Search configuration if no type provided (backward compatibility)
            if network in self.pool_configurations:
                for connector, pools in self.pool_configurations[network].items():
                    if exchange and connector.lower() != exchange.lower():
                        continue

                    for p_type in ['amm', 'clmm']:
                        if p_type not in pools:
                            continue

                        for pair_key, address in pools[p_type].items():
                            if address == pool_address:
                                tokens = pair_key.split("-")
                                self.logger().debug(f"📊 Found pool {pool_address[:10]}... as {pair_key} ({p_type})")
                                return {
                                    'address': pool_address,
                                    'type': p_type,
                                    'base_token': tokens[0] if len(tokens) >= 2 else None,
                                    'quote_token': tokens[1] if len(tokens) >= 2 else None,
                                    'pair_key': pair_key,
                                    'connector': connector
                                }

            # Pool not in config - use provided or default type
            return {
                'address': pool_address,
                'type': pool_type if pool_type else 'amm',
                'base_token': None,
                'quote_token': None
            }

        # Case 2: Pool key provided - look up by trading pair with type hint
        if pool_key and network in self.pool_configurations:
            network_pools = self.pool_configurations[network]

            tokens = pool_key.split("-")
            if len(tokens) < 2:
                self.logger().warning(f"⚠️ Invalid pool key format: {pool_key}")
                return None

            # SIMPLIFIED: Trust webhook pool_type directly - no complex fallback logic needed
            if pool_type and pool_type in ['amm', 'clmm', 'router']:
                self.logger().info(f"🎯 Webhook specified pool_type: {pool_type} for {pool_key}")

                # For router types (Jupiter, 0x), don't need pool lookup
                if pool_type == 'router':
                    self.logger().info(f"📡 Router type - no pool address needed for {exchange}")
                    return {
                        'address': None,  # Router doesn't use specific pool addresses
                        'type': pool_type,
                        'base_token': tokens[0],
                        'quote_token': tokens[1],
                        'pair_key': pool_key,
                        'connector': exchange.lower() if exchange else 'unknown'
                    }

                # For AMM/CLMM, look up the exact pool address
                # Check specific exchange first
                if exchange:
                    exchange_lower = exchange.lower()
                    if exchange_lower in network_pools:
                        exchange_pools = network_pools[exchange_lower]

                        if pool_type in exchange_pools and pool_key in exchange_pools[pool_type]:
                            pool_address = exchange_pools[pool_type][pool_key]
                            self.logger().info(
                                f"✅ Found {pool_key} pool: {pool_address[:10]}... ({pool_type} on {exchange_lower})")
                            return {
                                'address': pool_address,
                                'type': pool_type,
                                'base_token': tokens[0],
                                'quote_token': tokens[1],
                                'pair_key': pool_key,
                                'connector': exchange_lower
                            }
                        else:
                            self.logger().warning(
                                f"⚠️ Pool {pool_key} not found in {exchange_lower} {pool_type} configuration")

                # If not found in specific exchange, search all exchanges
                for connector, pools in network_pools.items():
                    if pool_type in pools and pool_key in pools[pool_type]:
                        pool_address = pools[pool_type][pool_key]
                        self.logger().info(
                            f"✅ Found {pool_key} pool: {pool_address[:10]}... ({pool_type} on {connector})")
                        return {
                            'address': pool_address,
                            'type': pool_type,
                            'base_token': tokens[0],
                            'quote_token': tokens[1],
                            'pair_key': pool_key,
                            'connector': connector
                        }

                # Pool type specified but not found
                self.logger().error(f"❌ Pool {pool_key} with type {pool_type} not found in configuration")
                return None

            # MINIMAL FALLBACK: Only when no pool_type provided (legacy support)
            self.logger().warning(f"⚠️ No pool_type specified, using fallback logic for {pool_key}")

            # AUTO-DETECT ROUTER TYPES: Jupiter, 0x don't need pool lookups
            if exchange and exchange.lower() in ['jupiter', '0x']:
                self.logger().info(f"🔍 Auto-detected router type for {exchange} - no pool address needed")
                return {
                    'address': None,  # Router doesn't use specific pool addresses
                    'type': 'router',
                    'base_token': tokens[0],
                    'quote_token': tokens[1],
                    'pair_key': pool_key,
                    'connector': exchange.lower()
                }

            # Simple fallback - check both types, AMM first for most cases
            for p_type in ['amm', 'clmm']:
                if exchange:
                    exchange_lower = exchange.lower()
                    if (exchange_lower in network_pools and
                        p_type in network_pools[exchange_lower] and
                            pool_key in network_pools[exchange_lower][p_type]):
                        pool_address = network_pools[exchange_lower][p_type][pool_key]
                        self.logger().info(f"✅ Fallback found {pool_key}: {pool_address[:10]}... ({p_type})")
                        return {
                            'address': pool_address,
                            'type': p_type,
                            'base_token': tokens[0],
                            'quote_token': tokens[1],
                            'pair_key': pool_key,
                            'connector': exchange_lower
                        }

            self.logger().error(f"❌ Pool {pool_key} not found in any configuration")

        return None

    async def _get_token_price(self, token: str, network: str, exchange: str) -> Optional[float]:
        """
        Unified token price getter - simplifies price fetching
        """
        if self._is_solana_network(network):
            price = await self._get_solana_token_price(token, network)
        else:
            price = await self._get_token_price_in_usd(token, network, exchange)

        return float(price) if price else None

    async def _load_token_decimals(self) -> None:
        """
        Load token decimals from Gateway configuration files
        Single source of truth for token decimal precision
        """
        try:
            self.token_decimals = {}  # {network: {symbol: decimals}}

            gateway_conf_path = self.gateway_conf_path
            tokens_path = os.path.join(gateway_conf_path, "tokens")

            # Map network names to token files
            token_files = {
                "arbitrum": "arbitrum.json",
                "mainnet": "ethereum.json",
                "polygon": "polygon.json",
                "base": "base.json",
                "optimism": "optimism.json",
                # Add other networks as needed
            }

            for network, filename in token_files.items():
                token_file = os.path.join(tokens_path, filename)

                if os.path.exists(token_file):
                    try:
                        with open(token_file, 'r') as file:
                            tokens = json.load(file)

                        self.token_decimals[network] = {}
                        for token in tokens:
                            symbol = token.get("symbol")
                            decimals = token.get("decimals")
                            if symbol and decimals is not None:
                                self.token_decimals[network][symbol] = decimals

                        self.logger().info(
                            f"✅ Loaded decimals for {len(self.token_decimals[network])} tokens on {network}")

                    except json.JSONDecodeError as e:
                        self.logger().error(f"❌ JSON error in {filename}: {e}")

        except Exception as e:
            self.logger().error(f"❌ Error loading token decimals: {e}")

    async def _execute_solana_buy_trade(self, base_token: str, quote_token: str,
                                        network: str, exchange: str, amount: float,
                                        pool_address: str, pool_type: str,
                                        original_usd_amount: float, signal_data: dict = None) -> bool:
        """
        Execute Solana BUY trade using connector framework (event-driven approach).
        For BUY: We want to acquire $X worth of base_token using quote_token

        This method now uses connector.place_order() which:
        - Triggers OrderFilledEvent when complete
        - Automatically records to database via MarketsRecorder
        - Handles retries and timeouts internally

        Args:
            signal_data: Original signal data for tracking purposes
        """
        try:
            self.logger().info(f"🎯 BUY ${original_usd_amount} worth of {base_token} using {quote_token}")

            # Get connector for this exchange
            connector = self._get_dex_connector(exchange, pool_type)
            if not connector:
                self.logger().error(f"❌ No connector found for {exchange}/{pool_type}")
                return False

            # Get base token price to calculate how much we want to receive
            base_price = await self._get_solana_token_price(base_token, network)
            if not base_price:
                self.logger().error(f"❌ Could not get {base_token} price")
                return False

            # Calculate how much base token we should receive
            base_amount_to_receive = original_usd_amount / float(base_price)

            self.logger().info(
                f"💱 ${original_usd_amount} = {base_amount_to_receive:.6f} {base_token} @ ${base_price:.2f}")

            # For logging: calculate approximate quote token needed
            if quote_token not in ["USDC", "USDT"]:
                quote_price = await self._get_solana_token_price(quote_token, network)
                if quote_price:
                    approx_quote_needed = original_usd_amount / float(quote_price)
                    self.logger().info(f"📊 Will spend approximately {approx_quote_needed:.6f} {quote_token}")

            # Build trading pair in format base-quote
            trading_pair = f"{base_token}-{quote_token}"

            # Use the price we got directly from the DEX (not connector.get_quote_price)
            # This avoids the Coinbase rate oracle issue where RAY-USDC doesn't exist
            # The connector will get the actual execution price from the DEX when placing the order
            current_price = Decimal(str(base_price))
            self.logger().info(f"📊 Using DEX price: ${current_price:.2f} (avoiding rate oracle)")

            # Place order through connector
            self.logger().info(f"📡 Placing order: BUY {base_amount_to_receive:.6f} {base_token} with {quote_token} on {exchange}/{pool_type}")

            order_id = connector.place_order(
                is_buy=True,
                trading_pair=trading_pair,
                amount=Decimal(str(base_amount_to_receive)),
                price=current_price
            )

            self.logger().info(f"✅ Order placed with ID: {order_id} (awaiting execution)")

            # Track this order for event handling
            self._dex_order_tracking[order_id] = {
                "signal_data": signal_data or {},
                "exchange": exchange,
                "pool_type": pool_type,
                "trading_pair": trading_pair,
                "base_token": base_token,
                "quote_token": quote_token,
                "network": network,
                "pool_address": pool_address,
                "usd_value": original_usd_amount,
                "timestamp": time.time()
            }

            # Track pending order for timeout monitoring
            self.pending_orders[order_id] = {
                'timestamp': time.time(),
                'details': {
                    'symbol': trading_pair,
                    'action': 'BUY',
                    'network': network,
                    'exchange': exchange,
                    'pool_type': pool_type,
                    'usd_value': original_usd_amount
                }
            }

            # Track position (preliminary - will be updated by did_fill_order event)
            self.active_positions[base_token] = {
                'quote_token': quote_token,
                'amount_bought': base_amount_to_receive,
                'usd_value': original_usd_amount,
                'pool': pool_address,
                'pool_type': pool_type,
                'network': network,
                'exchange': exchange,
                'timestamp': time.time(),
                'order_id': order_id,
                'status': 'pending'
            }

            # Note: Order execution happens asynchronously
            # The did_fill_order() event handler will be called when the trade completes
            # MarketsRecorder will automatically persist to database
            return True

        except Exception as e:
            self.logger().error(f"❌ Solana BUY error: {e}", exc_info=True)
            return False

    async def _execute_sell_trade(self, symbol: str, percentage: Union[float, Decimal],
                                  network: str, exchange: str = "uniswap",
                                  pool: str = None, pool_type: str = None) -> bool:
        """
        Execute SELL trade - Gateway 2.9 OPTIMIZED version
        Sells percentage of token balance back to original quote token
        """
        try:
            # Parse symbol once
            base_token, quote_token = self._parse_symbol_tokens(symbol, network)
            percentage_float = float(percentage)

            # Determine actual quote token (smart position tracking)
            actual_quote_token = self._determine_quote_token(base_token, quote_token, network)

            self.logger().info(
                f"📉 SELL: {percentage_float}% of {base_token} → {actual_quote_token} "
                f"on {network}/{exchange}"
            )

            # Gateway 2.9: Get pool info if not provided
            pool_info = None
            if not pool and network in self.pool_configurations:
                # Check tracked position first for pool info
                position = self.active_positions.get(base_token, {})
                if position and position.get('pool'):
                    pool = position['pool']
                    pool_type = position.get('pool_type', 'amm')
                    pool_info = {'address': pool, 'type': pool_type}
                else:
                    # Look up pool from configuration
                    pool_key = f"{base_token}-{actual_quote_token}"
                    pool_info = await self._get_pool_info(network, exchange, pool_key, pool, pool_type)

            # Execute network-specific trade
            if self._is_solana_network(network):
                success = await self._execute_solana_sell_trade(
                    base_token, network, exchange, percentage_float,
                    pool_info['address'] if pool_info and 'address' in pool_info else pool
                )
            else:
                success = await self._execute_evm_sell_trade(
                    base_token, network, exchange, percentage_float,
                    pool_info['address'] if pool_info and 'address' in pool_info else pool
                )

            # Handle success (simplified)
            if success:
                await self._handle_sell_success(base_token, actual_quote_token, network)

            return success

        except Exception as e:
            self.logger().error(f"❌ SELL trade failed: {e}")
            return False

    def _determine_quote_token(self, base_token: str, parsed_quote: str, network: str) -> str:
        """
        Helper: Determine the actual quote token to use
        Prioritizes tracked position info over parsed symbol
        """
        # Check for tracked position (smart!)
        position = self.active_positions.get(base_token, {})
        if position and 'quote_token' in position:
            quote_token = position['quote_token']
            self.logger().debug(f"📝 Using tracked quote token: {quote_token}")
            return quote_token

        # Network-specific defaults
        if self._is_solana_network(network):
            return parsed_quote  # Use what was parsed
        else:
            return "USDC"  # EVM default

    async def _handle_sell_success(self, base_token: str, quote_token: str, network: str):
        """
        Helper: Handle successful sell completion
        Consolidates logging and cleanup
        """
        # Extract and log transaction
        if hasattr(self, '_last_trade_response') and self._last_trade_response:
            tx_hash = self._extract_transaction_hash(self._last_trade_response, network)
            if tx_hash:
                explorer_url = self._get_blockchain_explorer_url(tx_hash, network)
                self.logger().info(f"✅ SELL successful: {explorer_url}")

        # Clean up position tracking
        if base_token in self.active_positions:
            del self.active_positions[base_token]
            self.logger().debug(f"📝 Position closed: {base_token}")

        # Update statistics
        self._update_trade_statistics({
            "baseToken": base_token,
            "quoteToken": quote_token,
            "side": "SELL",
            "network": network
        })

    async def _execute_evm_buy_trade(self, base_token: str, network: str, exchange: str,
                                     amount: float, pool: str = None, signal_data: dict = None) -> bool:
        """
        Execute EVM BUY trade using connector framework (event-driven approach).
        For BUY: We want to acquire $X worth of base_token using USDC

        This method now uses connector.place_order() which:
        - Triggers OrderFilledEvent when complete
        - Automatically records to database via MarketsRecorder
        - Handles retries and gas management internally

        Args:
            signal_data: Original signal data for tracking purposes
        """
        try:
            self.logger().info(f"🎯 BUY ${amount} worth of {base_token} using USDC on {network}")

            # Determine pool_type
            pool_type = None
            if pool and network in self.pool_configurations:
                if exchange.lower() in self.pool_configurations[network]:
                    connector_pools = self.pool_configurations[network][exchange.lower()]
                    for p_type in ["clmm", "amm"]:
                        if p_type in connector_pools and pool in connector_pools[p_type].values():
                            pool_type = p_type
                            break

            # Auto-detect router exchanges
            if not pool_type and exchange.lower() in ["0x"]:
                pool_type = "router"

            # Default to AMM for pool-based exchanges
            if not pool_type:
                pool_type = "amm"

            # Get connector for this exchange (network-specific for EVM)
            connector = self._get_dex_connector(exchange, pool_type, network)
            if not connector:
                self.logger().error(f"❌ No connector found for {exchange}/{pool_type}/{network}")
                return False

            quote_token = "USDC"

            # Build trading pair in format base-quote (e.g., "WBTC-USDC", "WETH-USDC")
            trading_pair = f"{base_token}-{quote_token}"

            # Get base token price from the DEX directly (not from connector.get_quote_price)
            # This avoids the Coinbase rate oracle issue where WBTC-USDC doesn't exist on Coinbase
            try:
                base_price = await self._get_token_price_in_usd(base_token, network, exchange, pool_type)
                if not base_price:
                    self.logger().error(f"❌ Could not get {base_token} price from DEX")
                    return False

                # Calculate how much base token we can buy with our USD budget
                base_amount_to_receive = Decimal(str(amount)) / Decimal(str(base_price))

                # Quantize to appropriate decimal places based on token
                # WBTC has 8 decimals, most tokens have 18, USDC has 6
                if base_token in ['WBTC', 'BTC']:
                    # Bitcoin-based tokens: 8 decimals
                    base_amount_to_receive = base_amount_to_receive.quantize(Decimal('0.00000001'))
                elif base_token in ['USDC', 'USDT', 'DAI']:
                    # Stablecoins: 6 decimals
                    base_amount_to_receive = base_amount_to_receive.quantize(Decimal('0.000001'))
                else:
                    # Most ERC20 tokens: 18 decimals
                    base_amount_to_receive = base_amount_to_receive.quantize(Decimal('0.000000000000000001'))

                # Use the DEX price directly (avoiding rate oracle)
                current_price = Decimal(str(base_price))

                self.logger().info(
                    f"💱 ${amount} ≈ {base_amount_to_receive:.8f} {base_token} @ ${current_price:.2f} per {base_token}")
                self.logger().info(f"📊 Using DEX price: ${current_price:.2f} (avoiding rate oracle)")

            except Exception as e:
                self.logger().error(f"❌ Could not calculate trade amounts: {e}", exc_info=True)
                return False

            # Place order through connector
            # Gateway BUY expects the amount of base token (WBTC) we want to receive
            self.logger().info(
                f"📡 Placing order: BUY {base_amount_to_receive:.8f} {base_token} "
                f"(≈ ${amount} USDC) on {exchange}/{pool_type}"
            )

            order_id = connector.place_order(
                is_buy=True,  # BUY operation (buying WBTC with USDC)
                trading_pair=trading_pair,  # WBTC-USDC (natural order)
                amount=base_amount_to_receive,  # Amount of WBTC we want to receive
                price=current_price  # Price in USDC per WBTC
            )

            self.logger().info(f"✅ Order placed with ID: {order_id} (awaiting execution)")

            # Track this order for event handling
            self._dex_order_tracking[order_id] = {
                "signal_data": signal_data or {},
                "exchange": exchange,
                "pool_type": pool_type,
                "trading_pair": trading_pair,
                "base_token": base_token,
                "quote_token": quote_token,
                "network": network,
                "pool_address": pool or "",
                "usd_value": amount,
                "timestamp": time.time()
            }

            # Track pending order for timeout monitoring
            self.pending_orders[order_id] = {
                'timestamp': time.time(),
                'details': {
                    'symbol': trading_pair,
                    'action': 'BUY',
                    'network': network,
                    'exchange': exchange,
                    'pool_type': pool_type,
                    'usd_value': amount
                }
            }

            # Track position (preliminary - will be updated by did_fill_order event)
            self.active_positions[base_token] = {
                'quote_token': quote_token,
                'amount_bought': float(base_amount_to_receive),
                'usd_value': amount,
                'pool': pool,
                'pool_type': pool_type,
                'network': network,
                'exchange': exchange,
                'timestamp': time.time(),
                'order_id': order_id,
                'status': 'pending'
            }

            # Note: Order execution happens asynchronously
            # The did_fill_order() event handler will be called when the trade completes
            # MarketsRecorder will automatically persist to database
            return True

        except Exception as e:
            self.logger().error(f"❌ EVM BUY error: {e}", exc_info=True)
            return False

    # Fix for WETH (and other 18-decimal tokens) sell precision error

    async def _execute_evm_sell_trade(self, base_token: str, network: str, exchange: str, percentage: float,
                                      pool: str = None, signal_data: dict = None) -> bool:
        """
        Execute SELL trade on EVM networks using connector framework.
        For EVM SELL: Sells base token (e.g., WBTC) for quote token (e.g., USDC) using is_buy=False

        This method uses connector.place_order() which:
        - Triggers OrderFilledEvent when complete
        - Automatically records to database via MarketsRecorder
        - Handles transaction submission and monitoring

        Args:
            signal_data: Original signal data for tracking purposes
        """
        try:
            # Step 1: Determine pool and quote token from position
            position = self.active_positions.get(base_token, {})

            if position:
                # Use tracked position info
                quote_token = position.get("quote_token", "USDC")
                pool_type = position.get("pool_type", "clmm")

                if not pool and position.get("pool"):
                    pool = position["pool"]
                    self.logger().info(f"📝 Using pool from BUY position: {pool[:10] if pool else 'auto'}...")

                self.logger().info(f"📝 Closing position: {base_token} → {quote_token} ({pool_type})")
            else:
                # No position tracked - determine pool info
                self.logger().info(f"⚠️ No position tracked for {base_token}, detecting pool configuration")

                quote_token = "USDC"
                pool_type = None

                # If pool address provided, get its info
                if pool:
                    pool_info = await self._get_pool_info(network, exchange, pool_address=pool)
                    if pool_info:
                        pool_type = pool_info['type']
                        if pool_info.get('quote_token'):
                            quote_token = pool_info['quote_token']
                        self.logger().info(f"📋 Found pool config: {pool_type} pool for {quote_token}")

                # If no pool provided, find one
                else:
                    if exchange and exchange.lower() == "0x":
                        pool_type = "router"
                        pool = None
                        self.logger().info("📋 0x router detected - no pool address needed")
                    else:
                        pool_key = f"{base_token}-{quote_token}"
                        pool_info = await self._get_pool_info(network, exchange, pool_key=pool_key)

                        if pool_info:
                            pool = pool_info['address']
                            pool_type = pool_info['type']
                            if pool_info.get('quote_token'):
                                quote_token = pool_info['quote_token']

                            if pool_type == 'router' or pool is None:
                                self.logger().info(f"📋 Found {pool_type} configuration for {base_token}-{quote_token}")
                            else:
                                self.logger().info(f"📋 Found {pool_type} pool: {pool[:10]}...")
                        else:
                            self.logger().warning(f"⚠️ No pool configuration found for {base_token}-{quote_token} on {exchange}")
                            pool = None
                            pool_type = None

                # Final fallback for pool type
                if not pool_type:
                    pool_type = "clmm"
                    self.logger().info("📋 Using default CLMM for EVM trading")

            # Auto-detect pool type for router exchanges
            if exchange.lower() in ['0x']:
                pool_type = 'router'

            # Default to CLMM for pool-based exchanges
            if not pool_type:
                pool_type = "clmm"

            # Step 2: Get balance
            balance = await self._get_token_balance(base_token, network)

            if balance is None:
                balance = 0

            if not balance or balance <= 0:
                self.logger().warning(f"⚠️ No {base_token} balance to sell")
                self.active_positions.pop(base_token, None)
                return False

            # Step 3: Calculate sell amount
            sell_amount = Decimal(str(float(balance) * (percentage / 100.0)))

            self.logger().info(f"💰 Selling {sell_amount:.6f} {base_token} ({percentage}% of {balance:.6f})")

            # Step 4: Get network-specific connector
            connector = self._get_dex_connector(exchange, pool_type, network)
            if not connector:
                self.logger().error(f"❌ No connector found for {exchange}/{pool_type}/{network}")
                return False

            # Get current price from DEX (not from connector.get_quote_price to avoid rate oracle issue)
            try:
                base_price = await self._get_token_price_in_usd(base_token, network, exchange, pool_type)
                if not base_price:
                    self.logger().error(f"❌ Could not get {base_token} price from DEX")
                    return False

                # Calculate expected USDC output
                expected_usdc = sell_amount * Decimal(str(base_price))

                # Use the DEX price directly (avoiding rate oracle)
                current_price = Decimal(str(base_price))

                self.logger().info(
                    f"💱 {sell_amount:.6f} {base_token} ≈ ${expected_usdc:.2f} USDC @ ${current_price:.2f} per {base_token}")
                self.logger().info(f"📊 Using DEX price: ${current_price:.2f} (avoiding rate oracle)")

            except Exception as e:
                self.logger().error(f"❌ Could not calculate trade amounts: {e}", exc_info=True)
                return False

            # Place order through connector
            # Gateway connector handles the swap direction internally via the is_buy parameter
            # We just need to provide the trading pair in the natural format (BASE-QUOTE)
            self.logger().info(f"📡 Placing order: SELL {sell_amount:.6f} {base_token} for USDC on {exchange}/{pool_type}")

            trading_pair = f"{base_token}-{quote_token}"  # "WBTC-USDC"

            order_id = connector.place_order(
                is_buy=False,  # SELL operation (selling WBTC for USDC)
                trading_pair=trading_pair,  # WBTC-USDC
                amount=sell_amount,  # Amount of WBTC to sell
                price=current_price  # Price in USDC per WBTC
            )

            self.logger().info(f"✅ Order placed with ID: {order_id} (awaiting execution)")

            # Track this order for event handling
            self._dex_order_tracking[order_id] = {
                "signal_data": signal_data or {},
                "exchange": exchange,
                "pool_type": pool_type,
                "trading_pair": trading_pair,
                "base_token": base_token,
                "quote_token": quote_token,
                "network": network,
                "pool_address": pool or "",
                "usd_value": float(expected_usdc),
                "timestamp": time.time(),
                "is_sell": True
            }

            # Mark position for removal (will be deleted by did_fill_order event)
            if base_token in self.active_positions:
                self.active_positions[base_token]['status'] = 'closing'

            return True

        except Exception as e:
            self.logger().error(f"❌ EVM SELL trade error: {e}")
            self.logger().debug(f"Traceback: {traceback.format_exc()}")
            return False

    async def _execute_solana_sell_trade(self, base_token: str, network: str, exchange: str,
                                         percentage: float, pool: str = None, signal_data: dict = None) -> bool:
        """
        Execute Solana SELL trade using connector framework (event-driven approach).
        For SELL: We want to sell X% of our base_token holdings for quote_token

        This method now uses connector.place_order() which:
        - Triggers OrderFilledEvent when complete
        - Automatically records to database via MarketsRecorder
        - Handles retries and timeouts internally

        Args:
            signal_data: Original signal data for tracking purposes
        """
        try:
            # Step 1: Determine pool and quote token from position
            position = self.active_positions.get(base_token, {})

            if position:
                # Use tracked position info
                quote_token = position.get("quote_token", "USDC")
                pool_type = position.get("pool_type", "amm")

                if not pool and position.get("pool"):
                    pool = position["pool"]
                    self.logger().info(f"📝 Using pool from BUY position: {pool[:10] if pool else 'router'}...")

                self.logger().info(f"📝 Closing position: {base_token} → {quote_token} ({pool_type})")

            else:
                # No position tracked - determine pool info
                self.logger().info(f"⚠️ No position tracked for {base_token}, detecting pool configuration")

                quote_token = "USDC"
                pool_type = None

                # If pool address provided, get its info
                if pool:
                    pool_info = await self._get_pool_info(network, exchange, pool_address=pool)
                    if pool_info:
                        pool_type = pool_info['type']
                        if pool_info.get('quote_token'):
                            quote_token = pool_info['quote_token']
                        self.logger().info(f"📋 Found pool config: {pool_type} pool for {quote_token}")

                # If no pool provided, find one
                else:
                    if exchange and exchange.lower() == "jupiter":
                        pool_type = "router"
                        pool = None
                        self.logger().info("📋 Jupiter router detected - no pool address needed")
                    else:
                        pool_key = f"{base_token}-{quote_token}"
                        pool_info = await self._get_pool_info(network, exchange, pool_key=pool_key)

                        if pool_info:
                            pool = pool_info['address']
                            pool_type = pool_info['type']
                            if pool_info.get('quote_token'):
                                quote_token = pool_info['quote_token']

                            if pool_type == 'router' or pool is None:
                                self.logger().info(f"📋 Found {pool_type} configuration for {base_token}-{quote_token}")
                            else:
                                self.logger().info(f"📋 Found {pool_type} pool: {pool[:10]}...")
                        else:
                            self.logger().warning(f"⚠️ No pool configuration found for {base_token}-{quote_token} on {exchange}")
                            pool = None
                            pool_type = None

                # Final fallback for pool type
                if not pool_type:
                    pool_type = "amm"
                    self.logger().info("📋 Using default AMM for Solana trading")

            # Step 2: Get balance
            balance = await self._get_token_balance(base_token, network)

            if balance is None:
                balance = 0

            if not balance or balance <= 0:
                self.logger().warning(f"⚠️ No {base_token} balance to sell")
                self.active_positions.pop(base_token, None)
                return False

            # Step 3: Calculate sell amount with SOL minimum balance protection
            sell_amount = float(balance) * (percentage / 100.0)

            # SOL minimum balance protection for gas fees
            if base_token == "SOL" and quote_token in ["USDC", "USDT"]:
                if sell_amount > (float(balance) - self.min_sol_balance):
                    original_sell_amount = sell_amount
                    sell_amount = max(0.0, float(balance) - self.min_sol_balance)
                    self.logger().info(
                        f"🛡️ SOL minimum balance protection: Reducing sell from {original_sell_amount:.6f} to {sell_amount:.6f} "
                        f"to preserve {self.min_sol_balance} SOL for gas fees"
                    )

                    if sell_amount <= 0:
                        self.logger().warning(
                            f"⚠️ Cannot sell SOL: Would leave less than minimum balance of {self.min_sol_balance} SOL for gas fees"
                        )
                        return False

            self.logger().info(f"💰 Selling {sell_amount:.6f} {base_token} ({percentage}% of {balance:.6f})")

            # Step 4: Get connector
            connector = self._get_dex_connector(exchange, pool_type)
            if not connector:
                self.logger().error(f"❌ No connector found for {exchange}/{pool_type}")
                return False

            # Step 5: Build trading pair in format base-quote
            trading_pair = f"{base_token}-{quote_token}"

            # Get current price from DEX (not from connector.get_quote_price to avoid rate oracle issue)
            try:
                base_price = await self._get_solana_token_price(base_token, network)
                if not base_price:
                    self.logger().error(f"❌ Could not get {base_token} price from DEX")
                    return False

                current_price = Decimal(str(base_price))
                expected_quote_amount = Decimal(str(sell_amount)) * current_price

                self.logger().info(
                    f"💱 {sell_amount:.6f} {base_token} @ ${current_price:.2f} ≈ {expected_quote_amount:.6f} {quote_token}")
                self.logger().info(f"📊 Using DEX price: ${current_price:.2f} (avoiding rate oracle)")

            except Exception as e:
                self.logger().error(f"❌ Could not calculate trade amounts: {e}", exc_info=True)
                return False

            # Step 6: Place order through connector
            self.logger().info(f"📡 Placing order: SELL {sell_amount:.6f} {base_token} for {quote_token} on {exchange}/{pool_type}")

            order_id = connector.place_order(
                is_buy=False,  # SELL order
                trading_pair=trading_pair,
                amount=Decimal(str(sell_amount)),
                price=current_price
            )

            self.logger().info(f"✅ Order placed with ID: {order_id} (awaiting execution)")

            # Track this order for event handling
            self._dex_order_tracking[order_id] = {
                "signal_data": signal_data or {},
                "exchange": exchange,
                "pool_type": pool_type,
                "trading_pair": trading_pair,
                "base_token": base_token,
                "quote_token": quote_token,
                "network": network,
                "pool_address": pool or "",
                "timestamp": time.time()
            }

            # Note: Order execution happens asynchronously
            # The did_fill_order() event handler will be called when the trade completes
            # MarketsRecorder will automatically persist to database
            # Position cleanup will happen in did_fill_order()
            return True

        except Exception as e:
            self.logger().error(f"❌ Solana SELL error: {e}", exc_info=True)
            return False

    def _parse_symbol_tokens(self, symbol: str, network: str) -> tuple:
        """
        Parse trading symbol into base and quote tokens
        Handles token normalization for cross-chain compatibility (e.g., BTC → WBTC on EVM)
        """
        symbol_upper = symbol.upper()

        # Solana-specific parsing
        if network == "mainnet-beta":
            known_tokens = ['SOL', 'USDC', 'USDT', 'RAY', 'PEPE', 'WIF', 'POPCAT',
                            'TRUMP', 'LAYER', 'JITOSOL', 'BONK', 'FARTCOIN']

            for token in known_tokens:
                if symbol_upper.startswith(token):
                    remainder = symbol_upper[len(token):]
                    if remainder in known_tokens:
                        return token, remainder
                if symbol_upper.endswith(token):
                    prefix = symbol_upper[:-len(token)]
                    if prefix in known_tokens:
                        return prefix, token

            if 'USD' in symbol_upper:
                parts = symbol_upper.split('USD')
                if len(parts) == 2 and parts[1] in ['C', 'T']:
                    return parts[0], 'USD' + parts[1]

        # Generic parsing for all chains
        for quote in ['USDC', 'USDT', 'USD', 'DAI', 'ETH', 'WETH']:
            if symbol_upper.endswith(quote):
                base = symbol_upper[:-len(quote)]
                if base:
                    # Apply token normalization for EVM chains
                    base = self._normalize_token_symbol(base, network)
                    return base, quote

        # Handle hyphenated format (e.g., "BTC-USDC")
        if '-' in symbol:
            parts = symbol.split('-')
            if len(parts) == 2:
                base = parts[0].upper()
                quote = parts[1].upper()
                # Apply token normalization for EVM chains
                base = self._normalize_token_symbol(base, network)
                return base, quote

        self.logger().warning(f"⚠️ Could not parse {symbol}, defaulting to {symbol}-USDC")
        return symbol.upper(), 'USDC'

    def _normalize_token_symbol(self, token: str, network: str) -> str:
        """
        Normalize token symbols for cross-chain compatibility

        Args:
            token: The token symbol to normalize (e.g., "BTC", "ETH")
            network: The network name (e.g., "arbitrum", "mainnet", "optimism")

        Returns:
            Normalized token symbol (e.g., "BTC" → "WBTC" on EVM chains)
        """
        # EVM chain detection
        evm_chains = ['arbitrum', 'mainnet', 'ethereum', 'optimism', 'base', 'polygon',
                      'avalanche', 'bsc', 'celo', 'sepolia']

        if network.lower() in evm_chains:
            # Map native/unwrapped tokens to their wrapped equivalents
            token_mapping = {
                'BTC': 'WBTC',   # Bitcoin → Wrapped Bitcoin
                'SOL': 'WSOL',   # Solana → Wrapped Solana (if bridged)
            }

            normalized = token_mapping.get(token.upper(), token.upper())
            if normalized != token.upper():
                self.logger().debug(f"🔄 Normalized {token} → {normalized} for {network}")
            return normalized

        # For non-EVM chains (like Solana), return as-is
        return token.upper()

    async def _get_token_price_in_usd(self, token: str, network: str, exchange: str = "raydium", pool_type: str = None) -> Optional[Decimal]:
        """
        Get token price in USD from Gateway with retry logic for transient errors
        FIXED: Use quote-swap endpoint with proper pool_type for all exchanges

        Args:
            token: The token to get price for
            network: The network (e.g., arbitrum, mainnet-beta)
            exchange: The exchange (e.g., uniswap, raydium)
            pool_type: The pool type (clmm, amm, router) - required for proper endpoint routing
        """
        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                return await self._fetch_token_price_internal(token, network, exchange, pool_type)
            except Exception as e:
                error_msg = str(e)

                # Check for transient division by zero error (likely RPC/cache issue on liquid pools)
                if "Division by zero" in error_msg or "division by zero" in error_msg.lower():
                    if attempt < max_retries - 1:
                        self.logger().warning(
                            f"⚠️ Transient error for {token} pool (attempt {attempt + 1}/{max_retries}): Division by zero - retrying in {retry_delay}s..."
                        )
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        # All retries exhausted
                        self.logger().error(
                            f"❌ Pool for {token} still showing zero liquidity after {max_retries} attempts - likely actual liquidity issue"
                        )
                        self.logger().warning(f"⚠️ Skipping trade for {token} due to persistent zero liquidity")
                        return None

                # For other errors, fail immediately
                self.logger().error(f"❌ Error fetching {token} price: {e}")
                fallback = self._get_fallback_price(token)
                self.logger().warning(f"⚠️ Using fallback price ${fallback:.2f} due to error")
                return fallback

        return None

    async def _fetch_token_price_internal(self, token: str, network: str, exchange: str = "raydium", pool_type: str = None) -> Optional[Decimal]:
        """
        Internal method to fetch token price (called by _get_token_price_in_usd with retry logic)
        """
        try:
            # For Raydium on Solana, always use quote-swap endpoint
            if network == "mainnet-beta" and exchange == "raydium":
                # Determine which pool to use for price query
                pool_address = None
                pool_type = "clmm"  # Default to CLMM for USDC pairs

                # Special case for SOL - we know it's in CLMM
                if token == "SOL":
                    pool_address = "3ucNos4NbumPLZNWztqGHNFFgkHeRMBQAVemeeomsUxv"
                    pool_type = "clmm"
                else:
                    # Try to find the token-USDC pool
                    pool_symbol = f"{token}-USDC"

                    if network in self.pool_configurations:
                        # Check CLMM first (preferred for USDC pairs)
                        if "clmm" in self.pool_configurations[network]:
                            if pool_symbol in self.pool_configurations[network]["clmm"]:
                                pool_address = self.pool_configurations[network]["clmm"][pool_symbol]
                                pool_type = "clmm"

                        # Check AMM if not found in CLMM
                        if not pool_address and "amm" in self.pool_configurations[network]:
                            if pool_symbol in self.pool_configurations[network]["amm"]:
                                pool_address = self.pool_configurations[network]["amm"][pool_symbol]
                                pool_type = "amm"

                # Use quote-swap endpoint (GET request)
                endpoint = f"/connectors/raydium/{pool_type}/quote-swap"

                # Build query parameters for GET request
                price_params = {
                    "network": network,
                    "baseToken": token,
                    "quoteToken": "USDC",
                    "amount": "1",  # String for GET params
                    "side": "SELL"
                }

                if pool_address:
                    price_params["poolAddress"] = pool_address

                self.logger().info(f"🔍 Fetching {token} price from Raydium {pool_type.upper()} using quote-swap...")

                # CRITICAL FIX: Pass params as the params argument, not data
                response = await self.gateway_request("GET", endpoint, params=price_params)

            elif network == "mainnet-beta" and exchange == "meteora":
                # Meteora also uses quote-swap endpoint
                endpoint = "/connectors/meteora/clmm/quote-swap"

                price_params = {
                    "network": network,
                    "baseToken": token,
                    "quoteToken": "USDC",
                    "amount": "1",  # String for GET params
                    "side": "SELL"
                }

                self.logger().info(f"🔍 Fetching {token} price from Meteora using quote-swap...")

                # CRITICAL FIX: Pass params as the params argument
                response = await self.gateway_request("GET", endpoint, params=price_params)

            elif network == "mainnet-beta" and exchange == "jupiter":
                # Jupiter router uses quote-swap endpoint
                endpoint = "/connectors/jupiter/router/quote-swap"

                price_params = {
                    "network": network,
                    "baseToken": token,
                    "quoteToken": "USDC",
                    "amount": "1",  # String for GET params
                    "side": "SELL"
                }

                self.logger().info(f"🔍 Fetching {token} price from Jupiter Router using quote-swap...")

                # Use GET request for quote-swap endpoint
                response = await self.gateway_request("GET", endpoint, params=price_params)

            else:
                # For other networks/exchanges (EVM), use proper pool_type routing
                if exchange in ["uniswap", "pancakeswap"]:
                    # Determine pool_type if not provided
                    if not pool_type:
                        # Default to clmm for modern DEXs, fallback to amm
                        pool_type = "clmm"
                        self.logger().debug(f"🔍 No pool_type provided, defaulting to {pool_type}")

                    # Use correct endpoint format with pool_type: /connectors/{exchange}/{pool_type}/quote-swap
                    endpoint = f"/connectors/{exchange}/{pool_type}/quote-swap"
                    price_params = {
                        "network": network,
                        "baseToken": token,
                        "quoteToken": "USDC",
                        "amount": "1",
                        "side": "SELL"
                    }
                    self.logger().info(f"🔍 Fetching {token} price from {exchange} {pool_type.upper()} on {network}...")
                    response = await self.gateway_request("GET", endpoint, params=price_params)
                else:
                    # Fallback to POST for price endpoint (if it exists)
                    endpoint = f"/connectors/{exchange}/price"
                    price_request = {
                        "network": network,
                        "baseToken": token,
                        "quoteToken": "USDC",
                        "amount": 1.0
                    }
                    self.logger().info(f"🔍 Fetching {token} price from {exchange} on {network}...")
                    response = await self.gateway_request("POST", endpoint, data=price_request)

            if self._is_successful_response(response):
                # Extract price from response
                if "price" in response:
                    price = Decimal(str(response["price"]))
                    self.logger().info(f"✅ Live {token} price: ${price:.2f} USD")
                    return price
                elif "amountOut" in response:
                    # quote-swap returns amountOut for 1 token
                    amount_out = Decimal(str(response["amountOut"]))
                    price = amount_out  # This is the price in USDC for 1 token
                    self.logger().info(f"✅ Live {token} price: ${price:.2f} USD")
                    return price
                elif "expectedAmount" in response:
                    # Some endpoints return expectedAmount instead of price
                    expected = Decimal(str(response["expectedAmount"]))
                    price = expected  # Already for 1 token
                    self.logger().info(f"✅ Live {token} price: ${price:.2f} USD")
                    return price

            # If price fetch failed, return None (caller will use fallback)
            self.logger().warning(f"⚠️ Could not fetch live price for {token}")
            return None

        except Exception as e:
            error_msg = str(e)
            # Check for division by zero error from Gateway (indicates zero liquidity pool)
            if "Division by zero" in error_msg or "division by zero" in error_msg.lower():
                self.logger().error(f"❌ Pool for {token} has ZERO LIQUIDITY - cannot execute trade")
                self.logger().warning(f"⚠️ Skipping trade for {token} due to zero liquidity pool")
                return None  # Return None to prevent trade execution with invalid pool

            self.logger().error(f"❌ Error fetching {token} price: {e}")
            fallback = self._get_fallback_price(token)
            self.logger().warning(f"⚠️ Using fallback price ${fallback:.2f} due to error")
            return fallback

    def _get_fallback_price(self, token: str) -> Decimal:
        """
        Get fallback price for token when live price unavailable
        Only used in edge situations when we see network issues
        """
        fallback_prices = {
            # Major tokens
            "BTC": Decimal("100000"),
            "WBTC": Decimal("100000"),
            "ETH": Decimal("3200"),
            "WETH": Decimal("3200"),
            "SOL": Decimal("200"),
            "RAY": Decimal("3.5"),

            # Stablecoins
            "USDC": Decimal("1"),
            "USDT": Decimal("1"),
            "DAI": Decimal("1"),

            # Meme/Alt tokens (approximate)
            "WIF": Decimal("2.5"),
            "POPCAT": Decimal("1.2"),
            "PEPE": Decimal("0.000012"),
            "TRUMP": Decimal("4.5"),
            "LAYER": Decimal("0.15"),

            # Other common tokens
            "MATIC": Decimal("0.70"),
            "LINK": Decimal("14"),
            "UNI": Decimal("7"),
            "AAVE": Decimal("95"),
            "COMP": Decimal("55"),
        }

        token_upper = token.upper()
        if token_upper in fallback_prices:
            return fallback_prices[token_upper]

        # Default fallback for unknown tokens
        self.logger().warning(f"⚠️ No fallback price for {token}, using $10 default")
        return Decimal("10")

    async def _get_solana_token_price(self, token: str, network: str) -> Optional[float]:
        """
        Get token price in USD with special handling for SOL and tokens without USDC pairs

        - SOL-USDC pool is in CLMM
        - Many tokens only have SOL pairs, not USDC pairs
        - Need to calculate USD price through SOL bridge
        - This method is kind of messy but it is reliable
        """
        try:
            # Special handling for stablecoins
            if token in ["USDC", "USDT"]:
                return 1.0

            self.logger().info(f"💰 Getting {token} price on {network}...")

            # For SOL, we KNOW it's in CLMM with a specific pool
            if token == "SOL":
                # Use the known CLMM pool directly
                pool_address = "3ucNos4NbumPLZNWztqGHNFFgkHeRMBQAVemeeomsUxv"
                pool_type = "clmm"

                self.logger().info(f"🔍 Using known SOL-USDC CLMM pool: {pool_address[:8]}...")

                # Try to get price from CLMM
                try:
                    # Method 1: Try quote-swap endpoint
                    quote_params = {
                        "network": network,
                        "baseToken": "SOL",
                        "quoteToken": "USDC",
                        "amount": "1",
                        "side": "SELL",
                        "poolAddress": pool_address
                    }

                    endpoint = "/connectors/raydium/clmm/quote-swap"
                    response = await self.gateway_request("GET", endpoint, params=quote_params)

                    if response and "amountOut" in response:
                        price = float(response["amountOut"])
                        self.logger().info(f"✅ SOL price from CLMM quote: ${price:.2f}")
                        return price

                except Exception as e:
                    self.logger().warning(f"⚠️ CLMM quote failed: {e}")

                # Method 2: Fallback to a reasonable SOL price
                fallback_price = 196.0
                self.logger().warning(f"⚠️ Using fallback SOL price: ${fallback_price:.2f}")
                return fallback_price

            # For other tokens, first try direct USDC pair
            pool_address = None
            pool_type = "amm"  # Default to AMM for other tokens

            # Check if we have a direct USDC pair in our configuration
            if network in self.pool_configurations:
                network_config = self.pool_configurations[network]

                # Check Raydium pools for USDC pair
                if "raydium" in network_config:
                    raydium_config = network_config["raydium"]

                    # Format symbol for lookup
                    formatted_symbol = f"{token}-USDC"

                    # Check AMM first for USDC pairs
                    if "amm" in raydium_config and formatted_symbol in raydium_config["amm"]:
                        pool_address = raydium_config["amm"][formatted_symbol]
                        pool_type = "amm"
                        self.logger().info(f"✅ Found AMM pool for {formatted_symbol}: {pool_address[:8]}...")

                    # Check CLMM if no AMM pool found
                    elif "clmm" in raydium_config and formatted_symbol in raydium_config["clmm"]:
                        pool_address = raydium_config["clmm"][formatted_symbol]
                        pool_type = "clmm"
                        self.logger().info(f"✅ Found CLMM pool for {formatted_symbol}: {pool_address[:8]}...")

            # If we have a direct USDC pool, use it
            if pool_address:
                quote_params = {
                    "network": network,
                    "baseToken": token,
                    "quoteToken": "USDC",
                    "amount": "1",
                    "side": "SELL",
                    "poolAddress": pool_address
                }

                endpoint = f"/connectors/raydium/{pool_type}/quote-swap"
                self.logger().debug(f"🔍 Getting {token} price from {endpoint}")

                response = await self.gateway_request("GET", endpoint, params=quote_params)

                if response and "amountOut" in response:
                    price = float(response["amountOut"])
                    self.logger().info(f"💰 {token} price: ${price:.6f}")
                    return price

            # If no direct USDC pair, try to get price through SOL bridge
            self.logger().info(f"🔄 No direct USDC pair for {token}, trying SOL bridge...")

            # Look for token-SOL pair
            sol_pool_address = None
            sol_pool_type = "amm"

            if network in self.pool_configurations and "raydium" in self.pool_configurations[network]:
                raydium_config = self.pool_configurations[network]["raydium"]

                # Check for token-SOL pair
                formatted_symbol = f"{token}-SOL"

                # Check AMM
                if "amm" in raydium_config and formatted_symbol in raydium_config["amm"]:
                    sol_pool_address = raydium_config["amm"][formatted_symbol]
                    sol_pool_type = "amm"
                    self.logger().info(f"✅ Found {formatted_symbol} AMM pool: {sol_pool_address[:8]}...")

                # Check CLMM
                elif "clmm" in raydium_config and formatted_symbol in raydium_config["clmm"]:
                    sol_pool_address = raydium_config["clmm"][formatted_symbol]
                    sol_pool_type = "clmm"
                    self.logger().info(f"✅ Found {formatted_symbol} CLMM pool: {sol_pool_address[:8]}...")

            if sol_pool_address:
                # Get token price in SOL
                quote_params = {
                    "network": network,
                    "baseToken": token,
                    "quoteToken": "SOL",
                    "amount": "1",
                    "side": "SELL",
                    "poolAddress": sol_pool_address
                }

                endpoint = f"/connectors/raydium/{sol_pool_type}/quote-swap"
                self.logger().debug(f"🔍 Getting {token} price in SOL from {endpoint}")

                response = await self.gateway_request("GET", endpoint, params=quote_params)

                if response and "amountOut" in response:
                    token_price_in_sol = float(response["amountOut"])
                    self.logger().info(f"💱 {token} = {token_price_in_sol:.9f} SOL")

                    # Get SOL price in USD
                    sol_price_usd = await self._get_solana_token_price("SOL", network)

                    if sol_price_usd:
                        # Calculate USD price
                        token_price_usd = token_price_in_sol * sol_price_usd
                        self.logger().info(f"💰 {token} price: ${token_price_usd:.9f} (via SOL bridge)")
                        return token_price_usd

            # If all else fails, try without pool address (let Gateway auto-select)
            self.logger().warning(f"⚠️ Trying to get {token} price without specific pool...")

            # Try token-USDC first
            try:
                quote_params = {
                    "network": network,
                    "baseToken": token,
                    "quoteToken": "USDC",
                    "amount": "1",
                    "side": "SELL"
                }

                response = await self.gateway_request("GET", "/connectors/raydium/amm/quote-swap", params=quote_params)

                if response and "amountOut" in response:
                    price = float(response["amountOut"])
                    self.logger().info(f"💰 {token} price (auto-selected pool): ${price:.6f}")
                    return price
            except Exception:
                pass

            # Try token-SOL as last resort
            try:
                quote_params = {
                    "network": network,
                    "baseToken": token,
                    "quoteToken": "SOL",
                    "amount": "1",
                    "side": "SELL"
                }

                response = await self.gateway_request("GET", "/connectors/raydium/amm/quote-swap", params=quote_params)

                if response and "amountOut" in response:
                    token_price_in_sol = float(response["amountOut"])
                    sol_price_usd = await self._get_solana_token_price("SOL", network)

                    if sol_price_usd:
                        token_price_usd = token_price_in_sol * sol_price_usd
                        self.logger().info(f"💰 {token} price (via SOL, auto-pool): ${token_price_usd:.9f}")
                        return token_price_usd
            except Exception:
                pass

            self.logger().warning(f"⚠️ Could not get price for {token}")
            return None

        except Exception as e:
            self.logger().error(f"❌ Error getting {token} price: {e}")
            return None

    def _get_wallet_for_network(self, network: str) -> str:
        """Get appropriate wallet address for network type"""
        if self._is_solana_network(network):
            return self.solana_wallet
        else:
            return self.arbitrum_wallet  # For EVM networks

    async def _get_token_balance(self, token_symbol: str, network: str) -> Optional[float]:
        """
        Query token balance - Updated for Gateway 2.9.0 endpoints
        """
        try:
            wallet_address = self._get_wallet_for_network(network)

            balance_request = {
                "network": network,
                "address": wallet_address,
                "tokens": [token_symbol]
            }

            # Gateway 2.9: Updated endpoint with /chains/ prefix
            if self._is_solana_network(network):
                endpoint = "/chains/solana/balances"
            else:
                endpoint = "/chains/ethereum/balances"

            response = await self.gateway_request("POST", endpoint, balance_request)

            if response and "balances" in response and response["balances"] is not None:
                balance = float(response["balances"].get(token_symbol, 0))
                self.logger().debug(f"💰 {token_symbol} balance on {network}: {balance}")
                return balance

            return None

        except Exception as e:
            self.logger().error(f"❌ Balance query failed: {e}")
            return None

    @staticmethod
    def _is_solana_network(network: str) -> bool:
        """
        Determine if a network is Solana-based

        SOLANA NETWORKS:
        - mainnet-beta (production)
        - devnet (testing)

        ALL OTHER NETWORKS ARE EVM:
        - mainnet, arbitrum, optimism, base, sepolia, bsc, avalanche, celo, polygon, blast, zora, worldchain
        """
        return network in ["mainnet-beta", "devnet"]

    @staticmethod
    def _get_blockchain_explorer_url(tx_hash: str, network: str) -> str:
        """
        Get blockchain explorer URL for transaction verification

        SUPPORTS ALL NETWORKS with appropriate explorers
        """
        if not tx_hash:
            return ""

        # === SOLANA NETWORKS ===
        if network in ["mainnet-beta", "devnet"]:
            if network == "mainnet-beta":
                return f"https://explorer.solana.com/tx/{tx_hash}"
            else:  # devnet
                return f"https://explorer.solana.com/tx/{tx_hash}?cluster=devnet"

        # === EVM NETWORKS ===
        explorer_urls = {
            "mainnet": f"https://etherscan.io/tx/{tx_hash}",
            "arbitrum": f"https://arbiscan.io/tx/{tx_hash}",
            "optimism": f"https://optimistic.etherscan.io/tx/{tx_hash}",
            "base": f"https://basescan.org/tx/{tx_hash}",
            "polygon": f"https://polygonscan.com/tx/{tx_hash}",
            "bsc": f"https://bscscan.com/tx/{tx_hash}",
            "avalanche": f"https://snowtrace.io/tx/{tx_hash}",
            "celo": f"https://celoscan.io/tx/{tx_hash}",
            "blast": f"https://blastscan.io/tx/{tx_hash}",
            "zora": f"https://explorer.zora.energy/tx/{tx_hash}",
            "worldchain": f"https://worldchain-mainnet.explorer.alchemy.com/tx/{tx_hash}",
            "sepolia": f"https://sepolia.etherscan.io/tx/{tx_hash}",
        }

        return explorer_urls.get(network, f"https://etherscan.io/tx/{tx_hash}")

    async def _initialize_dynamic_token_discovery(self) -> None:
        """
        Initialize dynamic token discovery for all supported networks
        Gateway 2.9: Token endpoints removed, using pool-based discovery
        """
        try:
            self.logger().info("🔄 Initializing token discovery from pool configurations...")

            # Extract tokens from pool configurations instead of API
            for network in self.supported_networks:
                tokens = set()  # Use set to avoid duplicates

                # Extract tokens from pool configurations
                if network in self.pool_configurations:
                    for connector, connector_config in self.pool_configurations[network].items():
                        for pool_type in ["amm", "clmm"]:
                            if pool_type in connector_config:
                                for pool_key in connector_config[pool_type].keys():
                                    # Parse pool key like "WETH-USDC" to get tokens
                                    if "-" in pool_key:
                                        base, quote = pool_key.split("-", 1)
                                        tokens.add(base)
                                        tokens.add(quote)

                self.supported_tokens[network] = list(tokens)

                if tokens:
                    self.logger().info(f"✅ Network {network}: {len(tokens)} tokens found in pools")
                else:
                    self.logger().debug(f"📋 Network {network}: No tokens in pool configurations")

            total_tokens = sum(len(tokens) for tokens in self.supported_tokens.values())
            self.logger().info(
                f"🎯 Token discovery complete: {total_tokens} unique tokens from pool configurations")

        except Exception as init_error:
            self.logger().error(f"❌ Token discovery initialization error: {init_error}")
            # Initialize empty lists as fallback
            for network in self.supported_networks:
                self.supported_tokens[network] = []

    def _extract_transaction_hash(
            self,
            response: Optional[Dict] = None,
            network: str = "arbitrum"
    ) -> Optional[str]:
        """
        Universal transaction hash extraction for Gateway 2.9.0

        SUPPORTS ALL NETWORKS:
        ✅ Solana: mainnet-beta, devnet
        ✅ Ethereum: mainnet, arbitrum, optimism, base, sepolia, bsc, avalanche, celo, polygon, blast, zora, worldchain

        Args:
            response: Gateway API response dictionary
            network: Network name (determines hash format validation)

        Returns:
            Transaction hash/signature string or None if not found
        """
        if not response or not isinstance(response, dict):
            return None

        try:
            # ===== Gateway 2.9.0 Response Format =====
            # Gateway uses 'signature' field for BOTH EVM and Solana (discovered through testing)
            signature = response.get("signature")
            if signature and isinstance(signature, str) and len(signature) > 10:

                # === SOLANA NETWORKS ===
                if network in ["mainnet-beta", "devnet"]:
                    # Solana signatures: base58 strings, typically 88 characters
                    if len(signature) >= 20:  # Solana signatures are much longer
                        return signature

                # === ALL EVM NETWORKS ===
                else:
                    # EVM networks (Ethereum, Arbitrum, Base, Avalanche, Polygon, BSC, etc.)
                    # All use same transaction hash format: 0x + 64 hex characters
                    if signature.startswith("0x") and len(signature) == 66:
                        return signature

            # ===== FALLBACK: Check documented fields =====
            hash_fields = ["hash", "txHash", "transactionHash", "tx_hash", "transaction_hash"]

            for field in hash_fields:
                if field in response:
                    hash_value = response[field]
                    if isinstance(hash_value, str) and len(hash_value) > 10:

                        # Validate format based on network
                        if network in ["mainnet-beta", "devnet"]:
                            # Solana: any string longer than 20 characters
                            if len(hash_value) >= 20:
                                return hash_value
                        else:
                            # EVM: must be 0x + 64 hex characters
                            if hash_value.startswith("0x") and len(hash_value) == 66:
                                return hash_value

            # ===== NESTED STRUCTURE CHECK =====
            nested_locations = ["data", "result", "transaction", "txn", "response"]

            for location in nested_locations:
                if location in response and isinstance(response[location], dict):
                    nested_response = response[location]

                    # ✅ FIXED: Recursively check nested structure using self
                    nested_hash = self._extract_transaction_hash(nested_response, network)
                    if nested_hash:
                        return nested_hash

            return None

        except (TypeError, AttributeError, KeyError, ValueError):
            return None

    def _check_daily_limits(self) -> bool:
        """Check if daily trading limits are reached"""
        return (self.daily_trade_count < self.max_daily_trades and
                self.daily_volume < self.max_daily_volume)

    async def gateway_request(self, method: str, endpoint: str, data: Optional[Dict] = None,
                              params: Optional[Dict] = None) -> Dict:
        """
        Gateway 2.9.0 compatible request method with proper query parameter handling
        Handle 500 errors with signatures (Solana timeout cases)
        """
        try:
            protocol = "https" if self.gateway_https else "http"

            # Ensure endpoint starts with /
            if not endpoint.startswith("/"):
                endpoint = f"/{endpoint}"

            base_url = f"{protocol}://{self.gateway_host}:{self.gateway_port}{endpoint}"

            # Handle query parameters for GET requests
            if method.upper() == "GET" and params:

                query_string = urlencode(params)
                url = f"{base_url}?{query_string}"
            else:
                url = base_url

            self.logger().debug(f"🔗 Gateway request: {method} {url}")

            # Prepare SSL context if using HTTPS
            ssl_context = None
            if self.gateway_https:
                ssl_context = ssl.create_default_context()
                ssl_context.load_cert_chain(self.gateway_cert_path, self.gateway_key_path)
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

            # Set timeout
            timeout = aiohttp.ClientTimeout(total=self.request_timeout)

            # Make the request
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }

                if method.upper() == "GET":
                    async with session.get(url, headers=headers, ssl=ssl_context) as response:
                        response_data = await response.json()

                        # Special handling for 500 errors with signatures
                        if response.status == 500 and "signature" in response_data:
                            self.logger().warning("⚠️ Gateway 500 with signature - likely confirmation timeout")
                        elif response.status >= 400:
                            self.logger().error(f"❌ Gateway error {response.status}: {response_data}")

                        return response_data
                else:
                    async with session.request(
                            method,
                            url,
                            headers=headers,
                            json=data,
                            ssl=ssl_context
                    ) as response:
                        response_data = await response.json()

                        # Special handling for 500 errors with signatures (Solana timeout case)
                        if response.status == 500 and "signature" in response_data:
                            self.logger().warning("⚠️ Gateway 500 with signature - likely confirmation timeout")
                        elif response.status >= 400:
                            self.logger().error(f"❌ Gateway error {response.status}: {response_data}")

                        return response_data

        except Exception as e:
            self.logger().error(f"❌ Gateway request error: {e}")
            return {"error": str(e)}

    def _is_successful_response(self, response: Optional[Dict]) -> bool:
        """
        FIXED: Enhanced response validation for Gateway 2.9.0 API responses
        Properly recognizes successful trade responses with 'signature' field

        Gateway 2.9 uses 'signature' field for BOTH EVM and Solana transaction hashes
        in successful trade responses.
        """
        try:
            if not response or not isinstance(response, dict):
                return False

            # CRITICAL: Check for explicit error field first
            if "error" in response:
                error_msg = response.get("error", "Unknown error")
                self.logger().debug(f"🔍 Response contains error: {error_msg}")
                return False

            # Check for HTTP error status codes
            status_code = response.get("statusCode", 0)
            if status_code >= 400:
                self.logger().debug(f"🔍 Response has error status code: {status_code}")
                return False

            # Check for error messages in message field
            message = response.get("message", "")
            if message and (
                    "error" in message.lower() or
                    "failed" in message.lower() or
                    "not found" in message.lower()):
                self.logger().debug(f"🔍 Response message indicates error: {message}")
                return False

            # Recognize successful TRADE responses (Gateway 2.9.0 format)
            # Gateway 2.9.0 uses 'signature' field for both EVM and Solana successful trades
            if "signature" in response:
                signature = response.get("signature")
                if signature and isinstance(signature, str) and len(signature) > 10:
                    self.logger().debug(f"✅ Trade response contains valid signature: {signature[:10]}...")
                    return True

            # Check for other success indicators in trade responses
            trade_success_fields = [
                "txHash", "hash", "transactionHash", "tx_hash",  # EVM transaction hashes
                "totalInputSwapped", "totalOutputSwapped",  # Trade amounts
                "baseTokenBalanceChange", "quoteTokenBalanceChange"  # Balance changes
            ]

            success_count = 0
            for field in trade_success_fields:
                if field in response and response[field] is not None:
                    success_count += 1

            # If we have multiple success indicators, consider it successful
            if success_count >= 2:
                self.logger().debug(f"✅ Trade response has {success_count} success indicators")
                return True

            # For Gateway configuration responses
            if "networks" in response:
                networks = response["networks"]
                if isinstance(networks, dict) and len(networks) > 0:
                    self.logger().debug(f"✅ Config response contains {len(networks)} networks")
                    return True

            # For token/connector responses
            if "tokens" in response or "connectors" in response:
                self.logger().debug("✅ Token/connector response detected")
                return True

            #  For balance responses
            if "balances" in response:
                balances = response["balances"]
                if isinstance(balances, dict):
                    self.logger().debug(f"✅ Balance response contains {len(balances)} balances")
                    return True

            # For empty but valid responses (like status checks)
            if len(response) > 0 and not any(key in response for key in ["error", "message"]):
                self.logger().debug(f"✅ Non-empty response without errors: {list(response.keys())}")
                return True

            # If we get here, log what we received for debugging
            self.logger().debug(f"🔍 Unclear response type - treating as unsuccessful: {list(response.keys())}")
            return False

        except Exception as validation_error:
            self.logger().error(f"❌ Error during response validation: {validation_error}")
            return False

    def on_start(self):
        """Start the strategy - unchanged"""
        self.logger().info("🚀 Starting MQTT Webhook Strategy with Gateway 2.9")

    async def on_stop(self):
        """Stop the strategy - Framework compliant method signature"""
        try:
            if self.mqtt_client and self.mqtt_connected:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
                self.logger().info("🔌 Disconnected from MQTT broker")

            self.logger().info("⏹️ Enhanced MQTT Webhook Strategy stopped")

        except Exception as stop_error:
            self.logger().error(f"❌ Error stopping strategy: {stop_error}")

    # =============================================
    # STATUS REPORTING METHODS FOR CLI
    # =============================================

    def format_status(self) -> str:
        """
        Enhanced status reporting for 'status --live' command
        Shows MQTT, Gateway, CEX, and trading information
        """
        # Strategy Header
        lines = [
            "📊 MQTT Webhook Strategy Status",
            "=" * 50
        ]

        # System Status Section
        lines.extend(self._format_system_status())

        # Trading Status Section
        lines.extend(self._format_trading_status())

        # Active Positions Section
        lines.extend(self._format_active_positions())

        # Configuration Section
        lines.extend(self._format_configuration_status())

        # Performance Section
        lines.extend(self._format_performance_metrics())

        # Warnings Section
        warning_lines = self._format_warnings()
        if warning_lines:
            lines.extend(["", "⚠️  WARNINGS ⚠️"] + warning_lines)

        return "\n".join(lines)

    def _format_system_status(self) -> List[str]:
        """Format system connectivity status"""
        lines = ["", "🔌 System Status:"]

        # Gateway Status
        gateway_status = "✅ Connected" if hasattr(self, '_initialized') and self._initialized else "🔄 Connecting"
        lines.append(f"  Gateway ({self.gateway_host}:{self.gateway_port}): {gateway_status}")

        # MQTT Status
        mqtt_status = "✅ Connected" if self.mqtt_connected else "❌ Disconnected"
        lines.append(f"  MQTT ({self.mqtt_host}:{self.mqtt_port}): {mqtt_status}")

        # CEX Status
        if self.cex_enabled:
            cex_status = self._get_cex_connection_status()
            cex_ready = "✅ Ready" if self.cex_ready else "🔄 Initializing"
            lines.append(f"  CEX ({self.cex_exchange_name}): {cex_status} - {cex_ready}")
        else:
            lines.append("  CEX: ❌ Disabled")

        return lines

    def _format_trading_status(self) -> List[str]:
        """Format current trading status and limits"""
        lines = ["", "📈 Trading Status:"]

        # Daily Limits
        trade_pct = (self.daily_trade_count / self.max_daily_trades) * 100 if self.max_daily_trades > 0 else 0
        volume_pct = (float(self.daily_volume) / float(self.max_daily_volume)) * 100 if self.max_daily_volume > 0 else 0

        lines.append(f"  Daily Trades: {self.daily_trade_count}/{self.max_daily_trades} ({trade_pct:.1f}%)")
        lines.append(f"  Daily Volume: ${self.daily_volume:,.2f}/${float(self.max_daily_volume):,.2f} ({volume_pct:.1f}%)")

        # CEX Daily Volume
        if self.cex_enabled:
            cex_pct = (self.cex_daily_volume / self.cex_daily_limit) * 100 if self.cex_daily_limit > 0 else 0
            lines.append(f"  CEX Daily Volume: ${self.cex_daily_volume:,.2f}/${self.cex_daily_limit:,.2f} ({cex_pct:.1f}%)")

        # Trade Settings
        lines.append(f"  Default Trade Amount: ${float(self.trade_amount):,.2f}")
        lines.append(f"  Slippage Tolerance: {self.slippage_tolerance:.1f}%")

        return lines

    def _format_active_positions(self) -> List[str]:
        """Format active positions information"""
        lines = ["", "💼 Active Positions:"]

        if not hasattr(self, 'active_positions') or not self.active_positions:
            lines.append("  No active positions")
            return lines

        # Position headers
        lines.append("  Token    Quote    Network     Exchange    Pool Type   USD Value")
        lines.append("  " + "-" * 65)

        total_usd_value = 0
        for token, position in self.active_positions.items():
            quote_token = position.get('quote_token', 'USDC')
            network = position.get('network', 'N/A')
            exchange = position.get('exchange', 'N/A')
            pool_type = position.get('pool_type', 'N/A')
            usd_value = position.get('usd_value', 0)

            # Truncate long values for display
            token_display = token[:8].ljust(8)
            quote_display = quote_token[:8].ljust(8)
            network_display = network[:10].ljust(10)
            exchange_display = exchange[:10].ljust(10)
            pool_display = pool_type[:9].ljust(9)

            lines.append(f"  {token_display} {quote_display} {network_display} {exchange_display} {pool_display} ${usd_value:>8.2f}")
            total_usd_value += float(usd_value)

        lines.append("  " + "-" * 65)
        lines.append(f"  Total USD Value: ${total_usd_value:,.2f}")

        return lines

    def _format_configuration_status(self) -> List[str]:
        """Format configuration status"""
        lines = ["", "⚙️  Configuration:"]

        # Network configurations
        if hasattr(self, 'supported_networks') and self.supported_networks:
            all_networks = list(self.supported_networks.keys())
            lines.append(f"  Supported Networks: {', '.join(all_networks)}")

        # DEX configurations
        supported_dexs = ["uniswap", "raydium", "meteora", "pancakeswap", "jupiter", "0x"]
        lines.append(f"  Supported DEXs: {', '.join(supported_dexs)}")

        # CEX configurations
        if self.cex_enabled:
            lines.append(f"  Supported CEXs: {self.cex_exchange_name}")
            cex_pairs = self.markets.get(self.cex_exchange_name, [])
            if cex_pairs:
                lines.append(f"  CEX Trading Pairs: {len(cex_pairs)} configured")
        else:
            lines.append("  Supported CEXs: None (CEX trading disabled)")

        # Pool configurations
        if hasattr(self, 'pool_configurations') and self.pool_configurations:
            total_pools = 0
            for network, config in self.pool_configurations.items():
                for connector, types in config.items():
                    for pool_type, pools in types.items():
                        total_pools += len(pools)
            lines.append(f"  Total Configured Pools: {total_pools}")

        # SOL Balance Protection
        if hasattr(self, 'min_sol_balance'):
            lines.append(f"  SOL Minimum Balance: {self.min_sol_balance} SOL")

        return lines

    def _get_database_pnl(self) -> Optional[Dict[str, any]]:
        """
        Calculate PnL from database using the reporting system.
        Returns dictionary with PnL metrics or None if database unavailable.
        """
        try:
            # Import reporting modules
            from pathlib import Path

            from hummingbot import data_path
            from reporting.analysis.pnl_calculator import PnLCalculator
            from reporting.database.connection import DatabaseManager
            from reporting.matching.trade_matcher import TradeMatcher
            from reporting.normalization.trade_normalizer import TradeNormalizer

            # Get database path (follows same pattern as MarketsRecorder)
            db_path = Path(data_path()) / "mqtt_webhook_strategy_w_cex.sqlite"

            if not db_path.exists():
                self.logger().debug(f"Database not found: {db_path}")
                return None

            # Load and process trades
            db = DatabaseManager(str(db_path))
            trades = db.get_all_trades()

            if not trades:
                return None

            # Normalize trades (handles CEX, Solana DEX, EVM DEX)
            normalizer = TradeNormalizer()
            normalized_trades = normalizer.normalize_trades(trades)

            # Match trades (FIFO)
            from reporting.matching.trade_matcher import MatchingMethod
            matcher = TradeMatcher(method=MatchingMethod.FIFO)
            result = matcher.match_trades(normalized_trades)

            # Calculate PnL
            calculator = PnLCalculator()
            report = calculator.calculate(
                matched_positions=result['matched_positions'],
                open_positions=result['open_positions'],
                all_trades=normalized_trades
            )

            # Calculate total trades from database
            total_trades = len(trades)

            # Calculate win rate from matched positions
            if result['matched_positions']:
                winning_positions = [p for p in result['matched_positions'] if p.realized_pnl > 0]
                win_rate = (len(winning_positions) / len(result['matched_positions'])) * 100
            else:
                win_rate = 0.0

            # Convert by_asset AssetPnL objects to dictionaries for easy access
            by_asset_dict = {}
            for asset, asset_pnl in report.by_asset.items():
                by_asset_dict[asset] = {
                    'realized_pnl': float(asset_pnl.total_realized_pnl),
                    'total_trades': asset_pnl.total_trades,
                    'win_rate': float(asset_pnl.win_rate)
                }

            return {
                'total_pnl': float(report.total_realized_pnl),
                'total_fees': float(report.total_fees),
                'net_pnl': float(report.net_pnl),
                'total_trades': total_trades,
                'matched_positions': len(result['matched_positions']),
                'open_positions': len(result['open_positions']),
                'win_rate': win_rate,
                'by_asset': by_asset_dict
            }

        except Exception as e:
            self.logger().warning(f"Could not calculate database PnL: {e}")
            return None

    def _format_performance_metrics(self) -> List[str]:
        """Format performance metrics using database PnL data"""
        lines = ["", "📊 Performance Metrics:"]

        # Try to get PnL from database first
        db_pnl = self._get_database_pnl()

        if db_pnl:
            # Use accurate database metrics
            lines.append(f"  Total Trades: {db_pnl['total_trades']}")
            lines.append(f"  Matched Positions: {db_pnl['matched_positions']}")
            lines.append(f"  Open Positions: {db_pnl['open_positions']}")
            lines.append(f"  Win Rate: {db_pnl['win_rate']:.1f}%")
            lines.append(f"  Total PnL: ${db_pnl['total_pnl']:.2f}")
            lines.append(f"  Total Fees: ${db_pnl['total_fees']:.4f}")
            lines.append(f"  Net PnL: ${db_pnl['net_pnl']:.2f}")

            # Show top 3 performing assets
            if db_pnl['by_asset']:
                lines.append("")
                lines.append("  Top Assets:")
                sorted_assets = sorted(
                    db_pnl['by_asset'].items(),
                    key=lambda x: x[1].get('realized_pnl', 0),
                    reverse=True
                )[:3]
                for asset, metrics in sorted_assets:
                    pnl = metrics.get('realized_pnl', 0)
                    trades = metrics.get('total_trades', 0)
                    lines.append(f"    {asset}: ${pnl:.2f} ({trades} trades)")
        else:
            # Fallback to in-memory tracking
            total_trades = getattr(self, 'successful_trades', 0) + getattr(self, 'failed_trades', 0)
            if total_trades > 0:
                success_rate = (getattr(self, 'successful_trades', 0) / total_trades) * 100
                lines.append(f"  Success Rate: {success_rate:.1f}% ({getattr(self, 'successful_trades', 0)}/{total_trades})")
            else:
                lines.append("  Success Rate: N/A (No trades yet)")

        # Average execution time (in-memory only)
        if hasattr(self, 'avg_execution_time') and getattr(self, 'avg_execution_time', 0) > 0:
            lines.append(f"  Avg Execution Time: {getattr(self, 'avg_execution_time', 0):.2f}s")

        # Last signal time (in-memory only)
        if hasattr(self, 'last_signal_time') and self.last_signal_time:
            time_diff = datetime.now(timezone.utc) - self.last_signal_time
            lines.append(f"  Last Signal: {time_diff.seconds // 60}m {time_diff.seconds % 60}s ago")

        return lines

    def _format_warnings(self) -> List[str]:
        """Format system warnings"""
        warnings = []

        # Check daily limits
        if self.daily_trade_count >= self.max_daily_trades * 0.9:
            warnings.append(f"  ⚠️  Approaching daily trade limit ({self.daily_trade_count}/{self.max_daily_trades})")

        if float(self.daily_volume) >= float(self.max_daily_volume) * 0.9:
            warnings.append(f"  ⚠️  Approaching daily volume limit (${self.daily_volume:,.2f}/${float(self.max_daily_volume):,.2f})")

        # Check system connectivity
        if not self.mqtt_connected:
            warnings.append("  🔴 MQTT not connected - signals will not be received")

        if self.cex_enabled and not self.cex_ready:
            warnings.append("  🔴 CEX connector not ready")

        # Check for stale positions (if implemented)
        if hasattr(self, 'active_positions') and self.active_positions:
            stale_count = len([p for p in self.active_positions.values()
                               if hasattr(p, 'timestamp') and
                               (datetime.now(timezone.utc) - p.get('timestamp', datetime.now(timezone.utc))).days > 1])
            if stale_count > 0:
                warnings.append(f"  ⚠️  {stale_count} positions older than 24h")

        return warnings

    def active_orders_df(self):
        """
        Return DataFrame of active positions
        This shows current positions as 'active orders' for the status display
        """

        if not hasattr(self, 'active_positions') or not self.active_positions:
            raise ValueError("No active positions")

        # Convert positions to order-like format for display
        orders_data = []

        for token, position in self.active_positions.items():
            quote_token = position.get('quote_token', 'USDC')
            network = position.get('network', 'Unknown')
            pool_type = position.get('pool_type', 'N/A')
            usd_value = position.get('usd_value', 0)

            # Format as trading pair
            market = f"{token}-{quote_token}"

            # Use network as "exchange" for display
            exchange = f"{network}/{position.get('exchange', 'DEX')}"

            orders_data.append({
                'Exchange': exchange[:20],  # Truncate for display
                'Market': market,
                'Side': 'HOLD',  # Positions are held, not buy/sell orders
                'Pool Type': pool_type,
                'USD Value': f"${usd_value:.2f}",
                'Age': self._calculate_position_age(position)
            })

        return pd.DataFrame(orders_data)

    def _calculate_position_age(self, position) -> str:
        """Calculate how long a position has been held"""
        if 'timestamp' not in position:
            return "Unknown"

        try:

            pos_time = position.get('timestamp')
            if isinstance(pos_time, str):
                # Parse timestamp string if needed
                pos_time = datetime.fromisoformat(pos_time.replace('Z', '+00:00'))

            age_delta = datetime.now(timezone.utc) - pos_time

            if age_delta.days > 0:
                return f"{age_delta.days}d"
            elif age_delta.seconds > 3600:
                return f"{age_delta.seconds // 3600}h"
            else:
                return f"{age_delta.seconds // 60}m"

        except Exception:
            return "Unknown"


# For compatibility with direct script execution
if __name__ == "__main__":
    pass
