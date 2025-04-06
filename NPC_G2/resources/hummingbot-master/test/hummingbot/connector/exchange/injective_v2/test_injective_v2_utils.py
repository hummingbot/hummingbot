from unittest import TestCase

from pyinjective import Address, PrivateKey
from pyinjective.core.network import Network

from hummingbot.connector.exchange.injective_v2 import injective_constants as CONSTANTS
from hummingbot.connector.exchange.injective_v2.data_sources.injective_grantee_data_source import (
    InjectiveGranteeDataSource,
)
from hummingbot.connector.exchange.injective_v2.data_sources.injective_vaults_data_source import (
    InjectiveVaultsDataSource,
)
from hummingbot.connector.exchange.injective_v2.injective_v2_utils import (
    FEE_CALCULATOR_MODES,
    InjectiveConfigMap,
    InjectiveCustomNetworkMode,
    InjectiveDelegatedAccountMode,
    InjectiveMainnetNetworkMode,
    InjectiveMessageBasedTransactionFeeCalculatorMode,
    InjectiveSimulatedTransactionFeeCalculatorMode,
    InjectiveTestnetNetworkMode,
    InjectiveVaultAccountMode,
)


class InjectiveConfigMapTests(TestCase):

    def test_mainnet_network_config_creation(self):
        network_config = InjectiveMainnetNetworkMode()

        network = network_config.network()
        expected_network = Network.mainnet(node="lb")

        self.assertEqual(expected_network.string(), network.string())
        self.assertEqual(expected_network.lcd_endpoint, network.lcd_endpoint)
        self.assertTrue(network_config.use_secure_connection())

    def test_testnet_network_config_creation(self):
        network_config = InjectiveTestnetNetworkMode(testnet_node="sentry")

        network = network_config.network()
        expected_network = Network.testnet(node="sentry")

        self.assertEqual(expected_network.string(), network.string())
        self.assertEqual(expected_network.lcd_endpoint, network.lcd_endpoint)
        self.assertTrue(network_config.use_secure_connection())

    def test_custom_network_config_creation(self):
        network_config = InjectiveCustomNetworkMode(
            lcd_endpoint="https://devnet.lcd.injective.dev",
            tm_websocket_endpoint="wss://devnet.tm.injective.dev/websocket",
            grpc_endpoint="devnet.injective.dev:9900",
            grpc_exchange_endpoint="devnet.injective.dev:9910",
            grpc_explorer_endpoint="devnet.injective.dev:9911",
            chain_stream_endpoint="devnet.injective.dev:9999",
            chain_id="injective-777",
            env="devnet",
            secure_connection=False,
        )

        network = network_config.network()
        expected_network = Network.custom(
            lcd_endpoint="https://devnet.lcd.injective.dev",
            tm_websocket_endpoint="wss://devnet.tm.injective.dev/websocket",
            grpc_endpoint="devnet.injective.dev:9900",
            grpc_exchange_endpoint="devnet.injective.dev:9910",
            grpc_explorer_endpoint="devnet.injective.dev:9911",
            chain_stream_endpoint="devnet.injective.dev:9999",
            chain_id="injective-777",
            env="devnet",
            official_tokens_list_url="",
        )

        self.assertEqual(expected_network.string(), network.string())
        self.assertEqual(expected_network.lcd_endpoint, network.lcd_endpoint)
        self.assertEqual(expected_network.tm_websocket_endpoint, network.tm_websocket_endpoint)
        self.assertEqual(expected_network.grpc_endpoint, network.grpc_endpoint)
        self.assertEqual(expected_network.grpc_exchange_endpoint, network.grpc_exchange_endpoint)
        self.assertEqual(expected_network.grpc_explorer_endpoint, network.grpc_explorer_endpoint)
        self.assertEqual(expected_network.chain_id, network.chain_id)
        self.assertEqual(expected_network.fee_denom, network.fee_denom)
        self.assertEqual(expected_network.env, network.env)
        self.assertFalse(network_config.use_secure_connection())

    def test_injective_delegate_account_config_creation(self):
        _, grantee_private_key = PrivateKey.generate()
        _, granter_private_key = PrivateKey.generate()

        config = InjectiveDelegatedAccountMode(
            private_key=granter_private_key.to_hex(),
            subaccount_index=0,
            granter_address=Address(bytes.fromhex(granter_private_key.to_public_key().to_hex())).to_acc_bech32(),
            granter_subaccount_index=0,
        )

        data_source = config.create_data_source(
            network=Network.testnet(node="sentry"),
            use_secure_connection=True,
            rate_limits=CONSTANTS.PUBLIC_NODE_RATE_LIMITS,
            fee_calculator_mode=InjectiveSimulatedTransactionFeeCalculatorMode(),
        )

        self.assertEqual(InjectiveGranteeDataSource, type(data_source))

    def test_injective_vault_account_config_creation(self):
        _, private_key = PrivateKey.generate()

        config = InjectiveVaultAccountMode(
            private_key=private_key.to_hex(),
            subaccount_index=0,
            vault_contract_address=Address(
                bytes.fromhex(private_key.to_public_key().to_hex())).to_acc_bech32(),
        )

        data_source = config.create_data_source(
            network=Network.testnet(node="sentry"),
            use_secure_connection=True,
            rate_limits=CONSTANTS.PUBLIC_NODE_RATE_LIMITS,
            fee_calculator_mode=InjectiveSimulatedTransactionFeeCalculatorMode(),
        )

        self.assertEqual(InjectiveVaultsDataSource, type(data_source))

    def test_injective_config_creation(self):
        network_config = InjectiveMainnetNetworkMode()

        _, grantee_private_key = PrivateKey.generate()
        _, granter_private_key = PrivateKey.generate()

        account_config = InjectiveDelegatedAccountMode(
            private_key=granter_private_key.to_hex(),
            subaccount_index=0,
            granter_address=Address(bytes.fromhex(granter_private_key.to_public_key().to_hex())).to_acc_bech32(),
            granter_subaccount_index=0,
        )

        injective_config = InjectiveConfigMap(
            network=network_config,
            account_type=account_config,
        )

        data_source = injective_config.create_data_source()

        self.assertEqual(InjectiveGranteeDataSource, type(data_source))

    def test_fee_calculator_validator(self):
        config = InjectiveConfigMap()

        config.fee_calculator = InjectiveSimulatedTransactionFeeCalculatorMode.Config.title
        self.assertEqual(InjectiveSimulatedTransactionFeeCalculatorMode(), config.fee_calculator)

        config.fee_calculator = InjectiveMessageBasedTransactionFeeCalculatorMode.Config.title
        self.assertEqual(InjectiveMessageBasedTransactionFeeCalculatorMode(), config.fee_calculator)

        with self.assertRaises(ValueError) as ex_context:
            config.fee_calculator = "invalid"

        self.assertEqual(
            f"Invalid fee calculator, please choose a value from {list(FEE_CALCULATOR_MODES.keys())}.",
            str(ex_context.exception.args[0][0].exc)
        )
