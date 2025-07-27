import re
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Union

from pydantic import ConfigDict, Field, SecretStr, field_validator
from pyinjective.async_client_v2 import AsyncClient
from pyinjective.composer_v2 import Composer
from pyinjective.core.broadcaster import (
    MessageBasedTransactionFeeCalculator,
    SimulatedTransactionFeeCalculator,
    TransactionFeeCalculator,
)
from pyinjective.core.network import Network
from pyinjective.wallet import PrivateKey

from hummingbot.client.config.config_data_types import BaseClientModel, BaseConnectorConfigMap
from hummingbot.connector.exchange.injective_v2 import injective_constants as CONSTANTS
from hummingbot.connector.exchange.injective_v2.data_sources.injective_grantee_data_source import (
    InjectiveGranteeDataSource,
)
from hummingbot.connector.exchange.injective_v2.data_sources.injective_read_only_data_source import (
    InjectiveReadOnlyDataSource,
)
from hummingbot.connector.exchange.injective_v2.data_sources.injective_vaults_data_source import (
    InjectiveVaultsDataSource,
)
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

if TYPE_CHECKING:
    from hummingbot.connector.exchange.injective_v2.data_sources.injective_data_source import InjectiveDataSource

CENTRALIZED = False
EXAMPLE_PAIR = "INJ-USDT"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
)

TESTNET_NODES = ["lb", "sentry"]


class InjectiveFeeCalculatorMode(BaseClientModel, ABC):
    @abstractmethod
    def create_calculator(
        self,
        client: AsyncClient,
        composer: Composer,
        gas_price: Optional[int] = None,
        gas_limit_adjustment_multiplier: Optional[Decimal] = None,
    ) -> Network:
        pass


class InjectiveSimulatedTransactionFeeCalculatorMode(InjectiveFeeCalculatorMode):
    name: Literal["simulated_transaction_fee_calculator"] = "simulated_transaction_fee_calculator"
    model_config = ConfigDict(title="simulated_transaction_fee_calculator")

    def create_calculator(
            self,
            client: AsyncClient,
            composer: Composer,
            gas_price: Optional[int] = None,
            gas_limit_adjustment_multiplier: Optional[Decimal] = None,
    ) -> TransactionFeeCalculator:
        return SimulatedTransactionFeeCalculator(
            client=client,
            composer=composer,
            gas_price=gas_price,
            gas_limit_adjustment_multiplier=gas_limit_adjustment_multiplier,
        )


class InjectiveMessageBasedTransactionFeeCalculatorMode(InjectiveFeeCalculatorMode):
    name: Literal["message_based_transaction_fee_calculator"] = "message_based_transaction_fee_calculator"
    model_config = ConfigDict(title="message_based_transaction_fee_calculator")

    def create_calculator(
            self,
            client: AsyncClient,
            composer: Composer,
            gas_price: Optional[int] = None,
            gas_limit_adjustment_multiplier: Optional[Decimal] = None,
    ) -> TransactionFeeCalculator:
        return MessageBasedTransactionFeeCalculator.new_using_gas_heuristics(
            client=client,
            composer=composer,
            gas_price=gas_price,
        )


FEE_CALCULATOR_MODES = {
    InjectiveSimulatedTransactionFeeCalculatorMode.model_config["title"]: InjectiveSimulatedTransactionFeeCalculatorMode,
    InjectiveMessageBasedTransactionFeeCalculatorMode.model_config["title"]: InjectiveMessageBasedTransactionFeeCalculatorMode,
}


class InjectiveNetworkMode(BaseClientModel, ABC):
    @abstractmethod
    def network(self) -> Network:
        pass


class InjectiveMainnetNetworkMode(InjectiveNetworkMode):
    model_config = ConfigDict(title="mainnet_network")

    def network(self) -> Network:
        return Network.mainnet()

    def rate_limits(self) -> List[RateLimit]:
        return CONSTANTS.PUBLIC_NODE_RATE_LIMITS


class InjectiveTestnetNetworkMode(InjectiveNetworkMode):
    testnet_node: str = Field(
        default="lb",
        json_schema_extra={
            "prompt": f"Enter the testnet node you want to connect to ({'/'.join(TESTNET_NODES)})",
            "prompt_on_new": True}
    )
    model_config = ConfigDict(title="testnet_network")

    @field_validator("testnet_node", mode="before")
    @classmethod
    def validate_node(cls, v: str):
        if v not in TESTNET_NODES:
            raise ValueError(f"{v} is not a valid node ({TESTNET_NODES})")
        return v

    def network(self) -> Network:
        return Network.testnet(node=self.testnet_node)

    def rate_limits(self) -> List[RateLimit]:
        return CONSTANTS.PUBLIC_NODE_RATE_LIMITS


class InjectiveCustomNetworkMode(InjectiveNetworkMode):
    lcd_endpoint: str = Field(
        default=...,
        json_schema_extra={"prompt": "Enter the network lcd_endpoint", "prompt_on_new": True},
    )
    tm_websocket_endpoint: str = Field(
        default=...,
        json_schema_extra={"prompt": "Enter the network tm_websocket_endpoint", "prompt_on_new": True},
    )
    grpc_endpoint: str = Field(
        default=...,
        json_schema_extra={"prompt": "Enter the network grpc_endpoint", "prompt_on_new": True},
    )
    grpc_exchange_endpoint: str = Field(
        default=...,
        json_schema_extra={"prompt": "Enter the network grpc_exchange_endpoint", "prompt_on_new": True},
    )
    grpc_explorer_endpoint: str = Field(
        default=...,
        json_schema_extra={"prompt": "Enter the network grpc_explorer_endpoint", "prompt_on_new": True},
    )
    chain_stream_endpoint: str = Field(
        default=...,
        json_schema_extra={"prompt": "Enter the network chain_stream_endpoint", "prompt_on_new": True},
    )
    chain_id: str = Field(
        default=...,
        json_schema_extra={"prompt": "Enter the network chain_id", "prompt_on_new": True},
    )
    env: str = Field(
        default=...,
        json_schema_extra={"prompt": "Enter the network environment name", "prompt_on_new": True},
    )
    model_config = ConfigDict(title="custom_network")

    def network(self) -> Network:
        return Network.custom(
            lcd_endpoint=self.lcd_endpoint,
            tm_websocket_endpoint=self.tm_websocket_endpoint,
            grpc_endpoint=self.grpc_endpoint,
            grpc_exchange_endpoint=self.grpc_exchange_endpoint,
            grpc_explorer_endpoint=self.grpc_explorer_endpoint,
            chain_stream_endpoint=self.chain_stream_endpoint,
            chain_id=self.chain_id,
            env=self.env,
            official_tokens_list_url=Network.mainnet().official_tokens_list_url,
        )

    def rate_limits(self) -> List[RateLimit]:
        return CONSTANTS.CUSTOM_NODE_RATE_LIMITS


NETWORK_MODES = {
    InjectiveMainnetNetworkMode.model_config["title"]: InjectiveMainnetNetworkMode,
    InjectiveTestnetNetworkMode.model_config["title"]: InjectiveTestnetNetworkMode,
    InjectiveCustomNetworkMode.model_config["title"]: InjectiveCustomNetworkMode,
}

# Captures a 12 or 24-word BIP39 seed phrase
RE_SEED_PHRASE = re.compile(r"^(?:[a-z]+(?: [a-z]+){11}|[a-z]+(?: [a-z]+){23})$")


class InjectiveAccountMode(BaseClientModel, ABC):

    @abstractmethod
    def create_data_source(
            self,
            network: Network,
            rate_limits: List[RateLimit],
            fee_calculator_mode: InjectiveFeeCalculatorMode,
    ) -> "InjectiveDataSource":
        pass


class InjectiveDelegatedAccountMode(InjectiveAccountMode):
    private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Injective trading account private key or seed phrase",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    subaccount_index: int = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Injective trading account subaccount index",
            "prompt_on_new": True,
        }
    )
    granter_address: str = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter the Injective address of the granter account (portfolio account)",
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    granter_subaccount_index: int = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter the Injective granter subaccount index (portfolio subaccount index)",
            "prompt_on_new": True,
        }
    )

    @field_validator("private_key", mode="before")
    @classmethod
    def validate_network(cls, v: str):
        # Both seed phrase and hex private keys supported
        if isinstance(v, str):
            v = v.strip()
            if RE_SEED_PHRASE.match(v):
                private_key = PrivateKey.from_mnemonic(v)
                return private_key.to_hex()
        return v
    model_config = ConfigDict(title="delegate_account")

    def create_data_source(
            self,
            network: Network,
            rate_limits: List[RateLimit],
            fee_calculator_mode: InjectiveFeeCalculatorMode,
    ) -> "InjectiveDataSource":
        return InjectiveGranteeDataSource(
            private_key=self.private_key.get_secret_value(),
            subaccount_index=self.subaccount_index,
            granter_address=self.granter_address,
            granter_subaccount_index=self.granter_subaccount_index,
            network=network,
            rate_limits=rate_limits,
            fee_calculator_mode=fee_calculator_mode,
        )


class InjectiveVaultAccountMode(InjectiveAccountMode):
    private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter the vault admin private key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    subaccount_index: int = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter the vault admin subaccount index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    vault_contract_address: str = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter the vault contract address",
            "prompt_on_new": True,
        }
    )
    vault_subaccount_index: int = Field(default=1)
    model_config = ConfigDict(title="vault_account")

    def create_data_source(
            self,
            network: Network,
            rate_limits: List[RateLimit],
            fee_calculator_mode: InjectiveFeeCalculatorMode,
    ) -> "InjectiveDataSource":
        return InjectiveVaultsDataSource(
            private_key=self.private_key.get_secret_value(),
            subaccount_index=self.subaccount_index,
            vault_contract_address=self.vault_contract_address,
            vault_subaccount_index=self.vault_subaccount_index,
            network=network,
            rate_limits=rate_limits,
            fee_calculator_mode=fee_calculator_mode,
        )


class InjectiveReadOnlyAccountMode(InjectiveAccountMode):
    model_config = ConfigDict(title="read_only_account")

    def create_data_source(
            self,
            network: Network,
            rate_limits: List[RateLimit],
            fee_calculator_mode: InjectiveFeeCalculatorMode,
    ) -> "InjectiveDataSource":
        return InjectiveReadOnlyDataSource(
            network=network,
            rate_limits=rate_limits,
        )


ACCOUNT_MODES = {
    InjectiveDelegatedAccountMode.model_config["title"]: InjectiveDelegatedAccountMode,
    InjectiveVaultAccountMode.model_config["title"]: InjectiveVaultAccountMode,
    InjectiveReadOnlyAccountMode.model_config["title"]: InjectiveReadOnlyAccountMode,
}


class InjectiveConfigMap(BaseConnectorConfigMap):
    # Setting a default dummy configuration to allow the bot to create a dummy instance to fetch all trading pairs
    connector: str = "injective_v2"
    receive_connector_configuration: bool = Field(default=True)
    network: Union[tuple(NETWORK_MODES.values())] = Field(
        default=InjectiveMainnetNetworkMode(),
        json_schema_extra={
            "prompt": f"Select the network ({'/'.join(list(NETWORK_MODES.keys()))})",
            "prompt_on_new": True},
    )
    account_type: Union[tuple(ACCOUNT_MODES.values())] = Field(
        default=InjectiveReadOnlyAccountMode(),
        json_schema_extra={
            "prompt": f"Select the account type ({'/'.join(list(ACCOUNT_MODES.keys()))})",
            "prompt_on_new": True},
    )
    fee_calculator: Union[tuple(FEE_CALCULATOR_MODES.values())] = Field(
        default=InjectiveMessageBasedTransactionFeeCalculatorMode(),
        discriminator="name",
        json_schema_extra={
            "prompt": f"Select the fee calculator ({'/'.join(list(FEE_CALCULATOR_MODES.keys()))})",
            "prompt_on_new": True},
    )
    model_config = ConfigDict(title="injective_v2")

    @field_validator("network", mode="before")
    @classmethod
    def validate_network(cls, v: Union[(str, Dict) + tuple(NETWORK_MODES.values())]):
        if isinstance(v, tuple(NETWORK_MODES.values()) + (Dict,)):
            sub_model = v
        elif v not in NETWORK_MODES:
            raise ValueError(
                f"Invalid network, please choose a value from {list(NETWORK_MODES.keys())}."
            )
        else:
            sub_model = NETWORK_MODES[v].model_construct()
        return sub_model

    @field_validator("account_type", mode="before")
    @classmethod
    def validate_account_type(cls, v: Union[(str, Dict) + tuple(ACCOUNT_MODES.values())]):
        if isinstance(v, tuple(ACCOUNT_MODES.values()) + (Dict,)):
            sub_model = v
        elif v not in ACCOUNT_MODES:
            raise ValueError(
                f"Invalid account type, please choose a value from {list(ACCOUNT_MODES.keys())}."
            )
        else:
            sub_model = ACCOUNT_MODES[v].model_construct()
        return sub_model

    @field_validator("fee_calculator", mode="before")
    @classmethod
    def validate_fee_calculator(cls, v: Union[(str, Dict) + tuple(FEE_CALCULATOR_MODES.values())]):
        if isinstance(v, tuple(FEE_CALCULATOR_MODES.values()) + (Dict,)):
            sub_model = v
        elif v not in FEE_CALCULATOR_MODES:
            raise ValueError(
                f"Invalid fee calculator, please choose a value from {list(FEE_CALCULATOR_MODES.keys())}."
            )
        else:
            sub_model = FEE_CALCULATOR_MODES[v].model_construct()
        return sub_model

    def create_data_source(self):
        return self.account_type.create_data_source(
            network=self.network.network(),
            rate_limits=self.network.rate_limits(),
            fee_calculator_mode=self.fee_calculator,
        )


KEYS = InjectiveConfigMap.model_construct()
