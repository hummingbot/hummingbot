import asyncio
import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast

from hummingbot.connector.gateway.amm.gateway_evm_amm import GatewayEVMAMM
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.gateway.gateway_price_shim import GatewayPriceShim
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_logger = None


class GatewayNearAMM(GatewayEVMAMM):
    """
    Defines basic functions common to connectors that interact with Gateway.
    """
    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 connector_name: str,
                 chain: str,
                 network: str,
                 address: str,
                 trading_pairs: List[str] = [],
                 additional_spenders: List[str] = [],  # not implemented
                 trading_required: bool = True
                 ):
        """
        :param connector_name: name of connector on gateway
        :param chain: refers to a block chain, e.g. ethereum or avalanche
        :param network: refers to a network of a particular blockchain e.g. mainnet or kovan
        :param address: the address of the eth wallet which has been added on gateway
        :param trading_pairs: a list of trading pairs
        :param trading_required: Whether actual trading is needed. Useful for some functionalities or commands like the balance command
        """
        super().__init__(client_config_map=client_config_map,
                         connector_name=connector_name,
                         chain=chain,
                         network=network,
                         address=address,
                         trading_pairs=trading_pairs,
                         additional_spenders=additional_spenders,
                         trading_required=trading_required)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(cls.__name__)
        return cast(HummingbotLogger, s_logger)

    async def update_order_status(self, tracked_orders: List[GatewayInFlightOrder]):
        """
        Calls REST API to get status update for each in-flight amm orders.
        """
        if len(tracked_orders) < 1:
            return

        # split canceled and non-canceled orders
        tx_hash_list: List[str] = await safe_gather(
            *[tracked_order.get_exchange_order_id() for tracked_order in tracked_orders]
        )
        self.logger().debug(
            "Polling for order status updates of %d orders.",
            len(tracked_orders)
        )
        update_results: List[Union[Dict[str, Any], Exception]] = await safe_gather(*[
            self._get_gateway_instance().get_transaction_status(
                chain=self.chain,
                network=self.network,
                transaction_hash=tx_hash,
                address=self.address,
                fail_silently=True
            )
            for tx_hash in tx_hash_list
        ], return_exceptions=True)
        for tracked_order, tx_details in zip(tracked_orders, update_results):
            if "txHash" not in tx_details:
                continue
            tx_status: int = tx_details.get("txStatus", -1)
            tx_receipt: Optional[Dict[str, Any]] = tx_details.get("txReceipt", None)
            if tx_receipt is not None:
                if tx_status == 1:
                    gas_used: int = tx_receipt["transaction_outcome"]["outcome"]["gas_burnt"]
                    gas_price: Decimal = tracked_order.gas_price
                    fee: Decimal = Decimal(str(gas_used)) * Decimal(str(gas_price)) / Decimal(str(1e24))

                    self.processs_trade_fill_update(tracked_order=tracked_order, fee=fee)

                    order_update: OrderUpdate = OrderUpdate(
                        client_order_id=tracked_order.client_order_id,
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=self.current_timestamp,
                        new_state=OrderState.FILLED,
                    )

                else:  # transaction failed
                    order_update: OrderUpdate = OrderUpdate(
                        client_order_id=tracked_order.client_order_id,
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=self.current_timestamp,
                        new_state=OrderState.FAILED,
                    )

                self._order_tracker.process_order_update(order_update)
            else:
                await self._order_tracker.process_order_not_found(tracked_order.client_order_id)

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        return Decimal("1e-15")

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "native_currency": self._native_currency is not None,
            "network_transaction_fee": self.network_transaction_fee is not None if self._trading_required else True,
        }

    async def start_network(self):
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._get_gas_estimate_task = safe_ensure_future(self.get_gas_estimate())
        self._get_chain_info_task = safe_ensure_future(self.get_chain_info())

    async def stop_network(self):
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._get_chain_info_task is not None:
            self._get_chain_info_task.cancel()
            self._get_chain_info_task = None
        if self._get_gas_estimate_task is not None:
            self._get_gas_estimate_task.cancel()
            self._get_chain_info_task = None

    async def cancel_outdated_orders(self, cancel_age: int) -> List[CancellationResult]:
        """
        We do not cancel transactions on Near network.
        """
        return []

    async def update_canceling_transactions(self, canceled_tracked_orders: List[GatewayInFlightOrder]):
        """
        Update tracked orders that have a cancel_tx_hash.
        :param canceled_tracked_orders: Canceled tracked_orders (cancel_tx_has is not None).
        """
        pass

    async def update_token_approval_status(self, tracked_approvals: List[GatewayInFlightOrder]):
        """
        Calls REST API to get status update for each in-flight token approval transaction.
        :param tracked_approvals: tracked approval orders.
        """
        pass

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

        # Get the price from gateway price shim for integration tests.
        if not ignore_shim:
            test_price: Optional[Decimal] = await GatewayPriceShim.get_instance().get_connector_price(
                self.connector_name,
                self.chain,
                self.network,
                trading_pair,
                is_buy,
                amount
            )
            if test_price is not None:
                # Grab the gas price for test net.
                try:
                    resp: Dict[str, Any] = await self._get_gateway_instance().get_price(
                        self.chain, self.network, self.connector_name, base, quote, amount, side
                    )
                    gas_price_token: str = resp["gasPriceToken"]
                    gas_cost: Decimal = Decimal(resp["gasCost"])
                    self.network_transaction_fee = TokenAmount(gas_price_token, gas_cost)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass
                return test_price

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
