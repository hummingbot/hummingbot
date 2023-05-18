from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, TypedDict

from pydantic import Field, SecretStr

import hummingbot.connector.exchange.coinbase_advanced_trade.cat_constants as CONSTANTS
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.web_assistant.connections.data_types import EndpointRESTRequest

CENTRALIZED = True
EXAMPLE_PAIR = "ZRX-ETH"

DEFAULT_FEES = TradeFeeSchema(
    percent_fee_token="USD",
    maker_percent_fee_decimal=Decimal("0.004"),
    taker_percent_fee_decimal=Decimal("0.006"),
    buy_percent_fee_deducted_from_returns=False
)


class FeeTierInfo(TypedDict):
    """
    {
        "pricing_tier": "<$10k",
        "usd_from": "0",
        "usd_to": "10,000",
        "taker_fee_rate": "0.0010",
        "maker_fee_rate": "0.0020"
    }
    """
    pricing_tier: str
    usd_from: str
    usd_to: str
    taker_fee_rate: str
    maker_fee_rate: str


class TradingSummaryInfo(TypedDict):
    """
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_gettransactionsummary
    {
        "total_volume": 1000,
        "total_fees": 25,
        "fee_tier": {
            "pricing_tier": "<$10k",
            "usd_from": "0",
            "usd_to": "10,000",
            "taker_fee_rate": "0.0010",
            "maker_fee_rate": "0.0020"
        },
        "margin_rate": {
            "value": "string"
        },
        "goods_and_services_tax": {
            "rate": "string",
            "type": "INCLUSIVE"
        },
        "advanced_trade_only_volume": 1000,
        "advanced_trade_only_fees": 25,
        "coinbase_pro_volume": 1000,
        "coinbase_pro_fees": 25
    }
    """
    total_volume: int
    total_fees: int
    fee_tier: FeeTierInfo
    margin_rate: Dict[str, str]
    goods_and_services_tax: Dict[str, str]
    advanced_trade_only_volume: int
    advanced_trade_only_fees: int
    coinbase_pro_volume: int
    coinbase_pro_fees: int


class BalanceInfo(TypedDict):
    """
    {
        "value": "1.23",
        "currency": "BTC"
    }
    """
    value: str
    currency: str


class AccountInfo(TypedDict):
    """
    https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getaccounts
    {
        "uuid": "8bfc20d7-f7c6-4422-bf07-8243ca4169fe",
        "name": "BTC Wallet",
        "currency": "BTC",
        "available_balance": {
            "value": "1.23",
            "currency": "BTC"
        },
        "default": false,
        "active": true,
        "created_at": "2021-05-31T09:59:59Z",
        "updated_at": "2021-05-31T09:59:59Z",
        "deleted_at": "2021-05-31T09:59:59Z",
        "type": ["ACCOUNT_TYPE_UNSPECIFIED",
                 "ACCOUNT_TYPE_CRYPTO",
                 "ACCOUNT_TYPE_FIAT",
                 "ACCOUNT_TYPE_VAULT"],
        "ready": true,
        "hold": {
            "value": "1.23",
            "currency": "BTC"
        }
    }
    """
    uuid: str
    name: str
    currency: str
    available_balance: BalanceInfo
    default: bool
    active: bool
    created_at: str
    updated_at: str
    deleted_at: str
    type: str
    ready: bool
    hold: BalanceInfo


class Accounts(TypedDict):
    """
    {
        "accounts": AccountInfo,
        "has_next": true,
        "cursor": "789100",
        "size": "integer"
    }
    """
    accounts: List[AccountInfo]
    has_next: bool
    cursor: str
    size: str


class TradeInfo(TypedDict):
    """
    {
        "trade_id": "34b080bf-fcfd-445a-832b-46b5ddc65601",
        "product_id": "BTC-USD",
        "price": "140.91",
        "size": "4",
        "time": "2021-05-31T09:59:59Z",
        "side": ["UNKNOWN_ORDER_SIDE", "BUY", "SELL"],
        "bid": "291.13",
        "ask": "292.40"
    }
    """
    trade_id: str
    product_id: str
    price: str
    size: str
    time: str
    side: str
    bid: str
    ask: str


class Trades(TypedDict):
    trades: List[TradeInfo]
    best_bid: str
    best_ask: str


class ProductInfo(TypedDict):
    product_id: str
    price: str
    price_percentage_change_24h: str
    volume_24h: str
    volume_percentage_change_24h: str
    base_increment: str
    quote_increment: str
    quote_min_size: str
    quote_max_size: str
    base_min_size: str
    base_max_size: str
    base_name: str
    quote_name: str
    watched: bool
    is_disabled: bool
    new: bool
    status: str
    cancel_only: bool
    limit_only: bool
    post_only: bool
    trading_disabled: bool
    auction_mode: bool
    product_type: str
    quote_currency_id: str
    base_currency_id: str
    mid_market_price: str
    base_display_symbol: str
    quote_display_symbol: str


class Products(TypedDict):
    """
    {
      "products": {
        "product_id": "BTC-USD",
        "price": "140.21",
        "price_percentage_change_24h": "9.43%",
        "volume_24h": "1908432",
        "volume_percentage_change_24h": "9.43%",
        "base_increment": "0.00000001",
        "quote_increment": "0.00000001",
        "quote_min_size": "0.00000001",
        "quote_max_size": "1000",
        "base_min_size": "0.00000001",
        "base_max_size": "1000",
        "base_name": "Bitcoin",
        "quote_name": "US Dollar",
        "watched": true,
        "is_disabled": false,
        "new": true,
        "status": "string",
        "cancel_only": true,
        "limit_only": true,
        "post_only": true,
        "trading_disabled": false,
        "auction_mode": true,
        "product_type": "SPOT",
        "quote_currency_id": "USD",
        "base_currency_id": "BTC",
        "mid_market_price": "140.22",
        "base_display_symbol": "BTC",
        "quote_display_symbol": "USD"
      },
      "num_products": 100
    }
    """
    products: List[ProductInfo]
    num_products: int


def is_product_tradable(product_info: ProductInfo) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param product_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    is_valid = all((product_info["product_type"] == "SPOT",
                    product_info["trading_disabled"] is False,
                    product_info["is_disabled"] is False,
                    product_info["cancel_only"] is False,
                    product_info["limit_only"] is False,
                    product_info["post_only"] is False,
                    product_info["auction_mode"] is False))
    return is_valid


def is_valid_account(account_info: AccountInfo) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param account_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    is_valid = all((account_info["active"] is True,
                    account_info["type"] in ("ACCOUNT_TYPE_CRYPTO", "ACCOUNT_TYPE_FIAT"),
                    account_info["ready"] is True))
    return is_valid


@dataclass
class CoinbaseAdvancedTradeRESTRequest(EndpointRESTRequest):
    def __post_init__(self):
        super().__post_init__()
        self._ensure_endpoint_for_auth()

    @property
    def base_url(self) -> str:
        return CONSTANTS.REST_URL

    def _ensure_endpoint_for_auth(self):
        if self.is_auth_required and self.endpoint is None:
            raise ValueError("The endpoint must be specified if authentication is required.")


class CoinbaseAdvancedTradeConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="coinbase_advanced_trade", const=True, client_data=None)
    coinbase_advanced_trade_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Coinbase Advanced Trade API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    coinbase_advanced_trade_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Coinbase Advanced Trade API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "coinbase_advanced_trade"


KEYS = CoinbaseAdvancedTradeConfigMap.construct()

# OTHER_DOMAINS = ["coinbase_advanced_trade_us"]
# OTHER_DOMAINS_PARAMETER = {"coinbase_advanced_trade_us": "us"}
# OTHER_DOMAINS_EXAMPLE_PAIR = {"coinbase_advanced_trade_us": "BTC-USDT"}
# OTHER_DOMAINS_DEFAULT_FEES = {"coinbase_advanced_trade_us": DEFAULT_FEES}
#
#
# class CoinbaseAdvancedTradeUSConfigMap(BaseConnectorConfigMap):
#     connector: str = Field(default="coinbase_advanced_trade_us", const=True, client_data=None)
#     coinbase_advanced_trade_api_key: SecretStr = Field(
#         default=...,
#         client_data=ClientFieldData(
#             prompt=lambda cm: "Enter your CoinbaseAdvancedTrade US API key",
#             is_secure=True,
#             is_connect_key=True,
#             prompt_on_new=True,
#         )
#     )
#     coinbase_advanced_trade_api_secret: SecretStr = Field(
#         default=...,
#         client_data=ClientFieldData(
#             prompt=lambda cm: "Enter your CoinbaseAdvancedTrade US API secret",
#             is_secure=True,
#             is_connect_key=True,
#             prompt_on_new=True,
#         )
#     )
#
#     class Config:
#         title = "coinbase_advanced_trade_us"
#
#
# OTHER_DOMAINS_KEYS = {"coinbase_advanced_trade_us": CoinbaseAdvancedTradeUSConfigMap.construct()}
