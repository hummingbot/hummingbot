import asyncio
import json
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from hummingbot.connector.exchange.swaphere.swaphere_constants import (
    SWAPHERE_BASE_URL,
    SWAPHERE_ORDER_BOOK_PATH,
    SWAPHERE_PLACE_ORDER_PATH,
    SWAPHERE_ORDER_DETAILS_PATH,
    SWAPHERE_ORDER_CANCEL_PATH,
    SWAPHERE_BALANCE_PATH,
    SWAPHERE_MY_TRADES_PATH,
    SWAPHERE_TICKER_PATH,
    SWAPHERE_INSTRUMENTS_PATH,
    ORDER_STATE,
    ORDER_TYPE_MAP,
    CLIENT_ID_PREFIX
)
from hummingbot.connector.exchange.swaphere.swaphere_auth import SwaphereAuth
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, AddedToCostTradeFee
from hummingbot.core.utils.async_utils import safe_gather, safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class SwaphereExchange(ExchangeBase):
    def __init__(
        self,
        api_key: str,
        privy_secret_key: str,
        trading_pairs: List[str] = None,
        trading_required: bool = True,
    ):
        super().__init__()
        self._api_key = api_key
        self._privy_secret_key = privy_secret_key
        self._trading_pairs = trading_pairs or []
        self._trading_required = trading_required
        
        self._auth = SwaphereAuth(api_key, privy_secret_key)
        self._web_assistants_factory = WebAssistantsFactory(auth=self._auth)
        self._rest_assistant = None
        
        # In-flight order management
        self._in_flight_orders = {}
        self._trading_rules = {}
        
    @property
    def name(self) -> str:
        return "swaphere"
        
    async def start_network(self):
        """Start network and initialize connections."""
        self._rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        await self._update_trading_rules()
        
    async def stop_network(self):
        """Stop network and close connections."""
        # Perform any cleanup operations here
        pass
        
    async def check_network(self) -> bool:
        """Check if the exchange is online and working properly."""
        try:
            await self._api_request(RESTMethod.GET, SWAPHERE_SERVER_TIME_PATH)
            return True
        except Exception:
            return False
            
    async def get_order_book(self, trading_pair: str) -> Dict[str, Any]:
        """Get order book for a specific trading pair."""
        params = {"symbol": trading_pair, "depth": 50}
        response = await self._api_request(RESTMethod.GET, SWAPHERE_ORDER_BOOK_PATH, params=params)
        return response
        
    async def get_trading_rules(self) -> Dict[str, TradingRule]:
        """Get trading rules for all trading pairs."""
        return self._trading_rules
        
    async def _update_trading_rules(self):
        """Update trading rules from the exchange."""
        instruments_info = await self._api_request(RESTMethod.GET, SWAPHERE_INSTRUMENTS_PATH)
        trading_rules = {}
        
        for instrument in instruments_info.get("instruments", []):
            try:
                trading_pair = instrument["symbol"]
                min_order_size = Decimal(instrument.get("min_size", "0"))
                max_order_size = Decimal(instrument.get("max_size", "9999999"))
                min_price_increment = Decimal(instrument.get("tick_size", "0.00000001"))
                min_base_amount_increment = Decimal(instrument.get("lot_size", "0.00000001"))
                
                trading_rules[trading_pair] = TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=min_order_size,
                    max_order_size=max_order_size, 
                    min_price_increment=min_price_increment,
                    min_base_amount_increment=min_base_amount_increment,
                )
            except Exception as e:
                self.logger().error(f"Error parsing trading pair rule {instrument}. Error: {e}")
                
        self._trading_rules = trading_rules
        
    async def place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        is_buy: bool,
        price: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """Place an order on the exchange."""
        order_type_str = ORDER_TYPE_MAP.get(order_type)
        side = "buy" if is_buy else "sell"
        
        data = {
            "symbol": trading_pair,
            "side": side,
            "type": order_type_str,
            "quantity": str(amount),
            "client_order_id": order_id,
        }
        
        if price is not None and order_type is not OrderType.MARKET:
            data["price"] = str(price)
            
        response = await self._api_request(RESTMethod.POST, SWAPHERE_PLACE_ORDER_PATH, data=data)
        return response
        
    async def execute_buy(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        price: Optional[Decimal] = None,
    ) -> str:
        """
        Execute a buy order
        :return: the client order id
        """
        client_order_id = order_id or get_new_client_order_id(True, trading_pair)
        try:
            order_result = await self.place_order(
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                is_buy=True,
                price=price,
                client_order_id=client_order_id,
            )
            
            exchange_order_id = order_result["data"][0]["ordId"]
            self.start_tracking_order(
                order_id=client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=TradeType.BUY,
                price=price,
                amount=amount,
            )
            
            self.logger().info(f"Buy order {client_order_id} created for {amount} {trading_pair}")
            return client_order_id
            
        except Exception as e:
            self.logger().error(f"Error creating buy order: {str(e)}", exc_info=True)
            raise
            
    async def execute_sell(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        price: Optional[Decimal] = None,
    ) -> str:
        """
        Execute a sell order
        :return: the client order id
        """
        client_order_id = order_id or get_new_client_order_id(False, trading_pair)
        try:
            order_result = await self.place_order(
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                is_buy=False,
                price=price,
                client_order_id=client_order_id,
            )
            
            exchange_order_id = order_result["data"][0]["ordId"]
            self.start_tracking_order(
                order_id=client_order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=TradeType.SELL,
                price=price,
                amount=amount,
            )
            
            self.logger().info(f"Sell order {client_order_id} created for {amount} {trading_pair}")
            return client_order_id
            
        except Exception as e:
            self.logger().error(f"Error creating sell order: {str(e)}", exc_info=True)
            raise
            
    def start_tracking_order(
        self,
        order_id: str,
        exchange_order_id: str,
        trading_pair: str,
        order_type: OrderType,
        trade_type: TradeType,
        price: Optional[Decimal],
        amount: Decimal,
    ):
        """
        Starts tracking an order by adding it to the order tracker
        """
        self._in_flight_orders[order_id] = InFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount,
            creation_timestamp=time.time() * 1000,
        )
        
    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]
            
    def get_order_book(self, trading_pair: str) -> Dict[str, Any]:
        """Get the local order book for a trading pair."""
        # This would typically connect to the order book tracker
        pass
        
    async def _api_request(
        self,
        method: RESTMethod,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make an API request to the exchange."""
        url = f"{SWAPHERE_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
        
        request_headers = {
            "Content-Type": "application/json",
        }
        if headers:
            request_headers.update(headers)
            
        response = await self._rest_assistant.call(
            method=method,
            url=url,
            params=params,
            data=json.dumps(data) if data else None,
            headers=request_headers,
        )
        
        response_json = await response.json()
        if "error" in response_json:
            raise ValueError(f"Error from Swaphere API: {response_json['error']}")
            
        return response_json 