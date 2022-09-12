#!/usr/bin/env python

import logging

# from decimal import Decimal
from typing import Any, Dict  # TYPE_CHECKING,; List,; Optional,; Union

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future  # safe_gather
from hummingbot.logger import HummingbotLogger

hws_logger = None


class CurveCortexArb(ConnectorBase):
    # We use StrategyPyBase to inherit the structure. We also
    # create a logger object before adding a constructor to the class.
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hws_logger
        if hws_logger is None:
            hws_logger = logging.getLogger(__name__)
        return hws_logger

    def __init__(self, client_config_map: "ClientConfigAdapter"):
        super().__init__(client_config_map),
        self._connector_ready = False
        self._curve_price_retrieved = False

    def _get_gateway_instance(self) -> GatewayHttpClient:
        gateway_instance = GatewayHttpClient.get_instance(self._client_config)
        self._connector_ready = True
        return gateway_instance

    async def get_curve_price(
        self,
        side: str
    ) -> Dict[str, Any]:
        return await self._get_gateway_instance().api_request("post", "amm/price", {
            "chain": "ethereum",
            "network": "mainnet",
            "connector": "curve",
            "quote": "USDC",
            "base": "USDC",
            "amount": "1",
            "side": side
        })

    async def get_vault_price(
        self,
        tradeType: str
    ) -> int:
        return await self._get_gateway_instance().api_request("post", "vault/price", {
            "chain": "ethereum",
            "network": "mainnet",
            "connector": "cortex",
            "amount": "1",
            "tradeType": tradeType
        })

    # After initializing the required variables, we define the tick method.
    # The tick method is the entry point for the strategy.
    def tick(self, timestamp: float):
        safe_ensure_future(self.main())

    # Emit a log message when the order completes
    # def did_complete_buy_order(self, order_completed_event):
    #     self.logger().info(f"Your limit buy order {order_completed_event.order_id} has been executed")
    #     self.logger().info(order_completed_event)
    def notify_hb_app(self, msg: str):
        """
        Method called to display message on the Output Panel(upper left)
        :param msg: The message to be notified
        """
        from hummingbot.client.hummingbot_application import HummingbotApplication
        HummingbotApplication.main_application().notify(msg)

    async def main(self):

        self.vault_mint_output = await self.get_vault_price(tradeType="mint")
        self.logger().info(f"vault mint price: {self.vault_mint_output}")
        self.vault_redeem_output = await self.get_vault_price(tradeType="redeem")
        self.logger().info(f"vault redeem price: {self.vault_redeem_output}")

        self.logger().info("calling self.get_curve_price(side=buy)")
        self.curve_buy_output = await self.get_curve_price(side='BUY')
        self.logger().info(f"curve buy price: {self.curve_buy_output}")
        self.curve_sell_output = await self.get_curve_price(side="SELL")
        self.logger().info(f"curve sell price: {self.curve_sell_output}")

        curve_buy_price = int(self.curve_buy_output['price']) / 10**12
        self.logger().info(f"Curve Buy Price: {curve_buy_price}")
        curve_sell_price = float(self.curve_sell_output['price']) * 10**12
        self.logger().info(f"Curve sell Price: {curve_sell_price}")

        vault_redeem_price = int(self.vault_redeem_output['assetAmountWithFee'])
        vault_mint_price = int(self.vault_mint_output['assetAmountWithFee'])
        self.logger().info(f"Vault Reedem Price: {vault_redeem_price}, vault mint price: {vault_mint_price}")

        self.notify_hb_app(f"Curve-Buy-Price - Vault-Redeem-Price: {curve_buy_price - vault_redeem_price}")
        self.notify_hb_app(f"Curve-Sell-Price - Vault-Mint-Price: {curve_sell_price - vault_mint_price}")
