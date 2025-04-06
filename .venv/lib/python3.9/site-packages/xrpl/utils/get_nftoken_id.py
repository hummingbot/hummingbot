"""Utils to get an NFTokenID from metadata"""

from typing import Callable, List, TypeVar, Union

from xrpl.models.transactions.metadata import (
    NFTokenMetadata,
    Node,
    TransactionMetadata,
    isCreatedNode,
    isModifiedNode,
)

T = TypeVar("T")
R = TypeVar("R")


def _flatmap(func: Callable[[T], List[R]], list_of_items: List[T]) -> List[R]:
    """
    Flattens objects into a single list, and applies func to every object in objects.

    Source: https://dev.to/turbaszek/flat-map-in-python-3g98

    Args:
        func: A function to apply to every object.
        list_of_items: A list of lists to be flattened and updated.

    Returns:
        A flattened list of modified items.
    """
    modified_items: List[R] = []
    for item in list_of_items:
        modified_items.extend(func(item))
    return modified_items


def get_nftoken_ids_from_nftokens(nftokens: List[NFTokenMetadata]) -> List[str]:
    """
    Extract NFTokenIDs from a list of NFTokens.

    Args:
        nftokens: A list of NFTokens

    Returns:
        A list of NFTokenIDs.
    """
    return [
        id
        for id in [token["NFToken"]["NFTokenID"] for token in nftokens]
        if id is not None
    ]


def get_nftoken_id(meta: TransactionMetadata) -> Union[str, None]:
    """
    Gets the NFTokenID for an NFT recently minted with NFTokenMint.

    Args:
        meta: Metadata from the response to submitting an NFTokenMint transaction.

    Returns:
        The newly minted NFToken's NFTokenID. None if there is no NFTokenID that was
        minted.

    Raises:
        TypeError: if given something other than metadata (e.g. the full
                    transaction response).
    """
    if meta is None or meta.get("AffectedNodes") is None:
        raise TypeError(
            f"""Unable to parse the parameter given to get_nftoken_id.
            'meta' must be the metadata from an NFTokenMint transaction.
            Received {meta} instead."""
        )

    """
    * When a mint results in splitting an existing page,
    * it results in a created page and a modified node. Sometimes,
    * the created node needs to be linked to a third page, resulting
    * in modifying that third page's PreviousPageMin or NextPageMin
    * field changing, but no NFTs within that page changing. In this
    * case, there will be no previous NFTs and we need to skip.
    * However, there will always be NFTs listed in the final fields,
    * as rippled outputs all fields in final fields even if they were
    * not changed. Thus why we add the additional condition to check
    * if the PreviousFields contains NFTokens
    """

    def has_nftoken_page(node: Node) -> bool:
        if isCreatedNode(node):
            return node["CreatedNode"]["LedgerEntryType"] == "NFTokenPage"
        elif isModifiedNode(node):
            return (
                node["ModifiedNode"]["LedgerEntryType"] == "NFTokenPage"
                and node["ModifiedNode"]["PreviousFields"]
                and "NFTokens" in node["ModifiedNode"]["PreviousFields"]
            )
        else:
            return False

    affected_nodes = [node for node in meta["AffectedNodes"] if has_nftoken_page(node)]

    if len(affected_nodes) == 0:
        return None

    def get_previous_nftokens(node: Node) -> List[NFTokenMetadata]:
        nftokens: List[NFTokenMetadata] = []
        if isModifiedNode(node):
            new_nftokens = node["ModifiedNode"]["PreviousFields"].get("NFTokens")
            if new_nftokens is not None:
                nftokens = new_nftokens
        return nftokens

    previous_token_ids = set(
        get_nftoken_ids_from_nftokens(_flatmap(get_previous_nftokens, affected_nodes))
    )

    def get_new_nftokens(node: Node) -> List[NFTokenMetadata]:
        nftokens: List[NFTokenMetadata] = []
        if isModifiedNode(node):
            nftokens = node["ModifiedNode"]["FinalFields"].get("NFTokens") or nftokens
        if isCreatedNode(node):
            nftokens = node["CreatedNode"]["NewFields"].get("NFTokens") or nftokens
        return nftokens

    final_token_ids = get_nftoken_ids_from_nftokens(
        _flatmap(get_new_nftokens, affected_nodes)
    )

    # Get the NFTokenID which wasn't there before this transaction completed.
    return [id for id in final_token_ids if (id not in previous_token_ids)][0]
