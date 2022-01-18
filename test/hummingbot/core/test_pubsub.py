import unittest
import gc
import weakref

from hummingbot.core.pubsub import PubSub
from hummingbot.core.event.event_logger import EventLogger

from test.mock.mock_events import MockEventType, MockEvent


class PubSubTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pubsub = PubSub()
        self.listener_zero = EventLogger()
        self.listener_one = EventLogger()
        self.event_tag_zero = MockEventType.EVENT_ZERO
        self.event_tag_one = MockEventType.EVENT_ONE
        self.event = MockEvent(payload=1)

    def test_get_listeners_no_listeners(self):
        listeners_count = len(self.pubsub.get_listeners(self.event_tag_zero))
        self.assertEqual(0, listeners_count)

    def test_add_listeners(self):
        self.pubsub.add_listener(self.event_tag_zero, self.listener_zero)
        listeners = self.pubsub.get_listeners(self.event_tag_zero)
        self.assertEqual(1, len(listeners))
        self.assertIn(self.listener_zero, listeners)

        self.pubsub.add_listener(self.event_tag_zero, self.listener_one)
        listeners = self.pubsub.get_listeners(self.event_tag_zero)
        self.assertEqual(2, len(listeners))
        self.assertIn(self.listener_zero, listeners)
        self.assertIn(self.listener_one, listeners)

    def test_add_listener_twice(self):
        self.pubsub.add_listener(self.event_tag_zero, self.listener_zero)
        listeners_count = len(self.pubsub.get_listeners(self.event_tag_zero))
        self.assertEqual(1, listeners_count)

        self.pubsub.add_listener(self.event_tag_zero, self.listener_zero)
        listeners_count = len(self.pubsub.get_listeners(self.event_tag_zero))
        self.assertEqual(1, listeners_count)

    def test_remove_listener(self):
        self.pubsub.add_listener(self.event_tag_zero, self.listener_zero)
        self.pubsub.add_listener(self.event_tag_zero, self.listener_one)

        self.pubsub.remove_listener(self.event_tag_zero, self.listener_zero)
        listeners = self.pubsub.get_listeners(self.event_tag_zero)
        self.assertNotIn(self.listener_zero, listeners)
        self.assertIn(self.listener_one, listeners)

    def test_add_listeners_to_separate_events(self):
        self.pubsub.add_listener(self.event_tag_zero, self.listener_zero)
        self.pubsub.add_listener(self.event_tag_one, self.listener_one)

        listeners_zero = self.pubsub.get_listeners(self.event_tag_zero)
        listeners_one = self.pubsub.get_listeners(self.event_tag_one)
        self.assertEqual(1, len(listeners_zero))
        self.assertEqual(1, len(listeners_one))

    def test_trigger_event(self):
        self.pubsub.add_listener(self.event_tag_zero, self.listener_zero)
        self.pubsub.add_listener(self.event_tag_one, self.listener_one)
        self.pubsub.trigger_event(self.event_tag_zero, self.event)
        self.assertEqual(1, len(self.listener_zero.event_log))
        self.assertEqual(self.event, self.listener_zero.event_log[0])
        self.assertEqual(0, len(self.listener_one.event_log))

    def test_lapsed_listener_remove_on_get_listeners(self):
        self.pubsub.add_listener(self.event_tag_zero, self.listener_zero)
        self.listener_zero = None  # remove strong reference
        gc.collect()
        listeners = self.pubsub.get_listeners(self.event_tag_zero)
        self.assertEqual(0, len(listeners))

    def test_lapsed_listener_remove_on_remove_listener(self):
        self.pubsub.add_listener(self.event_tag_zero, self.listener_zero)
        self.pubsub.add_listener(self.event_tag_zero, self.listener_one)
        listener_zero_weakref = weakref.ref(self.listener_zero)
        listener_one_weakref = weakref.ref(self.listener_one)
        listeners = None
        self.listener_zero = None  # remove strong reference
        gc.collect()
        self.pubsub.remove_listener(self.event_tag_zero, self.listener_one)
        self.assertEqual(None, listener_zero_weakref())
        self.assertNotEqual(None, listener_one_weakref())
        listeners = self.pubsub.get_listeners(self.event_tag_zero)
        self.assertEqual(0, len(listeners))


if __name__ == "__main__":
    unittest.main()
