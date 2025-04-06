from web3 import Web3

from pyinjective.utils.logger import LoggerProvider
from pyinjective.wallet import Address


class Peggo:
    def __init__(self, network: str):
        self.network = network

    def sendToInjective(
        self,
        ethereum_endpoint: str,
        private_key: str,
        token_contract: str,
        receiver: str,
        amount: float,
        maxFeePerGas: int,
        maxPriorityFeePerGas: int,
        peggo_abi: str,
        data: str,
        decimals=18,
    ):
        if self.network == "testnet":
            peggy_proxy_address = "0xd2C6753F6B1783EF0a3857275e16e79D91b539a3"
        elif self.network == "mainnet":
            peggy_proxy_address = "0xF955C57f9EA9Dc8781965FEaE0b6A2acE2BAD6f3"
        elif self.network == "devnet":
            peggy_proxy_address = "0x4F38F75606d046819638f909b66B112aF1095e8d"
        else:
            LoggerProvider().logger_for_class(logging_class=self.__class__).info("Network is not supported")
            raise RuntimeError(f"Network {self.network} not supported")
        web3 = Web3(Web3.HTTPProvider(ethereum_endpoint))
        contract = web3.eth.contract(address=peggy_proxy_address, abi=peggo_abi)

        token_contract_address = web3.to_checksum_address(token_contract)

        receiver_address = Address.from_acc_bech32(receiver)
        receiver_ethereum_address = Address.get_ethereum_address(receiver_address)
        receiver_address_checksum = web3.to_checksum_address(receiver_ethereum_address)
        receiver_slice = receiver_address_checksum[2:]
        receiver_padded_address = "0x" + receiver_slice.zfill(64)

        destination = web3.to_bytes(hexstr=receiver_padded_address)

        sender_ethereum_address = web3.eth.account.from_key(private_key).address
        sender_address_checksum = web3.to_checksum_address(sender_ethereum_address)
        nonce = web3.eth.get_transaction_count(sender_address_checksum)

        amount_to_send = int(amount * pow(10, decimals))

        gas = contract.functions.sendToInjective(
            token_contract_address, destination, amount_to_send, data
        ).estimate_gas({"from": sender_address_checksum})

        transaction_body = {
            "nonce": nonce,
            "gas": gas,
            "maxFeePerGas": web3.to_wei(maxFeePerGas, "gwei"),
            "maxPriorityFeePerGas": web3.to_wei(maxPriorityFeePerGas, "gwei"),
        }

        tx = contract.functions.sendToInjective(
            token_contract_address, destination, amount_to_send, data
        ).buildTransaction(transaction_body)

        signed_tx = web3.eth.account.signTransaction(tx, private_key=private_key)

        try:
            tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            LoggerProvider().logger_for_class(logging_class=self.__class__).info(
                f"Transferred {amount} {token_contract} from {sender_ethereum_address} to {receiver}"
            )
            LoggerProvider().logger_for_class(logging_class=self.__class__).info(
                "Transaction hash: {}".format(Web3.to_hex(tx_hash))
            )
        except Exception as e:
            LoggerProvider().logger_for_class(logging_class=self.__class__).info("Transaction failed {}".format(e))
