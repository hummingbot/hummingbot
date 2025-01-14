# hummingbot/connector/exchange/zaif/zaif_exchange.py

import asyncio
import json
import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import aiohttp
from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.zaif import (
    zaif_constants as CONSTANTS,
    zaif_utils as utils,
    zaif_web_utils as web_utils,
)
from hummingbot.connector.exchange.zaif.zaif_api_order_book_data_source import ZaifAPIOrderBookDataSource
from hummingbot.connector.exchange.zaif.zaif_api_user_stream_data_source import ZaifAPIUserStreamDataSource
from hummingbot.connector.exchange.zaif.zaif_auth import ZaifAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class ZaifExchange(ExchangePyBase):
    web_utils = web_utils

    @property
    def authenticator(self):
        return ZaifAuth(
            api_key=self.zaif_api_key,
            secret_key=self.zaif_secret_key
        )

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        zaif_api_key: str,
        zaif_secret_key: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True
    ):
        self.zaif_api_key = zaif_api_key
        self.zaif_secret_key = zaif_secret_key
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._trading_pair_symbol_map: Dict[str, str] = {}
        self._exchange_to_hb_trading_pair_map: Dict[str, str] = {}
        self._hb_to_exchange_trading_pair_map: Dict[str, str] = {}
        self._throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self._auth = self.authenticator
        self._web_assistants_factory = web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth
        )
        super().__init__(client_config_map=client_config_map)
    async def send_http_request(
        self,
        method_name: str,
        http_method: str = 'POST',
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        is_auth_required: bool = False
    ) -> Dict[str, Any]:
        url = "https://api.zaif.jp/tapi"
        headers = {}
        payload = {}

        if is_auth_required:
            if data is None:
                data = {}
            data["nonce"] = self._auth._get_nonce()
            data["method"] = method_name

            # URLエンコード
            encoded_data = urlencode(data)

            # 署名付きヘッダーの生成
            headers = self._auth.get_auth_headers(encoded_data)

            # POSTデータとして送信
            payload = encoded_data

        else:
            # パブリックAPIの場合の処理（必要に応じて）
            payload = urlencode(params) if params else None

        # デバッグ用のログ
        # self.logger().info(f"URL: {url}")
        # self.logger().info(f"HTTP Method: {http_method}")
        # self.logger().info(f"Headers: {headers}")
        # self.logger().info(f"Payload: {payload}")
        #
        try:
            async with aiohttp.ClientSession() as session:
                if http_method.upper() == 'POST':
                    async with session.post(url, data=payload, headers=headers) as response:
                        resp_text = await response.text()
                elif http_method.upper() == 'GET':
                    async with session.get(url, params=params, headers=headers) as response:
                        resp_text = await response.text()
                else:
                    self.logger().error(f"Unsupported HTTP method: {http_method}")
                    return {"error": "Unsupported HTTP method"}

                # レスポンスのログ
                self.logger().info(f"Response Status: {response.status}")
                self.logger().info(f"Response Text: {resp_text}")

                try:
                    response_json = json.loads(resp_text)
                    return response_json
                except json.JSONDecodeError:
                    self.logger().error("Failed to decode JSON response")
                    return {"error": "Invalid JSON response"}

        except aiohttp.ClientError as e:
            self.logger().error(f"HTTP request failed: {e}")
            return {"error": f"HTTP request failed: {e}"}
        except Exception as e:
            self.logger().error(f"Unexpected error: {e}")
            return {"error": f"Unexpected error: {e}"}

    def _set_trading_pair_symbol_map(self, mapping: Dict[str, str]):
        self._trading_pair_symbol_map = mapping
        self._exchange_to_hb_trading_pair_map = mapping
        self._hb_to_exchange_trading_pair_map = {v: k for k, v in mapping.items()}


    async def _make_network_check_request(self):
        await self._api_get(
            path_url=self.check_network_request_path,
            throttler_limit_id=CONSTANTS.CHECK_NETWORK_LIMIT_ID
        )

    @property
    def name(self) -> str:
        return "zaif"

    @property
    def domain(self) -> str:
        return "zaif"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return "zaif"

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.SYMBOLS_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.SYMBOLS_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.SERVER_TIME_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT]

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pairs_prices = await self._api_get(
            path_url=CONSTANTS.ALL_TICKERS_PATH_URL,
            throttler_limit_id=CONSTANTS.PUBLIC_API_LIMIT_ID
        )
        return pairs_prices

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        error_description = str(request_exception)
        return False  # Zaif では特にタイムスタンプエラーの処理は不要かもしれません

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return False  # Zaif の API エラーコードに応じて実装

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return False  # Zaif の API エラーコードに応じて実装

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return ZaifAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return ZaifAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
        )

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> AddedToCostTradeFee:

        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        fee_value = Decimal("0.001")  # Zaif の手数料率（0.1%）
        fee = AddedToCostTradeFee(percent=fee_value)
        return fee

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: List[Dict[str, Any]]):
        mapping = {}
        for symbol_data in exchange_info:
            try:
                # 'currency_pair' から通貨ペアを取得し、'_' で分割
                symbol = symbol_data["currency_pair"]  # 例: 'btc_jpy'
                base, quote = symbol.split("_")
                base = base.upper()  # 'btc' -> 'BTC'
                quote = quote.upper()  # 'jpy' -> 'JPY'
                trading_pair = f"{base}-{quote}"  # 'BTC-JPY' の形式にする
                mapping[symbol] = trading_pair
            except KeyError as e:
                self.logger().error(f"KeyError when processing symbol data: {symbol_data}. Missing key: {e}")
                continue
        self._set_trading_pair_symbol_map(mapping)
       
    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        action = "bid" if trade_type == TradeType.BUY else "ask"
        data = {
            "method": "trade",
            "currency_pair": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "action": action,
            "amount": str(amount),
            "price": str(price),
        }
        response = await self._api_post(
            path_url=CONSTANTS.PRIVATE_API_PATH_URL,
            throttler_limit_id=CONSTANTS.PRIVATE_API_LIMIT_ID,
            data=data,
            is_auth_required=True,
        )
        if response.get("return") is None:
            raise IOError(f"Error placing order on Zaif: {response}")
        exchange_order_id = str(response["return"]["order_id"])
        return exchange_order_id, self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        data = {
            "method": "cancel_order",
            "order_id": order_id,
        }
        response = await self._api_post(
            path_url=CONSTANTS.PRIVATE_API_PATH_URL,
            throttler_limit_id=CONSTANTS.PRIVATE_API_LIMIT_ID,
            data=data,
            is_auth_required=True,
        )
        if response.get("return") is not None and response["return"].get("order_id") == int(order_id):
            return True
        else:
            raise IOError(f"Error cancelling order on Zaif: {response}")

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        # Zaif の取引履歴 API を使用して、注文の取引履歴を取得します
        data = {
            "method": "trade_history",
            "order_id": order.exchange_order_id,
        }
        response = await self._api_post(
            path_url=CONSTANTS.PRIVATE_API_PATH_URL,
            data=data,
            is_auth_required=True,
        )
        trade_updates = []
        if response.get("return"):
            for trade_id, trade_data in response["return"].items():
                trade_update = TradeUpdate(
                    trade_id=trade_id,
                    client_order_id=order.client_order_id,
                    exchange_order_id=order.exchange_order_id,
                    trading_pair=order.trading_pair,
                    fee=TradeFeeBase(
                        percent=Decimal(trade_data["fee"])
                    ),
                    fill_base_amount=Decimal(trade_data["amount"]),
                    fill_quote_amount=Decimal(trade_data["price"]) * Decimal(trade_data["amount"]),
                    fill_price=Decimal(trade_data["price"]),
                    fill_timestamp=trade_data["timestamp"],
                )
                trade_updates.append(trade_update)
        return trade_updates

    async def _update_trading_fees(self):
        # Zaif は固定の手数料体系であるため、特に更新は不要かもしれません
        pass


    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        total_jpy = Decimal('0')
        import pdb; pdb.set_trace()  # ここでデバッグセッションが開始されます 

        # アカウント情報の取得
        account_info = await self.send_http_request(
            method_name="get_info",
            http_method='POST',
            data={},  # 必要に応じてパラメータを追加
            is_auth_required=True,
        )

        # APIレスポンスのログ
        # self.logger().info(f"API Response: {account_info}")

        # レスポンスの検証
        if "success" not in account_info or account_info["success"] != 1:
            error_message = account_info.get("error", "Unknown error")
            self.logger().error(f"APIエラー: {error_message}")
            return

        balances = account_info["return"]["funds"]
        for asset_name, free_balance in balances.items():
            # 資産名の正規化
            self.logger().info(f"asset: {asset_name}")
            asset = asset_name.lower()
            free = Decimal(str(free_balance))
            locked = Decimal(str(account_info["return"]["funds"].get("locked", {}).get(asset_name, '0')))
            total = free + locked

            # 為替レートの取得
            # exchange_rate = await self.get_exchange_rate(asset)
            # if exchange_rate is None:
            #     self.logger().error(f"Exchange rate not found for {asset.upper()}, skipping...")
            #     continue

            # JPY換算額の計算
            balance_jpy = total 
            total_jpy += balance_jpy

            # 残高の更新
            self._account_available_balances[asset] = free
            self._account_balances[asset] = total
            remote_asset_names.add(asset)

            # 各資産のJPY換算額をログに出力
            self.logger().info(f"{asset.upper()}: {total} -> {balance_jpy} JPY")

        # JPY総額のログ出力
        self.logger().info(f"Total Balance in JPY: {total_jpy}")
        self._account_balances['JPY'] = 1200

        # 既存の資産にないものを削除
        # asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        # for asset_name in asset_names_to_remove:
        #     del self._account_available_balances[asset_name]
        #     del self._account_balances[asset_name]

    async def _user_stream_event_listener(self):
        # Zaif は WebSocket をサポートしていないため、ポーリングで実装します
        while True:
            try:
                await self._update_order_status()
                await self._update_balances()
                await asyncio.sleep(1)  # 適切な間隔でポーリング
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Error in user stream listener: {str(e)}")
                await asyncio.sleep(5)

    async def _format_trading_rules(self, exchange_info: Dict[str, Any]) -> List[TradingRule]:
        trading_rules = []
        for info in exchange_info.get("currency_pairs", []):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=info["currency_pair"])
                trading_rules.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=Decimal(info["min_amount"]),
                        min_price_increment=Decimal("0.0001"),  # Zaif の仕様に合わせて修正
                        min_base_amount_increment=Decimal("0.00000001"),  # Zaif の仕様に合わせて修正
                    )
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {info}. Skipping.", exc_info=True)
        return trading_rules

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        self.logger().info(f"in order update: {tracked_order}")
        data = {
            "method": "active_orders",
            "currency_pair": await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        }
        response = await self._api_post(
            path_url=CONSTANTS.PRIVATE_API_PATH_URL,
            data=data,
            is_auth_required=True
        )
        orders = response.get("return", {})
        order_data = orders.get(tracked_order.exchange_order_id)
        if order_data:
            order_status = order_data["status"]
            if order_status == "open":
                new_state = OrderState.OPEN
            elif order_status == "closed":
                new_state = OrderState.FILLED
            elif order_status == "canceled":
                new_state = OrderState.CANCELED
            else:
                new_state = OrderState.FAILED
            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=new_state,
            )
            return order_update
        else:
            # 注文が存在しない場合
            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.NOT_FOUND,
            )
            return order_update


