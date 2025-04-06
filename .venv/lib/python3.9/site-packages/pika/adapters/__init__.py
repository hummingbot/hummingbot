"""
Connection Adapters
===================

Pika provides multiple adapters to connect to RabbitMQ:

- adapters.asyncio_connection.AsyncioConnection: Native Python3 AsyncIO use
- adapters.blocking_connection.BlockingConnection: Enables blocking,
  synchronous operation on top of library for simple uses.
- adapters.gevent_connection.GeventConnection: Connection adapter for use with
  Gevent.
- adapters.select_connection.SelectConnection: A native event based connection
  adapter that implements select, kqueue, poll and epoll.
- adapters.tornado_connection.TornadoConnection: Connection adapter for use
  with the Tornado web framework.
- adapters.twisted_connection.TwistedProtocolConnection: Connection adapter for
  use with the Twisted framework

"""
from pika.adapters.base_connection import BaseConnection
from pika.adapters.blocking_connection import BlockingConnection
from pika.adapters.select_connection import SelectConnection
from pika.adapters.select_connection import IOLoop
