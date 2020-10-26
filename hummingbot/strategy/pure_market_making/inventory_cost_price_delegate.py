from decimal import Decimal

from hummingbot.core.event.events import OrderFilledEvent, TradeType
from hummingbot.exceptions import NoPrice
from hummingbot.model.inventory_cost import InventoryCost
from hummingbot.model.sql_connection_manager import SQLConnectionManager


class InventoryCostPriceDelegate:
    def __init__(self, sql: SQLConnectionManager, trading_pair: str) -> None:
        self.base_asset, self.quote_asset = trading_pair.split("-")
        self._session = sql.get_shared_session()

    @property
    def ready(self) -> bool:
        return True

    def get_price(self) -> Decimal:
        record = InventoryCost.get_record(
            self._session, self.base_asset, self.quote_asset
        )
        try:
            price = record.quote_volume / record.base_volume
        except (ZeroDivisionError, AttributeError):
            raise NoPrice("Inventory cost delegate does not have price cost data yet")

        return Decimal(price)

    def process_order_fill_event(self, fill_event: OrderFilledEvent) -> None:
        base_asset, quote_asset = fill_event.trading_pair.split("-")
        quote_volume = fill_event.amount * fill_event.price
        base_volume = fill_event.amount

        for fee_asset, fee_amount in fill_event.trade_fee.flat_fees:
            if fill_event.trade_type == TradeType.BUY:
                if fee_asset == base_asset:
                    base_volume -= fee_amount
                elif fee_asset == quote_asset:
                    quote_volume += fee_amount
                else:
                    # Ok, some other asset used (like BNB), assume that we paid in base asset for simplicity
                    base_volume /= 1 + fill_event.trade_fee.percent
            else:
                if fee_asset == base_asset:
                    base_volume += fee_amount
                elif fee_asset == quote_asset:
                    quote_volume -= fee_amount
                else:
                    # Ok, some other asset used (like BNB), assume that we paid in quote asset for simplicity
                    quote_volume /= 1 + fill_event.trade_fee.percent

        if fill_event.trade_type == TradeType.SELL:
            base_volume = -base_volume
            quote_volume = -quote_volume

            # Make sure we're not going to create negative inventory cost here. If user didn't properly set cost,
            # just assume 0 cost, so consequent buys will set cost correctly
            record = InventoryCost.get_record(self._session, base_asset, quote_asset)
            if record:
                base_volume = max(-record.base_volume, base_volume)
                quote_volume = max(-record.quote_volume, quote_volume)
            else:
                base_volume = Decimal("0")
                quote_volume = Decimal("0")

        InventoryCost.update_or_create(
            self._session, base_asset, quote_asset, base_volume, quote_volume
        )
