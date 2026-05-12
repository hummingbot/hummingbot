from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.derivative.lighter_perpetual import (
    lighter_perpetual_constants as CONSTANTS,
    lighter_perpetual_web_utils as web_utils,
)
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.in_flight_order import OrderState


@dataclass(frozen=True)
class LighterMarketInfo:
    market_id: int
    exchange_symbol: str
    trading_pair: str
    base_asset: str
    quote_asset: str
    market_type: str
    min_base_amount: Decimal
    min_quote_amount: Decimal
    size_decimals: int
    price_decimals: int
    maker_fee: Decimal
    taker_fee: Decimal
    raw_info: Dict[str, Any]

    @property
    def min_base_increment(self) -> Decimal:
        return Decimal(f"1e-{self.size_decimals}")

    @property
    def min_price_increment(self) -> Decimal:
        return Decimal(f"1e-{self.price_decimals}")

    def trading_rule(self, collateral_token: Optional[str] = None) -> TradingRule:
        kwargs = {}
        if collateral_token is not None:
            kwargs.update(
                buy_order_collateral_token=collateral_token,
                sell_order_collateral_token=collateral_token,
            )
        return TradingRule(
            self.trading_pair,
            min_order_size=self.min_base_amount,
            min_base_amount_increment=self.min_base_increment,
            min_price_increment=self.min_price_increment,
            min_notional_size=self.min_quote_amount,
            **kwargs,
        )


def perpetual_markets_from_exchange_info(exchange_info: Dict[str, Any]) -> List[LighterMarketInfo]:
    markets = []
    for raw_market in exchange_info.get("order_book_details", []):
        if not web_utils.is_exchange_information_valid(raw_market):
            continue
        base_asset = str(raw_market["symbol"]).upper()
        trading_pair = combine_to_hb_trading_pair(
            base=base_asset, quote=CONSTANTS.PERPETUAL_QUOTE_TOKEN
        )
        markets.append(
            LighterMarketInfo(
                market_id=int(raw_market["market_id"]),
                exchange_symbol=base_asset,
                trading_pair=trading_pair,
                base_asset=base_asset,
                quote_asset=CONSTANTS.PERPETUAL_QUOTE_TOKEN,
                market_type="perp",
                min_base_amount=Decimal(str(raw_market["min_base_amount"])),
                min_quote_amount=Decimal(str(raw_market["min_quote_amount"])),
                size_decimals=int(raw_market["supported_size_decimals"]),
                price_decimals=int(raw_market["supported_price_decimals"]),
                maker_fee=Decimal(str(raw_market["maker_fee"])),
                taker_fee=Decimal(str(raw_market["taker_fee"])),
                raw_info=raw_market,
            )
        )
    return markets


def markets_by_id(markets: Iterable[LighterMarketInfo]) -> Dict[int, LighterMarketInfo]:
    return {market.market_id: market for market in markets}


def markets_by_trading_pair(markets: Iterable[LighterMarketInfo]) -> Dict[str, LighterMarketInfo]:
    return {market.trading_pair: market for market in markets}


def markets_by_exchange_symbol(markets: Iterable[LighterMarketInfo]) -> Dict[str, LighterMarketInfo]:
    return {market.exchange_symbol: market for market in markets}


def trading_pair_symbol_map(markets: Iterable[LighterMarketInfo]) -> bidict[str, str]:
    mapping = bidict()
    for market in markets:
        mapping[market.exchange_symbol] = market.trading_pair
    return mapping


def decimal_to_exchange_int(value: Decimal, decimals: int) -> int:
    scaled = value * (Decimal(10) ** decimals)
    return int(scaled.to_integral_value())


def timestamp_us_to_seconds(timestamp: Any) -> float:
    return float(timestamp or 0) * 1e-6


def next_funding_timestamp_seconds(last_funding_timestamp_ms: int) -> int:
    return int(last_funding_timestamp_ms / 1e3) + CONSTANTS.FUNDING_INTERVAL_SECONDS


def order_state_from_order_data(order_data: Dict[str, Any]) -> OrderState:
    status = str(order_data["status"])
    if status in CONSTANTS.OPEN_ORDER_STATES:
        filled_amount = Decimal(str(order_data.get("filled_base_amount", "0")))
        if filled_amount > Decimal("0"):
            return OrderState.PARTIALLY_FILLED
    return CONSTANTS.ORDER_STATE[status]


def account_index_from_account(account: Dict[str, Any]) -> int:
    return int(account.get("account_index", account.get("accountIndex", account.get("index"))))


def extract_account_snapshot(
    account_response: Dict[str, Any], account_index: Optional[int] = None, l1_address: Optional[str] = None
) -> Dict[str, Any]:
    accounts = account_response.get("accounts", account_response.get("sub_accounts", []))
    for account in accounts:
        if account_index is not None and account_index_from_account(account) == account_index:
            return account
        if (
            account_index is None
            and l1_address is not None
            and str(account.get("l1_address", "")).lower() == l1_address.lower()
        ):
            return account
    if account_index is None and l1_address is not None and len(accounts) > 0:
        return accounts[0]
    raise IOError(f"Account {account_index or l1_address} was not found in Lighter account response.")


def own_trade_details(trade: Dict[str, Any], account_index: int) -> Optional[Tuple[TradeType, str, str, bool]]:
    ask_account_id = int(trade.get("ask_account_id", -1))
    bid_account_id = int(trade.get("bid_account_id", -1))
    if ask_account_id == account_index:
        return (
            TradeType.SELL,
            str(trade.get("ask_client_id_str", trade.get("ask_client_id", ""))),
            str(trade.get("ask_id_str", trade.get("ask_id", ""))),
            bool(trade.get("is_maker_ask", False)),
        )
    if bid_account_id == account_index:
        return (
            TradeType.BUY,
            str(trade.get("bid_client_id_str", trade.get("bid_client_id", ""))),
            str(trade.get("bid_id_str", trade.get("bid_id", ""))),
            not bool(trade.get("is_maker_ask", False)),
        )
    return None
