"""High-level transaction methods with XRPL transactions."""

import asyncio
from typing import Optional

from xrpl.asyncio.transaction import main
from xrpl.clients.sync_client import SyncClient
from xrpl.models.response import Response
from xrpl.models.transactions.transaction import Transaction
from xrpl.wallet.main import Wallet


def sign_and_submit(
    transaction: Transaction,
    client: SyncClient,
    wallet: Wallet,
    autofill: bool = True,
    check_fee: bool = True,
) -> Response:
    """
    Signs a transaction (locally, without trusting external rippled nodes) and submits
    it to the XRPL.

    Args:
        transaction: the transaction to be signed and submitted.
        client: the network client with which to submit the transaction.
        wallet: the wallet with which to sign the transaction.
        autofill: whether to autofill the relevant fields. Defaults to True.
        check_fee: whether to check if the fee is higher than the expected transaction
            type fee. Defaults to True.

    Returns:
        The response from the ledger.
    """
    return asyncio.run(
        main.sign_and_submit(
            transaction,
            client,
            wallet,
            autofill,
            check_fee,
        )
    )


def submit(
    transaction: Transaction,
    client: SyncClient,
    *,
    fail_hard: bool = False,
) -> Response:
    """
    Submits a transaction to the ledger.

    Args:
        transaction: the Transaction to be submitted.
        client: the network client with which to submit the transaction.
        fail_hard: an optional boolean. If True, and the transaction fails for
            the initial server, do not retry or relay the transaction to other
            servers. Defaults to False.

    Returns:
        The response from the ledger.

    Raises:
        XRPLRequestFailureException: if the rippled API call fails.
    """
    return asyncio.run(
        main.submit(
            transaction,
            client,
            fail_hard=fail_hard,
        )
    )


sign = main.sign


def autofill_and_sign(
    transaction: Transaction,
    client: SyncClient,
    wallet: Wallet,
    check_fee: bool = True,
) -> Transaction:
    """
    Signs a transaction locally, without trusting external rippled nodes. Autofills
    relevant fields.

    Args:
        transaction: the transaction to be signed.
        client: a network client.
        wallet: the wallet with which to sign the transaction.
        check_fee: whether to check if the fee is higher than the expected transaction
            type fee. Defaults to True.

    Returns:
        The signed transaction.
    """
    return asyncio.run(
        main.autofill_and_sign(
            transaction,
            client,
            wallet,
            check_fee,
        )
    )


def autofill(
    transaction: Transaction, client: SyncClient, signers_count: Optional[int] = None
) -> Transaction:
    """
    Autofills fields in a transaction. This will set `sequence`, `fee`, and
    `last_ledger_sequence` according to the current state of the server this Client is
    connected to. It also converts all X-Addresses to classic addresses.

    Args:
        transaction: the transaction to be signed.
        client: a network client.
        signers_count: the expected number of signers for this transaction.
            Only used for multisigned transactions.

    Returns:
        The autofilled transaction.
    """
    return asyncio.run(
        main.autofill(
            transaction,
            client,
            signers_count,
        )
    )


def _calculate_fee_per_transaction_type(
    transaction: Transaction,
    client: SyncClient,
    signers_count: Optional[int] = None,
) -> str:
    """
    Calculate the total fee in drops for a transaction based on:
    - the network fee
    - the transaction condition

    https://xrpl.org/transaction-cost.html#special-transaction-costs

    Args:
        transaction: the Transaction to be submitted.
        client: the network client with which to submit the transaction.
        signers_count: the expected number of signers for this transaction.
            Only used for multisigned transactions.

    Returns:
        The expected Transaction fee in drops
    """
    return asyncio.run(
        main._calculate_fee_per_transaction_type(transaction, client, signers_count)
    )
