import asyncio
import logging
from typing import Any, Optional

import aiomqtt
import ujson

# Sentinels pushed onto the incoming queue to drive the fake message iterator.
_DISCONNECT = object()


class FakeMQTTMessage:
    """Mimics an ``aiomqtt.Message`` (``.topic`` str-able, ``.payload`` bytes).

    ``envelope=True`` wraps the payload in the commlib RPC ``{header, data}``
    envelope (for command/RPC requests); ``envelope=False`` sends the payload
    verbatim (for plain pub/sub messages such as external events).
    """

    def __init__(self, topic: str, payload: Any, envelope: bool = True):
        self.topic = topic
        if envelope:
            payload = {
                'header': {
                    'reply_to': f"test_reply/{topic}"
                },
                'data': payload
            }
        self.payload = ujson.dumps(payload).encode('utf-8')


class FakeMQTTClient:
    """Minimal stand-in for ``aiomqtt.Client`` used as the gateway transport.

    All connection state is delegated to the shared ``FakeMQTTBroker`` so it
    survives across reconnects (a fresh client is created per ``_run`` cycle).
    """

    def __init__(self, broker: "FakeMQTTBroker"):
        self._broker = broker

    async def __aenter__(self) -> "FakeMQTTClient":
        self._broker._connected = True
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self._broker._connected = False
        return False

    async def subscribe(self, topic: str, qos: int = 0, **kwargs):
        self._broker._subscriptions[topic] = qos

    async def unsubscribe(self, topic: str, **kwargs):
        self._broker._subscriptions.pop(topic, None)

    async def publish(self, topic: str, payload: Any = None, qos: int = 0, **kwargs):
        self._broker._record(topic, payload)

    @property
    def messages(self):
        return self._message_iterator()

    async def _message_iterator(self):
        while True:
            item = await self._broker.incoming.get()
            if item is _DISCONNECT:
                raise aiomqtt.MqttError("Simulated broker disconnect")
            yield item


class FakeMQTTBroker:
    def __init__(self):
        self._connected = False
        self._subscriptions = {}
        self._received_msgs = {}
        self._incoming: Optional[asyncio.Queue] = None

    @property
    def incoming(self) -> asyncio.Queue:
        # Created lazily so it binds to the test's current event loop.
        if self._incoming is None:
            self._incoming = asyncio.Queue()
        return self._incoming

    def create_client(self, *args, **kwargs) -> FakeMQTTClient:
        return FakeMQTTClient(self)

    def _record(self, topic: str, payload: Any):
        if isinstance(payload, (bytes, bytearray)):
            payload = payload.decode('utf-8')
        if isinstance(payload, str):
            payload = ujson.loads(payload)
        logging.info(f"\nFakeMQTT publish on\n> {topic}\n     {payload}\n")
        if not self._received_msgs.get(topic):
            self._received_msgs[topic] = []
        self._received_msgs[topic].append(payload)

    def publish_to_subscription(self, topic: str, payload: Any):
        """Inject an inbound RPC request (wrapped in the commlib envelope)."""
        self.incoming.put_nowait(FakeMQTTMessage(topic=topic, payload=payload))

    def publish_event(self, topic: str, payload: Any):
        """Inject a plain inbound pub/sub message (e.g. an external event)."""
        self.incoming.put_nowait(FakeMQTTMessage(topic=topic, payload=payload, envelope=False))

    def inject_disconnect(self):
        """Force the in-flight message iterator to raise ``MqttError``."""
        self.incoming.put_nowait(_DISCONNECT)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def subscriptions(self):
        return self._subscriptions

    @property
    def received_msgs(self):
        return self._received_msgs

    def is_msg_received(self, topic, content=None, msg_key='msg'):
        msg_found = False
        if topic in self.received_msgs:
            if not content:
                msg_found = True
            else:
                for msg in self.received_msgs[topic]:
                    if str(content) == str(msg[msg_key]):
                        msg_found = True
                        break
        return msg_found

    def clear(self):
        self._received_msgs = {}
        self._subscriptions = {}
        self._connected = False
        self._incoming = None
