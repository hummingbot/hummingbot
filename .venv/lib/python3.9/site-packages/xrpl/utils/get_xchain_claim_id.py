"""Utils to get an XChainClaimID from metadata."""

from xrpl.models.transactions.metadata import TransactionMetadata, isCreatedNode


def get_xchain_claim_id(meta: TransactionMetadata) -> str:
    """
    Gets the XChainClaimID from a recently-submitted XChainCreateClaimID transaction.

    Args:
        meta: Metadata from the response to submitting an XChainCreateClaimID
            transaction.

    Returns:
        The newly created XChainClaimID.

    Raises:
        TypeError: if given something other than metadata (e.g. the full
                    transaction response).
    """
    if meta is None or meta.get("AffectedNodes") is None:
        raise TypeError(
            f"""Unable to parse the parameter given to get_xchain_claim_id.
            'meta' must be the metadata from an XChainCreateClaimID transaction.
            Received {meta} instead."""
        )

    affected_nodes = [
        node
        for node in meta["AffectedNodes"]
        if isCreatedNode(node)
        and node["CreatedNode"]["LedgerEntryType"] == "XChainOwnedClaimID"
    ]

    if len(affected_nodes) == 0:
        raise TypeError("No XChainOwnedClaimID created.")

    if len(affected_nodes) > 1:
        # Sanity check - should never happen
        raise TypeError(
            "Multiple XChainOwnedClaimIDs were somehow created. Please report this "
            "error."
        )

    # Get the NFTokenID which wasn't there before this transaction completed.
    return affected_nodes[0]["CreatedNode"]["NewFields"]["XChainClaimID"]
