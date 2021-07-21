from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Dict

import hummingbot.connector.exchange.ndax.ndax_constants as CONSTANTS


class NdaxMessagePayload(ABC):

    @classmethod
    def _all_subclasses(cls):
        for subclass in cls.__subclasses__():
            yield from subclass._all_subclasses()
            if not subclass == NdaxMessagePayload:
                yield subclass

    @classmethod
    @abstractmethod
    def applies_to(cls, endpoint: str) -> bool:
        raise NotImplementedError

    @classmethod
    def _payload_class_for_endpoint(cls, endpoint: str):
        payload_class = next((subclass for subclass in cls._all_subclasses()
                              if subclass.applies_to(endpoint)), NdaxUnknownMessagePayload)
        return payload_class

    @classmethod
    @abstractmethod
    def _new_from_payload(cls, endpoint: str, payload: Dict[str, Any]):
        raise NotImplementedError

    @classmethod
    def new_instance(cls, endpoint: str, payload: Dict[str, Any]):
        payload_class = cls._payload_class_for_endpoint(endpoint)
        return payload_class._new_from_payload(endpoint=endpoint, payload=payload)


class NdaxUnknownMessagePayload(NdaxMessagePayload):

    def __init__(self, endpoint: str, payload: Dict[str, Any]):
        super().__init__()
        self._endpoint = endpoint
        self._payload = payload

    @classmethod
    def applies_to(cls, endpoint: str) -> bool:
        return False

    @classmethod
    def _new_from_payload(cls, endpoint: str, payload: Dict[str, Any]):
        return cls(endpoint=endpoint, payload=payload)

    @property
    def endpoint(self):
        return self._endpoint

    @property
    def payload(self):
        return self._payload


class NdaxAccountPositionEventPayload(NdaxMessagePayload):
    _oms_id_field_name = "OMSId"
    _account_id_field_name = "AccountId"
    _product_symbol_field_name = "ProductSymbol"
    _product_id_field_name = "ProductId"
    _amount_field_name = "Amount"
    _hold_field_name = "Hold"
    _pending_deposits_field_name = "PendingDeposits"
    _pending_withdraws_field_name = "PendingWithdraws"
    _total_day_deposits_field_name = "TotalDayDeposits"
    _total_day_withdraws_field_name = "TotalDayWithdraws"

    def __init__(self,
                 oms_id: int,
                 account_id: int,
                 product_symbol: str,
                 product_id: int,
                 amount: float,
                 on_hold: float,
                 pending_deposits: float,
                 pending_withdraws: float,
                 total_day_deposits: float,
                 total_day_withdraws: float):
        super().__init__()
        self._oms_id = oms_id
        self._account_id = account_id
        self._product_symbol = product_symbol
        self._product_id = product_id
        self._amount = Decimal(str(amount))
        self._on_hold = Decimal(str(on_hold))
        self._pending_deposits = Decimal(str(pending_deposits))
        self._pending_withdraws = Decimal(str(pending_withdraws))
        self._total_day_deposits = Decimal(str(total_day_deposits))
        self._total_day_withdraws = Decimal(str(total_day_withdraws))

    @classmethod
    def endpoint_name(cls):
        return CONSTANTS.ACCOUNT_POSITION_EVENT_ENDPOINT_NAME

    @classmethod
    def applies_to(cls, endpoint: str) -> bool:
        return endpoint == cls.endpoint_name()

    @classmethod
    def _new_from_payload(cls, endpoint: str, payload: Dict[str, Any]):
        return cls(oms_id=payload[cls._oms_id_field_name],
                   account_id=payload[cls._account_id_field_name],
                   product_symbol=payload[cls._product_symbol_field_name],
                   product_id=payload[cls._product_id_field_name],
                   amount=payload[cls._amount_field_name],
                   on_hold=payload[cls._hold_field_name],
                   pending_deposits=payload[cls._pending_deposits_field_name],
                   pending_withdraws=payload[cls._pending_withdraws_field_name],
                   total_day_deposits=payload[cls._total_day_deposits_field_name],
                   total_day_withdraws=payload[cls._total_day_withdraws_field_name])

    @property
    def oms_id(self):
        return self._oms_id

    @property
    def account_id(self):
        return self._account_id

    @property
    def product_symbol(self):
        return self._product_symbol

    @property
    def product_id(self):
        return self._product_id

    @property
    def amount(self):
        return self._amount

    @property
    def on_hold(self):
        return self._on_hold

    @property
    def pending_deposits(self):
        return self._pending_deposits

    @property
    def pending_withdraws(self):
        return self._pending_withdraws

    @property
    def total_day_deposits(self):
        return self._total_day_deposits

    @property
    def total_day_withdraws(self):
        return self._total_day_withdraws

    def process_event(self, connector):
        connector.process_account_position_event(self)
