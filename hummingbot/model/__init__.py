from sqlalchemy.ext.declarative import declarative_base

HummingbotBase = declarative_base()


def get_declarative_base():
    from .market_state import MarketState  # noqa: F401
    from .metadata import Metadata  # noqa: F401
    from .order import Order  # noqa: F401
    from .order_status import OrderStatus  # noqa: F401
    from .range_position_collected_fees import RangePositionCollectedFees  # noqa: F401
    from .range_position_update import RangePositionUpdate  # noqa: F401
    from .trade_fill import TradeFill  # noqa: F401
    return HummingbotBase
