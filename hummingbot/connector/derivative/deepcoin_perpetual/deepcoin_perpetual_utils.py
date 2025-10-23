from decimal import Decimal
from typing import Any, Dict, List, Tuple
from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.data_type.common import OrderType, TradeType, PositionSide, PositionMode, PositionAction
from hummingbot.core.data_type.trade_fee import TradeFeeBase, TokenAmount, AddedToCostTradeFee, DeductedFromReturnsTradeFee
from hummingbot.connector.derivative.deepcoin_perpetual import deepcoin_perpetual_constants as CONSTANTS
# Deepcoin fees
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0004"),
    taker_percent_fee_decimal=Decimal("0.0006"),
)

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    """
    return (exchange_info.get("instType") == "SWAP"
            and exchange_info.get("state") == "live")


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    """
    Converts exchange trading pair to Hummingbot format
    """
    if exchange_trading_pair:
        pair = exchange_trading_pair.replace("-SWAP", "")
        return pair
    return None


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    """
    Converts Hummingbot trading pair to exchange format
    """
    return hb_trading_pair+("-SWAP")

def is_exchange_inverse(hb_trading_pair: str) -> bool:
    """
    Converts Hummingbot trading pair to exchange format
    """
    _, quote_asset = split_hb_trading_pair(hb_trading_pair)
    if quote_asset == "USD":
        return True
    return False

def convert_from_exchange_order_type(exchange_order_type: str) -> OrderType:
    """
    Converts exchange order type to Hummingbot OrderType
    """
    if exchange_order_type.upper() == "LIMIT":
        return OrderType.LIMIT
    elif exchange_order_type.upper() == "MARKET":
        return OrderType.MARKET
    elif exchange_order_type.upper() == "POST_ONLY":
        return OrderType.LIMIT_MAKER
    else:
        return OrderType.LIMIT


def convert_to_exchange_order_type(order_type: OrderType) -> str:
    """
    Converts Hummingbot OrderType to exchange order type
    """
    if order_type == OrderType.LIMIT:
        return "limit"
    elif order_type == OrderType.MARKET:
        return "market"
    elif order_type == OrderType.LIMIT_MAKER:
        return "post_only"
    else:
        return "limit"


def convert_from_exchange_side(exchange_side: str) -> TradeType:
    """
    Converts exchange side to Hummingbot TradeType
    """
    if exchange_side.upper() == "BUY":
        return TradeType.BUY
    elif exchange_side.upper() == "SELL":
        return TradeType.SELL
    else:
        return TradeType.BUY


def convert_to_exchange_side(trade_type: TradeType) -> str:
    """
    Converts Hummingbot TradeType to exchange side
    """
    if trade_type == TradeType.BUY:
        return "buy"
    elif trade_type == TradeType.SELL:
        return "sell"
    else:
        return "buy"


def convert_from_exchange_position_side(exchange_position_side: str) -> PositionSide:
    """
    Converts exchange position side to Hummingbot PositionSide
    """
    if exchange_position_side.lower() == "long":
        return PositionSide.LONG
    elif exchange_position_side.lower() == "short":
        return PositionSide.SHORT
    else:
        return PositionSide.LONG


def convert_to_exchange_position_side(position_side: PositionSide) -> str:
    """
    Converts Hummingbot PositionSide to exchange position side
    """
    if position_side == PositionSide.LONG:
        return CONSTANTS.POSITION_SIDE_LONG
    elif position_side == PositionSide.SHORT:
        return CONSTANTS.POSITION_SIDE_SHORT
    else:
        return CONSTANTS.POSITION_SIDE_LONG


def convert_from_exchange_position_mode(exchange_position_mode: str) -> PositionMode:
    """
    Converts exchange position mode to Hummingbot PositionMode
    """
    if exchange_position_mode.lower() == "one_way":
        return PositionMode.ONEWAY
    elif exchange_position_mode.lower() == "hedge":
        return PositionMode.HEDGE
    else:
        return PositionMode.ONEWAY


def convert_to_exchange_position_mode(position_mode: PositionMode) -> str:
    """
    Converts Hummingbot PositionMode to exchange position mode
    """
    if position_mode == PositionMode.ONEWAY:
        return CONSTANTS.POSITION_MODE_ONE_WAY
    elif position_mode == PositionMode.HEDGE:
        return CONSTANTS.POSITION_MODE_HEDGE
    else:
        return CONSTANTS.POSITION_MODE_ONE_WAY


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    """
    Creates a new client order ID for a given trading pair
    """
    import time
    return f"{CONSTANTS.HBOT_BROKER_ID}-{trading_pair}-{int(time.time() * 1e6)}"


def extract_trading_pair_from_exchange_symbol(symbol: str) -> Optional[str]:
    """
    Extracts trading pair from exchange symbol
    """
    if "-" in symbol:
        return symbol.replace("-", "")
    return symbol


def get_trading_pair_from_exchange_info(symbol_info: Dict[str, Any]) -> Optional[str]:
    """
    Extracts trading pair from exchange symbol info
    """
    symbol = symbol_info.get("symbol", "")
    if symbol:
        return extract_trading_pair_from_exchange_symbol(symbol)
    return None


def parse_trading_rules(symbols: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parses trading rules from exchange symbols info
    """
    trading_rules = []
    for symbol_info in symbols:
        try:
            trading_pair = get_trading_pair_from_exchange_info(symbol_info)
            if trading_pair:
                trading_rules.append({
                    "trading_pair": trading_pair,
                    "min_order_size": Decimal(symbol_info.get("minOrderSize", "0.001")),
                    "max_order_size": Decimal(symbol_info.get("maxOrderSize", "1000000")),
                    "min_price_increment": Decimal(symbol_info.get("tickSize", "0.01")),
                    "min_base_amount_increment": Decimal(symbol_info.get("stepSize", "0.001")),
                    "min_notional_size": Decimal(symbol_info.get("minNotional", "5.0")),
                    "buy_order_fee": Decimal(symbol_info.get("makerFeeRate", "0.001")),
                    "sell_order_fee": Decimal(symbol_info.get("takerFeeRate", "0.001")),
                })
        except Exception as e:
            # Skip invalid symbols
            continue
    return trading_rules


def parse_order_status(exchange_order: Dict[str, Any]) -> str:
    """
    Parses order status from exchange order info
    """
    status = exchange_order.get("status", "").lower()
    return CONSTANTS.ORDER_STATE.get(status, "unknown")


def parse_position_data(position_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parses position data from exchange
    """
    return {
        "trading_pair": extract_trading_pair_from_exchange_symbol(position_data.get("symbol", "")),
        "position_side": convert_from_exchange_position_side(position_data.get("side", "")),
        "amount": Decimal(position_data.get("size", "0")),
        "entry_price": Decimal(position_data.get("entryPrice", "0")),
        "mark_price": Decimal(position_data.get("markPrice", "0")),
        "unrealized_pnl": Decimal(position_data.get("unrealizedPnl", "0")),
        "leverage": Decimal(position_data.get("leverage", "1")),
    }


def parse_trade_fee(fee_info: Dict[str, Any], trade_type: TradeType) -> TradeFeeBase:
    """
    Parses trade fee from exchange trade info
    """
    fee_currency = fee_info.get("feeCurrency", "")
    fee_amount = Decimal(fee_info.get("fee", "0"))
    
    if fee_amount > 0:
        if trade_type == TradeType.BUY:
            return DeductedFromReturnsTradeFee(flat_fees=[TokenAmount(fee_currency, fee_amount)])
        else:
            return AddedToCostTradeFee(flat_fees=[TokenAmount(fee_currency, fee_amount)])
    
    return TradeFeeBase.new_spot_fee(
        fee_schema=TradeFeeBase.new_spot_fee_schema(),
        maker_percent=Decimal("0.001"),
        taker_percent=Decimal("0.001")
    )


def parse_order_fill_from_trade(trade: Dict[str, Any], order: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parses order fill from exchange trade info
    """
    return {
        "trade_id": trade.get("tradeId", ""),
        "client_order_id": order.get("clientOrderId", ""),
        "exchange_order_id": order.get("orderId", ""),
        "trading_pair": extract_trading_pair_from_exchange_symbol(trade.get("symbol", "")),
        "trade_type": convert_from_exchange_side(trade.get("side", "")),
        "order_type": convert_from_exchange_order_type(trade.get("type", "")),
        "price": Decimal(trade.get("price", "0")),
        "amount": Decimal(trade.get("size", "0")),
        "trade_fee": parse_trade_fee(trade, convert_from_exchange_side(trade.get("side", ""))),
        "timestamp": trade.get("time", 0),
    }


class DeepcoinPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "deepcoin_perpetual"
    deepcoin_perpetual_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Deepcoin Perpetual API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    deepcoin_perpetual_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Deepcoin Perpetual API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    deepcoin_perpetual_passphrase: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Deepcoin Perpetual API passphrase",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="deepcoin_perpetual")


KEYS = DeepcoinPerpetualConfigMap.model_construct()



class DeepcoinPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "deepcoin_perpetual_testnet"
    deepcoin_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Deepcoin Perpetual Testnet API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    deepcoin_perpetual_testnet_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Deepcoin Perpetual Testnet API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    deepcoin_perpetual_testnet_passphrase: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Deepcoin Perpetual Testnet API passphrase",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="deepcoin_perpetual_testnet")


OTHER_DOMAINS_KEYS = {
    "deepcoin_perpetual_testnet": DeepcoinPerpetualTestnetConfigMap.model_construct()
}
