from hummingbot.connector.derivative.derivative_base import DerivativeBase
from hummingbot.connector.derivative.aevo_perpetual import aevo_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_api_order_book_data_source import AevoPerpetualAPIOrderBookDataSource
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_user_stream_data_source import AevoPerpetualUserStreamDataSource
import asyncio


class AevoPerpetualDerivative(DerivativeBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._domain = "aevo"
    
    @property
    def name(self) -> str:
        return "aevo_perpetual"

    @property
    def authenticator(self):
        return self._auth

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    async def start_network(self):
        await self._stop_network()
        self._stop_network_task = asyncio.create_task(self._start_network())

    def _create_order_book_data_source(self):
        return AevoPerpetualAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            domain=self._domain,
            api_factory=self._web_assistants_factory,
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer)

    def _create_user_stream_data_source(self):
        return AevoPerpetualUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            api_factory=self._web_assistants_factory,
            domain=self._domain)

    async def _start_network(self):
        self._order_book_tracker.start()
        self._user_stream_tracker.start()
        self._status_polling_task = asyncio.create_task(self._status_polling_loop())

    async def _stop_network(self):
        self._order_book_tracker.stop()
        self._user_stream_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()


    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: float,
                           trade_type: str,
                           order_type: str,
                           price: float,
                           **kwargs) -> Tuple[str, float]:
        params = {
            "instrument_name": trading_pair,
            "is_buy": trade_type.upper() == "BUY",
            "limit_price": str(price),
            "quantity": str(amount),
            "post_only": kwargs.get("post_only", False),
            "reduce_only": kwargs.get("reduce_only", False),
            "time_in_force": kwargs.get("time_in_force", "GTC"),
            # "client_order_id": order_id 
            # TODO: details on client_order_id support in Aevo docs are sparse, 
            # might need to pass it in a different field or it might be auto-generated.
            # Keeping it commented out for now until we can verify with live keys. 
        }
        
        # Determine endpoint based on order type if needed, or just standard /orders
        response = await self._api_factory.call_rest(
            method="POST",
            url=f"{CONSTANTS.AEVO_BASE_URL}{CONSTANTS.ORDER_PATH_URL}",
            data=params,
            is_auth_required=True
        )
        
        # Parse response to get exchange order ID and timestamp
        exchange_order_id = str(response.get("order_id", order_id))
        transact_time = float(response.get("timestamp", self._time_synchronizer.time() * 1e9)) * 1e-9
        
        return exchange_order_id, transact_time

    async def _cancel_order(self, order_id: str, trading_pair: str, timestamp: float) -> Any:
        # Aevo Cancel: DELETE /orders/{order_id}
        response = await self._api_factory.call_rest(
            method="DELETE",
            url=f"{CONSTANTS.AEVO_BASE_URL}{CONSTANTS.ORDER_PATH_URL}/{order_id}",
            is_auth_required=True
        )
        return response

