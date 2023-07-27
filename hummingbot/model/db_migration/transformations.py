from sqlalchemy import Column, Integer, Text

from hummingbot.model.db_migration.base_transformation import DatabaseTransformation
from hummingbot.model.decimal_type_decorator import SqliteDecimal
from hummingbot.model.sql_connection_manager import SQLConnectionManager


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


class ConvertPriceAndAmountColumnsToBigint(DatabaseTransformation):
    order_migration_queries = [
        ('create table Order_dg_tmp'
         '(	id TEXT not null'
         '		primary key,'
         '	config_file_path TEXT not null,'
         '	strategy TEXT not null,'
         '	market TEXT not null,'
         '	symbol TEXT not null,'
         '	base_asset TEXT not null,'
         '	quote_asset TEXT not null,'
         '	creation_timestamp BIGINT not null,'
         '	order_type TEXT not null,'
         '	amount BIGINT not null,'
         '	leverage INTEGER not null,'
         '	price FLOAT not null,'
         '	last_status TEXT not null,'
         '	last_update_timestamp BIGINT not null,'
         '	exchange_order_id TEXT,'
         '	position TEXT);'),
        ('insert into Order_dg_tmp(id, config_file_path, strategy, market, symbol, base_asset, '
         'quote_asset, creation_timestamp, order_type, amount, leverage, price, last_status, '
         'last_update_timestamp, exchange_order_id, position) '
         'select id, config_file_path, strategy, market, symbol, base_asset, quote_asset, '
         'creation_timestamp, order_type, CAST(amount * 1000000 AS INTEGER), leverage, '
         'CAST(price * 1000000 AS INTEGER), last_status, last_update_timestamp, exchange_order_id, '
         'position from "Order";'),
        'drop table "Order";',
        'alter table Order_dg_tmp rename to "Order";',
        'create index o_config_timestamp_index on "Order" (config_file_path, creation_timestamp);',
        'create index o_market_base_asset_timestamp_index on "Order" (market, base_asset, creation_timestamp);',
        'create index o_market_quote_asset_timestamp_index on "Order" (market, quote_asset, creation_timestamp);',
        'create index o_market_trading_pair_timestamp_index on "Order" (market, symbol, creation_timestamp);'
    ]

    trade_fill_migration_queries = [
        ('create table TradeFill_dg_tmp'
         '(	config_file_path TEXT not null,'
         '	strategy TEXT not null,'
         '	market TEXT not null,'
         '	symbol TEXT not null,'
         '	base_asset TEXT not null,'
         '	quote_asset TEXT not null,'
         '	timestamp BIGINT not null,'
         '	order_id TEXT not null'
         '		references "Order",'
         '	trade_type TEXT not null,'
         '	order_type TEXT not null,'
         '	price BIGINT not null,'
         '	amount FLOAT not null,'
         '	leverage INTEGER not null,'
         '	trade_fee JSON not null,'
         '	exchange_trade_id TEXT not null,'
         '	position TEXT,'
         '	constraint TradeFill_pk'
         '	primary key (market, order_id, exchange_trade_id)'
         ');'),
        ('insert into TradeFill_dg_tmp(config_file_path, strategy, market, symbol, base_asset, '
         'quote_asset, timestamp, order_id, trade_type, order_type, price, amount, leverage, '
         'trade_fee, exchange_trade_id, position) '
         'select config_file_path, strategy, market, symbol, base_asset, quote_asset, timestamp, '
         'order_id, trade_type, order_type, CAST(price * 1000000 AS INTEGER), '
         "CAST(amount * 1000000 AS INTEGER), leverage, trade_fee, exchange_trade_id || '_' || id, position "
         'from TradeFill;'),
        'drop table TradeFill;',
        'alter table TradeFill_dg_tmp rename to TradeFill;',
        'create index tf_config_timestamp_index on TradeFill (config_file_path, timestamp);',
        'create index tf_market_base_asset_timestamp_index on TradeFill (market, base_asset, timestamp);',
        'create index tf_market_quote_asset_timestamp_index on TradeFill (market, quote_asset, timestamp);',
        'create index tf_market_trading_pair_timestamp_index on TradeFill (market, symbol, timestamp);'
    ]

    def apply(self, db_handle: SQLConnectionManager) -> SQLConnectionManager:
        for query in self.order_migration_queries:
            db_handle.engine.execute(query)
        for query in self.trade_fill_migration_queries:
            db_handle.engine.execute(query)
        return db_handle

    @property
    def name(self):
        return "ConvertPriceAndAmountColumnsToBigint"

    @property
    def to_version(self):
        return 20220130


class AddTradeFeeInQuote(DatabaseTransformation):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def apply(self, db_handle: SQLConnectionManager) -> SQLConnectionManager:
        trade_fee = Column("trade_fee_in_quote", SqliteDecimal(6), nullable=True)
        self.add_column(db_handle.engine, "TradeFill", trade_fee, dry_run=False)
        return db_handle

    @property
    def name(self):
        return "AddTradeFeeInQuote"

    @property
    def to_version(self):
        return 20230516
