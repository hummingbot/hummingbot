from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Literal, Optional

from hummingbot.connector.exchange.twofinance import twofinance_constants as CONSTANTS

OrderSide = Literal["BUY", "SELL"]
MatchEngineOrderType = Literal["MARKET", "LIMIT", "STOP", "STOP_LIMIT"]
TimeInForce = Literal["GTC", "IOC", "FOK", "AON"]
CommandOperation = Literal["ADD", "DELETE", "REPLACE", "MODIFY"]


class CommandStatus(str, Enum):
    ACCEPTED_TO_QUEUE = "accepted-to-queue"
    REJECTED_BY_PARSER = "rejected-by-parser"
    REJECTED_BY_RISK = "rejected-by-risk"
    DUPLICATE = "duplicate"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class OrderCommand:
    client_order_id: str
    engine_id: str
    symbol_id: int
    market: str
    wallet_id: int
    side: OrderSide
    order_type: MatchEngineOrderType
    quantity: Decimal | str
    price: Decimal | str | None = None
    time_in_force: TimeInForce | None = None
    idempotency_key: str | None = None
    operation: CommandOperation = "ADD"
    order_id: int | str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": CONSTANTS.MATCHENGINE_ORDER_COMMAND_SCHEMA,
            "message_type": "ORDER",
            "operation": self.operation,
            "client_order_id": self.client_order_id,
            "idempotency_key": self.idempotency_key or self.client_order_id,
            "engine_id": self.engine_id,
            "market": self.market,
            "wallet_id": self.wallet_id,
            "symbol_id": self.symbol_id,
        }
        if self.operation == "ADD":
            payload.update(
                {
                    "side": self.side,
                    "order_type": self.order_type,
                    "quantity": decimal_to_str(self.quantity),
                }
            )
            if self.price is not None:
                payload["price"] = decimal_to_str(self.price)
            if self.time_in_force is not None:
                payload["time_in_force"] = self.time_in_force
        elif self.operation == "DELETE":
            payload["order_id"] = require_order_id(self.order_id)
        elif self.operation in {"REPLACE", "MODIFY"}:
            payload["order_id"] = require_order_id(self.order_id)
            payload["quantity"] = decimal_to_str(self.quantity)
            if self.price is not None:
                payload["price"] = decimal_to_str(self.price)
        return payload


@dataclass(frozen=True)
class CommandResponse:
    status: CommandStatus
    client_order_id: str | None = None
    order_id: str | None = None
    reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.status in {CommandStatus.ACCEPTED_TO_QUEUE, CommandStatus.DUPLICATE}


@dataclass(frozen=True)
class MatchEngineEvent:
    event_type: str
    sequence: int
    event_id: str
    symbol_id: int | None = None
    market: str | None = None
    timestamp_ns: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    schema: str = CONSTANTS.MATCHENGINE_EVENT_SCHEMA
    engine_id: str | None = None

    @classmethod
    def from_payload(cls, data: dict[str, Any]) -> "MatchEngineEvent":
        payload = data.get("payload")
        if not isinstance(payload, dict):
            payload = {
                key: value
                for key, value in data.items()
                if key
                not in {
                    "schema",
                    "engine_id",
                    "sequence",
                    "event_id",
                    "event_type",
                    "symbol_id",
                    "market",
                    "timestamp_ns",
                }
            }
        return cls(
            schema=str(data.get("schema", CONSTANTS.MATCHENGINE_EVENT_SCHEMA)),
            engine_id=optional_str(data.get("engine_id")),
            sequence=int(data.get("sequence", 0)),
            event_id=str(data.get("event_id") or data.get("sequence") or ""),
            event_type=str(data.get("event_type") or data.get("type") or ""),
            symbol_id=optional_int(data.get("symbol_id")),
            market=optional_str(data.get("market")),
            timestamp_ns=optional_int(data.get("timestamp_ns")),
            payload=payload,
        )


def parse_command_response(data: dict[str, Any]) -> CommandResponse:
    message_type = str(data.get("message_type") or data.get("MessageType") or data.get("type") or "").upper()
    status_value = str(data.get("status") or data.get("Status") or "").lower().replace("_", "-")
    error_code = data.get("error_code") if data.get("error_code") is not None else data.get("ErrorCode")
    if error_code is None:
        error_code = data.get("reason_code")
    error_code_value = str(error_code or "")
    if message_type in {"ACK", "12"} and status_value not in {"timeout", "unavailable"}:
        status = CommandStatus.ACCEPTED_TO_QUEUE
    elif message_type == "REJECT":
        status = CommandStatus.REJECTED_BY_PARSER
    elif status_value in {"ok", "accepted", "accepted-to-queue", "queued"} or error_code_value in {"OK", "0"}:
        status = CommandStatus.ACCEPTED_TO_QUEUE
    elif status_value == "duplicate" or error_code_value == "ORDER_DUPLICATE":
        status = CommandStatus.DUPLICATE
    elif status_value in {"timeout", "unavailable"}:
        status = CommandStatus.UNAVAILABLE
    elif error_code_value in {"BALANCE_INSUFICIENT", "WALLET_NOT_FOUND"} or status_value.startswith("rejected-by-risk"):
        status = CommandStatus.REJECTED_BY_RISK
    elif status_value.startswith("rejected") or (error_code_value and error_code_value != "0"):
        status = CommandStatus.REJECTED_BY_PARSER
    else:
        status = CommandStatus.UNKNOWN
    return CommandResponse(
        status=status,
        client_order_id=optional_str(data.get("client_order_id") or data.get("ClientOrderId")),
        order_id=optional_str(data.get("order_id") or data.get("OrderId")),
        reason=optional_str(data.get("reason") or data.get("reason_code") or data.get("message") or data.get("Message") or error_code_value),
        raw=data,
    )


def is_command_response(payload: dict[str, Any]) -> bool:
    message_type = str(payload.get("message_type") or payload.get("MessageType") or payload.get("type") or "").upper()
    return message_type in {"ACK", "ERROR", "REJECT", "12", "15"} or "error_code" in payload or "ErrorCode" in payload


def event_order_state(event: MatchEngineEvent):
    state = {
        "ORDER_ACCEPTED": CONSTANTS.ORDER_STATE["OPEN"],
        "ORDER_UPDATED": CONSTANTS.ORDER_STATE["OPEN"],
        "ORDER_MODIFIED": CONSTANTS.ORDER_STATE["OPEN"],
        "ORDER_REPLACED": CONSTANTS.ORDER_STATE["OPEN"],
        "ORDER_EXECUTED": CONSTANTS.ORDER_STATE["PARTIALLY_FILLED"],
        "ORDER_CANCELED": CONSTANTS.ORDER_STATE["CANCELED"],
        "ORDER_REJECTED": CONSTANTS.ORDER_STATE["REJECTED"],
    }.get(event.event_type)
    raw_status = event.payload.get("order_status") or event.payload.get("status")
    if raw_status is not None:
        if isinstance(raw_status, int):
            state = {
                0: CONSTANTS.ORDER_STATE["CANCELED"],
                1: CONSTANTS.ORDER_STATE["OPEN"],
                2: CONSTANTS.ORDER_STATE["FILLED"],
                3: CONSTANTS.ORDER_STATE["PARTIALLY_FILLED"],
            }.get(raw_status, state)
        else:
            state = CONSTANTS.ORDER_STATE.get(str(raw_status).upper(), state)
    return state


def decimal_to_str(value: Decimal | str) -> str:
    return format(to_decimal(value), "f")


def to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    return int(value)


def optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def require_order_id(value: int | str | None) -> int | str:
    if value is None:
        raise ValueError("order_id is required")
    return value
