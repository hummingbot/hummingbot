import asyncio
import logging
from typing import (
    TYPE_CHECKING,
    Any,
    List,
    Sequence,
    Union,
    cast,
    overload,
)

from eth_typing import (
    HexStr,
)

from web3.exceptions import (
    SubscriptionProcessingFinished,
    TaskNotRunning,
    Web3TypeError,
    Web3ValueError,
)
from web3.providers.persistent.subscription_container import (
    SubscriptionContainer,
)
from web3.types import (
    FormattedEthSubscriptionResponse,
    RPCResponse,
)
from web3.utils.subscriptions import (
    EthSubscription,
    EthSubscriptionContext,
)

if TYPE_CHECKING:
    from web3 import AsyncWeb3  # noqa: F401
    from web3.providers.persistent import (  # noqa: F401
        PersistentConnectionProvider,
        RequestProcessor,
    )


class SubscriptionManager:
    """
    The ``SubscriptionManager`` is responsible for subscribing, unsubscribing, and
    managing all active subscriptions for an ``AsyncWeb3`` instance. It is also
    used for processing all subscriptions that have handler functions.
    """

    logger: logging.Logger = logging.getLogger(
        "web3.providers.persistent.subscription_manager"
    )
    total_handler_calls: int = 0

    def __init__(self, w3: "AsyncWeb3") -> None:
        self._w3 = w3
        self._provider = cast("PersistentConnectionProvider", w3.provider)
        self._subscription_container = SubscriptionContainer()

        # share the subscription container with the request processor so it can separate
        # subscriptions into different queues based on ``sub._handler`` presence
        self._provider._request_processor._subscription_container = (
            self._subscription_container
        )

    def _add_subscription(self, subscription: EthSubscription[Any]) -> None:
        self._subscription_container.add_subscription(subscription)

    def _remove_subscription(self, subscription: EthSubscription[Any]) -> None:
        self._subscription_container.remove_subscription(subscription)

    def _validate_and_normalize_label(self, subscription: EthSubscription[Any]) -> None:
        if subscription.label == subscription._default_label:
            # if no custom label was provided, generate a unique label
            i = 2
            while self.get_by_label(subscription._label) is not None:
                subscription._label = f"{subscription._default_label}#{i}"
                i += 1
        else:
            if (
                subscription._label
                in self._subscription_container.subscriptions_by_label
            ):
                raise Web3ValueError(
                    "Subscription label already exists. Subscriptions must have unique "
                    f"labels.\n    label: {subscription._label}"
                )

    @property
    def subscriptions(self) -> List[EthSubscription[Any]]:
        return self._subscription_container.subscriptions

    def get_by_id(self, sub_id: HexStr) -> EthSubscription[Any]:
        return self._subscription_container.get_by_id(sub_id)

    def get_by_label(self, label: str) -> EthSubscription[Any]:
        return self._subscription_container.get_by_label(label)

    @overload
    async def subscribe(self, subscriptions: EthSubscription[Any]) -> HexStr:
        ...

    @overload
    async def subscribe(
        self, subscriptions: Sequence[EthSubscription[Any]]
    ) -> List[HexStr]:
        ...

    async def subscribe(
        self, subscriptions: Union[EthSubscription[Any], Sequence[EthSubscription[Any]]]
    ) -> Union[HexStr, List[HexStr]]:
        """
        Used to subscribe to a single or multiple subscriptions.

        :param subscriptions: A single subscription or a sequence of subscriptions.
        :type subscriptions: Union[EthSubscription, Sequence[EthSubscription]]
        :return:
        """
        if isinstance(subscriptions, EthSubscription):
            subscriptions.manager = self
            self._validate_and_normalize_label(subscriptions)
            sub_id = await self._w3.eth._subscribe(*subscriptions.subscription_params)
            subscriptions._id = sub_id
            self._add_subscription(subscriptions)
            self.logger.info(
                "Successfully subscribed to subscription:\n    "
                f"label: {subscriptions.label}\n    id: {sub_id}"
            )
            return sub_id
        elif isinstance(subscriptions, Sequence):
            if len(subscriptions) == 0:
                raise Web3ValueError("No subscriptions provided.")

            sub_ids: List[HexStr] = []
            for sub in subscriptions:
                sub_ids.append(await self.subscribe(sub))
            return sub_ids
        raise Web3TypeError("Expected a Subscription or a sequence of Subscriptions.")

    @overload
    async def unsubscribe(self, subscriptions: EthSubscription[Any]) -> bool:
        ...

    @overload
    async def unsubscribe(self, subscriptions: HexStr) -> bool:
        ...

    @overload
    async def unsubscribe(
        self,
        subscriptions: Sequence[Union[EthSubscription[Any], HexStr]],
    ) -> bool:
        ...

    async def unsubscribe(
        self,
        subscriptions: Union[
            EthSubscription[Any],
            HexStr,
            Sequence[Union[EthSubscription[Any], HexStr]],
        ],
    ) -> bool:
        """
        Used to unsubscribe from one or multiple subscriptions.

        :param subscriptions: The subscription(s) to unsubscribe from.
        :type subscriptions: Union[EthSubscription, Sequence[EthSubscription], HexStr,
            Sequence[HexStr]]
        :return: ``True`` if unsubscribing to all was successful, ``False`` otherwise
            with a warning.
        :rtype: bool
        """
        if isinstance(subscriptions, EthSubscription) or isinstance(subscriptions, str):
            if isinstance(subscriptions, str):
                subscription_id = subscriptions
                subscriptions = self.get_by_id(subscription_id)
                if subscriptions is None:
                    raise Web3ValueError(
                        "Subscription not found or is not being managed by the "
                        f"subscription manager.\n    id: {subscription_id}"
                    )

            if subscriptions not in self.subscriptions:
                raise Web3ValueError(
                    "Subscription not found or is not being managed by the "
                    "subscription manager.\n    "
                    f"label: {subscriptions.label}\n    id: {subscriptions._id}"
                )

            if await self._w3.eth._unsubscribe(subscriptions.id):
                self._remove_subscription(subscriptions)
                self.logger.info(
                    "Successfully unsubscribed from subscription:\n    "
                    f"label: {subscriptions.label}\n    id: {subscriptions.id}"
                )

                if len(self._subscription_container.handler_subscriptions) == 0:
                    queue = (
                        self._provider._request_processor._handler_subscription_queue
                    )
                    await queue.put(SubscriptionProcessingFinished())
                return True

        elif isinstance(subscriptions, Sequence):
            if len(subscriptions) == 0:
                raise Web3ValueError("No subscriptions provided.")

            unsubscribed: List[bool] = []
            # re-create the subscription list to prevent modifying the original list
            # in case ``subscription_manager.subscriptions`` was passed in directly
            subs = [sub for sub in subscriptions]
            for sub in subs:
                if isinstance(sub, str):
                    sub = HexStr(sub)
                unsubscribed.append(await self.unsubscribe(sub))
            return all(unsubscribed)

        self.logger.warning(
            f"Failed to unsubscribe from subscription\n    subscription={subscriptions}"
        )
        return False

    async def unsubscribe_all(self) -> bool:
        """
        Used to unsubscribe from all subscriptions that are being managed by the
        subscription manager.

        :return: ``True`` if unsubscribing was successful, ``False`` otherwise.
        :rtype: bool
        """
        unsubscribed = [
            await self.unsubscribe(sub)
            # use copy to prevent modifying the list while iterating over it
            for sub in self.subscriptions.copy()
        ]
        if all(unsubscribed):
            self.logger.info("Successfully unsubscribed from all subscriptions.")
            return True
        else:
            if len(self.subscriptions) > 0:
                self.logger.warning(
                    "Failed to unsubscribe from all subscriptions. Some subscriptions "
                    f"are still active.\n    subscriptions={self.subscriptions}"
                )
            return False

    async def handle_subscriptions(self, run_forever: bool = False) -> None:
        """
        Used to handle all subscriptions that have handlers. The method will run until
        all subscriptions that have handler functions are unsubscribed from or, if
        ``run_forever`` is set to ``True``, it will run indefinitely.

        :param run_forever: If ``True``, the method will run indefinitely.
        :type run_forever: bool
        :return: None
        """
        if not self._subscription_container.handler_subscriptions and not run_forever:
            self.logger.warning(
                "No handler subscriptions found. Subscription handler did not run."
            )
            return

        queue = self._provider._request_processor._handler_subscription_queue
        while run_forever or self._subscription_container.handler_subscriptions:
            try:
                response = cast(RPCResponse, await queue.get())
                formatted_sub_response = cast(
                    FormattedEthSubscriptionResponse,
                    await self._w3.manager._process_response(response),
                )

                # if the subscription was unsubscribed from, the response won't be
                # formatted because we lost the request information
                sub_id = formatted_sub_response.get("subscription")
                sub = self._subscription_container.get_handler_subscription_by_id(
                    sub_id
                )
                if sub:
                    await sub._handler(
                        EthSubscriptionContext(
                            self._w3,
                            sub,
                            formatted_sub_response["result"],
                            **sub._handler_context,
                        )
                    )
            except SubscriptionProcessingFinished:
                if not run_forever:
                    self.logger.info(
                        "All handler subscriptions have been unsubscribed from. "
                        "Stopping subscription handling."
                    )
                    break
            except TaskNotRunning:
                await asyncio.sleep(0)
                self._provider._handle_listener_task_exceptions()
                self.logger.error(
                    "Message listener background task for the provider has stopped "
                    "unexpectedly. Stopping subscription handling."
                )

        # no active handler subscriptions, clear the handler subscription queue
        self._provider._request_processor._reset_handler_subscription_queue()
