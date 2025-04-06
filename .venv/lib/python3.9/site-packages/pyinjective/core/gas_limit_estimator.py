import math
from abc import ABC, abstractmethod
from typing import List, Union

from google.protobuf import any_pb2

from pyinjective.proto.cosmos.authz.v1beta1 import tx_pb2 as cosmos_authz_tx_pb
from pyinjective.proto.cosmos.gov.v1beta1 import tx_pb2 as gov_tx_pb
from pyinjective.proto.cosmwasm.wasm.v1 import tx_pb2 as wasm_tx_pb
from pyinjective.proto.injective.exchange.v1beta1 import (
    exchange_pb2 as injective_exchange_pb,
    tx_pb2 as injective_exchange_tx_pb,
)

SPOT_ORDER_CREATION_GAS_LIMIT = 52_000
DERIVATIVE_ORDER_CREATION_GAS_LIMIT = 84_000
SPOT_ORDER_CANCELATION_GAS_LIMIT = 50_000
DERIVATIVE_ORDER_CANCELATION_GAS_LIMIT = 68_000
# POST ONLY orders take around 50% more gas to create than normal orders due to the required validations
SPOT_POST_ONLY_ORDER_MULTIPLIER = 0.62
DERIVATIVE_POST_ONLY_ORDER_MULTIPLIER = 0.35


class GasLimitEstimator(ABC):
    GENERAL_MESSAGE_GAS_LIMIT = 25_000
    BASIC_REFERENCE_GAS_LIMIT = 150_000

    @classmethod
    @abstractmethod
    def applies_to(cls, message: any_pb2.Any) -> bool:
        ...

    @classmethod
    def for_message(cls, message: any_pb2.Any):
        estimator_class = next(
            (
                estimator_subclass
                for estimator_subclass in cls.__subclasses__()
                if estimator_subclass.applies_to(message=message)
            ),
            None,
        )
        if estimator_class is None:
            estimator = DefaultGasLimitEstimator()
        else:
            estimator = estimator_class(message=message)

        return estimator

    @abstractmethod
    def gas_limit(self) -> int:
        ...

    @staticmethod
    def message_type(message: any_pb2.Any) -> str:
        if isinstance(message, any_pb2.Any):
            message_type = message.type_url
        else:
            message_type = message.DESCRIPTOR.full_name
        return message_type

    @abstractmethod
    def _message_class(self, message: any_pb2.Any):
        ...

    def _parsed_message(self, message: any_pb2.Any) -> any_pb2.Any:
        if isinstance(message, any_pb2.Any):
            parsed_message = self._message_class(message=message).FromString(message.value)
        else:
            parsed_message = message
        return parsed_message

    def _select_post_only_orders(
        self,
        orders: List[Union[injective_exchange_pb.SpotOrder, injective_exchange_pb.DerivativeOrder]],
    ) -> List[Union[injective_exchange_pb.SpotOrder, injective_exchange_pb.DerivativeOrder]]:
        return [
            order
            for order in orders
            if order.order_type in [injective_exchange_pb.OrderType.BUY_PO, injective_exchange_pb.OrderType.SELL_PO]
        ]


class DefaultGasLimitEstimator(GasLimitEstimator):
    DEFAULT_GAS_LIMIT = 150_000

    @classmethod
    def applies_to(cls, message: any_pb2.Any) -> bool:
        return False

    def gas_limit(self) -> int:
        return self.DEFAULT_GAS_LIMIT

    def _message_class(self, message: any_pb2.Any):
        # This class should not try to convert messages
        raise NotImplementedError


class BatchCreateSpotLimitOrdersGasLimitEstimator(GasLimitEstimator):
    def __init__(self, message: any_pb2.Any):
        self._message = self._parsed_message(message=message)

    @classmethod
    def applies_to(cls, message: any_pb2.Any):
        return cls.message_type(message=message).endswith("MsgBatchCreateSpotLimitOrders")

    def gas_limit(self) -> int:
        post_only_orders = self._select_post_only_orders(orders=self._message.orders)

        total = 0
        total += self.GENERAL_MESSAGE_GAS_LIMIT
        total += len(self._message.orders) * SPOT_ORDER_CREATION_GAS_LIMIT
        total += math.ceil(len(post_only_orders) * SPOT_ORDER_CREATION_GAS_LIMIT * SPOT_POST_ONLY_ORDER_MULTIPLIER)

        return total

    def _message_class(self, message: any_pb2.Any):
        return injective_exchange_tx_pb.MsgBatchCreateSpotLimitOrders


class BatchCancelSpotOrdersGasLimitEstimator(GasLimitEstimator):
    def __init__(self, message: any_pb2.Any):
        self._message = self._parsed_message(message=message)

    @classmethod
    def applies_to(cls, message: any_pb2.Any):
        return cls.message_type(message=message).endswith("MsgBatchCancelSpotOrders")

    def gas_limit(self) -> int:
        total = 0
        total += self.GENERAL_MESSAGE_GAS_LIMIT
        total += len(self._message.data) * SPOT_ORDER_CANCELATION_GAS_LIMIT

        return total

    def _message_class(self, message: any_pb2.Any):
        return injective_exchange_tx_pb.MsgBatchCancelSpotOrders


class BatchCreateDerivativeLimitOrdersGasLimitEstimator(GasLimitEstimator):
    def __init__(self, message: any_pb2.Any):
        self._message = self._parsed_message(message=message)

    @classmethod
    def applies_to(cls, message: any_pb2.Any):
        return cls.message_type(message=message).endswith("MsgBatchCreateDerivativeLimitOrders")

    def gas_limit(self) -> int:
        post_only_orders = self._select_post_only_orders(orders=self._message.orders)

        total = 0
        total += self.GENERAL_MESSAGE_GAS_LIMIT
        total += len(self._message.orders) * DERIVATIVE_ORDER_CREATION_GAS_LIMIT
        total += math.ceil(
            len(post_only_orders) * DERIVATIVE_ORDER_CREATION_GAS_LIMIT * DERIVATIVE_POST_ONLY_ORDER_MULTIPLIER
        )

        return total

    def _message_class(self, message: any_pb2.Any):
        return injective_exchange_tx_pb.MsgBatchCreateDerivativeLimitOrders


class BatchCancelDerivativeOrdersGasLimitEstimator(GasLimitEstimator):
    def __init__(self, message: any_pb2.Any):
        self._message = self._parsed_message(message=message)

    @classmethod
    def applies_to(cls, message: any_pb2.Any):
        return cls.message_type(message=message).endswith("MsgBatchCancelDerivativeOrders")

    def gas_limit(self) -> int:
        total = 0
        total += self.GENERAL_MESSAGE_GAS_LIMIT
        total += len(self._message.data) * DERIVATIVE_ORDER_CANCELATION_GAS_LIMIT

        return total

    def _message_class(self, message: any_pb2.Any):
        return injective_exchange_tx_pb.MsgBatchCancelDerivativeOrders


class BatchUpdateOrdersGasLimitEstimator(GasLimitEstimator):
    CANCEL_ALL_SPOT_MARKET_GAS_LIMIT = 40_000
    CANCEL_ALL_DERIVATIVE_MARKET_GAS_LIMIT = 50_000
    MESSAGE_GAS_LIMIT = 30_000

    AVERAGE_CANCEL_ALL_AFFECTED_ORDERS = 20

    def __init__(self, message: any_pb2.Any):
        self._message = self._parsed_message(message=message)

    @classmethod
    def applies_to(cls, message: any_pb2.Any):
        return cls.message_type(message=message).endswith("MsgBatchUpdateOrders")

    def gas_limit(self) -> int:
        post_only_spot_orders = self._select_post_only_orders(orders=self._message.spot_orders_to_create)
        post_only_derivative_orders = self._select_post_only_orders(orders=self._message.derivative_orders_to_create)
        post_only_binary_options_orders = self._select_post_only_orders(
            orders=self._message.binary_options_orders_to_create
        )

        total = 0
        total += self.MESSAGE_GAS_LIMIT
        total += len(self._message.spot_orders_to_create) * SPOT_ORDER_CREATION_GAS_LIMIT
        total += len(self._message.derivative_orders_to_create) * DERIVATIVE_ORDER_CREATION_GAS_LIMIT
        total += len(self._message.binary_options_orders_to_create) * DERIVATIVE_ORDER_CREATION_GAS_LIMIT

        total += math.ceil(len(post_only_spot_orders) * SPOT_ORDER_CREATION_GAS_LIMIT * SPOT_POST_ONLY_ORDER_MULTIPLIER)
        total += math.ceil(
            len(post_only_derivative_orders)
            * DERIVATIVE_ORDER_CREATION_GAS_LIMIT
            * DERIVATIVE_POST_ONLY_ORDER_MULTIPLIER
        )
        total += math.ceil(
            len(post_only_binary_options_orders)
            * DERIVATIVE_ORDER_CREATION_GAS_LIMIT
            * DERIVATIVE_POST_ONLY_ORDER_MULTIPLIER
        )

        total += len(self._message.spot_orders_to_cancel) * SPOT_ORDER_CANCELATION_GAS_LIMIT
        total += len(self._message.derivative_orders_to_cancel) * DERIVATIVE_ORDER_CANCELATION_GAS_LIMIT
        total += len(self._message.binary_options_orders_to_cancel) * DERIVATIVE_ORDER_CANCELATION_GAS_LIMIT

        total += (
            len(self._message.spot_market_ids_to_cancel_all)
            * self.CANCEL_ALL_SPOT_MARKET_GAS_LIMIT
            * self.AVERAGE_CANCEL_ALL_AFFECTED_ORDERS
        )
        total += (
            len(self._message.derivative_market_ids_to_cancel_all)
            * self.CANCEL_ALL_DERIVATIVE_MARKET_GAS_LIMIT
            * self.AVERAGE_CANCEL_ALL_AFFECTED_ORDERS
        )
        total += (
            len(self._message.binary_options_market_ids_to_cancel_all)
            * self.CANCEL_ALL_DERIVATIVE_MARKET_GAS_LIMIT
            * self.AVERAGE_CANCEL_ALL_AFFECTED_ORDERS
        )

        return total

    def _message_class(self, message: any_pb2.Any):
        return injective_exchange_tx_pb.MsgBatchUpdateOrders


class ExecGasLimitEstimator(GasLimitEstimator):
    DEFAULT_GAS_LIMIT = 20_000

    def __init__(self, message: any_pb2.Any):
        self._message = self._parsed_message(message=message)

    @classmethod
    def applies_to(cls, message: any_pb2.Any) -> bool:
        return cls.message_type(message=message).endswith("MsgExec")

    def gas_limit(self) -> int:
        total = sum(
            [GasLimitEstimator.for_message(message=inner_message).gas_limit() for inner_message in self._message.msgs]
        )
        total += self.DEFAULT_GAS_LIMIT

        return total

    def _message_class(self, message: any_pb2.Any):
        return cosmos_authz_tx_pb.MsgExec


class PrivilegedExecuteContractGasLimitEstimator(GasLimitEstimator):
    def __init__(self, message: any_pb2.Any):
        self._message = self._parsed_message(message=message)

    @classmethod
    def applies_to(cls, message: any_pb2.Any) -> bool:
        return cls.message_type(message=message).endswith("MsgPrivilegedExecuteContract")

    def gas_limit(self) -> int:
        return self.BASIC_REFERENCE_GAS_LIMIT * 6

    def _message_class(self, message: any_pb2.Any):
        return injective_exchange_tx_pb.MsgPrivilegedExecuteContract


class ExecuteContractGasLimitEstimator(GasLimitEstimator):
    def __init__(self, message: any_pb2.Any):
        self._message = self._parsed_message(message=message)

    @classmethod
    def applies_to(cls, message: any_pb2.Any) -> bool:
        return cls.message_type(message=message).endswith("MsgExecuteContract")

    def gas_limit(self) -> int:
        return int(self.BASIC_REFERENCE_GAS_LIMIT * 2.5)

    def _message_class(self, message: any_pb2.Any):
        return wasm_tx_pb.MsgExecuteContract


class GeneralWasmGasLimitEstimator(GasLimitEstimator):
    def __init__(self, message: any_pb2.Any):
        self._message = self._parsed_message(message=message)

    @classmethod
    def applies_to(cls, message: any_pb2.Any) -> bool:
        return "wasm." in cls.message_type(message=message)

    def gas_limit(self) -> int:
        return int(self.BASIC_REFERENCE_GAS_LIMIT * 1.5)

    def _message_class(self, message: any_pb2.Any):
        return wasm_tx_pb.MsgInstantiateContract2


class GovernanceGasLimitEstimator(GasLimitEstimator):
    def __init__(self, message: any_pb2.Any):
        self._message = self._parsed_message(message=message)

    @classmethod
    def applies_to(cls, message: any_pb2.Any) -> bool:
        message_type = cls.message_type(message=message)
        return "gov." in message_type and (
            message_type.endswith("MsgDeposit") or message_type.endswith("MsgSubmitProposal")
        )

    def gas_limit(self) -> int:
        return int(self.BASIC_REFERENCE_GAS_LIMIT * 15)

    def _message_class(self, message: any_pb2.Any):
        if "MsgDeposit" in self.message_type(message=message):
            message_class = gov_tx_pb.MsgDeposit
        else:
            message_class = gov_tx_pb.MsgSubmitProposal
        return message_class


class GenericExchangeGasLimitEstimator(GasLimitEstimator):
    BASIC_REFERENCE_GAS_LIMIT = 120_000

    def __init__(self, message: any_pb2.Any):
        self._message = message

    @classmethod
    def applies_to(cls, message: any_pb2.Any) -> bool:
        message_type = cls.message_type(message=message)
        return "exchange." in message_type

    def gas_limit(self) -> int:
        return self.BASIC_REFERENCE_GAS_LIMIT

    def _message_class(self, message: any_pb2.Any):
        # This class applies to many different messages, but we don't need to transform from Any format
        raise NotImplementedError
