import logging
from abc import ABC, abstractmethod
import functools
from sqlalchemy import (
    Column,
)


@functools.total_ordering
class DatabaseTransformation(ABC):
    def __init__(self, migrator):
        self.migrator = migrator

    @abstractmethod
    def apply(self, db_handle):
        pass

    @property
    @abstractmethod
    def name(self):
        return ""

    @property
    def from_version(self):
        return 0

    @property
    @abstractmethod
    def to_version(self):
        return None

    def does_apply_to_version(self, original_version: int, target_version: int) -> bool:
        if self.to_version is not None:
            # from_version > 0 means from_version property was overridden by transformation class
            if self.from_version > 0:
                return (self.from_version >= original_version) and (self.to_version <= target_version)
            return (self.to_version > original_version) and (self.to_version <= target_version)
        return False

    def __eq__(self, other):
        return (self.to_version == other.to_version) and (self.from_version == other.to_version)

    def __lt__(self, other):
        if self.to_version == other.to_version:
            return self.from_version < other.from_version
        else:
            return self.to_version < other.to_version

    def add_column(self, engine, table_name, column: Column, dry_run=True):
        column_name = column.compile(dialect=engine.dialect)
        column_type = column.type.compile(engine.dialect)
        column_nullable = "NULL" if column.nullable else "NOT NULL"
        query_to_execute = f'ALTER TABLE \"{table_name}\" ADD COLUMN {column_name} {column_type} {column_nullable}'
        if dry_run:
            logging.getLogger().info(f"Query to execute in DB: {query_to_execute}")
        else:
            engine.execute(query_to_execute)
