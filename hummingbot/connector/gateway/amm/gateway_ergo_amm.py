import asyncio
from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING
from hummingbot.connector.gateway.amm.gateway_evm_amm import GatewayEVMAMM
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.utils import async_ttl_cache
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.events import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.logger import HummingbotLogger
if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class GatewayErgoAMM(GatewayEVMAMM):
    """
    Defines basic functions common to connectors that interact with Gateway.
    """

    API_CALL_TIMEOUT = 60.0
    POLL_INTERVAL = 15.0

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        connector_name: str,
        chain: str,
        network: str,
        address: str,
        trading_pairs: List[str] = [],
        additional_spenders: List[str] = [],  # not implemented
        trading_required: bool = True,
    ):
        """
        :param connector_name: name of connector on gateway
        :param chain: refers to a block chain, e.g. ethereum or avalanche
        :param network: refers to a network of a particular blockchain e.g. mainnet or kovan
        :param address: the address of the eth wallet which has been added on gateway
        :param trading_pairs: a list of trading pairs
        :param trading_required: Whether actual trading is needed. Useful for some functionalities or commands like the balance command
        """
        super().__init__(
            client_config_map=client_config_map,
            connector_name=connector_name,
            chain=chain,
            network=network,
            address=address,
            trading_pairs=trading_pairs,
            additional_spenders=additional_spenders,
            trading_required=trading_required,
        )

    async def get_chain_info(self):
        """
        Calls the base endpoint of the connector on Gateway to know basic info about chain being used.
        """
        try:
            self._chain_info = await self._get_gateway_instance().get_network_status(
                chain=self.chain, network=self.network
            )
            if not isinstance(self._chain_info, list):
                self._native_currency = self._chain_info.get("nativeCurrency", "ERG")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network("Error fetching chain info", exc_info=True, app_warning_msg=str(e))

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        This is intentionally left blank, because cancellation is not supported for tezos blockchain.
        """
        return []

    async def _execute_cancel(self, order_id: str, cancel_age: int) -> Optional[str]:
        """
        This is intentionally left blank, because cancellation is not supported for tezos blockchain.
        """
        pass

    async def cancel_outdated_orders(self, cancel_age: int) -> List[CancellationResult]:
        """
        This is intentionally left blank, because cancellation is not supported for tezos blockchain.
        """
        return []

    @async_ttl_cache(ttl=5, maxsize=10)
    async def get_quote_price(
            self,
            trading_pair: str,
            is_buy: bool,
            amount: Decimal,
            ignore_shim: bool = False
    ) -> Optional[Decimal]:
        """
        Retrieves a quote price.

        :param trading_pair: The market trading pair
        :param is_buy: True for an intention to buy, False for an intention to sell
        :param amount: The amount required (in base token unit)
        :param ignore_shim: Ignore the price shim, and return the real price on the network
        :return: The quote price.
        """

        base, quote = trading_pair.split("-")
        side: TradeType = TradeType.BUY if is_buy else TradeType.SELL

        # Pull the price from gateway.
        try:
            resp: Dict[str, Any] = await self._get_gateway_instance().get_price(
                self.chain, self.network, self.connector_name, base, quote, amount, side
            )
            return self.parse_price_response(base, quote, amount, side, price_response=resp, process_exception=False)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error getting quote price for {trading_pair} {side} order for {amount} amount.",
                exc_info=True,
                app_warning_msg=str(e)
            )
