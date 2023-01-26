import asyncio

from hummingbot.client.settings import GatewayConnectionSetting
from hummingbot.core.event.events import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import Decimal, ScriptStrategyBase


class GatewayAmmTrade(ScriptStrategyBase):
    """
    This example shows how to execute a swap on Uniswap and poll for the result
    """
    # params
    connector_chain_network = "uniswap_ethereum_goerli"
    trading_pair = {"WETH-UNI"}
    order_amount = Decimal("0.0001")
    side = "BUY"
    # lower than the current price
    # limit_price = "1.3"

    markets = {
        connector_chain_network: trading_pair
    }
    on_going_task = False

    def on_tick(self):
        if not self.on_going_task:
            self.on_going_task = True
            safe_ensure_future(self.async_task())

    async def async_task(self):
        # Fetch Pair
        base_asset, quote_asset = list(self.trading_pair)[0].split("-")
        # Fetch wallet address
        connector, chain, network = self.connector_chain_network.split("_")
        gateway_connections_conf = GatewayConnectionSetting.load()
        if len(gateway_connections_conf) < 1:
            self.notify("No existing wallet.\n")
            return
        connector_wallet = [w for w in gateway_connections_conf if w["chain"] == chain and w["connector"] == connector and w["network"] == network]
        self.logger().info(f"Using Address {connector_wallet[0]['wallet_address']}")
        # Check trade side
        if (self.side == "BUY"):
            trade_type = TradeType.BUY
        else:
            trade_type = TradeType.SELL

        # Fetch the Price
        dataPrice = await GatewayHttpClient.get_instance().get_price(
            chain,
            network,
            connector,
            base_asset,
            quote_asset,
            self.order_amount,
            trade_type
        )

        self.logger().info(f"POST /amm/price [ side: {self.side}, base: {base_asset}, quote: {quote_asset}, amount: {self.order_amount}, Price: {dataPrice['price']} ]")

        # Execute the Trade
        data = await GatewayHttpClient.get_instance().amm_trade(
            chain,
            network,
            connector,
            connector_wallet[0]['wallet_address'],
            base_asset,
            quote_asset,
            trade_type,
            self.order_amount,
            # dataPrice['price']
        )
        # Call Function to poll
        await self.poll_transaction(chain, network, data['txHash'])

    async def poll_transaction(self, chain, network, txHash):
        # Polling For transaction status
        pending: bool = True
        while pending is True:
            self.logger().info(f"POST /network/poll [ txHash: {txHash} ]")
            pollData = await GatewayHttpClient.get_instance().get_transaction_status(
                chain,
                network,
                txHash
            )
            transaction_status = pollData.get("txStatus")
            if transaction_status == 1:
                self.logger().info(f"Trade with transaction hash {txHash} has been executed successfully.")
                pending = False
            elif transaction_status in [-1, 0, 2]:
                self.logger().info(f"Trade is pending confirmation, Transaction hash: {txHash}")
                await asyncio.sleep(2)
            else:
                self.logger().info(f"Unknown txStatus: {transaction_status}")
                self.logger().info(f"{pollData}")
                pending = False
