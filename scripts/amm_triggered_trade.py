import asyncio
import os
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.client.settings import GatewayConnectionSetting
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.event.events import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class AmmTriggeredTradeConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    connector: str = Field("jupiter", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Connector (e.g. jupiter, uniswap)"))
    chain: str = Field("solana", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Chain (e.g. solana, ethereum)"))
    network: str = Field("mainnet-beta", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Network (e.g. mainnet-beta (solana), base (ethereum))"))
    trading_pair: str = Field("SOL-USDC", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Trading pair (e.g. SOL-USDC)"))
    target_price: Decimal = Field(Decimal("142"), client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Target price to trigger trade"))
    trigger_above: bool = Field(False, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Trigger when price rises above target? (True for above/False for below)"))
    side: str = Field("BUY", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Trade side (BUY or SELL)"))
    order_amount: Decimal = Field(Decimal("0.01"), client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Order amount (in base token)"))


class AmmPriceTriggeredTrade(ScriptStrategyBase):
    """
    This strategy polls AMM prices and executes a trade when a price threshold is reached.
    """

    @classmethod
    def init_markets(cls, config: AmmTriggeredTradeConfig):
        # Construct connector_chain_network from the individual components
        connector_chain_network = f"{config.connector}_{config.chain}_{config.network}"
        cls.markets = {connector_chain_network: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: AmmTriggeredTradeConfig):
        super().__init__(connectors)
        self.config = config

        # State tracking
        self.trade_executed = False
        self.trade_in_progress = False
        self.gateway_ready = False

        # Log startup information
        self.logger().info("Starting AmmPriceTriggeredTrade strategy")
        self.logger().info(f"Connector: {self.config.connector}")
        self.logger().info(f"Chain: {self.config.chain}")
        self.logger().info(f"Network: {self.config.network}")
        self.logger().info(f"Trading pair: {self.config.trading_pair}")
        self.logger().info(f"Target price: {self.config.target_price}")
        condition = "rises above" if self.config.trigger_above else "falls below"
        self.logger().info(f"Will execute {self.config.side} when price {condition} target")

        # Check Gateway status
        safe_ensure_future(self.check_gateway_status())

    async def check_gateway_status(self):
        """Check if Gateway server is online"""
        self.logger().info("Checking Gateway server status...")
        try:
            gateway_http_client = GatewayHttpClient.get_instance()
            if await gateway_http_client.ping_gateway():
                self.gateway_ready = True
                self.logger().info("Gateway server is online!")

                # Verify wallet connections
                connector = self.config.connector
                chain = self.config.chain
                network = self.config.network
                gateway_connections_conf = GatewayConnectionSetting.load()

                if len(gateway_connections_conf) < 1:
                    self.logger().error("No wallet connections found. Please connect a wallet using 'gateway connect'.")
                else:
                    wallet = [w for w in gateway_connections_conf
                              if w["chain"] == chain and w["connector"] == connector and w["network"] == network]

                    if not wallet:
                        self.logger().error(f"No wallet found for {chain}/{connector}/{network}. "
                                            f"Please connect using 'gateway connect'.")
                    else:
                        self.logger().info(f"Found wallet connection for {chain}/{connector}/{network}!")
            else:
                self.gateway_ready = False
                self.logger().error("Gateway server is offline! Make sure Gateway is running before using this strategy.")
        except Exception as e:
            self.gateway_ready = False
            self.logger().error(f"Error connecting to Gateway server: {str(e)}")

    def on_tick(self):
        # Don't check price if trade already executed or in progress, or if gateway is not ready
        if self.trade_executed or self.trade_in_progress or not self.gateway_ready:
            return

        # Check price on each tick
        safe_ensure_future(self.check_price_and_trade())

    async def check_price_and_trade(self):
        """Check current price and trigger trade if condition is met"""
        if self.trade_in_progress or self.trade_executed:
            return

        self.trade_in_progress = True

        try:
            base, quote = self.config.trading_pair.split("-")
            connector = self.config.connector
            chain = self.config.chain
            network = self.config.network

            if (self.config.side == "BUY"):
                trade_type = TradeType.BUY
            else:
                trade_type = TradeType.SELL

            # Convert target price to string for logging
            target_price_str = str(self.config.target_price)
            condition = "rises above" if self.config.trigger_above else "falls below"
            self.logger().info(f"Checking if {base}-{quote} price {condition} {target_price_str}")

            try:
                # Fetch current price
                self.logger().info("Checking current price...")
                price_data = await GatewayHttpClient.get_instance().get_price(
                    chain,
                    network,
                    connector,
                    base,
                    quote,
                    self.config.order_amount,
                    trade_type
                )

                current_price = Decimal(price_data["price"])
                self.logger().info(f"Current price: {current_price}")

                # Check if price condition is met
                condition_met = False
                if self.config.trigger_above and current_price > self.config.target_price:
                    condition_met = True
                    self.logger().info(f"Price rose above target: {current_price} > {self.config.target_price}")
                elif not self.config.trigger_above and current_price < self.config.target_price:
                    condition_met = True
                    self.logger().info(f"Price fell below target: {current_price} < {self.config.target_price}")

                if condition_met:
                    self.logger().info("Price condition met! Executing trade...")
                    await self.execute_trade(chain, network, connector, base, quote, trade_type, current_price)

            except Exception as e:
                self.logger().error(f"Error checking price: {str(e)}")

        except Exception as e:
            self.logger().error(f"Error in check_price_and_trade: {str(e)}")

        finally:
            if not self.trade_executed:
                self.trade_in_progress = False

    async def execute_trade(self, chain, network, connector, base, quote, trade_type, current_price):
        """Execute the trade when the price condition is met"""
        try:
            # Fetch wallet address
            gateway_connections_conf = GatewayConnectionSetting.load()
            if len(gateway_connections_conf) < 1:
                self.logger().error("No existing wallet.")
                self.trade_in_progress = False
                return

            wallet = [w for w in gateway_connections_conf
                      if w["chain"] == chain and w["connector"] == connector and w["network"] == network]

            if not wallet:
                self.logger().error(f"No wallet found for {chain}/{connector}/{network}")
                self.trade_in_progress = False
                return

            address = wallet[0]['wallet_address']

            # Get initial balances
            await self.get_balance(chain, network, address, base, quote)

            # Execute trade
            self.logger().info(f"POST /amm/trade [ connector: {connector}, base: {base}, quote: {quote}, "
                               f"amount: {self.config.order_amount}, side: {self.config.side} ]")

            trade_data = await GatewayHttpClient.get_instance().amm_trade(
                chain,
                network,
                connector,
                address,
                base,
                quote,
                trade_type,
                self.config.order_amount
            )

            # Poll for swap result
            tx_hash = trade_data.get("txHash")
            if tx_hash:
                self.logger().info(f"Trade submitted with transaction hash: {tx_hash}")
                await self.poll_transaction(chain, network, tx_hash)
                await self.get_balance(chain, network, address, base, quote)
                self.trade_executed = True
                condition = "rose above" if self.config.trigger_above else "fell below"
                self.logger().info(f"Price-triggered trade completed successfully! {base}-{quote} price {condition} {self.config.target_price} (actual: {current_price})")
            else:
                self.logger().error("No transaction hash returned from trade")
                self.trade_in_progress = False

        except Exception as e:
            self.logger().error(f"Error executing trade: {str(e)}")
            self.trade_in_progress = False

    async def get_balance(self, chain, network, address, base, quote):
        """Fetch and log balances of base and quote tokens"""
        self.logger().info(f"POST /network/balance [ address: {address}, tokens: [{base}, {quote}] ]")
        try:
            balance_data = await GatewayHttpClient.get_instance().get_balances(
                chain,
                network,
                address,
                [base, quote]
            )

            self.logger().info(f"Balances for {address}: {balance_data['balances']}")

        except Exception as e:
            self.logger().error(f"Failed to get balances: {str(e)}")

    async def poll_transaction(self, chain, network, tx_hash):
        """Poll until transaction is confirmed"""
        pending = True
        while pending:
            self.logger().info(f"POST /network/poll [ txHash: {tx_hash} ]")
            poll_data = await GatewayHttpClient.get_instance().get_transaction_status(
                chain,
                network,
                tx_hash
            )

            transaction_status = poll_data.get("txStatus")

            if transaction_status == 1:
                self.logger().info(f"Trade with transaction hash {tx_hash} has been executed successfully.")
                pending = False
            elif transaction_status in [-1, 0, 2]:
                self.logger().info(f"Trade is pending confirmation, Transaction hash: {tx_hash}")
                await asyncio.sleep(2)
            else:
                self.logger().info(f"Unknown txStatus: {transaction_status}")
                self.logger().info(f"{poll_data}")
                pending = False

    def format_status(self) -> str:
        """Format status message for display in Hummingbot"""
        if not self.gateway_ready:
            return "Gateway server is not available. Please start Gateway and restart the strategy."

        if self.trade_executed:
            return "Trade has been executed successfully!"

        if self.trade_in_progress:
            return "Currently checking price or executing trade..."

        base, quote = self.config.trading_pair.split("-")
        condition = "rises above" if self.config.trigger_above else "falls below"

        lines = []
        connector_chain_network = f"{self.config.connector}_{self.config.chain}_{self.config.network}"
        lines.append(f"Monitoring {base}-{quote} price on {connector_chain_network}")
        lines.append(f"Will execute {self.config.side} trade when price {condition} {self.config.target_price}")
        lines.append(f"Trade amount: {self.config.order_amount} {base}")
        lines.append("Checking price on every tick")

        return "\n".join(lines)
