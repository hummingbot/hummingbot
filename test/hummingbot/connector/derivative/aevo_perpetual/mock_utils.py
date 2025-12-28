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
sys.modules["hummingbot.core.web_assistant.auth"] = mock_auth_module
sys.modules["hummingbot.core.web_assistant.connections.data_types"] = mock_data_types_module
sys.modules["hummingbot.core.api_throttler.data_types"] = mock_throttler_types_module
sys.modules["hexbytes"] = mock_hexbytes_module
