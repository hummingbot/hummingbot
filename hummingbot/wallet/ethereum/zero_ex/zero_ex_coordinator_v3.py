import aiohttp
import random
import os
from decimal import Decimal
from typing import (
    List,
    Tuple
)
from time import time
from math import floor
import ujson
from web3 import Web3
from web3.contract import Contract
from zero_ex.order_utils import Order
from hummingbot.wallet.ethereum.zero_ex.zero_ex_transaction_encoder_v3 import (
    ZeroExTransaction,
    SignedZeroExTransaction,
    get_transaction_hash_hex
)
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet
from hummingbot.wallet.ethereum.zero_ex.zero_ex_custom_utils_v3 import (
    convert_order_to_tuple,
    fix_signature
)

with open(os.path.join(os.path.dirname(__file__), "zero_ex_exchange_abi_v3.json")) as exchange_abi_json:
    exchange_abi: List[any] = ujson.load(exchange_abi_json)

with open(os.path.join(os.path.dirname(__file__), "zero_ex_coordinator_abi_v3.json")) as coordinator_abi_json:
    coordinator_abi: List[any] = ujson.load(coordinator_abi_json)

with open(os.path.join(os.path.dirname(__file__), "zero_ex_coordinator_registry_abi_v3.json")) as coordinator_registry_abi_json:
    coordinator_registry_abi: List[any] = ujson.load(coordinator_registry_abi_json)

# 150,000 per order by gas
PROTOCOL_FEE_MULTIPLIER = 150000

DEFAULT_APPROVAL_EXPIRATION_TIME_SECONDS = 90
DEFAULT_EXPIRATION_TIME_BUFFER_SECONDS = 30


class ZeroExCoordinatorFailedException(Exception):
    def __init__(self, approvedOrders: [], cancellations: [], errors: []):
        self.approvedOrders = approvedOrders
        self.cancellations = cancellations
        self.errors = errors


class ZeroExCoordinator:
    def __init__(self,
                 provider: Web3.HTTPProvider,
                 w3: Web3,
                 exchange_address: str,
                 coordinator_address: str,
                 coordinator_registry_address: str,
                 wallet: Web3Wallet,
                 chain_id: int):
        self._provider: Web3.HTTPProvider = provider
        self._w3: Web3 = w3
        self._exchange_contract: Contract = w3.eth.contract(address=exchange_address, abi=exchange_abi)
        self._exchange_address: str = exchange_address
        self._coordinator_contract: Contract = w3.eth.contract(address=coordinator_address, abi=coordinator_abi)
        self._coordinator_address: str = coordinator_address
        self._registry_contract: Contract = w3.eth.contract(address=coordinator_registry_address, abi=coordinator_registry_abi)
        self._registry_address: str = coordinator_registry_address
        self._wallet: Web3Wallet = wallet
        self._feeRecipientToEndpoint = {}
        self._chain_id = chain_id
        self._current_gas_price = wallet.gas_price + 10

    @property
    def contract(self) -> Contract:
        return self._coordinator_contract

    @property
    def coordinator_address(self) -> str:
        return self._coordinator_address

    @property
    def wallet(self) -> Web3Wallet:
        return self._wallet

    async def fill_order(self, order: Order, taker_asset_fill_amount: Decimal, signature: str) -> Tuple[str, Decimal]:
        order_tuple: Tuple = convert_order_to_tuple(order)
        signature: bytes = self._w3.toBytes(hexstr=signature)

        # Set gas to 1, so it avoids estimateGas call in Web3, which will revert
        fillOrderData = self._exchange_contract.functions.fillOrder(
            order_tuple,
            int(taker_asset_fill_amount),
            signature
        ).buildTransaction({'gas': 1})

        data = fillOrderData['data']

        self._current_gas_price = self._wallet.gas_price + 10

        tx_hash, protocol_fee = await self._handle_fills(data, self._wallet.address, [order])

        return tx_hash, protocol_fee

    async def batch_fill_orders(self, orders: List[Order], taker_asset_fill_amounts: List[Decimal], signatures: List[str]) -> Tuple[str, Decimal]:
        order_tuples: List[Tuple] = [convert_order_to_tuple(order) for order in orders]
        signatures: List[bytes] = [self._w3.toBytes(hexstr=signature) for signature in signatures]
        taker_asset_fill_amounts: List[int] = [int(amount) for amount in taker_asset_fill_amounts]

        # Set gas to 1, so it avoids estimateGas call in Web3, which will revert
        batchFillOrderData = self._exchange_contract.functions.batchFillOrders(
            order_tuples,
            taker_asset_fill_amounts,
            signatures
        ).buildTransaction({'gas': 1})

        data = batchFillOrderData['data']

        self._current_gas_price = self._wallet.gas_price + 10

        tx_hash, protocol_fee = await self._handle_fills(data, self._wallet.address, orders)

        return tx_hash, protocol_fee

    async def soft_cancel_order(self, order: Order) -> bool:
        order_tuple: Tuple = convert_order_to_tuple(order)

        # Set gas to 1, so it avoids estimateGas call in Web3, which will revert
        cancelOrderData = self._exchange_contract.functions.cancelOrder(
            order_tuple
        ).buildTransaction({'gas': 1})

        data = cancelOrderData['data']

        transaction = self._generate_signed_zero_ex_transaction(data, order['makerAddress'], self._chain_id)
        endpoint = await self._get_server_endpoint_or_throw(order['feeRecipientAddress'])

        response = await self._execute_server_request(transaction, order['makerAddress'], endpoint)
        if response['isError']:
            approvedOrders = []
            cancellations = []
            errors = {
                **response,
                'orders': [order]
            }

            raise ZeroExCoordinatorFailedException(
                approvedOrders,
                cancellations,
                errors,
            )
        else:
            return True

    async def batch_soft_cancel_orders(self, orders: List[Order]) -> bool:
        order_tuples: List[Tuple] = [convert_order_to_tuple(order) for order in orders]

        makerAddress = orders[0]['makerAddress']

        # Set gas to 1, so it avoids estimateGas call in Web3, which will revert
        batchCancelOrderData = self._exchange_contract.functions.batchCancelOrders(
            order_tuples
        ).buildTransaction({'gas': 1})

        data = batchCancelOrderData['data']

        serverEndpointsToOrders = await self._map_server_endpoints_to_orders(orders)

        errorResponses: [] = []
        successResponses: [] = []
        transaction = self._generate_signed_zero_ex_transaction(data, makerAddress, self._chain_id)
        for endpoint in serverEndpointsToOrders:
            response = await self._execute_server_request(transaction, makerAddress, endpoint)
            if response['isError']:
                errorResponses.append(response)
            else:
                successResponses.append(response['body'])

        if len(errorResponses) == 0:
            return True
        else:
            errorsWithOrders = []

            for errorResponse in errorResponses:
                errorsWithOrders.append({
                    **errorResponse,
                    'orders': serverEndpointsToOrders[errorResponse['coordinatorOperator']]
                })

            approvedOrders = []
            cancellations = successResponses

            raise ZeroExCoordinatorFailedException(
                approvedOrders,
                cancellations,
                errorsWithOrders
            )

    async def hard_cancel_order(self, order: List[Order]) -> str:
        order_tuple: Tuple = convert_order_to_tuple(order)

        # Set gas to 1, so it avoids estimateGas call in Web3, which will revert
        hardCancelOrderData = self._exchange_contract.functions.cancelOrder(
            order_tuple
        ).buildTransaction({'gas': 1})

        data = hardCancelOrderData['data']

        self._current_gas_price = self._wallet.gas_price + 10

        transaction = self._generate_signed_zero_ex_transaction(data, order['makerAddress'], self._chain_id)

        tx_hash = await self._submit_coordinator_transaction(
            transaction,
            Web3.toChecksumAddress(order['makerAddress']),
            transaction['signature'],
            [],
            0
        )

        return tx_hash

    async def batch_hard_cancel_orders(self, orders: List[Order]) -> str:
        order_tuples: List[Tuple] = [convert_order_to_tuple(order) for order in orders]

        makerAddress = orders[0]['makerAddress']

        # Set gas to 1, so it avoids estimateGas call in Web3, which will revert
        batchHardCancelOrderData = self._exchange_contract.functions.batchCancelOrders(
            order_tuples
        ).buildTransaction({'gas': 1})

        data = batchHardCancelOrderData['data']

        self._current_gas_price = self._wallet.gas_price + 10

        transaction = self._generate_signed_zero_ex_transaction(data, makerAddress, self._chain_id)

        tx_hash = await self._submit_coordinator_transaction(
            transaction,
            Web3.toChecksumAddress(makerAddress),
            transaction['signature'],
            [],
            0
        )

        return tx_hash

    async def _handle_fills(self, data: str, takerAddress: str, signedOrders: List[Order]) -> Tuple[str, Decimal]:
        coordinatorOrders = [o for o in signedOrders if o['senderAddress'] == self._coordinator_address.lower()]
        serverEndpointsToOrders = await self._map_server_endpoints_to_orders(coordinatorOrders)

        errorResponses = []
        approvalResponses = []

        transaction = self._generate_signed_zero_ex_transaction(data, takerAddress, self._chain_id)

        for endpoint in serverEndpointsToOrders:
            response = await self._execute_server_request(transaction, takerAddress, endpoint)
            if response['isError']:
                errorResponses.append(response)
            else:
                approvalResponses.append(response)

        if len(errorResponses) == 0:
            # concatenate all approval responses
            allSignatures: List[str] = []
            allExpirationTimes: List[int] = []

            for approval in approvalResponses:
                allSignatures = allSignatures + approval['body']['signatures']
                allExpirationTimes = allExpirationTimes + [approval['body']['expirationTimeSeconds'] for i in approval['body']['signatures']]

            # submit transaction with approvals
            tx_hash, protocol_fee = await self._submit_coordinator_transaction(
                transaction,
                takerAddress,
                transaction['signature'],
                allSignatures,
                PROTOCOL_FEE_MULTIPLIER * len(signedOrders)
            )

            return tx_hash, protocol_fee
        else:
            # format errors and approvals
            approvedOrders = []

            for order in signedOrders:
                if order['senderAddress'] != self._coordinator_address:
                    approvedOrders.append(order)

            for approval in approvalResponses:
                approvedOrders = approvedOrders + serverEndpointsToOrders[approval['coordinatorOperator']]

            errorsWithOrders = []

            for errorResponse in errorResponses:
                errorsWithOrders.append({
                    **errorResponse,
                    'orders': serverEndpointsToOrders[errorResponse['coordinatorOperator']]
                })

            approvedOrders = []
            cancellations = []

            raise ZeroExCoordinatorFailedException(
                approvedOrders,
                cancellations,
                errorsWithOrders
            )

    async def _map_server_endpoints_to_orders(self, coordinatorOrders: List[Order]) -> List[str]:
        feeRecipientsToOrders = {}

        for order in coordinatorOrders:
            feeRecipient = order['feeRecipientAddress']
            if feeRecipient not in feeRecipientsToOrders:
                feeRecipientsToOrders[feeRecipient] = []
            feeRecipientsToOrders[feeRecipient].append(order)

        serverEndpointsToOrders = {}

        for feeRecipient in feeRecipientsToOrders:
            endpoint = await self._get_server_endpoint_or_throw(feeRecipient)
            orders = feeRecipientsToOrders[feeRecipient]
            if endpoint not in serverEndpointsToOrders:
                serverEndpointsToOrders[endpoint] = []

            serverEndpointsToOrders[endpoint] = serverEndpointsToOrders[endpoint] + orders

        return serverEndpointsToOrders

    async def _get_server_endpoint_or_throw(self, feeRecipientAddress: str) -> str:
        if feeRecipientAddress in self._feeRecipientToEndpoint:
            return self._feeRecipientToEndpoint[feeRecipientAddress]
        else:
            return await self._fetch_server_endpoint_or_throw(feeRecipientAddress)

    async def _fetch_server_endpoint_or_throw(self, feeRecipient: str) -> str:
        coordinatorOperatorEndpoint: str = self._registry_contract.functions.getCoordinatorEndpoint(Web3.toChecksumAddress(feeRecipient)).call()

        if (coordinatorOperatorEndpoint == '') or (coordinatorOperatorEndpoint is None):
            raise Exception(
                'No Coordinator server endpoint found in Coordinator Registry for feeRecipientAddress: ' + feeRecipient + '. Registry contract address: ' + self._registry_address
            )

        return coordinatorOperatorEndpoint

    def _generate_signed_zero_ex_transaction(self, data: str, signerAddress: str, chainId: int) -> any:
        expirationTimeSeconds = floor(time()) + DEFAULT_APPROVAL_EXPIRATION_TIME_SECONDS - DEFAULT_EXPIRATION_TIME_BUFFER_SECONDS

        transaction: ZeroExTransaction = {
            'salt': random.randint(1, 100000000000000),
            'signerAddress': signerAddress.lower(),
            'data': data,
            'domain': {
                'verifyingContract': self._exchange_address.lower(),
                'chainId': chainId
            },
            'expirationTimeSeconds': expirationTimeSeconds,
            'gasPrice': int(self._current_gas_price)
        }

        order_hash_hex = get_transaction_hash_hex(transaction)

        signature = self._wallet.current_backend.sign_hash(hexstr=order_hash_hex)
        fixed_signature = fix_signature(self._provider,
                                        signerAddress,
                                        order_hash_hex,
                                        signature,
                                        chainId)

        transaction['signature'] = fixed_signature

        return transaction

    async def _execute_server_request(self, signedTransaction: SignedZeroExTransaction, txOrigin: str, endpoint: str) -> bool:
        requestPayload = {
            "signedTransaction": signedTransaction,
            "txOrigin": txOrigin.lower()
        }

        try:
            response = await self._post_request(endpoint + '/v2/request_transaction?chainId=' + str(self._chain_id), requestPayload)

            status = response.status

            isError = status != 200
            isValidationError = status == 400

            if not isError or isValidationError:
                try:
                    json = await response.json()
                    if isError:
                        error = json
                        body = None
                    else:
                        body = json
                        error = "Error signalled but empty response returned"
                except Exception as ex:
                    isError = True
                    isValidationError = False
                    body = None
                    error = str(ex)
            else:
                body = None
                error = None
        except Exception as ex:
            status = 500
            body = None
            error = str(ex)
            isError = True
            isValidationError = False

        result = {
            'isError': isError,
            'status': status,
            'body': body,
            'error': error,
            'request': requestPayload,
            'coordinatorOperator': endpoint,
        }
        return result

    async def _post_request(self, url, data, timeout=10):
        async with aiohttp.ClientSession() as client:
            async with client.request('POST',
                                      url=url,
                                      timeout=timeout,
                                      json=data,
                                      headers={'Content-Type': 'application/json; charset=utf-8'}) as response:
                try:
                    await response.json()
                    return response
                except aiohttp.ContentTypeError:
                    error = await response.text()
                    raise ValueError(error)

    async def _submit_coordinator_transaction(
        self,
        transaction,
        txOrigin: str,
        transactionSignature: str,
        approvalSignatures: List[str],
        protocolFeeMultiplier
    ) -> Tuple[str, Decimal]:
        transaction: Tuple[str, any] = (
            transaction["salt"],
            transaction["expirationTimeSeconds"],
            transaction["gasPrice"],
            Web3.toChecksumAddress(transaction["signerAddress"]),
            self._w3.toBytes(hexstr=transaction["data"])
        )
        transactionSignature: bytes = self._w3.toBytes(hexstr=transactionSignature)
        approvalSignatures: List[bytes] = [self._w3.toBytes(hexstr=signature) for signature in approvalSignatures]

        gas_price = self._current_gas_price
        protocol_fee = protocolFeeMultiplier * gas_price
        tx_hash: str = self._wallet.execute_transaction(
            self._coordinator_contract.functions.executeTransaction(
                transaction,
                txOrigin,
                transactionSignature,
                approvalSignatures
            ),
            gasPrice=int(gas_price),
            value=int(protocol_fee)
        )
        return tx_hash, Decimal(protocol_fee)
