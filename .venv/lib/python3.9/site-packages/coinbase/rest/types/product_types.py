from typing import Any, Dict, List, Optional

from coinbase.rest.types.base_response import BaseResponse


# Get Best Bid/Ask
class GetBestBidAskResponse(BaseResponse):
    def __init__(self, response: dict):
        if "pricebooks" in response:
            self.pricebooks: Optional[List[PriceBook]] = [
                PriceBook(**pricebook) for pricebook in response.pop("pricebooks")
            ]
        super().__init__(**response)


# Get Product Book
class GetProductBookResponse(BaseResponse):
    def __init__(self, response: dict):
        if "pricebook" in response:
            self.pricebook: PriceBook = PriceBook(**response.pop("pricebook"))
        if "last" in response:
            self.last: Optional[str] = response.pop("last")
        if "mid_market" in response:
            self.mid_market: Optional[str] = response.pop("mid_market")
        if "spread_bps" in response:
            self.spread_bps: Optional[str] = response.pop("spread_bps")
        if "spread_absolute" in response:
            self.spread_absolute: Optional[str] = response.pop("spread_absolute")
        super().__init__(**response)


# List Products
class ListProductsResponse(BaseResponse):
    def __init__(self, response: dict):
        if "products" in response:
            self.products: Optional[List[Product]] = [
                Product(**product) for product in response.pop("products")
            ]
        if "num_products" in response:
            self.num_products: Optional[int] = response.pop("num_products")
        super().__init__(**response)


# Get Product
class GetProductResponse(BaseResponse):
    def __init__(self, response: dict):
        if "product_id" in response:
            self.product_id: str = response.pop("product_id")
        if "price" in response:
            self.price: str = response.pop("price")
        if "price_percentage_change_24h" in response:
            self.price_percentage_change_24h: str = response.pop(
                "price_percentage_change_24h"
            )
        if "volume_24h" in response:
            self.volume_24h: str = response.pop("volume_24h")
        if "volume_percentage_change_24h" in response:
            self.volume_percentage_change_24h: str = response.pop(
                "volume_percentage_change_24h"
            )
        if "base_increment" in response:
            self.base_increment: str = response.pop("base_increment")
        if "quote_increment" in response:
            self.quote_increment: str = response.pop("quote_increment")
        if "quote_min_size" in response:
            self.quote_min_size: str = response.pop("quote_min_size")
        if "quote_max_size" in response:
            self.quote_max_size: str = response.pop("quote_max_size")
        if "base_min_size" in response:
            self.base_min_size: str = response.pop("base_min_size")
        if "base_max_size" in response:
            self.base_max_size: str = response.pop("base_max_size")
        if "base_name" in response:
            self.base_name: str = response.pop("base_name")
        if "quote_name" in response:
            self.quote_name: str = response.pop("quote_name")
        if "watched" in response:
            self.watched: bool = response.pop("watched")
        if "is_disabled" in response:
            self.is_disabled: bool = response.pop("is_disabled")
        if "new" in response:
            self.new: bool = response.pop("new")
        if "status" in response:
            self.status: str = response.pop("status")
        if "cancel_only" in response:
            self.cancel_only: bool = response.pop("cancel_only")
        if "limit_only" in response:
            self.limit_only: bool = response.pop("limit_only")
        if "post_only" in response:
            self.post_only: bool = response.pop("post_only")
        if "trading_disabled" in response:
            self.trading_disabled: bool = response.pop("trading_disabled")
        if "auction_mode" in response:
            self.auction_mode: bool = response.pop("auction_mode")
        if "product_type" in response:
            self.product_type: Optional[str] = response.pop("product_type")
        if "quote_currency_id" in response:
            self.quote_currency_id: Optional[str] = response.pop("quote_currency_id")
        if "base_currency_id" in response:
            self.base_currency_id: Optional[str] = response.pop("base_currency_id")
        if "fcm_trading_session_details" in response:
            self.fcm_trading_session_details: Optional[Dict[str, Any]] = response.pop(
                "fcm_trading_session_details"
            )
        if "mid_market_price" in response:
            self.mid_market_price: Optional[str] = response.pop("mid_market_price")
        if "alias" in response:
            self.alias: Optional[str] = response.pop("alias")
        if "alias_to" in response:
            self.alias_to: Optional[List[str]] = response.pop("alias_to")
        if "base_display_symbol" in response:
            self.base_display_symbol: str = response.pop("base_display_symbol")
        if "quote_display_symbol" in response:
            self.quote_display_symbol: Optional[str] = response.pop(
                "quote_display_symbol"
            )
        if "view_only" in response:
            self.view_only: Optional[bool] = response.pop("view_only")
        if "price_increment" in response:
            self.price_increment: Optional[str] = response.pop("price_increment")
        if "display_name" in response:
            self.display_name: Optional[str] = response.pop("display_name")
        if "product_venue" in response:
            self.product_venue: Optional[str] = response.pop("product_venue")
        if "approximate_quote_24h_volume" in response:
            self.approximate_quote_24h_volume: Optional[str] = response.pop(
                "approximate_quote_24h_volume"
            )
        if "future_product_details" in response:
            self.future_product_details: Optional[Dict[str, Any]] = response.pop(
                "future_product_details"
            )
        super().__init__(**response)


# Get Product Candles
class GetProductCandlesResponse(BaseResponse):
    def __init__(self, response: dict):
        if "candles" in response:
            self.candles: Optional[List[Candle]] = [
                Candle(**candle) for candle in response.pop("candles")
            ]
        super().__init__(**response)


# Get Market Trades
class GetMarketTradesResponse(BaseResponse):
    def __init__(self, response: dict):
        if "trades" in response:
            self.trades: Optional[List[HistoricalMarketTrade]] = [
                HistoricalMarketTrade(**trade) for trade in response.pop("trades")
            ]
        if "best_bid" in response:
            self.best_bid: Optional[str] = response.pop("best_bid")
        if "best_ask" in response:
            self.best_ask: Optional[str] = response.pop("best_ask")
        super().__init__(**response)


# ----------------------------------------------------------------


class L2Level(BaseResponse):
    def __init__(self, **kwargs):
        if "price" in kwargs:
            self.price: str = kwargs.pop("price")
        if "size" in kwargs:
            self.size: str = kwargs.pop("size")
        super().__init__(**kwargs)


class PriceBook(BaseResponse):
    def __init__(self, **kwargs):
        if "product_id" in kwargs:
            self.product_id: str = kwargs.pop("product_id")
        if "bids" in kwargs:
            self.bids: List[L2Level] = [
                L2Level(**l2_level) for l2_level in kwargs.pop("bids")
            ]
        if "asks" in kwargs:
            self.asks: List[L2Level] = [
                L2Level(**l2_level) for l2_level in kwargs.pop("asks")
            ]
        if "time" in kwargs:
            self.time: Optional[Dict[str, Any]] = kwargs.pop("time")
        super().__init__(**kwargs)


class Product(BaseResponse):
    def __init__(self, **kwargs):
        if "product_id" in kwargs:
            self.product_id: str = kwargs.pop("product_id")
        if "price" in kwargs:
            self.price: str = kwargs.pop("price")
        if "price_percentage_change_24h" in kwargs:
            self.price_percentage_change_24h: str = kwargs.pop(
                "price_percentage_change_24h"
            )
        if "volume_24h" in kwargs:
            self.volume_24h: str = kwargs.pop("volume_24h")
        if "volume_percentage_change_24h" in kwargs:
            self.volume_percentage_change_24h: str = kwargs.pop(
                "volume_percentage_change_24h"
            )
        if "base_increment" in kwargs:
            self.base_increment: str = kwargs.pop("base_increment")
        if "quote_increment" in kwargs:
            self.quote_increment: str = kwargs.pop("quote_increment")
        if "quote_min_size" in kwargs:
            self.quote_min_size: str = kwargs.pop("quote_min_size")
        if "quote_max_size" in kwargs:
            self.quote_max_size: str = kwargs.pop("quote_max_size")
        if "base_min_size" in kwargs:
            self.base_min_size: str = kwargs.pop("base_min_size")
        if "base_max_size" in kwargs:
            self.base_max_size: str = kwargs.pop("base_max_size")
        if "base_name" in kwargs:
            self.base_name: str = kwargs.pop("base_name")
        if "quote_name" in kwargs:
            self.quote_name: str = kwargs.pop("quote_name")
        if "watched" in kwargs:
            self.watched: bool = kwargs.pop("watched")
        if "is_disabled" in kwargs:
            self.is_disabled: bool = kwargs.pop("is_disabled")
        if "new" in kwargs:
            self.new: bool = kwargs.pop("new")
        if "status" in kwargs:
            self.status: str = kwargs.pop("status")
        if "cancel_only" in kwargs:
            self.cancel_only: bool = kwargs.pop("cancel_only")
        if "limit_only" in kwargs:
            self.limit_only: bool = kwargs.pop("limit_only")
        if "post_only" in kwargs:
            self.post_only: bool = kwargs.pop("post_only")
        if "trading_disabled" in kwargs:
            self.trading_disabled: bool = kwargs.pop("trading_disabled")
        if "auction_mode" in kwargs:
            self.auction_mode: bool = kwargs.pop("auction_mode")
        if "product_type" in kwargs:
            self.product_type: Optional[str] = kwargs.pop("product_type")
        if "quote_currency_id" in kwargs:
            self.quote_currency_id: Optional[str] = kwargs.pop("quote_currency_id")
        if "base_currency_id" in kwargs:
            self.base_currency_id: Optional[str] = kwargs.pop("base_currency_id")
        if "fcm_trading_session_details" in kwargs:
            self.fcm_trading_session_details: Optional[Dict[str, Any]] = kwargs.pop(
                "fcm_trading_session_details"
            )
        if "mid_market_price" in kwargs:
            self.mid_market_price: Optional[str] = kwargs.pop("mid_market_price")
        if "alias" in kwargs:
            self.alias: Optional[str] = kwargs.pop("alias")
        if "alias_to" in kwargs:
            self.alias_to: Optional[List[str]] = kwargs.pop("alias_to")
        if "base_display_symbol" in kwargs:
            self.base_display_symbol: str = kwargs.pop("base_display_symbol")
        if "quote_display_symbol" in kwargs:
            self.quote_display_symbol: Optional[str] = kwargs.pop(
                "quote_display_symbol"
            )
        if "view_only" in kwargs:
            self.view_only: Optional[bool] = kwargs.pop("view_only")
        if "price_increment" in kwargs:
            self.price_increment: Optional[str] = kwargs.pop("price_increment")
        if "display_name" in kwargs:
            self.display_name: Optional[str] = kwargs.pop("display_name")
        if "product_venue" in kwargs:
            self.product_venue: Optional[str] = kwargs.pop("product_venue")
        if "approximate_quote_24h_volume" in kwargs:
            self.approximate_quote_24h_volume: Optional[str] = kwargs.pop(
                "approximate_quote_24h_volume"
            )
        if "future_product_details" in kwargs:
            self.future_product_details: Optional[Dict[str, Any]] = kwargs.pop(
                "future_product_details"
            )
        super().__init__(**kwargs)


class Candle(BaseResponse):
    def __init__(self, **kwargs):
        if "start" in kwargs:
            self.start: Optional[str] = kwargs.pop("start")
        if "low" in kwargs:
            self.low: Optional[str] = kwargs.pop("low")
        if "high" in kwargs:
            self.high: Optional[str] = kwargs.pop("high")
        if "open" in kwargs:
            self.open: Optional[str] = kwargs.pop("open")
        if "close" in kwargs:
            self.close: Optional[str] = kwargs.pop("close")
        if "volume" in kwargs:
            self.volume: Optional[str] = kwargs.pop("volume")
        super().__init__(**kwargs)


class HistoricalMarketTrade(BaseResponse):
    def __init__(self, **kwargs):
        if "trade_id" in kwargs:
            self.trade_id: Optional[str] = kwargs.pop("trade_id")
        if "product_id" in kwargs:
            self.product_id: Optional[str] = kwargs.pop("product_id")
        if "price" in kwargs:
            self.price: Optional[str] = kwargs.pop("price")
        if "size" in kwargs:
            self.size: Optional[str] = kwargs.pop("size")
        if "time" in kwargs:
            self.time: Optional[str] = kwargs.pop("time")
        if "side" in kwargs:
            self.side: Optional[str] = kwargs.pop("side")
        if "exchange" in kwargs:
            self.exchange: Optional[str] = kwargs.pop("exchange")
        super().__init__(**kwargs)
