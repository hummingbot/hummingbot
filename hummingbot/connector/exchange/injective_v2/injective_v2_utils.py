import re
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional, Union

from pydantic import Field, SecretStr
from pydantic.class_validators import validator
from pyinjective.async_client import AsyncClient
from pyinjective.composer import Composer
from pyinjective.core.broadcaster import (
    MessageBasedTransactionFeeCalculator,
    SimulatedTransactionFeeCalculator,
    TransactionFeeCalculator,
)
from pyinjective.core.network import Network
from pyinjective.wallet import PrivateKey

from hummingbot.client.config.config_data_types import BaseClientModel, BaseConnectorConfigMap, ClientFieldData
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
    name: str = Field(
        default="simulated_transaction_fee_calculator",
        const=True,
        client_data=ClientFieldData(),
    )

    class Config:
        title = "simulated_transaction_fee_calculator"

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
    name: str = Field(
        default="message_based_transaction_fee_calculator",
        const=True,
        client_data=ClientFieldData(),
    )

    class Config:
        title = "message_based_transaction_fee_calculator"

    def create_calculator(
            self,
            client: AsyncClient,
            composer: Composer,
            gas_price: Optional[int] = None,
            gas_limit_adjustment_multiplier: Optional[Decimal] = None,
    ) -> TransactionFeeCalculator:
        return MessageBasedTransactionFeeCalculator(
            client=client,
            composer=composer,
            gas_price=gas_price,
        )


FEE_CALCULATOR_MODES = {
    InjectiveSimulatedTransactionFeeCalculatorMode.Config.title: InjectiveSimulatedTransactionFeeCalculatorMode,
    InjectiveMessageBasedTransactionFeeCalculatorMode.Config.title: InjectiveMessageBasedTransactionFeeCalculatorMode,
}


class InjectiveNetworkMode(BaseClientModel, ABC):
    @abstractmethod
    def network(self) -> Network:
        pass

    @abstractmethod
    def use_secure_connection(self) -> bool:
        pass


class InjectiveMainnetNetworkMode(InjectiveNetworkMode):

    class Config:
        title = "mainnet_network"

    def network(self) -> Network:
        return Network.mainnet()

    def use_secure_connection(self) -> bool:
        return True

    def rate_limits(self) -> List[RateLimit]:
        return CONSTANTS.PUBLIC_NODE_RATE_LIMITS


class InjectiveTestnetNetworkMode(InjectiveNetworkMode):
    testnet_node: str = Field(
        default="lb",
        client_data=ClientFieldData(
            prompt=lambda cm: (f"Enter the testnet node you want to connect to ({'/'.join(TESTNET_NODES)})"),
            prompt_on_new=True
        ),
    )

    class Config:
        title = "testnet_network"

    @validator("testnet_node", pre=True)
    def validate_node(cls, v: str):
        if v not in TESTNET_NODES:
            raise ValueError(f"{v} is not a valid node ({TESTNET_NODES})")
        return v

    def network(self) -> Network:
        return Network.testnet(node=self.testnet_node)

    def use_secure_connection(self) -> bool:
        return True

    def rate_limits(self) -> List[RateLimit]:
        return CONSTANTS.PUBLIC_NODE_RATE_LIMITS


class InjectiveCustomNetworkMode(InjectiveNetworkMode):
    lcd_endpoint: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: ("Enter the network lcd_endpoint"),
            prompt_on_new=True
        ),
    )
    tm_websocket_endpoint: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: ("Enter the network tm_websocket_endpoint"),
            prompt_on_new=True
        ),
    )
    grpc_endpoint: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: ("Enter the network grpc_endpoint"),
            prompt_on_new=True
        ),
    )
    grpc_exchange_endpoint: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: ("Enter the network grpc_exchange_endpoint"),
            prompt_on_new=True
        ),
    )
    grpc_explorer_endpoint: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: ("Enter the network grpc_explorer_endpoint"),
            prompt_on_new=True
        ),
    )
    chain_stream_endpoint: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: ("Enter the network chain_stream_endpoint"),
            prompt_on_new=True
        ),
    )
    chain_id: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: ("Enter the network chain_id"),
            prompt_on_new=True
        ),
    )
    env: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: ("Enter the network environment name"),
            prompt_on_new=True
        ),
    )
    secure_connection: bool = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: ("Should this configuration use secure connections? (yes/no)"),
            prompt_on_new=True
        ),
    )

    class Config:
        title = "custom_network"

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

    def use_secure_connection(self) -> bool:
        return self.secure_connection

    def rate_limits(self) -> List[RateLimit]:
        return CONSTANTS.CUSTOM_NODE_RATE_LIMITS


NETWORK_MODES = {
    InjectiveMainnetNetworkMode.Config.title: InjectiveMainnetNetworkMode,
    InjectiveTestnetNetworkMode.Config.title: InjectiveTestnetNetworkMode,
    InjectiveCustomNetworkMode.Config.title: InjectiveCustomNetworkMode,
}

# Captures a 12 or 24-word BIP39 seed phrase
RE_SEED_PHRASE = re.compile(r"^(?:[a-z]+(?: [a-z]+){11}|[a-z]+(?: [a-z]+){23})$")


class InjectiveAccountMode(BaseClientModel, ABC):

    @abstractmethod
    def create_data_source(
            self,
            network: Network,
            use_secure_connection: bool,
            rate_limits: List[RateLimit],
            fee_calculator_mode: InjectiveFeeCalculatorMode,
    ) -> "InjectiveDataSource":
        pass


class InjectiveDelegatedAccountMode(InjectiveAccountMode):
    private_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Injective trading account private key or seed phrase",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    subaccount_index: int = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Injective trading account subaccount index",
            prompt_on_new=True,
        ),
    )
    granter_address: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter the Injective address of the granter account (portfolio account)",
            prompt_on_new=True,
        ),
    )
    granter_subaccount_index: int = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter the Injective granter subaccount index (portfolio subaccount index)",
            prompt_on_new=True,
        ),
    )

    @validator("private_key", pre=True)
    def validate_network(cls, v: str):
        # Both seed phrase and hex private keys supported
        if isinstance(v, str):
            v = v.strip()
            if RE_SEED_PHRASE.match(v):
                private_key = PrivateKey.from_mnemonic(v)
                return private_key.to_hex()
        return v

    class Config:
        title = "delegate_account"

    def create_data_source(
            self,
            network: Network,
            use_secure_connection: bool,
            rate_limits: List[RateLimit],
            fee_calculator_mode: InjectiveFeeCalculatorMode,
    ) -> "InjectiveDataSource":
        return InjectiveGranteeDataSource(
            private_key=self.private_key.get_secret_value(),
            subaccount_index=self.subaccount_index,
            granter_address=self.granter_address,
            granter_subaccount_index=self.granter_subaccount_index,
            network=network,
            use_secure_connection=use_secure_connection,
            rate_limits=rate_limits,
            fee_calculator_mode=fee_calculator_mode,
        )


class InjectiveVaultAccountMode(InjectiveAccountMode):
    private_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter the vault admin private key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    subaccount_index: int = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter the vault admin subaccount index",
            prompt_on_new=True,
        ),
    )
    vault_contract_address: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter the vault contract address",
            prompt_on_new=True,
        ),
    )
    vault_subaccount_index: int = Field(
        default=1,
        const=True,
        client_data=None
    )

    class Config:
        title = "vault_account"

    def create_data_source(
            self,
            network: Network,
            use_secure_connection: bool,
            rate_limits: List[RateLimit],
            fee_calculator_mode: InjectiveFeeCalculatorMode,
    ) -> "InjectiveDataSource":
        return InjectiveVaultsDataSource(
            private_key=self.private_key.get_secret_value(),
            subaccount_index=self.subaccount_index,
            vault_contract_address=self.vault_contract_address,
            vault_subaccount_index=self.vault_subaccount_index,
            network=network,
            use_secure_connection=use_secure_connection,
            rate_limits=rate_limits,
            fee_calculator_mode=fee_calculator_mode,
        )


class InjectiveReadOnlyAccountMode(InjectiveAccountMode):

    class Config:
        title = "read_only_account"

    def create_data_source(
            self,
            network: Network, use_secure_connection: bool,
            rate_limits: List[RateLimit],
            fee_calculator_mode: InjectiveFeeCalculatorMode,
    ) -> "InjectiveDataSource":
        return InjectiveReadOnlyDataSource(
            network=network,
            use_secure_connection=use_secure_connection,
            rate_limits=rate_limits,
        )


ACCOUNT_MODES = {
    InjectiveDelegatedAccountMode.Config.title: InjectiveDelegatedAccountMode,
    InjectiveVaultAccountMode.Config.title: InjectiveVaultAccountMode,
    InjectiveReadOnlyAccountMode.Config.title: InjectiveReadOnlyAccountMode,
}


class InjectiveConfigMap(BaseConnectorConfigMap):
    # Setting a default dummy configuration to allow the bot to create a dummy instance to fetch all trading pairs
    connector: str = Field(default="injective_v2", const=True, client_data=None)
    receive_connector_configuration: bool = Field(
        default=True, const=True,
        client_data=ClientFieldData(),
    )
    network: Union[tuple(NETWORK_MODES.values())] = Field(
        default=InjectiveMainnetNetworkMode(),
        client_data=ClientFieldData(
            prompt=lambda cm: f"Select the network ({'/'.join(list(NETWORK_MODES.keys()))})",
            prompt_on_new=True,
        ),
    )
    account_type: Union[tuple(ACCOUNT_MODES.values())] = Field(
        default=InjectiveReadOnlyAccountMode(),
        client_data=ClientFieldData(
            prompt=lambda cm: f"Select the type of account configuration ({'/'.join(list(ACCOUNT_MODES.keys()))})",
            prompt_on_new=True,
        ),
    )
    fee_calculator: Union[tuple(FEE_CALCULATOR_MODES.values())] = Field(
        default=InjectiveSimulatedTransactionFeeCalculatorMode(),
        client_data=ClientFieldData(
            prompt=lambda cm: f"Select the fee calculator ({'/'.join(list(FEE_CALCULATOR_MODES.keys()))})",
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "injective_v2"

    @validator("network", pre=True)
    def validate_network(cls, v: Union[(str, Dict) + tuple(NETWORK_MODES.values())]):
        if isinstance(v, tuple(NETWORK_MODES.values()) + (Dict,)):
            sub_model = v
        elif v not in NETWORK_MODES:
            raise ValueError(
                f"Invalid network, please choose a value from {list(NETWORK_MODES.keys())}."
            )
        else:
            sub_model = NETWORK_MODES[v].construct()
        return sub_model

    @validator("account_type", pre=True)
    def validate_account_type(cls, v: Union[(str, Dict) + tuple(ACCOUNT_MODES.values())]):
        if isinstance(v, tuple(ACCOUNT_MODES.values()) + (Dict,)):
            sub_model = v
        elif v not in ACCOUNT_MODES:
            raise ValueError(
                f"Invalid account type, please choose a value from {list(ACCOUNT_MODES.keys())}."
            )
        else:
            sub_model = ACCOUNT_MODES[v].construct()
        return sub_model

    @validator("fee_calculator", pre=True)
    def validate_fee_calculator(cls, v: Union[(str, Dict) + tuple(FEE_CALCULATOR_MODES.values())]):
        if isinstance(v, tuple(FEE_CALCULATOR_MODES.values()) + (Dict,)):
            sub_model = v
        elif v not in FEE_CALCULATOR_MODES:
            raise ValueError(
                f"Invalid fee calculator, please choose a value from {list(FEE_CALCULATOR_MODES.keys())}."
            )
        else:
            sub_model = FEE_CALCULATOR_MODES[v].construct()
        return sub_model

    def create_data_source(self):
        return self.account_type.create_data_source(
            network=self.network.network(),
            use_secure_connection=self.network.use_secure_connection(),
            rate_limits=self.network.rate_limits(),
            fee_calculator_mode=self.fee_calculator,
        )


KEYS = InjectiveConfigMap.construct()
