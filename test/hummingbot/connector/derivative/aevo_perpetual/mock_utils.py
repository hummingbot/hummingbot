import sys
from types import ModuleType
from unittest.mock import MagicMock

# Define Mock Classes
class MockAuthBase:
    pass

class MockRESTRequest:
    def __init__(self, method, url, data=None, headers=None):
        self.method = method
        self.url = url
        self.data = data
        self.headers = headers or {}

class MockWSRequest:
    pass

class MockWSResponse:
    pass

class MockRESTResponse:
    pass

class MockRESTMethod:
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"

class MockOrderBookMessageType:
    SNAPSHOT = 1
    TRADE = 2

class MockTaskLog:
    pass

class MockRateLimit:
    def __init__(self, limit_id, limit, time_interval):
        pass

class MockHexBytes:
    pass

mock_hexbytes_module = ModuleType("hexbytes")
mock_hexbytes_module.HexBytes = MockHexBytes

# Create Mock Modules
mock_auth_module = ModuleType("hummingbot.core.web_assistant.auth")
mock_auth_module.AuthBase = MockAuthBase

mock_data_types_module = ModuleType("hummingbot.core.web_assistant.connections.data_types")
mock_data_types_module.RESTRequest = MockRESTRequest
mock_data_types_module.WSRequest = MockWSRequest
mock_data_types_module.WSResponse = MockWSResponse
mock_data_types_module.RESTResponse = MockRESTResponse
mock_data_types_module.RESTMethod = MockRESTMethod

mock_throttler_types_module = ModuleType("hummingbot.core.api_throttler.data_types")
mock_throttler_types_module.TaskLog = MockTaskLog
mock_throttler_types_module.RateLimit = MockRateLimit

# Mock pydantic
mock_pydantic_module = ModuleType("pydantic")
class MockSecretStr:
    def __init__(self, value):
        self._value = value
    def get_secret_value(self):
        return self._value
mock_pydantic_module.SecretStr = MockSecretStr
sys.modules["pydantic"] = mock_pydantic_module

# Mock pydantic_core
moved_pydantic_core_here = True # Just a marker to ensure placement

# Mock pydantic_core
mock_pydantic_core_module = ModuleType("pydantic_core")
class MockCoreSchema:
    class CoreSchema:
        pass
mock_pydantic_core_module.core_schema = MockCoreSchema
sys.modules["pydantic_core"] = mock_pydantic_core_module

# Inject Mocks
sys.modules["hummingbot.core.web_assistant.connections.data_types"] = mock_data_types_module
sys.modules["hummingbot.core.api_throttler.data_types"] = mock_throttler_types_module
sys.modules["hexbytes"] = mock_hexbytes_module

# Mock DerivativeBase
mock_derivative_base_module = ModuleType("hummingbot.connector.derivative.derivative_base")
class MockDerivativeBase:
    def __init__(self, **kwargs):
        pass
    def start(self): pass
    def stop(self): pass
    
mock_derivative_base_module.DerivativeBase = MockDerivativeBase
sys.modules["hummingbot.connector.derivative.derivative_base"] = mock_derivative_base_module

# Mock OrderBook modules
mock_ob_module = ModuleType("hummingbot.core.data_type.order_book")
class MockOrderBook:
    pass
mock_ob_module.OrderBook = MockOrderBook
sys.modules["hummingbot.core.data_type.order_book"] = mock_ob_module

mock_ob_message_module = ModuleType("hummingbot.core.data_type.order_book_message")
class MockOrderBookMessage:
    def __init__(self, *args, **kwargs): pass
class MockOrderBookMessageType:
    SNAPSHOT = 1
    TRADE = 2
mock_ob_message_module.OrderBookMessage = MockOrderBookMessage
mock_ob_message_module.OrderBookMessageType = MockOrderBookMessageType
sys.modules["hummingbot.core.data_type.order_book_message"] = mock_ob_message_module

mock_ob_ds_module = ModuleType("hummingbot.core.data_type.order_book_tracker_data_source")
class MockOrderBookTrackerDataSource:
    def __init__(self, trading_pairs): self._trading_pairs = trading_pairs
mock_ob_ds_module.OrderBookTrackerDataSource = MockOrderBookTrackerDataSource
sys.modules["hummingbot.core.data_type.order_book_tracker_data_source"] = mock_ob_ds_module

# Mock Throttler
mock_throttler_module = ModuleType("hummingbot.core.api_throttler.async_throttler")
class MockAsyncThrottler:
    pass
mock_throttler_module.AsyncThrottler = MockAsyncThrottler
sys.modules["hummingbot.core.api_throttler.async_throttler"] = mock_throttler_module
