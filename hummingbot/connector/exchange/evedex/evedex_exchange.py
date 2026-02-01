from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.exchange.evedex import evedex_constants as CONSTANTS
from hummingbot.connector.exchange.evedex.evedex_auth import EvedexAuth
from hummingbot.connector.exchange.evedex.evedex_api_order_book_data_source import EvedexAPIOrderBookDataSource
from hummingbot.connector.exchange.evedex.evedex_api_user_stream_data_source import EvedexAPIUserStreamDataSource
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionMode, PositionAction, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


class EvedexExchange(PerpetualDerivativePyBase):
    def __init__(self,
                 evedex_private_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 **kwargs):
        self._evedex_private_key = evedex_private_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._domain = domain
        self._auth = EvedexAuth(private_key=self._evedex_private_key)
        super().__init__(**kwargs)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self):
        return self._auth

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def client_order_id_max_length(self) -> int:
        return 32

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_BROKER_ID

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.INSTRUMENTS_PATH_URL

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.INSTRUMENTS_PATH_URL

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.CHECK_NETWORK_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]

    def supported_position_modes(self):
        return [PositionMode.ONEWAY]

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return WebAssistantsFactory(auth=self._auth)

    def _create_order_book_data_source(self):
        return EvedexAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            domain=self._domain,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self):
        return EvedexAPIUserStreamDataSource(
            auth=self._auth,
            api_factory=self._web_assistants_factory,
            domain=self._domain
        )

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 position_action: PositionAction,
                 amount: Decimal,
                 price: Decimal = Decimal("0"),
                 is_maker: Optional[bool] = None) -> Any:
        # Placeholder for fee calculation
        return None

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        position_action: PositionAction = PositionAction.NIL,
        **kwargs,
    ) -> Tuple[str, float]:

        side = "BUY" if trade_type == TradeType.BUY else "SELL"
        api_params = {
            "instrument": trading_pair,
            "side": side,
            "quantity": f"{amount:f}",
            "type": "MARKET" if order_type == OrderType.MARKET else "LIMIT",
            "clientOrderId": order_id,
            "reduceOnly": position_action == PositionAction.CLOSE,
        }
        if order_type == OrderType.LIMIT:
            api_params["price"] = f"{price:f}"
            api_params["timeInForce"] = "GTC"

        # Sign request (handled by auth in factory if configured, but EIP-712 usually requires payload signing explicitly)
        # Assuming rest_assistant uses auth to sign headers or payload.
        # But for EIP-712 we likely need to sign payload and send signature in body or header.
        # Our EvedexAuth.sign_request() returns a signature.

        # Here we manually sign for now
        signature = self._auth.sign_request(method="POST", endpoint=CONSTANTS.ORDER_PATH_URL, params=api_params)
        api_params["signature"] = signature
        api_params["wallet"] = self._auth.get_public_key()

        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=f"{CONSTANTS.REST_URL}{CONSTANTS.ORDER_PATH_URL}",
            method=RESTMethod.POST,
            data=api_params,
            throttler_limit_id=CONSTANTS.ORDER_PATH_URL,
        )
        data = await response.json()

        # Evedex usually returns the order object
        exchange_order_id = str(data.get("id"))

        return exchange_order_id, self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        api_params = {
            "clientOrderId": order_id,
        }
        # Sign
        signature = self._auth.sign_request(method="DELETE", endpoint=CONSTANTS.ORDER_PATH_URL, params=api_params)
        api_params["signature"] = signature
        api_params["wallet"] = self._auth.get_public_key()

        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        await rest_assistant.execute_request(
            url=f"{CONSTANTS.REST_URL}{CONSTANTS.ORDER_PATH_URL}",
            method=RESTMethod.DELETE,
            params=api_params,
            throttler_limit_id=CONSTANTS.ORDER_PATH_URL,
        )
        return True

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        # Exchange info dict is result of INSTRUMENTS_PATH_URL
        # List of instruments
        rules = []
        for instrument in exchange_info_dict:
            name = instrument["name"]
            # Extract min size, step size etc from instrument config
            min_size = Decimal(instrument.get("minQuantity", "0.001"))
            step_size = Decimal(instrument.get("quantityIncrement", "0.001"))
            tick_size = Decimal(instrument.get("priceIncrement", "0.01"))

            rules.append(
                TradingRule(
                    trading_pair=name,
                    min_order_size=min_size,
                    min_price_increment=tick_size,
                    min_base_amount_increment=step_size,
                    supports_market_orders=True,
                )
            )
        return rules

    async def _update_balances(self):
        # Fetch balances via REST (SIWE Auth handled in UserStream usually, but for REST we might need separate auth flow)
        # Using the signature approach on each request
        # Actually standard flow:
        # 1. Login to get Token
        # 2. Use Token in Header
        # I haven't implemented automatic token refreshing for REST in EvedexExchange yet.
        # This is a complexity.
        # For now, let's assume we can fetch balance via signed request directly if supported, OR we reuse the token logic.

        # Simplification: Just Stub
        pass

    async def _update_positions(self):
        pass

    async def _update_order_status(self):
        pass
