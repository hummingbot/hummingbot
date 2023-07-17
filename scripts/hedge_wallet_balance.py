from decimal import Decimal

# from hummingbot.core.data_type.common import OrderType, TradeType
# from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class HedgeWalletBalance(ScriptStrategyBase):
    """
    BotCamp Cohort: 5
    Design Template: https://github.com/hummingbot/hummingbot-botcamp/issues/51
    Video: https://github.com/hummingbot/hummingbot-botcamp/issues/51
    Description:
    A utility script that hedges changes to blockchain wallet balances on a CEX
    """

    # Wallet params
    chain = "polygon"
    network = "mainnet"
    address = "0xDA50C69342216b538Daf06FfECDa7363E0B96684"
    symbol = "MATIC"

    # Hedge params
    exchange = "kucoin_paper_trade"
    trading_pair = "MATIC-USDT"
    threshold = 0.1
    markets = {exchange: {trading_pair}}

    on_going_task = False

    def on_tick(self):
        # only execute once
        if not self.on_going_task:
            self.on_going_task = True
            # wrap async task in safe_ensure_future
            safe_ensure_future(self.async_task())

    # async task since we are using Gateway
    async def async_task(self):
        # fetch balances
        self.logger().info(f"POST /chain/balances [ address: {self.address}, chain: {self.chain}, network: {self.network}, symbol: {self.symbol}")
        data = await GatewayHttpClient.get_instance().get_balances(
            self.chain,
            self.network,
            self.address,
            [self.symbol]
        )
        balance = Decimal(data['balances'][self.symbol])
        self.logger().info(f"Balances: {balance}")
