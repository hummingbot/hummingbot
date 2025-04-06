from typing import (
    Any,
    Dict,
)

from toolz import (
    assoc,
    dissoc,
)

from eth_account._utils.validation import (
    is_rlp_structured_access_list,
    is_rlp_structured_authorization_list,
    is_rpc_structured_access_list,
    is_rpc_structured_authorization_list,
)
from eth_account.datastructures import (
    CustomPydanticModel,
)
from eth_account.types import (
    AccessList,
    AuthorizationList,
    RLPStructuredAccessList,
    RLPStructuredAuthorizationList,
    TransactionDictType,
)


def normalize_transaction_dict(txn_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes a transaction dictionary.
    """
    # convert all lists to tuples recursively
    for key, value in txn_dict.items():
        if isinstance(value, (list, tuple)):
            txn_dict[key] = tuple(
                normalize_transaction_dict(item) if isinstance(item, dict) else item
                for item in value
            )

        elif isinstance(value, dict):
            txn_dict[key] = normalize_transaction_dict(value)

    return txn_dict


def set_transaction_type_if_needed(
    transaction_dict: TransactionDictType,
) -> TransactionDictType:
    if "type" not in transaction_dict:
        if all(
            type_1_arg in transaction_dict for type_1_arg in ("gasPrice", "accessList")
        ):
            # access list txn - type 1
            transaction_dict = assoc(transaction_dict, "type", "0x1")
        elif any(
            type_2_arg in transaction_dict
            for type_2_arg in ("maxFeePerGas", "maxPriorityFeePerGas")
        ):
            if any(
                type_3_arg in transaction_dict
                for type_3_arg in ("maxFeePerBlobGas", "blobVersionedHashes")
            ):
                # blob txn - type 3
                transaction_dict = assoc(transaction_dict, "type", "0x3")
            elif "authorizationList" in transaction_dict:
                # set code txn - type 4
                transaction_dict = assoc(transaction_dict, "type", "0x4")
            else:
                # dynamic fee txn - type 2
                transaction_dict = assoc(transaction_dict, "type", "0x2")
    return transaction_dict


def json_serialize_classes_in_transaction(val: Any) -> Any:
    """
    Serialize class objects in a transaction using expected defined instructions.
    Pydantic models are serialized with:

    - ``mode="json"``           Uses the json encoder to serialize the model.
    - ``by_alias=True``:        Uses the alias generator to turn all non-excluded fields
                                into lowerCamelCase dicts.
    - ``exclude=val._exclude:   Fields excluded for serialization are defined within a
                                ``_exclude`` property on the pydantic model.
    """
    if isinstance(val, CustomPydanticModel):
        return val.recursive_model_dump()
    elif isinstance(val, dict):
        return {k: json_serialize_classes_in_transaction(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple)):
        return val.__class__(json_serialize_classes_in_transaction(v) for v in val)
    else:
        return val


# JSON-RPC to rlp transaction structure
def transaction_rpc_to_rlp_structure(dictionary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a JSON-RPC-structured transaction to an rlp-structured transaction.
    """
    access_list = dictionary.get("accessList")
    if access_list:
        dictionary = dissoc(dictionary, "accessList")
        rlp_structured_access_list = _access_list_rpc_to_rlp_structure(access_list)
        dictionary = assoc(dictionary, "accessList", rlp_structured_access_list)

    authorization_list = dictionary.get("authorizationList")
    if authorization_list:
        dictionary = dissoc(dictionary, "authorizationList")
        rlp_structured_authorization_list = _authorization_list_rpc_to_rlp_structure(
            authorization_list
        )
        dictionary = assoc(
            dictionary, "authorizationList", rlp_structured_authorization_list
        )
    return dictionary


def _access_list_rpc_to_rlp_structure(
    access_list: AccessList,
) -> RLPStructuredAccessList:
    if not is_rpc_structured_access_list(access_list):
        raise ValueError(
            "provided object not formatted as JSON-RPC-structured access list"
        )

    # flatten each dict into a tuple of its values
    return tuple(
        (
            d["address"],  # value of address
            tuple(_ for _ in d["storageKeys"]),  # tuple of storage key values
        )
        for d in access_list
    )


def _authorization_list_rpc_to_rlp_structure(
    authorization_list: AuthorizationList,
) -> RLPStructuredAuthorizationList:
    if not is_rpc_structured_authorization_list(authorization_list):
        raise ValueError(
            "provided object not formatted as JSON-RPC-structured authorization list"
        )
    # flatten each dict into a tuple of its values
    return tuple(
        (
            d["chainId"],
            d["address"],
            d["nonce"],
            d["yParity"],
            d["r"],
            d["s"],
        )
        for d in authorization_list
    )


# rlp to JSON-RPC transaction structure
def transaction_rlp_to_rpc_structure(dictionary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert an rlp-structured transaction to a JSON-RPC-structured transaction.
    """
    access_list = dictionary.get("accessList")
    authorization_list = dictionary.get("authorizationList")
    if access_list:
        dictionary = dissoc(dictionary, "accessList")
        rpc_structured_access_list = _access_list_rlp_to_rpc_structure(access_list)
        dictionary = assoc(dictionary, "accessList", rpc_structured_access_list)
    if authorization_list:
        dictionary = dissoc(dictionary, "authorizationList")
        rpc_structured_authorization_list = _authorization_list_rlp_to_rpc_structure(
            authorization_list
        )
        dictionary = assoc(
            dictionary, "authorizationList", rpc_structured_authorization_list
        )
    return dictionary


def _access_list_rlp_to_rpc_structure(
    access_list: RLPStructuredAccessList,
) -> AccessList:
    if not is_rlp_structured_access_list(access_list):
        raise ValueError("provided object not formatted as rlp-structured access list")

    # build a dictionary with appropriate keys for each tuple
    return tuple({"address": t[0], "storageKeys": t[1]} for t in access_list)


def _authorization_list_rlp_to_rpc_structure(
    authorization_list: RLPStructuredAuthorizationList,
) -> AuthorizationList:
    if not is_rlp_structured_authorization_list(authorization_list):
        raise ValueError(
            "provided object not formatted as rlp-structured authorization list"
        )
    return tuple(
        {
            "chainId": t[0],
            "address": t[1],
            "nonce": t[2],
            "yParity": t[3],
            "r": t[4],
            "s": t[5],
        }
        for t in authorization_list
    )
