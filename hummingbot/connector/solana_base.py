import logging
from decimal import Decimal
from typing import Dict, List, Any, Union
import base58

from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.gateway_base import GatewayBase

s_logger = None
s_decimal_0 = Decimal("0")
s_decimal_NaN = Decimal("nan")
logging.basicConfig(level=METRICS_LOG_LEVEL)


class SolanaBase(GatewayBase):
    """
    SolanaInFlightOrder connects with solana gateway APIs and provides user account and transactions tracking.
    """

    API_CALL_TIMEOUT = 10.0
    POLL_INTERVAL = 60.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 trading_pairs: List[str],
                 solana_wallet_private_key: str,
                 trading_required: bool = True
                 ):
        """
        :param trading_pairs: a list of trading pairs
        :param solana_wallet_private_key: a solana wallet keypair, encoded in base58, 64 bytes long,
        (first 32 bytes are the secret, last 32 bytes the public key)
        :param trading_required: Whether actual trading is needed. Useful for some functionalities or commands like the balance command
        """
        super().__init__(trading_pairs, trading_required)
        self._tokens = set()
        for trading_pair in trading_pairs:
            self._tokens.update(set(trading_pair.split("-")))
        self._solana_wallet_address = base58.b58encode(base58.b58decode(solana_wallet_private_key)[32:]).decode('ascii')
        self._solana_wallet_private_key = solana_wallet_private_key

    @property
    def network_base_path(self):
        return "solana"

    @property
    def private_key(self):
        return self._solana_wallet_private_key

    async def init(self):
        if self._trading_required is True:
            await self.auto_create_token_accounts()

    async def auto_create_token_accounts(self):
        """Automatically creates all token accounts required for trading."""
        for token in self._tokens:
            await self.get_or_create_token_account(token)

    async def get_or_create_token_account(self, token_symbol: str) -> Union[Dict[str, Any], None]:
        resp = await self._api_request("post",
                                       "solana/token",
                                       {"token": token_symbol,
                                        "privateKey": self._solana_wallet_private_key})
        if resp.get("accountAddress", None) is None:
            self.logger().info(f"Token account initialization for {token_symbol} on {self.name} failed.")
            return None
        else:
            self.logger().info(f"{token_symbol} account on wallet {self._solana_wallet_address} initialized"
                               f" with mint address {resp['mintAddress']}.")
            return resp

    async def _update(self):
        await self._update_balances()

    @property
    def name(self):
        raise NotImplementedError

    @property
    def base_path(self):
        raise NotImplementedError

    @staticmethod
    async def fetch_trading_pairs(self) -> List[str]:
        # TODO: Get Solana trading pairs
        raise NotImplementedError

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        # TODO: Find out smallest price increments
        return super().get_order_price_quantum()

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        # TODO: Find out smallest size increments
        return super().get_order_size_quantum()

    @property
    def ready(self):
        return all(self.status_dict.values())

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True
        }
