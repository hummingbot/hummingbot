from decimal import Decimal
from typing import List

from hummingbot.connector.gateway_base import GatewayBase

s_logger = None
s_decimal_0 = Decimal("0")
s_decimal_NaN = Decimal("nan")


class BalancerConnector(GatewayBase):
    """
    BalancerConnector connects with balancer gateway APIs and provides pricing, user account tracking and trading
    functionality.
    """

    def __init__(self,
                 trading_pairs: List[str],
                 wallet_private_key: str,
                 ethereum_rpc_url: str,
                 trading_required: bool = True
                 ):
        """
        :param trading_pairs: a list of trading pairs
        :param wallet_private_key: a private key for eth wallet
        :param ethereum_rpc_url: this is usually infura RPC URL
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__(trading_pairs,
                         wallet_private_key,
                         trading_required)

    @property
    def name(self):
        return "balancer"

    @property
    def base_path(self):
        return "eth/balancer"
