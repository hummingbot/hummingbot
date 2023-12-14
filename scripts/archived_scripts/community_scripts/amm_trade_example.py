import asyncio

from hummingbot.client.settings import GatewayConnectionSetting
from hummingbot.core.event.events import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import Decimal, ScriptStrategyBase


class AmmTradeExample(ScriptStrategyBase):
    """
    This example shows how to call the /amm/trade Gateway endpoint to execute a swap transaction
    """
    # swap params
    connector_chain_network = "uniswap_ethereum_goerli"
    trading_pair = {"WETH-DAI"}
    side = "SELL"
    order_amount = Decimal("0.01")
    slippage_buffer = 0.01
    markets = {
        connector_chain_network: trading_pair
    }
    on_going_task = False

    def on_tick(self):
        # only execute once
        if not self.on_going_task:
            self.on_going_task = True
            # wrap async task in safe_ensure_future
            safe_ensure_future(self.async_task())

    # async task since we are using Gateway
    async def async_task(self):
        base, quote = list(self.trading_pair)[0].split("-")
        connector, chain, network = self.connector_chain_network.split("_")
        if (self.side == "BUY"):
            trade_type = TradeType.BUY
        else:
            trade_type = TradeType.SELL

        # fetch current price
        self.logger().info(f"POST /amm/price [ connector: {connector}, base: {base}, quote: {quote}, amount: {self.order_amount}, side: {self.side} ]")
        priceData = await GatewayHttpClient.get_instance().get_price(
            chain,
            network,
            connector,
            base,
            quote,
            self.order_amount,
            trade_type
        )
        self.logger().info(f"Price: {priceData['price']}")
        self.logger().info(f"Amount: {priceData['amount']}")

        # add slippage buffer to current price
        if (self.side == "BUY"):
            price = float(priceData['price']) * (1 + self.slippage_buffer)
        else:
            price = float(priceData['price']) * (1 - self.slippage_buffer)
        self.logger().info(f"Swap Limit Price: {price}")

        # fetch wallet address and print balances
        gateway_connections_conf = GatewayConnectionSetting.load()
        if len(gateway_connections_conf) < 1:
            self.notify("No existing wallet.\n")
            return
        wallet = [w for w in gateway_connections_conf if w["chain"] == chain and w["connector"] == connector and w["network"] == network]
        address = wallet[0]['wallet_address']
        await self.get_balance(chain, network, address, base, quote)

        # execute swap
        self.logger().info(f"POST /amm/trade [ connector: {connector}, base: {base}, quote: {quote}, amount: {self.order_amount}, side: {self.side}, price: {price} ]")
        tradeData = await GatewayHttpClient.get_instance().amm_trade(
            chain,
            network,
            connector,
            address,
            base,
            quote,
            trade_type,
            self.order_amount,
            Decimal(price)
        )

        # poll for swap result and print resulting balances
        await self.poll_transaction(chain, network, tradeData['txHash'])
        await self.get_balance(chain, network, address, base, quote)

    # fetch and print balance of base and quote tokens
    async def get_balance(self, chain, network, address, base, quote):
        self.logger().info(f"POST /network/balance [ address: {address}, base: {base}, quote: {quote} ]")
        balanceData = await GatewayHttpClient.get_instance().get_balances(
            chain,
            network,
            address,
            [base, quote]
        )
        self.logger().info(f"Balances for {address}: {balanceData['balances']}")

    # continuously poll for transaction until confirmed
    async def poll_transaction(self, chain, network, txHash):
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
