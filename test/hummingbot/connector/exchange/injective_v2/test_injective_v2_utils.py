import copy
import io
from unittest import TestCase

import yaml
from pydantic import ValidationError
from pyinjective import Address, PrivateKey
from pyinjective.core.network import Network

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.injective_v2 import injective_constants as CONSTANTS
from hummingbot.connector.exchange.injective_v2.data_sources.injective_grantee_data_source import (
    InjectiveGranteeDataSource,
)
from hummingbot.connector.exchange.injective_v2.injective_v2_utils import (
    InjectiveConfigMap,
    InjectiveCustomNetworkMode,
    InjectiveDelegatedAccountMode,
    InjectiveMainnetNetworkMode,
    InjectiveMessageBasedTransactionFeeCalculatorMode,
    InjectiveSimulatedTransactionFeeCalculatorMode,
    InjectiveTestnetNetworkMode,
)


class InjectiveConfigMapTests(TestCase):

    def test_mainnet_network_config_creation(self):
        network_config = InjectiveMainnetNetworkMode()

        network = network_config.network()
        expected_network = Network.mainnet(node="lb")

        self.assertEqual(expected_network.string(), network.string())
        self.assertEqual(expected_network.lcd_endpoint, network.lcd_endpoint)

    def test_testnet_network_config_creation(self):
        network_config = InjectiveTestnetNetworkMode(testnet_node="sentry")

        network = network_config.network()
        expected_network = Network.testnet(node="sentry")

        self.assertEqual(expected_network.string(), network.string())
        self.assertEqual(expected_network.lcd_endpoint, network.lcd_endpoint)

    def test_custom_network_config_creation(self):
        network_config = InjectiveCustomNetworkMode(
            lcd_endpoint="https://devnet.lcd.injective.dev",
            tm_websocket_endpoint="wss://devnet.tm.injective.dev/websocket",
            grpc_endpoint="devnet.injective.dev:9900",
            grpc_exchange_endpoint="devnet.injective.dev:9910",
            grpc_explorer_endpoint="devnet.injective.dev:9911",
            chain_stream_endpoint="devnet.injective.dev:9999",
            chain_id="injective-777",
            env="devnet"
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
            rate_limits=CONSTANTS.PUBLIC_NODE_RATE_LIMITS,
            fee_calculator_mode=InjectiveSimulatedTransactionFeeCalculatorMode(),
        )

        self.assertEqual(InjectiveGranteeDataSource, type(data_source))

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

    # def test_fee_calculator_validator(self):
    #     config = InjectiveConfigMap()
    #
    #     config.fee_calculator = InjectiveSimulatedTransactionFeeCalculatorMode.model_config["title"]
    #     self.assertEqual(InjectiveSimulatedTransactionFeeCalculatorMode(), config.fee_calculator)
    #
    #     config.fee_calculator = InjectiveMessageBasedTransactionFeeCalculatorMode.model_config["title"]
    #     self.assertEqual(InjectiveMessageBasedTransactionFeeCalculatorMode(), config.fee_calculator)
    #
    #     with self.assertRaises(ValueError) as ex_context:
    #         config.fee_calculator = "invalid"
    #
    #     self.assertEqual(
    #         f"Invalid fee calculator, please choose a value from {list(FEE_CALCULATOR_MODES.keys())}.",
    #         str(ex_context.exception.errors()[0]["ctx"]["error"].args[0])
    #     )

    def test_fee_calculator_mode_config_parsing(self):
        config = InjectiveConfigMap()
        config.fee_calculator = InjectiveSimulatedTransactionFeeCalculatorMode()

        config_adapter = ClientConfigAdapter(config)
        result_yaml = config_adapter.generate_yml_output_str_with_comments()

        expected_yaml = """###############################
###   injective_v2 config   ###
###############################

connector: injective_v2

receive_connector_configuration: true

network: {}

account_type: {}

fee_calculator:
  name: simulated_transaction_fee_calculator
"""

        self.assertEqual(expected_yaml, result_yaml)

        stream = io.StringIO(result_yaml)
        config_dict = yaml.safe_load(stream)

        new_config = InjectiveConfigMap()
        loaded_config = new_config.model_validate(config_dict)

        self.assertIsInstance(new_config.fee_calculator, InjectiveMessageBasedTransactionFeeCalculatorMode)
        self.assertIsInstance(loaded_config.fee_calculator, InjectiveSimulatedTransactionFeeCalculatorMode)

        invalid_yaml = copy.deepcopy(config_dict)
        invalid_yaml["fee_calculator"]["name"] = "invalid"

        with self.assertRaises(ValidationError) as ex_context:
            new_config.model_validate(invalid_yaml)

        expected_error_message = "Input tag 'invalid' found using 'name' does not match any of the expected tags: 'simulated_transaction_fee_calculator', 'message_based_transaction_fee_calculator' [type=union_tag_invalid, input_value={'name': 'invalid'}, input_type=dict]"
        self.assertIn(expected_error_message, str(ex_context.exception))
