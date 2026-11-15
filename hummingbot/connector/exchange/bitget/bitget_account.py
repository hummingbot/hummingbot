"""
The account identity shared by bitget and bitget_perpetual.

Both connectors read the same UTA wallet, so the balance command folds them together when their
account_group_id matches. The id is keyed on the account's user id, so different API keys of one
account match. The user id is learned once per API key and shared by both connectors: whichever
connector reads it first, the other one with the same key reports the same id, even if its own read
failed. Keys are only ever held as SHA-256 fingerprints.
"""
import hashlib
import time
from typing import Dict, Optional

USER_ID_RETRY_INTERVAL_SECONDS = 60.0

_user_ids: Dict[str, str] = {}
_retry_after: Dict[str, float] = {}


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _time() -> float:
    return time.time()


def known_user_id(api_key: str) -> Optional[str]:
    return _user_ids.get(_fingerprint(api_key)) if api_key else None


def account_group_id(api_key: Optional[str]) -> Optional[str]:
    """Hash of the account's user id once known, of the API key until then; None without a key."""
    if not api_key:
        return None
    identity = known_user_id(api_key) or api_key
    return f"bitget_uta:{_fingerprint(identity)[:16]}"


def needs_user_id(api_key: Optional[str]) -> bool:
    if not api_key:
        return False
    fingerprint = _fingerprint(api_key)
    return fingerprint not in _user_ids and _time() >= _retry_after.get(fingerprint, 0.0)


def remember_user_id(api_key: str, user_id: str) -> None:
    fingerprint = _fingerprint(api_key)
    _user_ids[fingerprint] = user_id
    _retry_after.pop(fingerprint, None)


def user_id_read_failed(api_key: str) -> None:
    _retry_after[_fingerprint(api_key)] = _time() + USER_ID_RETRY_INTERVAL_SECONDS


def forget_all() -> None:
    _user_ids.clear()
    _retry_after.clear()
