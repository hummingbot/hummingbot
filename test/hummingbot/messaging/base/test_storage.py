import asyncio
import os
import sqlite3
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from hummingbot import data_path
from hummingbot.messaging.base.models import BotInstance, BrokerMessage, MessageStatus
from hummingbot.messaging.base.storage import MessageStorage


class MessageStorageTest(unittest.TestCase):
    TEST_DB_NAME = "test_hummingbot_messages.sqlite"

    def setUp(self):
        """Set up the test environment before each test"""
        self.test_db_path = os.path.join(data_path(), self.TEST_DB_NAME)

        # Patch the DB_NAME to use a test database instead
        self.db_name_patcher = patch.object(MessageStorage, 'DB_NAME', self.TEST_DB_NAME)
        self.db_name_patcher.start()

        # Create the storage instance
        self.storage = MessageStorage()

        # Clear the test database before each test
        self._clear_test_db()

    def tearDown(self):
        """Clean up after each test"""
        self.db_name_patcher.stop()

        # Remove the test database
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except PermissionError:
                pass  # On Windows, sometimes the file is locked

    def _clear_test_db(self):
        """Clear the test database tables"""
        try:
            conn = sqlite3.connect(self.test_db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages")
            cursor.execute("DELETE FROM instances")
            conn.commit()
            conn.close()
        except sqlite3.Error:
            # Table might not exist yet
            pass

    def test_initialization(self):
        """Test that the database is initialized correctly"""
        # Verify that the database file exists
        self.assertTrue(os.path.exists(self.test_db_path))

        # Verify that the tables were created
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()

        # Check messages table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        self.assertIsNotNone(cursor.fetchone())

        # Check instances table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='instances'")
        self.assertIsNotNone(cursor.fetchone())

        # Check index
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_instance_status'")
        self.assertIsNotNone(cursor.fetchone())

        conn.close()

    def test_save_message(self):
        """Test saving a message to the database"""
        # Create a test message
        now = datetime.utcnow()
        message = BrokerMessage(
            id=None,
            instance_id="test_instance|default",
            strategy_name="test_strategy",
            command="status",
            source="telegram",
            chat_id="12345",
            status=MessageStatus.NEW,
            created_at=now,
            updated_at=now,
            response=None,
            error=None
        )

        # Save the message
        message_id = asyncio.get_event_loop().run_until_complete(
            self.storage.save_message(message)
        )

        # Verify the message was saved with an ID
        self.assertIsNotNone(message_id)
        self.assertGreater(message_id, 0)

        # Verify we can retrieve the message directly from the database
        conn = sqlite3.connect(self.test_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
        row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row['instance_id'], "test_instance|default")
        self.assertEqual(row['command'], "status")
        self.assertEqual(row['status'], MessageStatus.NEW.value)

    def test_get_pending_messages(self):
        """Test retrieving pending messages"""
        # Add two test messages
        now = datetime.utcnow()

        message1 = BrokerMessage(
            id=None,
            instance_id="instance1|default",
            strategy_name="strategy1",
            command="status",
            source="telegram",
            chat_id="12345",
            status=MessageStatus.NEW,
            created_at=now,
            updated_at=now,
            response=None,
            error=None
        )

        message2 = BrokerMessage(
            id=None,
            instance_id="instance2|default",
            strategy_name="strategy2",
            command="balance",
            source="telegram",
            chat_id="12345",
            status=MessageStatus.NEW,
            created_at=now,
            updated_at=now,
            response=None,
            error=None
        )

        # Save the messages
        msg_id1 = asyncio.get_event_loop().run_until_complete(self.storage.save_message(message1))
        msg_id2 = asyncio.get_event_loop().run_until_complete(self.storage.save_message(message2))

        # Test retrieval of all pending messages
        pending_messages = asyncio.get_event_loop().run_until_complete(
            self.storage.get_pending_messages()
        )

        self.assertEqual(len(pending_messages), 2)
        self.assertEqual(pending_messages[0].id, msg_id1)
        self.assertEqual(pending_messages[1].id, msg_id2)

        # Test retrieval by instance ID
        instance_messages = asyncio.get_event_loop().run_until_complete(
            self.storage.get_pending_messages(instance_id="instance1|default")
        )

        self.assertEqual(len(instance_messages), 1)
        self.assertEqual(instance_messages[0].id, msg_id1)
        self.assertEqual(instance_messages[0].command, "status")

    def test_update_message_status(self):
        """Test updating the status of a message"""
        # Create and save a test message
        now = datetime.utcnow()
        message = BrokerMessage(
            id=None,
            instance_id="test_instance|default",
            strategy_name="test_strategy",
            command="status",
            source="telegram",
            chat_id="12345",
            status=MessageStatus.NEW,
            created_at=now,
            updated_at=now,
            response=None,
            error=None
        )

        msg_id = asyncio.get_event_loop().run_until_complete(self.storage.save_message(message))

        # Update the message status
        asyncio.get_event_loop().run_until_complete(
            self.storage.update_message_status(
                msg_id,
                MessageStatus.COMPLETED,
                response="Command executed successfully",
                error=None
            )
        )

        # Verify the message was updated
        conn = sqlite3.connect(self.test_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM messages WHERE id = ?", (msg_id,))
        row = cursor.fetchone()
        conn.close()

        self.assertEqual(row['status'], MessageStatus.COMPLETED.value)
        self.assertEqual(row['response'], "Command executed successfully")
        self.assertIsNone(row['error'])

    def test_get_completed_messages(self):
        """Test retrieving completed messages"""
        # Add completed and failed messages
        now = datetime.utcnow()

        # Completed message
        completed_message = BrokerMessage(
            id=None,
            instance_id="instance1|default",
            strategy_name="strategy1",
            command="status",
            source="telegram",
            chat_id="12345",
            status=MessageStatus.COMPLETED,
            created_at=now,
            updated_at=now,
            response="Command executed successfully",
            error=None
        )

        # Failed message
        failed_message = BrokerMessage(
            id=None,
            instance_id="instance2|default",
            strategy_name="strategy2",
            command="invalid",
            source="telegram",
            chat_id="12345",
            status=MessageStatus.FAILED,
            created_at=now,
            updated_at=now,
            response=None,
            error="Invalid command"
        )

        # Processing message (should not be retrieved)
        processing_message = BrokerMessage(
            id=None,
            instance_id="instance3|default",
            strategy_name="strategy3",
            command="balance",
            source="telegram",
            chat_id="12345",
            status=MessageStatus.PROCESSING,
            created_at=now,
            updated_at=now,
            response=None,
            error=None
        )

        # Save the messages
        completed_id = asyncio.get_event_loop().run_until_complete(self.storage.save_message(completed_message))
        failed_id = asyncio.get_event_loop().run_until_complete(self.storage.save_message(failed_message))
        asyncio.get_event_loop().run_until_complete(self.storage.save_message(processing_message))

        # Get completed/failed messages
        completed_messages = asyncio.get_event_loop().run_until_complete(
            self.storage.get_completed_messages()
        )

        message_ids = [msg.id for msg in completed_messages]
        self.assertEqual(len(completed_messages), 2)
        self.assertIn(completed_id, message_ids)
        self.assertIn(failed_id, message_ids)

    def test_purge_old_messages(self):
        """Test purging old messages"""
        # Create messages with different dates
        now = datetime.utcnow()
        old_date = (now - timedelta(days=10)).isoformat()
        recent_date = now.isoformat()

        # Add an old message directly to the database
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (instance_id, strategy_name, command, source, chat_id, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("old_instance|default", "old_strategy", "status", "telegram", "12345", "completed", old_date, old_date)
        )
        old_id = cursor.lastrowid

        # Add a recent message
        cursor.execute(
            "INSERT INTO messages (instance_id, strategy_name, command, source, chat_id, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("recent_instance|default", "recent_strategy", "status", "telegram", "12345", "completed", recent_date, recent_date)
        )
        recent_id = cursor.lastrowid

        conn.commit()
        conn.close()

        # Purge messages older than 7 days
        deleted_count = asyncio.get_event_loop().run_until_complete(
            self.storage.purge_old_messages(7)
        )

        # Verify only the old message was deleted
        self.assertEqual(deleted_count, 1)

        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()

        # Check old message is gone
        cursor.execute("SELECT id FROM messages WHERE id = ?", (old_id,))
        self.assertIsNone(cursor.fetchone())

        # Check recent message still exists
        cursor.execute("SELECT id FROM messages WHERE id = ?", (recent_id,))
        self.assertIsNotNone(cursor.fetchone())

        conn.close()

    def test_register_instance(self):
        """Test registering a bot instance"""
        instance = BotInstance(
            composite_id="test_instance|test_strategy",
            instance_id="test_instance",
            strategy_file="test_strategy",
            strategy_name="Test Strategy",
            markets=["binance", "kucoin"],
            description="Test bot instance"
        )

        # Register the instance
        result = asyncio.get_event_loop().run_until_complete(
            self.storage.register_instance(instance)
        )

        self.assertTrue(result)

        # Verify the instance was registered
        conn = sqlite3.connect(self.test_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM instances WHERE composite_id = ?", ("test_instance|test_strategy",))
        row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row['instance_id'], "test_instance")
        self.assertEqual(row['strategy_file'], "test_strategy")
        self.assertEqual(row['strategy_name'], "Test Strategy")
        self.assertIn("binance", row['markets'])
        self.assertIn("kucoin", row['markets'])
        self.assertEqual(row['description'], "Test bot instance")

    def test_get_all_instances(self):
        """Test retrieving all registered instances"""
        # Register two test instances
        instance1 = BotInstance(
            composite_id="instance1|strategy1",
            instance_id="instance1",
            strategy_file="strategy1",
            strategy_name="Strategy One",
            markets=["binance"],
            description="Test instance one"
        )

        instance2 = BotInstance(
            composite_id="instance2|strategy2",
            instance_id="instance2",
            strategy_file="strategy2",
            strategy_name="Strategy Two",
            markets=["kucoin"],
            description="Test instance two"
        )

        asyncio.get_event_loop().run_until_complete(self.storage.register_instance(instance1))
        asyncio.get_event_loop().run_until_complete(self.storage.register_instance(instance2))

        # Retrieve all instances
        instances = asyncio.get_event_loop().run_until_complete(
            self.storage.get_all_instances()
        )

        self.assertEqual(len(instances), 2)

        # Check that we got the correct instances (order may vary)
        instance_ids = [instance.instance_id for instance in instances]
        self.assertIn("instance1", instance_ids)
        self.assertIn("instance2", instance_ids)

    def test_delete_message(self):
        """Test deleting a message"""
        # Create a test message
        now = datetime.utcnow()
        message = BrokerMessage(
            id=None,
            instance_id="test_instance|default",
            strategy_name="test_strategy",
            command="status",
            source="telegram",
            chat_id="12345",
            status=MessageStatus.COMPLETED,
            created_at=now,
            updated_at=now,
            response="Test response",
            error=None
        )

        # Save the message
        msg_id = asyncio.get_event_loop().run_until_complete(self.storage.save_message(message))

        # Delete the message
        result = asyncio.get_event_loop().run_until_complete(
            self.storage.delete_message(msg_id)
        )

        self.assertTrue(result)

        # Verify the message was deleted
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM messages WHERE id = ?", (msg_id,))
        self.assertIsNone(cursor.fetchone())
        conn.close()


if __name__ == "__main__":
    unittest.main()
