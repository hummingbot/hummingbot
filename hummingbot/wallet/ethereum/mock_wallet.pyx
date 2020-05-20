from decimal import Decimal
from eth_account import Account
import logging
import math
from typing import (
    Union,
    Dict
)
from web3 import Web3
from web3.datastructures import AttributeDict
from web3.exceptions import BlockNotFound

from hummingbot.wallet.ethereum.erc20_token import ERC20Token
from hummingbot.wallet.wallet_base cimport WalletBase
from hummingbot.logger import HummingbotLogger

s_logger = None


def get_logger() -> HummingbotLogger:
    global s_logger
    if s_logger is None:
        s_logger = logging.getLogger(__name__)
    return s_logger


cdef class ERC20Contract:
    cdef:
        public str asset_name
        public str address
        public object contract
        public int decimals

    def __init__(self, str asset_name, str address, object contract, int decimals):
        self.asset_name = asset_name
        self.address = address
        self.contract = contract
        self.decimals = decimals


cdef class MockWallet(WalletBase):
    def __init__(self, private_key: Union[str, bytes], w3_url: str, contract_abi: Dict[str, str],
                 chain_id: int = 3):
        super().__init__()
        self._w3 = Web3(Web3.HTTPProvider(w3_url))
        self._account = Account.privateKeyToAccount(private_key)
        self._local_nonce = self.get_remote_nonce()
        self._erc20_contracts = {}
        self._chain_id = chain_id
        for address, abi_json in contract_abi.items():
            contract = self._w3.eth.contract(address=address, abi=abi_json)
            asset_name = ERC20Token.get_symbol_from_contract(contract)
            decimals = contract.functions.decimals().call()
            self._erc20_contracts[asset_name] = ERC20Contract(asset_name, address, contract, decimals)

    @property
    def address(self) -> str:
        return self._account.address

    @property
    def gas_price(self) -> int:
        """
        :return: Gas price in wei
        """
        return self._w3.eth.gasPrice

    @property
    def nonce(self) -> int:
        remote_nonce = self.get_remote_nonce()
        retval = max(remote_nonce, self._local_nonce)
        self._local_nonce = retval
        return retval

    def send_signed_transaction(self, signed_transaction: AttributeDict):
        try:
            self._w3.eth.sendRawTransaction(signed_transaction.rawTransaction)
            self._local_nonce += 1
        except Exception:
            get_logger().error("Error sending transaction to Ethereum network.", exc_info=True)

    def get_all_balances(self) -> Dict[str, Decimal]:
        retval = {"ETH": self.c_get_balance("ETH")}
        for asset_name in self._erc20_contracts.keys():
            retval[asset_name] = self.c_get_balance(asset_name)
        return retval

    def get_remote_nonce(self):
        try:
            remote_nonce = self._w3.eth.getTransactionCount(self.address, block_identifier="pending")
            return remote_nonce
        except BlockNotFound:
            return None

    cdef object c_get_balance(self, str asset_name):
        if asset_name == "ETH":
            return Decimal(self._w3.eth.getBalance(self.address)) * Decimal("1e-18")
        else:
            if asset_name not in self._erc20_contracts:
                raise ValueError(f"{asset_name} is not a recognized asset in this wallet.")
            contract = self._erc20_contracts[asset_name].contract
            decimals = self._erc20_contracts[asset_name].decimals
            return Decimal(contract.functions.balanceOf(self.address).call()) * Decimal(f"1e-{decimals}")

    cdef str c_send(self, str address, str asset_name, object amount):
        if asset_name == "ETH":
            gas_price = self.gas_price
            raw_amount = int(amount * Decimal("1e18"))
            transaction = {
                "to": address,
                "value": raw_amount,
                "gas": 21000,
                "gasPrice": gas_price,
                "nonce": self.nonce,
                "chainId": self._chain_id
            }
            signed_transaction = self._account.signTransaction(transaction)
            print(f"transaction: {transaction}")
            print(f"signed transaction: {signed_transaction}")
            tx_hash = signed_transaction.hash.hex()
            self.send_signed_transaction(signed_transaction)
            return tx_hash
        else:
            if asset_name not in self._erc20_contracts:
                raise ValueError(f"{asset_name} is not a recognized asset in this wallet.")
            contract = self._erc20_contracts[asset_name].contract
            decimals = self._erc20_contracts[asset_name].decimals
            raw_amount = int(amount * Decimal(f"1e{decimals}"))
            transaction = contract.functions.transfer(address, raw_amount).buildTransaction({
                "nonce": self.nonce,
                "chainId": self._chain_id,
                "gas": 500000,
                "gasPrice": self.gas_price
            })
            signed_transaction = self._account.signTransaction(transaction)
            print(f"transaction: {transaction}")
            print(f"signed transaction: {signed_transaction}")
            tx_hash = signed_transaction.hash.hex()
            self.send_signed_transaction(signed_transaction)
            return tx_hash
