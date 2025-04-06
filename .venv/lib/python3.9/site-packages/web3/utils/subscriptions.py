from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    List,
    Optional,
    Sequence,
    TypeVar,
    Union,
)

from eth_typing import (
    Address,
    ChecksumAddress,
    HexStr,
)
from hexbytes import (
    HexBytes,
)

from web3.exceptions import (
    Web3AttributeError,
    Web3ValueError,
)
from web3.types import (
    BlockData,
    FilterParams,
    LogReceipt,
    SyncProgress,
    TxData,
)

if TYPE_CHECKING:
    from web3 import (
        AsyncWeb3,
    )
    from web3.providers.persistent.subscription_manager import (
        SubscriptionManager,
    )
    from web3.types import EthSubscriptionResult  # noqa: F401


TSubscriptionResult = TypeVar("TSubscriptionResult", bound="EthSubscriptionResult")
TSubscription = TypeVar("TSubscription", bound="EthSubscription[Any]")


class EthSubscriptionContext(Generic[TSubscription, TSubscriptionResult]):
    def __init__(
        self,
        async_w3: "AsyncWeb3",
        subscription: TSubscription,
        result: TSubscriptionResult,
        **kwargs: Any,
    ) -> None:
        self.async_w3 = async_w3
        self.subscription = subscription
        self.result = result
        self.__dict__.update(kwargs)

    def __getattr__(self, item: str) -> Any:
        if item in self.__dict__:
            return self.__dict__[item]
        raise Web3AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{item}'"
        )


EthSubscriptionHandler = Callable[
    [EthSubscriptionContext[Any, Any]], Coroutine[Any, Any, None]
]


def handler_wrapper(
    handler: Optional[EthSubscriptionHandler],
) -> Optional[EthSubscriptionHandler]:
    """Wrap the handler to add bookkeeping and context creation."""
    if handler is None:
        return None

    async def wrapped_handler(
        context: EthSubscriptionContext[TSubscription, TSubscriptionResult],
    ) -> None:
        sub = context.subscription
        sub.handler_call_count += 1
        sub.manager.total_handler_calls += 1
        sub.manager.logger.debug(
            f"Subscription handler called.\n"
            f"    label: {sub.label}\n"
            f"    call count: {sub.handler_call_count}\n"
            f"    total handler calls: {sub.manager.total_handler_calls}"
        )
        await handler(context)

    return wrapped_handler


class EthSubscription(Generic[TSubscriptionResult]):
    _id: HexStr = None
    manager: "SubscriptionManager" = None

    def __init__(
        self: TSubscription,
        subscription_params: Optional[Sequence[Any]] = None,
        handler: Optional[EthSubscriptionHandler] = None,
        handler_context: Optional[Dict[str, Any]] = None,
        label: Optional[str] = None,
    ) -> None:
        self._subscription_params = subscription_params
        self._handler = handler_wrapper(handler)
        self._handler_context = handler_context or {}
        self._label = label
        self.handler_call_count = 0

    @property
    def _default_label(self) -> str:
        return f"{self.__class__.__name__}{self.subscription_params}"

    @classmethod
    def _create_type_aware_subscription(
        cls,
        subscription_params: Optional[Sequence[Any]],
        handler: Optional[EthSubscriptionHandler] = None,
        handler_context: Optional[Dict[str, Any]] = None,
        label: Optional[str] = None,
    ) -> "EthSubscription[Any]":
        subscription_type = subscription_params[0]
        subscription_arg = (
            subscription_params[1] if len(subscription_params) > 1 else None
        )
        if subscription_type == "newHeads":
            return NewHeadsSubscription(
                handler=handler, handler_context=handler_context, label=label
            )
        elif subscription_type == "logs":
            subscription_arg = subscription_arg or {}
            return LogsSubscription(
                **subscription_arg,
                handler=handler,
                handler_context=handler_context,
                label=label,
            )
        elif subscription_type == "newPendingTransactions":
            subscription_arg = subscription_arg or False
            return PendingTxSubscription(
                full_transactions=subscription_arg,
                handler=handler,
                handler_context=handler_context,
                label=label,
            )
        elif subscription_type == "syncing":
            return SyncingSubscription(
                handler=handler, handler_context=handler_context, label=label
            )
        else:
            params = (
                (subscription_type, subscription_arg)
                if subscription_arg
                else (subscription_type,)
            )
            return cls(
                params,
                handler=handler,
                handler_context=handler_context,
                label=label,
            )

    @property
    def subscription_params(self) -> Sequence[Any]:
        return self._subscription_params

    @property
    def label(self) -> str:
        if not self._label:
            self._label = self._default_label
        return self._label

    @property
    def id(self) -> HexStr:
        if not self._id:
            raise Web3ValueError("No `id` found for subscription.")
        return self._id

    async def unsubscribe(self) -> bool:
        return await self.manager.unsubscribe(self)


LogsSubscriptionContext = EthSubscriptionContext[
    "LogsSubscription", "EthSubscriptionResult"
]
LogsSubscriptionHandler = Callable[[LogsSubscriptionContext], Coroutine[Any, Any, None]]


class LogsSubscription(EthSubscription[LogReceipt]):
    def __init__(
        self,
        address: Optional[
            Union[Address, ChecksumAddress, List[Address], List[ChecksumAddress]]
        ] = None,
        topics: Optional[List[HexStr]] = None,
        handler: LogsSubscriptionHandler = None,
        handler_context: Optional[Dict[str, Any]] = None,
        label: Optional[str] = None,
    ) -> None:
        self.address = address
        self.topics = topics

        logs_filter: FilterParams = {}
        if address:
            logs_filter["address"] = address
        if topics:
            logs_filter["topics"] = topics
        self.logs_filter = logs_filter

        super().__init__(
            subscription_params=("logs", logs_filter),
            handler=handler,
            handler_context=handler_context,
            label=label,
        )


NewHeadsSubscriptionContext = EthSubscriptionContext["NewHeadsSubscription", BlockData]
NewHeadsSubscriptionHandler = Callable[
    [NewHeadsSubscriptionContext], Coroutine[Any, Any, None]
]


class NewHeadsSubscription(EthSubscription[BlockData]):
    def __init__(
        self,
        label: Optional[str] = None,
        handler: Optional[NewHeadsSubscriptionHandler] = None,
        handler_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            subscription_params=("newHeads",),
            handler=handler,
            handler_context=handler_context,
            label=label,
        )


PendingTxSubscriptionContext = EthSubscriptionContext[
    "PendingTxSubscription", Union[HexBytes, TxData]
]
PendingTxSubscriptionHandler = Callable[
    [PendingTxSubscriptionContext], Coroutine[Any, Any, None]
]


class PendingTxSubscription(EthSubscription[Union[HexBytes, TxData]]):
    def __init__(
        self,
        full_transactions: bool = False,
        label: Optional[str] = None,
        handler: Optional[PendingTxSubscriptionHandler] = None,
        handler_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.full_transactions = full_transactions
        super().__init__(
            subscription_params=("newPendingTransactions", full_transactions),
            handler=handler,
            handler_context=handler_context,
            label=label,
        )


SyncingSubscriptionContext = EthSubscriptionContext["SyncingSubscription", SyncProgress]
SyncingSubscriptionHandler = Callable[
    [SyncingSubscriptionContext], Coroutine[Any, Any, None]
]


class SyncingSubscription(EthSubscription[SyncProgress]):
    def __init__(
        self,
        label: Optional[str] = None,
        handler: Optional[SyncingSubscriptionHandler] = None,
        handler_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            subscription_params=("syncing",),
            handler=handler,
            handler_context=handler_context,
            label=label,
        )
