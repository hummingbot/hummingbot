from libc.stdint cimport int64_t
from hummingbot.core.clock cimport Clock
from hummingbot.core.model.sql_connection_manager import SQLConnectionManager


cdef class SQLKeepAlive(TimeIterator):
    def __init__(self, sql: SQLConnectionManager, tick_size: int = 60.0):
        super().__init__()
        self._sql = sql
        self._tick_size = tick_size
        self._last_timestamp = 0

    cdef c_start(self, Clock clock, double timestamp):
        TimeIterator.c_start(self, clock, timestamp)
        self._last_timestamp = timestamp

    cdef c_tick(self, double timestamp):
        TimeIterator.c_tick(self, timestamp)

        cdef:
            int64_t last_tick = <int64_t>(self._last_timestamp // self._tick_size)
            int64_t current_tick = <int64_t>(timestamp // self._tick_size)
        self._last_timestamp = timestamp
        if current_tick > last_tick:
            # Call get_shared_session() to ping and reconnect the backing SQL connection if needed.
            self._sql.get_shared_session()
