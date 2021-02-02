from hummingbot.model.db_migration.base_transformation import DatabaseTransformation
from hummingbot.model.sql_connection_manager import SQLConnectionManager
from sqlalchemy import (
    Column,
    Text,
    Integer
)


class AddExchangeOrderIdColumnToOrders(DatabaseTransformation):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def apply(self, db_handle: SQLConnectionManager) -> SQLConnectionManager:
        exchange_order_id_column = Column("exchange_order_id", Text, nullable=True)
        self.add_column(db_handle.engine, "Order", exchange_order_id_column, dry_run=False)
        return db_handle

    @property
    def name(self):
        return "AddExchangeOrderIdColumnToOrders"

    @property
    def to_version(self):
        return 20210118


class AddLeverageAndPositionColumns(DatabaseTransformation):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def apply(self, db_handle: SQLConnectionManager) -> SQLConnectionManager:
        leverage_column = Column("leverage", Integer, nullable=True)
        position_column = Column("position", Text, nullable=True)
        self.add_column(db_handle.engine, "Order", leverage_column, dry_run=False)
        self.add_column(db_handle.engine, "Order", position_column, dry_run=False)
        self.add_column(db_handle.engine, "TradeFill", leverage_column, dry_run=False)
        self.add_column(db_handle.engine, "TradeFill", position_column, dry_run=False)
        return db_handle

    @property
    def name(self):
        return "AddLeverageAndPositionColumns"

    @property
    def to_version(self):
        return 20210119
