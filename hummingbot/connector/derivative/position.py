from decimal import Decimal

from hummingbot.core.data_type.common import PositionSide


class Position:
    def __init__(self,
                 trading_pair: str,
                 position_side: PositionSide,
                 unrealized_pnl: Decimal,
                 entry_price: Decimal,
                 amount: Decimal,
                 leverage: Decimal):
        self._trading_pair = trading_pair
        self._position_side = position_side
        self._unrealized_pnl = unrealized_pnl
        self._entry_price = entry_price
        self._amount = amount
        self._leverage = leverage

    def __repr__(self) -> str:
        return (
            f"Position("
            f" trading_pair={self._trading_pair},"
            f" position_side={self._position_side},"
            f" unrealized_pnl={self._unrealized_pnl},"
            f" entry_price={self._entry_price},"
            f" amount={self._amount},"
            f" leverage={self._leverage}"
            f")"
        )

    @property
    def trading_pair(self) -> str:
        return self._trading_pair

    @property
    def position_side(self) -> PositionSide:
        return self._position_side

    @property
    def unrealized_pnl(self) -> Decimal:
        return self._unrealized_pnl

    @property
    def entry_price(self) -> Decimal:
        return self._entry_price

    @property
    def amount(self) -> Decimal:
        return self._amount

    @property
    def leverage(self) -> Decimal:
        return self._leverage

    def update_position(self,
                        position_side: PositionSide = None,
                        unrealized_pnl: Decimal = None,
                        entry_price: Decimal = None,
                        amount: Decimal = None,
                        leverage: Decimal = None):
        self._position_side = position_side if position_side is not None else self._position_side
        self._unrealized_pnl = unrealized_pnl if unrealized_pnl is not None else self._unrealized_pnl
        self._entry_price = entry_price if entry_price is not None else self._entry_price
        self._amount = amount if amount is not None else self._amount
        self._leverage = leverage if leverage is not None else self._leverage
