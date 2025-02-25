from hummingbot.core.event.events import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import Decimal, ScriptStrategyBase


class AmmPriceExample(ScriptStrategyBase):
    """
    This example shows how to call the /amm/price Gateway endpoint to fetch price for a swap
    """
    # swap params
    connector_chain_network = "uniswap_ethereum_goerli"
    trading_pair = {"WETH-DAI"}
    side = "SELL"
    order_amount = Decimal("0.01")
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

        # fetch price
        self.logger().info(f"POST /amm/price [ connector: {connector}, base: {base}, quote: {quote}, amount: {self.order_amount}, side: {self.side} ]")
        data = await GatewayHttpClient.get_instance().get_price(
            chain,
            network,
            connector,
            base,
            quote,
            self.order_amount,
            trade_type
        )
        self.logger().info(f"Price: {data['price']}")
        self.logger().info(f"Amount: {data['amount']}")
