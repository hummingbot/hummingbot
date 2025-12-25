import asyncio
import logging
from typing import Dict, List

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from . import (
    evedex_perpetual_constants as CONSTANTS,
    evedex_perpetual_utils as utils,
    evedex_perpetual_web_utils as web_utils,
)
from .evedex_perpetual_auth import (
    EvedexPerpetualAuth,
)

logger = logging.getLogger(__name__)


class EvedexPerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):
    def __init__(
        self,
        auth: EvedexPerpetualAuth,
        ws_assistant: WSAssistant,
        throttler: AsyncThrottler,
        environment: str = "demo",
    ):
        super().__init__()
        self._auth = auth
        self._ws_assistant = ws_assistant
        self._throttler = throttler
        self._environment = environment
        self._env_prefix = CONSTANTS.ENV_PREFIX[environment]
        self._ws_base = web_utils.get_ws_url(environment)
        
        self._ws_connect_lock = asyncio.Lock()
        self._ws_connected = False
        
        self._subscribed_channels: List[str] = []
        
    async def listen_for_user_stream(
        self,
        output: asyncio.Queue
    ) -> None:
        while True:
            try:
                await self._subscribe_user_channels(output)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"User stream error: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    async def _subscribe_user_channels(
        self,
        output: asyncio.Queue
    ) -> None:
        await self._ensure_ws_connection()
        
        user_id = self._auth.user_exchange_id
        if not user_id:
            logger.warning("No user exchange ID available, cannot subscribe to user stream")
            await asyncio.sleep(5)
            return
        
        channels_to_subscribe = [
            CONSTANTS.WS_CHANNELS["order"].format(user_id=user_id),
            CONSTANTS.WS_CHANNELS["order_fills"].format(user_id=user_id),
            CONSTANTS.WS_CHANNELS["position"].format(user_id=user_id),
            CONSTANTS.WS_CHANNELS["user"].format(user_id=user_id),
            CONSTANTS.WS_CHANNELS["funding"].format(user_id=user_id),
            CONSTANTS.WS_CHANNELS["order_fee"].format(user_id=user_id),
        ]
        
        for channel in channels_to_subscribe:
            subscribe_msg = {
                "method": 1,
                "params": {
                    "channel": channel,
                }
            }
            
            await self._ws_assistant.send(WSJSONRequest(payload=subscribe_msg))
            self._subscribed_channels.append(channel)
            logger.info(f"Subscribed to user channel: {channel}")
        
        async for msg in self._ws_assistant.iter_messages():
            try:
                await self._process_user_stream_message(msg, output)
            except Exception as e:
                logger.error(f"Error processing user stream message: {e}")
        # Connection closed, mark as disconnected
        self._ws_connected = False
    
    async def _process_user_stream_message(
        self,
        msg: Dict,
        output: asyncio.Queue
    ) -> None:
        channel = msg.get("channel", "")
        data = msg.get("data", {})
        
        if not channel or not data:
            return
        
        if "order-" in channel and "orderFills-" not in channel:
            await self._handle_order_update(data, output)
        elif "orderFills-" in channel:
            await self._handle_order_fill(data, output)
        elif "position-" in channel:
            await self._handle_position_update(data, output)
        elif "user-" in channel:
            await self._handle_balance_update(data, output)
        elif "funding-" in channel:
            await self._handle_funding_update(data, output)
        elif "order-fee-" in channel:
            await self._handle_fee_update(data, output)
    
    async def _handle_order_update(
        self,
        data: Dict,
        output: asyncio.Queue
    ) -> None:
        message = {
            "type": "order_update",
            "order_id": data.get("orderId"),
            "client_order_id": data.get("clientOrderId"),
            "trading_pair": utils.to_trading_pair(data.get("instrument", "")),
            "status": web_utils.parse_order_status(data.get("status", "")),
            "side": web_utils.parse_order_side(data.get("side", "")),
            "order_type": data.get("type", "").lower(),
            "price": float(data.get("price", 0)),
            "quantity": float(data.get("quantity", 0)),
            "filled_quantity": float(data.get("filledQuantity", 0)),
            "remaining_quantity": float(data.get("remainingQuantity", 0)),
            "timestamp": web_utils.parse_timestamp_ms(data.get("t", 0)),
            "raw": data,
        }
        
        await output.put(message)
        logger.debug(f"Order update: {data.get('orderId')} - {data.get('status')}")
    
    async def _handle_order_fill(
        self,
        data: Dict,
        output: asyncio.Queue
    ) -> None:
        message = {
            "type": "order_fill",
            "order_id": data.get("orderId"),
            "execution_id": data.get("executionId"),
            "trading_pair": utils.to_trading_pair(data.get("instrument", "")),
            "side": web_utils.parse_order_side(data.get("side", "")),
            "price": float(data.get("price", 0)),
            "quantity": float(data.get("quantity", 0)),
            "fee": float(data.get("fee", 0)),
            "fee_currency": data.get("feeCurrency", ""),
            "is_maker": data.get("maker", False),
            "timestamp": web_utils.parse_timestamp_ms(data.get("t", 0)),
            "raw": data,
        }
        
        await output.put(message)
        logger.debug(
            f"Order fill: {data.get('orderId')} - "
            f"{data.get('quantity')}@{data.get('price')}"
        )
    
    async def _handle_position_update(
        self,
        data: Dict,
        output: asyncio.Queue
    ) -> None:
        message = {
            "type": "position_update",
            "trading_pair": utils.to_trading_pair(data.get("instrument", "")),
            "position_side": data.get("side", "").lower(),
            "quantity": float(data.get("quantity", 0)),
            "entry_price": float(data.get("entryPrice", 0)),
            "mark_price": float(data.get("markPrice", 0)),
            "liquidation_price": float(data.get("liquidationPrice", 0)),
            "unrealized_pnl": float(data.get("unrealizedPnl", 0)),
            "realized_pnl": float(data.get("realizedPnl", 0)),
            "leverage": float(data.get("leverage", 1)),
            "timestamp": web_utils.parse_timestamp_ms(data.get("t", 0)),
            "raw": data,
        }
        
        await output.put(message)
        logger.debug(
            f"Position update: {data.get('instrument')} - "
            f"{data.get('quantity')}@{data.get('entryPrice')}"
        )
    
    async def _handle_balance_update(
        self,
        data: Dict,
        output: asyncio.Queue
    ) -> None:
        message = {
            "type": "balance_update",
            "currency": data.get("currency", ""),
            "total_balance": float(data.get("totalBalance", 0)),
            "available_balance": float(data.get("availableBalance", 0)),
            "margin_balance": float(data.get("marginBalance", 0)),
            "unrealized_pnl": float(data.get("unrealizedPnl", 0)),
            "timestamp": web_utils.parse_timestamp_ms(data.get("t", 0)),
            "raw": data,
        }
        
        await output.put(message)
        logger.debug(
            f"Balance update: {data.get('currency')} - "
            f"available={data.get('availableBalance')}"
        )
    
    async def _handle_funding_update(
        self,
        data: Dict,
        output: asyncio.Queue
    ) -> None:
        message = {
            "type": "funding_payment",
            "trading_pair": utils.to_trading_pair(data.get("instrument", "")),
            "funding_rate": float(data.get("fundingRate", 0)),
            "payment": float(data.get("payment", 0)),
            "timestamp": web_utils.parse_timestamp_ms(data.get("t", 0)),
            "raw": data,
        }
        
        await output.put(message)
        logger.debug(
            f"Funding payment: {data.get('instrument')} - "
            f"rate={data.get('fundingRate')}, payment={data.get('payment')}"
        )
    
    async def _handle_fee_update(
        self,
        data: Dict,
        output: asyncio.Queue
    ) -> None:
        message = {
            "type": "fee_update",
            "order_id": data.get("orderId"),
            "fee": float(data.get("fee", 0)),
            "fee_currency": data.get("feeCurrency", ""),
            "timestamp": web_utils.parse_timestamp_ms(data.get("t", 0)),
            "raw": data,
        }
        
        await output.put(message)

    async def _ensure_ws_connection(self):
        if self._ws_connected:
            return
        
        async with self._ws_connect_lock:
            if self._ws_connected:
                return
            
            try:
                await self._ws_assistant.connect(
                    ws_url=self._ws_base,
                    ping_timeout=CONSTANTS.WS_HEARTBEAT_INTERVAL,
                )
            except RuntimeError:
                # Already connected
                pass
            
            auth_payload = self._auth.get_ws_auth_payload()
            if auth_payload:
                connect_msg = {"connect": auth_payload}
                await self._ws_assistant.send(WSJSONRequest(payload=connect_msg))
            
            self._ws_connected = True
