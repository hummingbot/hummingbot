"""Models for a transaction's metadata."""

from typing import Dict, List, Union

from typing_extensions import Literal, NotRequired, TypeAlias, TypedDict, TypeGuard

from xrpl.models.amounts.amount import Amount


class NFTokenMetadataFields(TypedDict):
    """Model for NFToken data in metadata."""

    NFTokenID: str
    URI: str


class NFTokenMetadata(TypedDict):
    """Model what NFTokens look like in metadata."""

    NFToken: NFTokenMetadataFields


class Fields(TypedDict):
    """Model for possible fields."""

    Flags: int
    Sequence: int
    Account: NotRequired[str]
    LowLimit: NotRequired[Dict[str, str]]
    HighLimit: NotRequired[Dict[str, str]]
    Balance: NotRequired[Union[Dict[str, str], str]]
    TakerGets: NotRequired[Union[Dict[str, str], str]]
    TakerPays: NotRequired[Union[Dict[str, str], str]]
    BookDirectory: NotRequired[str]
    Expiration: NotRequired[int]
    NFTokens: NotRequired[List[NFTokenMetadata]]
    XChainClaimID: NotRequired[str]


class CreatedNodeFields(TypedDict):
    """Fields of a CreatedNode."""

    LedgerEntryType: str
    LedgerIndex: str
    NewFields: Fields


class CreatedNode(TypedDict):
    """CreatedNode model."""

    CreatedNode: CreatedNodeFields


class ModifiedNodeFields(TypedDict):
    """Fields of a ModifiedNode."""

    LedgerEntryType: str
    LedgerIndex: str
    FinalFields: NotRequired[Fields]
    PreviousFields: NotRequired[Fields]
    PreviousTxnID: NotRequired[str]
    PreviousTxnLgrSeq: NotRequired[int]


class ModifiedNode(TypedDict):
    """ModifiedNode model."""

    ModifiedNode: ModifiedNodeFields


class DeletedNodeFields(TypedDict):
    """Fields of a DeletedNode."""

    LedgerEntryType: str
    LedgerIndex: str
    FinalFields: Fields
    PreviousFields: NotRequired[Fields]


class DeletedNode(TypedDict):
    """DeletedNode model."""

    DeletedNode: DeletedNodeFields


class TransactionMetadata(TypedDict):
    """A model for a transaction's metadata."""

    AffectedNodes: List[Union[CreatedNode, ModifiedNode, DeletedNode]]
    TransactionIndex: int
    TransactionResult: str
    DeliveredAmount: NotRequired[Amount]
    # "unavailable" possible for transactions before 2014-01-20
    delivered_amount: NotRequired[Union[Amount, Literal["unavailable"]]]


Node: TypeAlias = Union[CreatedNode, ModifiedNode, DeletedNode]


# TODO: make these methods use snake_case
def isCreatedNode(node: Node) -> TypeGuard[CreatedNode]:
    """
    Typeguard for CreatedNode

    Args:
        node: A node of any type (CreatedNode, ModifiedNode, or DeletedNode)

    Returns:
        Whether this node is a CreatedNode.
    """
    return "CreatedNode" in node


def isModifiedNode(node: Node) -> TypeGuard[ModifiedNode]:
    """
    Typeguard for ModifiedNode

    Args:
        node: A node of any type (CreatedNode, ModifiedNode, or DeletedNode)

    Returns:
        Whether this node is a ModifiedNode.
    """
    return "ModifiedNode" in node


def isDeletedNode(node: Node) -> TypeGuard[DeletedNode]:
    """
    Typeguard for DeletedNode

    Args:
        node: A node of any type (CreatedNode, ModifiedNode, or DeletedNode)

    Returns:
        Whether this node is a DeletedNode.
    """
    return "DeletedNode" in node
