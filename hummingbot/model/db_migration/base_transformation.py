import re
from typing import List, Dict, Any, Optional

from sqlalchemy import Inspector, inspect

from hummingbot.logger import HummingbotLogger
from hummingbot.model.db_migration.script_base import ScriptBase


class BaseTransformation(ScriptBase):
    """
    Base class for transformations
    """

    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger(cls.__name__)
        return cls._logger

    def __init__(self, table_name: str, session_factory: callable, **kwargs):
        super().__init__(session_factory)
        self.table_name = table_name
        self.where_clause = kwargs.get("where_clause", None)
        self.columns = kwargs.get("columns", [])
        self.inspector: Inspector = inspect(self.engine)

    def validate_table_name(self, table_name: str) -> bool:
        """
        Validate that the table name exists and only contains alphanumeric characters and underscores
        """
        if not re.match(r'^[a-zA-Z0-9_]+$', table_name):
            self.logger().error(f"Invalid table name format: {table_name}")
            return False
        
        # Check if table exists in the database
        if table_name not in self.inspector.get_table_names():
            self.logger().error(f"Table does not exist: {table_name}")
            return False
            
        return True
        
    def validate_where_clause(self, where_clause: str) -> bool:
        """
        Validate that the where clause only contains safe characters
        This is a basic validation and should be enhanced based on specific needs
        """
        if not where_clause:
            return True
            
        # Basic validation - allow alphanumeric, spaces, and common SQL operators
        if not re.match(r'^[a-zA-Z0-9_\s=<>!\'"%.*()]+$', where_clause):
            self.logger().error(f"Invalid where clause format: {where_clause}")
            return False
            
        return True

    def delete(self) -> None:
        """
        Delete data from the table
        """
        if not self.validate_table_name(self.table_name):
            raise ValueError(f"Invalid table name: {self.table_name}")
            
        if self.where_clause and not self.validate_where_clause(self.where_clause):
            raise ValueError(f"Invalid where clause: {self.where_clause}")
        
        # Execute the DELETE query with validated inputs
        if self.where_clause:
            query = f"DELETE FROM {self.table_name} WHERE {self.where_clause}"
        else:
            query = f"DELETE FROM {self.table_name}"
            
        self.execute(query)

    def select(self) -> List[Dict[str, Any]]:
        """
        Select data from the table
        """
        if not self.validate_table_name(self.table_name):
            raise ValueError(f"Invalid table name: {self.table_name}")
            
        if self.where_clause and not self.validate_where_clause(self.where_clause):
            raise ValueError(f"Invalid where clause: {self.where_clause}")
            
        # Validate columns if specified
        columns_str = "*"
        if self.columns:
            # Validate each column name
            for col in self.columns:
                if not re.match(r'^[a-zA-Z0-9_]+$', col):
                    raise ValueError(f"Invalid column name: {col}")
            columns_str = ", ".join(self.columns)
            
        # Execute the SELECT query with validated inputs
        if self.where_clause:
            query = f"SELECT {columns_str} FROM {self.table_name} WHERE {self.where_clause}"
        else:
            query = f"SELECT {columns_str} FROM {self.table_name}"
            
        return self.query(query)
