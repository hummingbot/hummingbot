"""Helper functions to normalize an affected node."""

from typing import List, Optional, Union, cast

from typing_extensions import Literal, TypedDict

from xrpl.models import TransactionMetadata
from xrpl.models.transactions.metadata import (
    CreatedNode,
    CreatedNodeFields,
    DeletedNode,
    DeletedNodeFields,
    Fields,
    ModifiedNode,
    ModifiedNodeFields,
)


class NormalizedNode(TypedDict):
    """A model representing an affected node in a standard format."""

    NodeType: Literal["CreatedNode", "ModifiedNode", "DeletedNode"]
    LedgerEntryType: str
    LedgerIndex: str
    NewFields: Optional[Fields]
    FinalFields: Optional[Fields]
    PreviousFields: Optional[Fields]
    PreviousTxnID: Optional[str]
    PreviousTxnLgrSeq: Optional[int]


def _normalize_node(
    affected_node: Union[CreatedNode, ModifiedNode, DeletedNode]
) -> NormalizedNode:
    node_keys = affected_node.keys()
    assert len(node_keys) == 1
    diff_type = cast(
        Literal["CreatedNode", "ModifiedNode", "DeletedNode"],
        list(node_keys)[0],
    )
    if diff_type == "CreatedNode":
        node: Union[CreatedNodeFields, ModifiedNodeFields, DeletedNodeFields] = cast(
            CreatedNode, affected_node
        )["CreatedNode"]
    elif diff_type == "ModifiedNode":
        node = cast(ModifiedNode, affected_node)["ModifiedNode"]
    else:
        node = cast(DeletedNode, affected_node)["DeletedNode"]
    ledger_entry_type = node["LedgerEntryType"]
    ledger_index = node["LedgerIndex"]
    new_fields = cast(Optional[Fields], node.get("NewFields"))
    previous_fields = cast(Optional[Fields], node.get("PreviousFields"))
    final_fields = cast(Optional[Fields], node.get("FinalFields"))
    previous_txn_id = cast(Optional[str], node.get("PreviousTxnID"))
    previous_txn_lgr_seq = cast(Optional[int], node.get("PreviousTxnLgrSeq"))
    return NormalizedNode(
        NodeType=diff_type,
        LedgerEntryType=ledger_entry_type,
        LedgerIndex=ledger_index,
        NewFields=new_fields,
        PreviousFields=previous_fields,
        FinalFields=final_fields,
        PreviousTxnID=previous_txn_id,
        PreviousTxnLgrSeq=previous_txn_lgr_seq,
    )


def normalize_nodes(metadata: TransactionMetadata) -> List[NormalizedNode]:
    """
    Normalize all nodes of a transaction's metadata.

    Args:
        metadata: The transaction's metadata.

    Returns:
        The normalized nodes.
    """
    return [_normalize_node(node) for node in metadata["AffectedNodes"]]
