import logging
from decimal import Decimal
from typing import Any, Dict, List, Union, cast, Optional

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook

from hummingbot.connector.gateway.clob.clob_types import Chain
from hummingbot.connector.gateway.gateway_base import GatewayBase
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.events import (
    OrderType,
    TradeType,
)
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.logger import HummingbotLogger
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL

ZERO = Decimal("0")
NaN = Decimal("nan")


class GatewayCLOB(GatewayBase, ExchangeBase):
    # API_CALL_TIMEOUT = 10.0
    # POLL_INTERVAL = 60.0

    _logger: HummingbotLogger

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            logging.basicConfig(level=METRICS_LOG_LEVEL)
            cls._logger = cast(HummingbotLogger, logging.getLogger(cls.__name__))

        return cls._logger

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "account_balance": len(self._account_balances) > 0 if self._is_trading_required else True,
            "token_accounts": len(self._account_balances) > 0 if self._is_trading_required else True
        }

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        raise NotImplementedError

    @property
    def limit_orders(self) -> List[LimitOrder]:
        raise NotImplementedError

    def __init__(
        self,
        chain: str,
        network: str,
        connector: str,
        wallet_address: str,
        trading_pairs: List[str],
        is_trading_required: bool = True
    ):
        """
        :param wallet_address: a solana wallet keypair, encoded in base58, 64 bytes long,
        (first 32 bytes are the secret, last 32 bytes the public key)
        :param is_trading_required: Whether actual trading is needed. Useful for some functionalities or commands like the balance command
        """
        super().__init__(chain, network, connector, wallet_address, trading_pairs, is_trading_required)

    async def initialize(self):
        if self._is_trading_required is True:
            await self.auto_create_token_accounts()

    async def auto_create_token_accounts(self):
        """Automatically creates all token accounts required for trading."""
        for token in self._tokens:
            await self.get_or_create_token_account(token)

    async def get_or_create_token_account(self, token: str) -> Union[Dict[str, Any], None]:
        if Chain.SOLANA == self.chain:
            response = await GatewayHttpClient.get_instance().solana_post_token(
                self.network,
                self.address,
                token
            )

            if response.get("accountAddress", None) is None:
                self.logger().warning(f"""Token account initialization failed (chain: {self.chain}, network: {self.network}, connector: {self.connector}, wallet: "{self._address}" token: "{token}").""")

                return None
            else:
                self.logger().info(f"""Token account successfully initialized (chain: {self.chain}, network: {self.network}, connector: {self.connector}, wallet: "{self._address}" token: "{token}", mint_address: "{response['mintAddress']}").""")

                return response
        else:
            raise ValueError(f"""Chain "{self.chain}" not supported.""")

    async def _update(self):
        await self._update_balances()

    def buy(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type=OrderType.MARKET,
        price: Decimal = NaN,
        **kwargs
    ) -> str:
        raise NotImplementedError

    def sell(
        self,
        trading_pair: str,
        amount: Decimal,
        order_type=OrderType.MARKET,
        price: Decimal = NaN,
        **kwargs
    ) -> str:
        raise NotImplementedError

    def cancel(
        self,
        trading_pair: str,
        client_order_id: str
    ):
        raise NotImplementedError

    def get_order_book(self, trading_pair: str) -> OrderBook:
        raise NotImplementedError

    def get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = NaN,
        is_maker: Optional[bool] = None
    ) -> AddedToCostTradeFee:
        raise NotImplementedError
