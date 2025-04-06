import datetime
from abc import ABC, abstractmethod
from http.cookies import SimpleCookie
from typing import List, Optional
from warnings import warn

import grpc
from grpc import ChannelCredentials
from grpc.aio import Call, Metadata


class CookieAssistant(ABC):
    @abstractmethod
    def cookie(self) -> Optional[str]:
        ...

    @abstractmethod
    async def process_response_metadata(self, grpc_call: Call):
        ...

    def metadata(self) -> Metadata:
        cookie = self.cookie()
        metadata = Metadata()
        if cookie is not None and cookie != "":
            metadata.add("cookie", cookie)
        return metadata


class BareMetalLoadBalancedCookieAssistant(CookieAssistant):
    def __init__(self):
        self._cookie: Optional[str] = None

    def cookie(self) -> Optional[str]:
        self._check_cookie_expiration()

        return self._cookie

    async def process_response_metadata(self, grpc_call: Call):
        metadata = await grpc_call.initial_metadata()
        if "set-cookie" in metadata:
            self._cookie = metadata["set-cookie"]

    def _check_cookie_expiration(self):
        if self._is_cookie_expired(cookie_data=self._cookie):
            self._cookie = None

    def _is_cookie_expired(self, cookie_data: str) -> bool:
        # The cookies for these nodes do not expire
        return False


class ExpiringCookieAssistant(CookieAssistant):
    def __init__(self, expiration_time_keys_sequence: List[str], time_format: str):
        self._cookie: Optional[str] = None
        self._expiration_time_keys_sequence = expiration_time_keys_sequence
        self._time_format = time_format

    @classmethod
    def for_kubernetes_public_server(cls):
        return cls(
            expiration_time_keys_sequence=["grpc-cookie", "expires"],
            time_format="%a, %d-%b-%Y %H:%M:%S %Z",
        )

    def cookie(self) -> Optional[str]:
        self._check_cookie_expiration()

        return self._cookie

    async def process_response_metadata(self, grpc_call: Call):
        metadata = await grpc_call.initial_metadata()
        if "set-cookie" in metadata:
            self._cookie = metadata["set-cookie"]

    def _check_cookie_expiration(self):
        if self._is_cookie_expired():
            self._cookie = None

    def _is_cookie_expired(self) -> bool:
        is_expired = False

        if self._cookie is not None:
            cookie = SimpleCookie()
            cookie.load(self._cookie)
            cookie_map = cookie

            for key in self._expiration_time_keys_sequence[:-1]:
                cookie_map = cookie.get(key, {})

            expiration_data: Optional[str] = cookie_map.get(self._expiration_time_keys_sequence[-1], None)
            if expiration_data is not None:
                expiration_time = datetime.datetime.strptime(expiration_data, self._time_format)
                is_expired = datetime.datetime.utcnow() >= expiration_time

        return is_expired


class DisabledCookieAssistant(CookieAssistant):
    def cookie(self) -> Optional[str]:
        return None

    async def process_response_metadata(self, grpc_call: Call):
        pass


class Network:
    def __init__(
        self,
        lcd_endpoint: str,
        tm_websocket_endpoint: str,
        grpc_endpoint: str,
        grpc_exchange_endpoint: str,
        grpc_explorer_endpoint: str,
        chain_stream_endpoint: str,
        chain_id: str,
        fee_denom: str,
        env: str,
        chain_cookie_assistant: CookieAssistant,
        exchange_cookie_assistant: CookieAssistant,
        explorer_cookie_assistant: CookieAssistant,
        official_tokens_list_url: str,
        use_secure_connection: Optional[bool] = None,
        grpc_channel_credentials: Optional[ChannelCredentials] = None,
        grpc_exchange_channel_credentials: Optional[ChannelCredentials] = None,
        grpc_explorer_channel_credentials: Optional[ChannelCredentials] = None,
        chain_stream_channel_credentials: Optional[ChannelCredentials] = None,
    ):
        # the `use_secure_connection` parameter is ignored and will be deprecated soon.
        if use_secure_connection is not None:
            warn(
                "use_secure_connection parameter in Network is no longer used and will be deprecated",
                DeprecationWarning,
                stacklevel=2,
            )

        self.lcd_endpoint = lcd_endpoint
        self.tm_websocket_endpoint = tm_websocket_endpoint
        self.grpc_endpoint = grpc_endpoint
        self.grpc_exchange_endpoint = grpc_exchange_endpoint
        self.grpc_explorer_endpoint = grpc_explorer_endpoint
        self.chain_stream_endpoint = chain_stream_endpoint
        self.chain_id = chain_id
        self.fee_denom = fee_denom
        self.env = env
        self.chain_cookie_assistant = chain_cookie_assistant
        self.exchange_cookie_assistant = exchange_cookie_assistant
        self.explorer_cookie_assistant = explorer_cookie_assistant
        self.official_tokens_list_url = official_tokens_list_url
        self.grpc_channel_credentials = grpc_channel_credentials
        self.grpc_exchange_channel_credentials = grpc_exchange_channel_credentials
        self.grpc_explorer_channel_credentials = grpc_explorer_channel_credentials
        self.chain_stream_channel_credentials = chain_stream_channel_credentials

    @classmethod
    def devnet(cls):
        return cls(
            lcd_endpoint="https://devnet.lcd.injective.dev",
            tm_websocket_endpoint="wss://devnet.tm.injective.dev/websocket",
            grpc_endpoint="devnet.injective.dev:9900",
            grpc_exchange_endpoint="devnet.injective.dev:9910",
            grpc_explorer_endpoint="devnet.injective.dev:9911",
            chain_stream_endpoint="devnet.injective.dev:9999",
            chain_id="injective-777",
            fee_denom="inj",
            env="devnet",
            chain_cookie_assistant=DisabledCookieAssistant(),
            exchange_cookie_assistant=DisabledCookieAssistant(),
            explorer_cookie_assistant=DisabledCookieAssistant(),
            official_tokens_list_url="https://github.com/InjectiveLabs/injective-lists/raw/master/tokens/devnet.json",
        )

    @classmethod
    def testnet(cls, node="lb"):
        nodes = [
            "lb",
            "sentry",
        ]
        if node not in nodes:
            raise ValueError("Must be one of {}".format(nodes))

        grpc_channel_credentials = grpc.ssl_channel_credentials()
        grpc_exchange_channel_credentials = grpc.ssl_channel_credentials()
        grpc_explorer_channel_credentials = grpc.ssl_channel_credentials()
        chain_stream_channel_credentials = grpc.ssl_channel_credentials()

        if node == "lb":
            lcd_endpoint = "https://testnet.sentry.lcd.injective.network:443"
            tm_websocket_endpoint = "wss://testnet.sentry.tm.injective.network:443/websocket"
            grpc_endpoint = "testnet.sentry.chain.grpc.injective.network:443"
            grpc_exchange_endpoint = "testnet.sentry.exchange.grpc.injective.network:443"
            grpc_explorer_endpoint = "testnet.sentry.explorer.grpc.injective.network:443"
            chain_stream_endpoint = "testnet.sentry.chain.stream.injective.network:443"
            chain_cookie_assistant = BareMetalLoadBalancedCookieAssistant()
            exchange_cookie_assistant = BareMetalLoadBalancedCookieAssistant()
            explorer_cookie_assistant = BareMetalLoadBalancedCookieAssistant()
        else:
            lcd_endpoint = "https://testnet.lcd.injective.network:443"
            tm_websocket_endpoint = "wss://testnet.tm.injective.network:443/websocket"
            grpc_endpoint = "testnet.chain.grpc.injective.network:443"
            grpc_exchange_endpoint = "testnet.exchange.grpc.injective.network:443"
            grpc_explorer_endpoint = "testnet.explorer.grpc.injective.network:443"
            chain_stream_endpoint = "testnet.chain.stream.injective.network:443"
            chain_cookie_assistant = DisabledCookieAssistant()
            exchange_cookie_assistant = DisabledCookieAssistant()
            explorer_cookie_assistant = DisabledCookieAssistant()

        return cls(
            lcd_endpoint=lcd_endpoint,
            tm_websocket_endpoint=tm_websocket_endpoint,
            grpc_endpoint=grpc_endpoint,
            grpc_exchange_endpoint=grpc_exchange_endpoint,
            grpc_explorer_endpoint=grpc_explorer_endpoint,
            chain_stream_endpoint=chain_stream_endpoint,
            chain_id="injective-888",
            fee_denom="inj",
            env="testnet",
            chain_cookie_assistant=chain_cookie_assistant,
            exchange_cookie_assistant=exchange_cookie_assistant,
            explorer_cookie_assistant=explorer_cookie_assistant,
            grpc_channel_credentials=grpc_channel_credentials,
            grpc_exchange_channel_credentials=grpc_exchange_channel_credentials,
            grpc_explorer_channel_credentials=grpc_explorer_channel_credentials,
            chain_stream_channel_credentials=chain_stream_channel_credentials,
            official_tokens_list_url="https://github.com/InjectiveLabs/injective-lists/raw/master/tokens/testnet.json",
        )

    @classmethod
    def mainnet(cls, node="lb"):
        nodes = [
            "lb",
        ]
        if node not in nodes:
            raise ValueError("Must be one of {}".format(nodes))

        lcd_endpoint = "https://sentry.lcd.injective.network:443"
        tm_websocket_endpoint = "wss://sentry.tm.injective.network:443/websocket"
        grpc_endpoint = "sentry.chain.grpc.injective.network:443"
        grpc_exchange_endpoint = "sentry.exchange.grpc.injective.network:443"
        grpc_explorer_endpoint = "sentry.explorer.grpc.injective.network:443"
        chain_stream_endpoint = "sentry.chain.stream.injective.network:443"
        chain_cookie_assistant = BareMetalLoadBalancedCookieAssistant()
        exchange_cookie_assistant = BareMetalLoadBalancedCookieAssistant()
        explorer_cookie_assistant = BareMetalLoadBalancedCookieAssistant()
        grpc_channel_credentials = grpc.ssl_channel_credentials()
        grpc_exchange_channel_credentials = grpc.ssl_channel_credentials()
        grpc_explorer_channel_credentials = grpc.ssl_channel_credentials()
        chain_stream_channel_credentials = grpc.ssl_channel_credentials()

        return cls(
            lcd_endpoint=lcd_endpoint,
            tm_websocket_endpoint=tm_websocket_endpoint,
            grpc_endpoint=grpc_endpoint,
            grpc_exchange_endpoint=grpc_exchange_endpoint,
            grpc_explorer_endpoint=grpc_explorer_endpoint,
            chain_stream_endpoint=chain_stream_endpoint,
            chain_id="injective-1",
            fee_denom="inj",
            env="mainnet",
            chain_cookie_assistant=chain_cookie_assistant,
            exchange_cookie_assistant=exchange_cookie_assistant,
            explorer_cookie_assistant=explorer_cookie_assistant,
            grpc_channel_credentials=grpc_channel_credentials,
            grpc_exchange_channel_credentials=grpc_exchange_channel_credentials,
            grpc_explorer_channel_credentials=grpc_explorer_channel_credentials,
            chain_stream_channel_credentials=chain_stream_channel_credentials,
            official_tokens_list_url="https://github.com/InjectiveLabs/injective-lists/raw/master/tokens/mainnet.json",
        )

    @classmethod
    def local(cls):
        return cls(
            lcd_endpoint="http://localhost:10337",
            tm_websocket_endpoint="ws://localhost:26657/websocket",
            grpc_endpoint="localhost:9900",
            grpc_exchange_endpoint="localhost:9910",
            grpc_explorer_endpoint="localhost:9911",
            chain_stream_endpoint="localhost:9999",
            chain_id="injective-1",
            fee_denom="inj",
            env="local",
            chain_cookie_assistant=DisabledCookieAssistant(),
            exchange_cookie_assistant=DisabledCookieAssistant(),
            explorer_cookie_assistant=DisabledCookieAssistant(),
            official_tokens_list_url="https://github.com/InjectiveLabs/injective-lists/raw/master/tokens/mainnet.json",
        )

    @classmethod
    def custom(
        cls,
        lcd_endpoint,
        tm_websocket_endpoint,
        grpc_endpoint,
        grpc_exchange_endpoint,
        grpc_explorer_endpoint,
        chain_stream_endpoint,
        chain_id,
        env,
        official_tokens_list_url: str,
        chain_cookie_assistant: Optional[CookieAssistant] = None,
        exchange_cookie_assistant: Optional[CookieAssistant] = None,
        explorer_cookie_assistant: Optional[CookieAssistant] = None,
        use_secure_connection: Optional[bool] = None,
        grpc_channel_credentials: Optional[ChannelCredentials] = None,
        grpc_exchange_channel_credentials: Optional[ChannelCredentials] = None,
        grpc_explorer_channel_credentials: Optional[ChannelCredentials] = None,
        chain_stream_channel_credentials: Optional[ChannelCredentials] = None,
    ):
        # the `use_secure_connection` parameter is ignored and will be deprecated soon.
        if use_secure_connection is not None:
            warn(
                "use_secure_connection parameter in Network is no longer used and will be deprecated",
                DeprecationWarning,
                stacklevel=2,
            )

        chain_assistant = chain_cookie_assistant or DisabledCookieAssistant()
        exchange_assistant = exchange_cookie_assistant or DisabledCookieAssistant()
        explorer_assistant = explorer_cookie_assistant or DisabledCookieAssistant()
        return cls(
            lcd_endpoint=lcd_endpoint,
            tm_websocket_endpoint=tm_websocket_endpoint,
            grpc_endpoint=grpc_endpoint,
            grpc_exchange_endpoint=grpc_exchange_endpoint,
            grpc_explorer_endpoint=grpc_explorer_endpoint,
            chain_stream_endpoint=chain_stream_endpoint,
            chain_id=chain_id,
            fee_denom="inj",
            env=env,
            chain_cookie_assistant=chain_assistant,
            exchange_cookie_assistant=exchange_assistant,
            explorer_cookie_assistant=explorer_assistant,
            official_tokens_list_url=official_tokens_list_url,
            grpc_channel_credentials=grpc_channel_credentials,
            grpc_exchange_channel_credentials=grpc_exchange_channel_credentials,
            grpc_explorer_channel_credentials=grpc_explorer_channel_credentials,
            chain_stream_channel_credentials=chain_stream_channel_credentials,
        )

    @classmethod
    def custom_chain_and_public_indexer_mainnet(
        cls,
        lcd_endpoint,
        tm_websocket_endpoint,
        grpc_endpoint,
        chain_stream_endpoint,
        chain_cookie_assistant: Optional[CookieAssistant] = None,
    ):
        mainnet_network = cls.mainnet()

        return cls.custom(
            lcd_endpoint=lcd_endpoint,
            tm_websocket_endpoint=tm_websocket_endpoint,
            grpc_endpoint=grpc_endpoint,
            grpc_exchange_endpoint=mainnet_network.grpc_exchange_endpoint,
            grpc_explorer_endpoint=mainnet_network.grpc_explorer_endpoint,
            chain_stream_endpoint=chain_stream_endpoint,
            chain_id="injective-1",
            env="mainnet",
            chain_cookie_assistant=chain_cookie_assistant or DisabledCookieAssistant(),
            exchange_cookie_assistant=mainnet_network.exchange_cookie_assistant,
            explorer_cookie_assistant=mainnet_network.explorer_cookie_assistant,
            official_tokens_list_url=mainnet_network.official_tokens_list_url,
            grpc_channel_credentials=None,
            grpc_exchange_channel_credentials=mainnet_network.grpc_exchange_channel_credentials,
            grpc_explorer_channel_credentials=mainnet_network.grpc_explorer_channel_credentials,
            chain_stream_channel_credentials=None,
        )

    def string(self):
        return self.env

    def create_chain_grpc_channel(self) -> grpc.Channel:
        return self._create_grpc_channel(self.grpc_endpoint, self.grpc_channel_credentials)

    def create_exchange_grpc_channel(self) -> grpc.Channel:
        return self._create_grpc_channel(self.grpc_exchange_endpoint, self.grpc_exchange_channel_credentials)

    def create_explorer_grpc_channel(self) -> grpc.Channel:
        return self._create_grpc_channel(self.grpc_explorer_endpoint, self.grpc_explorer_channel_credentials)

    def create_chain_stream_grpc_channel(self) -> grpc.Channel:
        return self._create_grpc_channel(self.chain_stream_endpoint, self.chain_stream_channel_credentials)

    def _create_grpc_channel(self, endpoint: str, credentials: Optional[ChannelCredentials]) -> grpc.Channel:
        if credentials is None:
            channel = grpc.aio.insecure_channel(endpoint)
        else:
            channel = grpc.aio.secure_channel(endpoint, credentials)
        return channel
