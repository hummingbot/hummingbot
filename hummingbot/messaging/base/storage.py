import asyncio
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from hummingbot import data_path

from .models import BotInstance, BrokerMessage, MessageStatus

logger = logging.getLogger(__name__)


class MessageStorage:
    """
    Independent storage mechanism for broker messages, completely separate from Hummingbot's main database.
    """
    DB_NAME = "hummingbot_messages.sqlite"

    def __init__(self):
        """Initialize the message storage with a dedicated database file."""
        self._db_path = os.path.join(data_path(), self.DB_NAME)
        self._init_db()
        logger.info(f"Message broker database initialized at {self._db_path}")

    def _init_db(self):
        """Initialize the database and create tables if they don't exist."""
        try:
            # Create directory if it doesn't exist
            db_dir = os.path.dirname(self._db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir)

            conn = sqlite3.connect(self._db_path, timeout=30.0)
            try:
                # Optimize database settings
                conn.execute("PRAGMA journal_mode=WAL")  # Use Write-Ahead Logging
                conn.execute("PRAGMA synchronous=NORMAL")  # Reduce synchronous setting for better performance
                conn.execute("PRAGMA busy_timeout=5000")  # Set busy timeout to 5 seconds

                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        instance_id TEXT NOT NULL,
                        strategy_name TEXT NOT NULL,
                        command TEXT NOT NULL,
                        source TEXT NOT NULL,
                        chat_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        response TEXT,
                        error TEXT
                    )
                ''')

                # Create index for faster message lookups by instance_id and status
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_instance_status ON messages (instance_id, status)')

                # Create instances table to track all available bot instances
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS instances (
                        composite_id TEXT PRIMARY KEY,
                        instance_id TEXT NOT NULL,
                        strategy_file TEXT NOT NULL,
                        strategy_name TEXT,
                        markets TEXT,
                        description TEXT
                    )
                ''')

                conn.commit()
                logger.debug(f"Database initialized successfully at {self._db_path}")
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.error(f"SQLite error initializing message database: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error initializing message database: {e}", exc_info=True)
            raise

    def _dict_to_message(self, row: Dict[str, Any]) -> BrokerMessage:
        """Convert a database row to a BrokerMessage object."""
        return BrokerMessage(
            id=row['id'],
            instance_id=row['instance_id'],
            strategy_name=row['strategy_name'],
            command=row['command'],
            source=row['source'],
            chat_id=row['chat_id'],
            status=MessageStatus(row['status']),
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            response=row['response'],
            error=row['error']
        )

    async def save_message(self, message: BrokerMessage) -> int:
        """Save a message to the database asynchronously."""
        now = datetime.utcnow().isoformat()

        query = '''
            INSERT INTO messages (
                instance_id, strategy_name, command, source, chat_id,
                status, created_at, updated_at, response, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            message.instance_id, message.strategy_name, message.command,
            message.source, message.chat_id, message.status.value,
            now, now, message.response, message.error
        )

        # Run database operation in a separate thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._execute_save_message, query, params)

    def _execute_save_message(self, query: str, params: tuple) -> int:
        """Execute the save message query synchronously."""
        conn = None
        try:
            conn = sqlite3.connect(self._db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")  # Use Write-Ahead Logging for better concurrency
            conn.execute("PRAGMA busy_timeout=5000")  # Set busy timeout to 5 seconds
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            message_id = cursor.lastrowid
            if not message_id:
                raise sqlite3.Error("Failed to get row ID after insert")
            logger.debug(f"Saved message with ID {message_id}, instance_id: {params[0]}")
            return message_id
        except sqlite3.Error as e:
            logger.error(f"Database error while saving message: {e}", exc_info=True)
            if conn:
                conn.rollback()
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving message: {e}", exc_info=True)
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    async def get_pending_messages(self, instance_id: str = None) -> List[BrokerMessage]:
        """Get pending messages asynchronously.

        Args:
            instance_id: Optional instance ID. If provided, filter messages for this instance only.
                         If None, return all pending messages for all instances.
        """
        if instance_id:
            query = '''
                SELECT id, instance_id, strategy_name, command, source, chat_id,
                       status, created_at, updated_at, response, error
                FROM messages
                WHERE instance_id = ? AND status = ?
                ORDER BY created_at ASC
            '''
        else:
            query = '''
                SELECT id, instance_id, strategy_name, command, source, chat_id,
                       status, created_at, updated_at, response, error
                FROM messages
                WHERE status = ?
                ORDER BY created_at ASC
            '''

        # Run database operation in a separate thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        rows = await loop.run_in_executor(
            None,
            self._execute_get_pending_messages,
            query,
            instance_id
        )
        messages = [self._dict_to_message(row) for row in rows]
        if messages:
            logger.debug(f"Retrieved {len(messages)} pending messages")
        return messages

    def _execute_get_pending_messages(self, query: str, instance_id: str = None) -> List[Dict[str, Any]]:
        """Execute the get pending messages query synchronously."""
        conn = None
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                conn = sqlite3.connect(self._db_path, timeout=30.0)
                # Performance optimizations
                conn.execute("PRAGMA busy_timeout=5000")  # Set busy timeout to 5 seconds

                # Configure connection to return dictionary-like rows
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Execute query with appropriate parameters based on whether instance_id is provided
                if instance_id:
                    cursor.execute(query, (instance_id, MessageStatus.NEW.value))
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Querying pending messages for instance {instance_id}")
                else:
                    cursor.execute(query, (MessageStatus.NEW.value,))
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug("Querying all pending messages")

                rows = [dict(row) for row in cursor.fetchall()]
                return rows
            except sqlite3.OperationalError as e:
                # Database is locked, retry after delay
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"Database locked, retrying ({retry_count}/{max_retries}): {e}")
                    import time
                    time.sleep(0.5 * retry_count)  # Exponential backoff
                    continue
                logger.error(f"Database error after {max_retries} retries: {e}", exc_info=True)
                return []
            except sqlite3.Error as e:
                logger.error(f"Database error while retrieving pending messages: {e}", exc_info=True)
                return []
            except Exception as e:
                logger.error(f"Unexpected error retrieving pending messages: {e}", exc_info=True)
                return []
            finally:
                if conn:
                    conn.close()
        return []

    async def update_message_status(
        self,
        message_id: int,
        status: MessageStatus,
        response: Optional[str] = None,
        error: Optional[str] = None
    ) -> None:
        """Update the status of a message asynchronously."""
        query = '''
            UPDATE messages
            SET status = ?, updated_at = ?, response = ?, error = ?
            WHERE id = ?
        '''

        now = datetime.utcnow().isoformat()
        params = (status.value, now, response, error, message_id)

        # Run database operation in a separate thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            self._execute_update_message_status,
            query,
            params
        )

    def _execute_update_message_status(self, query: str, params: tuple) -> None:
        """Execute the update message status query synchronously."""
        conn = None
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                conn = sqlite3.connect(self._db_path, timeout=30.0)
                conn.execute("PRAGMA busy_timeout=5000")  # Set busy timeout to 5 seconds
                cursor = conn.cursor()
                cursor.execute(query, params)
                if cursor.rowcount == 0:
                    logger.warning(f"No message found with ID {params[4]} to update status")
                else:
                    logger.debug(f"Updated message {params[4]} status to {params[0]}")
                conn.commit()
                return
            except sqlite3.OperationalError as e:
                # Database is locked, retry after delay
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"Database locked while updating status, retrying ({retry_count}/{max_retries}): {e}")
                    import time
                    time.sleep(0.5 * retry_count)  # Exponential backoff
                    continue
                logger.error(f"Database error after {max_retries} retries: {e}", exc_info=True)
                if conn:
                    conn.rollback()
                break
            except sqlite3.Error as e:
                logger.error(f"Database error while updating message status: {e}", exc_info=True)
                if conn:
                    conn.rollback()
                break
            except Exception as e:
                logger.error(f"Unexpected error updating message status: {e}", exc_info=True)
                if conn:
                    conn.rollback()
                break
            finally:
                if conn:
                    conn.close()

    async def get_completed_messages(self) -> List[BrokerMessage]:
        """Get messages that have been completed or failed."""
        query = '''
            SELECT id, instance_id, strategy_name, command, source, chat_id,
                   status, created_at, updated_at, response, error
            FROM messages
            WHERE status IN (?, ?)
            AND updated_at > datetime('now', '-10 minute')
            ORDER BY updated_at DESC
            LIMIT 100
        '''

        # Run database operation in a separate thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        rows = await loop.run_in_executor(
            None,
            self._execute_get_completed_messages,
            query
        )
        messages = [self._dict_to_message(row) for row in rows]
        logger.debug(f"Retrieved {len(messages)} completed/failed messages from database")
        for msg in messages:
            logger.debug(f"Retrieved message ID {msg.id}, status: {msg.status.value}, command: {msg.command}, instance: {msg.instance_id}")
        return messages

    def _execute_get_completed_messages(self, query: str) -> List[Dict[str, Any]]:
        """Execute the get completed messages query synchronously."""
        conn = None
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                conn = sqlite3.connect(self._db_path, timeout=30.0)
                conn.execute("PRAGMA busy_timeout=5000")  # Set busy timeout to 5 seconds

                # Configure connection to return dictionary-like rows
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    query,
                    (MessageStatus.COMPLETED.value, MessageStatus.FAILED.value)
                )
                rows = [dict(row) for row in cursor.fetchall()]
                logger.debug(f"Database query returned {len(rows)} completed messages")
                return rows
            except sqlite3.OperationalError as e:
                # Database is locked, retry after delay
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"Database locked while getting completed messages, retrying ({retry_count}/{max_retries}): {e}")
                    import time
                    time.sleep(0.5 * retry_count)  # Exponential backoff
                    continue
                logger.error(f"Database error after {max_retries} retries: {e}", exc_info=True)
                return []
            except sqlite3.Error as e:
                logger.error(f"Database error while retrieving completed messages: {e}", exc_info=True)
                return []
            except Exception as e:
                logger.error(f"Unexpected error retrieving completed messages: {e}", exc_info=True)
                return []
            finally:
                if conn:
                    conn.close()
        return []

    async def purge_old_messages(self, days: int = 7) -> int:
        """Remove messages older than the specified number of days."""
        # Run in a separate thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._execute_purge_old_messages, days)

    def _execute_purge_old_messages(self, days: int) -> int:
        """Execute purge of old messages synchronously."""
        conn = None
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            # Calculate the date threshold
            import time
            threshold = datetime.fromtimestamp(time.time() - days * 86400).isoformat()

            # Delete old records
            cursor.execute(
                "DELETE FROM messages WHERE created_at < ?",
                (threshold,)
            )
            deleted_count = cursor.rowcount
            conn.commit()

            if deleted_count > 0:
                logger.info(f"Purged {deleted_count} messages older than {days} days")
            return deleted_count
        except sqlite3.Error as e:
            logger.error(f"Database error while purging old messages: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return 0
        finally:
            if conn:
                conn.close()

    async def delete_message(self, message_id: int) -> bool:
        """Delete a processed message from the database.

        Args:
            message_id: The ID of the message to delete

        Returns:
            bool: True if message was deleted successfully
        """
        # Run in a separate thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._execute_delete_message, message_id)

    def _execute_delete_message(self, message_id: int) -> bool:
        """Execute message deletion synchronously."""
        conn = None
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                conn = sqlite3.connect(self._db_path, timeout=30.0)
                conn.execute("PRAGMA busy_timeout=5000")  # Set busy timeout to 5 seconds
                cursor = conn.cursor()

                # Delete the message with the specified ID
                cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
                deleted = cursor.rowcount > 0
                conn.commit()

                if deleted:
                    logger.debug(f"Deleted processed message with ID {message_id}")
                else:
                    logger.warning(f"No message found with ID {message_id} to delete")

                return deleted
            except sqlite3.OperationalError as e:
                # Database is locked, retry after delay
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"Database locked while deleting message, retrying ({retry_count}/{max_retries}): {e}")
                    import time
                    time.sleep(0.5 * retry_count)  # Exponential backoff
                    continue
                logger.error(f"Database error after {max_retries} retries: {e}", exc_info=True)
                if conn:
                    conn.rollback()
                return False
            except sqlite3.Error as e:
                logger.error(f"Database error while deleting message: {e}", exc_info=True)
                if conn:
                    conn.rollback()
                return False
            except Exception as e:
                logger.error(f"Unexpected error deleting message: {e}", exc_info=True)
                if conn:
                    conn.rollback()
                return False
            finally:
                if conn:
                    conn.close()
        return False

    async def register_instance(self, instance: BotInstance) -> bool:
        """Register or update a bot instance in the registry

        Args:
            instance: The BotInstance object with instance information

        Returns:
            bool: True if instance was registered successfully
        """
        # Run in a separate thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._execute_register_instance, instance)

    def _execute_register_instance(self, instance: BotInstance) -> bool:
        """Execute instance registration synchronously"""
        conn = None
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                conn = sqlite3.connect(self._db_path, timeout=30.0)
                conn.execute("PRAGMA busy_timeout=5000")  # Set busy timeout to 5 seconds
                cursor = conn.cursor()

                # Convert markets list to JSON string
                import json
                markets_str = json.dumps(instance.markets) if instance.markets else None

                # Insert or update the instance record
                cursor.execute("""
                    INSERT OR REPLACE INTO instances
                    (composite_id, instance_id, strategy_file, strategy_name, markets, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    instance.composite_id,
                    instance.instance_id,
                    instance.strategy_file,
                    instance.strategy_name,
                    markets_str,
                    instance.description
                ))
                conn.commit()

                logger.debug(f"Registered instance {instance.instance_id} with composite ID {instance.composite_id}")
                return True
            except sqlite3.OperationalError as e:
                # Database is locked, retry after delay
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"Database locked while registering instance, retrying ({retry_count}/{max_retries}): {e}")
                    import time
                    time.sleep(0.5 * retry_count)  # Exponential backoff
                    continue
                logger.error(f"Database error after {max_retries} retries while registering instance: {e}", exc_info=True)
                if conn:
                    conn.rollback()
                return False
            except sqlite3.Error as e:
                logger.error(f"Database error while registering instance: {e}", exc_info=True)
                if conn:
                    conn.rollback()
                return False
            except Exception as e:
                logger.error(f"Unexpected error registering instance: {e}", exc_info=True)
                if conn:
                    conn.rollback()
                return False
            finally:
                if conn:
                    conn.close()
        return False

    async def get_all_instances(self) -> List[BotInstance]:
        """Get all registered bot instances

        Returns:
            List of BotInstance objects representing all registered instances
        """
        # Run in a separate thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        instances_data = await loop.run_in_executor(None, self._execute_get_all_instances)

        # Convert raw data to BotInstance objects
        instances = []
        for data in instances_data:
            try:
                import json
                markets = json.loads(data["markets"]) if data["markets"] else None
            except (json.JSONDecodeError, TypeError):
                markets = None

            instances.append(BotInstance(
                composite_id=data["composite_id"],
                instance_id=data["instance_id"],
                strategy_file=data["strategy_file"],
                strategy_name=data["strategy_name"],
                markets=markets,
                description=data["description"],
            ))

        return instances

    def _execute_get_all_instances(self) -> List[Dict[str, Any]]:
        """Execute get all instances query synchronously"""
        conn = None
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                conn = sqlite3.connect(self._db_path, timeout=30.0)
                conn.execute("PRAGMA busy_timeout=5000")
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Get all instances ordered by last seen time (most recent first)
                cursor.execute("""
                    SELECT * FROM instances
                    ORDER BY composite_id DESC
                """)

                rows = [dict(row) for row in cursor.fetchall()]
                logger.debug(f"Retrieved {len(rows)} bot instances from database")
                return rows
            except sqlite3.OperationalError as e:
                # Database is locked, retry after delay
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"Database locked while getting instances, retrying ({retry_count}/{max_retries}): {e}")
                    import time
                    time.sleep(0.5 * retry_count)  # Exponential backoff
                    continue
                logger.error(f"Database error after {max_retries} retries while getting instances: {e}", exc_info=True)
                return []
            except sqlite3.Error as e:
                logger.error(f"Database error while getting instances: {e}", exc_info=True)
                return []
            except Exception as e:
                logger.error(f"Unexpected error getting instances: {e}", exc_info=True)
                return []
            finally:
                if conn:
                    conn.close()
        return []
