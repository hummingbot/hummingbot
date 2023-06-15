from enum import Enum, auto


class StrEnum(Enum):
    def _generate_next_value_(name, start, count, last_values):
        return name

    # This is needed to be used seamlessly with Pydantic BaseModel
    def __str__(self):
        return self.name


class CoinbaseAdvancedTradeExchangeAccountTypeEnum(StrEnum):
    ACCOUNT_TYPE_UNSPECIFIED = auto()
    ACCOUNT_TYPE_CRYPTO = auto()
    ACCOUNT_TYPE_FIAT = auto()
    ACCOUNT_TYPE_VAULT = auto()


# --- Orders ---

class CoinbaseAdvancedTradeOrderSide(StrEnum):
    UNKNOWN_ORDER_SIDE = auto()
    BUY = auto()
    SELL = auto()


class CoinbaseAdvancedTradeCreateOrderFailureReason(StrEnum):
    UNKNOWN_FAILURE_REASON = auto()
    UNSUPPORTED_ORDER_CONFIGURATION = auto()
    INVALID_SIDE = auto()
    INVALID_PRODUCT_ID = auto()
    INVALID_SIZE_PRECISION = auto()
    INVALID_PRICE_PRECISION = auto()
    INSUFFICIENT_FUND = auto()
    INVALID_LEDGER_BALANCE = auto()
    ORDER_ENTRY_DISABLED = auto()
    INELIGIBLE_PAIR = auto()
    INVALID_LIMIT_PRICE_POST_ONLY = auto()
    INVALID_LIMIT_PRICE = auto()
    INVALID_NO_LIQUIDITY = auto()
    INVALID_REQUEST = auto()
    COMMANDER_REJECTED_NEW_ORDER = auto()
    INSUFFICIENT_FUNDS = auto()


class CoinbaseAdvancedTradePreviewFailureReason(StrEnum):
    UNKNOWN_PREVIEW_FAILURE_REASON = auto()
    PREVIEW_MISSING_COMMISSION_RATE = auto()
    PREVIEW_INVALID_SIDE = auto()
    PREVIEW_INVALID_ORDER_CONFIG = auto()
    PREVIEW_INVALID_PRODUCT_ID = auto()
    PREVIEW_INVALID_SIZE_PRECISION = auto()
    PREVIEW_INVALID_PRICE_PRECISION = auto()
    PREVIEW_MISSING_PRODUCT_PRICE_BOOK = auto()
    PREVIEW_INVALID_LEDGER_BALANCE = auto()
    PREVIEW_INSUFFICIENT_LEDGER_BALANCE = auto()
    PREVIEW_INVALID_LIMIT_PRICE_POST_ONLY = auto()
    PREVIEW_INVALID_LIMIT_PRICE = auto()
    PREVIEW_INVALID_NO_LIQUIDITY = auto()
    PREVIEW_INSUFFICIENT_FUND = auto()
    PREVIEW_INVALID_COMMISSION_CONFIGURATION = auto()
    PREVIEW_INVALID_STOP_PRICE = auto()
    PREVIEW_INVALID_BASE_SIZE_TOO_LARGE = auto()
    PREVIEW_INVALID_BASE_SIZE_TOO_SMALL = auto()
    PREVIEW_INVALID_QUOTE_SIZE_PRECISION = auto()
    PREVIEW_INVALID_QUOTE_SIZE_TOO_LARGE = auto()
    PREVIEW_INVALID_PRICE_TOO_LARGE = auto()
    PREVIEW_INVALID_QUOTE_SIZE_TOO_SMALL = auto()
    PREVIEW_BREACHED_PRICE_LIMIT = auto()
    PREVIEW_BREACHED_ACCOUNT_POSITION_LIMIT = auto()
    PREVIEW_BREACHED_COMPANY_POSITION_LIMIT = auto()
    PREVIEW_INVALID_MARGIN_HEALTH = auto()
    PREVIEW_RISK_PROXY_FAILURE = auto()


class CoinbaseAdvancedTradeNewOrderFailureReason(StrEnum):
    UNKNOWN_FAILURE_REASON = auto()
    UNSUPPORTED_ORDER_CONFIGURATION = auto()
    INVALID_SIDE = auto()
    INVALID_PRODUCT_ID = auto()
    INVALID_SIZE_PRECISION = auto()
    INVALID_PRICE_PRECISION = auto()
    INSUFFICIENT_FUND = auto()
    INVALID_LEDGER_BALANCE = auto()
    ORDER_ENTRY_DISABLED = auto()
    INELIGIBLE_PAIR = auto()
    INVALID_LIMIT_PRICE_POST_ONLY = auto()
    INVALID_LIMIT_PRICE = auto()
    INVALID_NO_LIQUIDITY = auto()
    INVALID_REQUEST = auto()
    COMMANDER_REJECTED_NEW_ORDER = auto()
    INSUFFICIENT_FUNDS = auto()


class CoinbaseAdvancedTradeCancelFailureReason(StrEnum):
    UNKNOWN_CANCEL_FAILURE_REASON = auto()
    INVALID_CANCEL_REQUEST = auto()
    UNKNOWN_CANCEL_ORDER = auto()
    COMMANDER_REJECTED_CANCEL_ORDER = auto()
    DUPLICATE_CANCEL_REQUEST = auto()


class CoinbaseAdvancedTradeExchangeOrderStatusEnum(StrEnum):
    OPEN = auto()
    FILLED = auto()
    CANCELLED = auto()
    EXPIRED = auto()
    FAILED = auto()
    UNKNOWN_ORDER_STATUS = auto()


class CoinbaseAdvancedTradeExchangeTimeInForceEnum(StrEnum):
    UNKNOWN_TIME_IN_FORCE = auto()
    GOOD_UNTIL_DATE_TIME = auto()
    GOOD_UNTIL_CANCELLED = auto()
    IMMEDIATE_OR_CANCEL = auto()
    FILL_OR_KILL = auto()


class CoinbaseAdvancedTradeExchangeOrderTypeEnum(StrEnum):
    UNKNOWN_ORDER_TYPE = auto()
    MARKET = auto()
    LIMIT = auto()
    STOP = auto()
    STOP_LIMIT = auto()


class CoinbaseAdvancedTradeExchangeTradeTypeEnum(StrEnum):
    FILL = auto()
    REVERSAL = auto()
    CORRECTION = auto()
    SYNTHETIC = auto()


class CoinbaseAdvancedTradeLiquidityIndicator(StrEnum):
    UNKNOWN_LIQUIDITY_INDICATOR = auto()
    MAKER = auto()
    TAKER = auto()


class CoinbaseAdvancedTradeStopDirection(StrEnum):
    UNKNOWN_STOP_DIRECTION = auto()
    STOP_DIRECTION_STOP_UP = auto()
    STOP_DIRECTION_STOP_DOWN = auto()


class CoinbaseAdvancedTradeGoodsAndServicesTaxType(StrEnum):
    INCLUSIVE = auto()
    EXCLUSIVE = auto()


# --- Websocket Enums ---


class CoinbaseAdvancedTradeWSSRequestType(StrEnum):
    subscribe = auto()
    unsubscribe = auto()


class CoinbaseAdvancedTradeWSSProductType(StrEnum):
    SPOT = auto()


class CoinbaseAdvancedTradeWSSEventType(StrEnum):
    snapshot = auto()
    update = auto()


class CoinbaseAdvancedTradeWSSOrderMakerSide(StrEnum):
    BUY = auto()
    SELL = auto()


class CoinbaseAdvancedTradeWSSOrderBidAskSide(StrEnum):
    bid = auto()
    ask = auto()


class CoinbaseAdvancedTradeWSSOrderStatus(StrEnum):
    PENDING = auto()
    OPEN = auto()
    FILLED = auto()
    CANCELLED = auto()
    EXPIRED = auto()
    FAILED = auto()


class CoinbaseAdvancedTradeWSSOrderType(StrEnum):
    Market = auto()
    Limit = auto()
    Stop_Limit = "Stop Limit"


class CoinbaseAdvancedTradeWSSChannel(StrEnum):
    market_trades = auto()
    status = auto()
    ticker = auto()
    ticker_batch = auto()
    l2_data = auto()
    user = auto()
