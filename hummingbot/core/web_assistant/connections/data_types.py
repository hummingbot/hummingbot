"""
Data types for web assistant connections.
Minimal implementation to support connector development.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from enum import Enum


class RESTMethod(Enum):
    """HTTP REST methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class RESTRequest:
    """REST request data structure."""
    method: RESTMethod
    url: str
    params: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    is_auth_required: bool = False


@dataclass
class RESTResponse:
    """REST response data structure."""
    status: int
    data: Any
    headers: Dict[str, str]
    url: str


@dataclass
class WSRequest:
    """WebSocket request data structure."""
    payload: Dict[str, Any]
    is_auth_required: bool = False


@dataclass
class WSResponse:
    """WebSocket response data structure."""
    data: Any
    timestamp: float


@dataclass
class WSJSONRequest:
    """
    WebSocket JSON request data structure.
    Used for sending JSON-formatted messages over WebSocket connections.
    """
    payload: Dict[str, Any]
    is_auth_required: bool = False

    def __post_init__(self):
        """Post-initialization validation."""
        if not isinstance(self.payload, dict):
            raise ValueError("WSJSONRequest payload must be a dictionary")

    def to_json(self) -> Dict[str, Any]:
        """Convert request to JSON format."""
        return self.payload.copy()

    @classmethod
    def from_dict(cls, data: Dict[str, Any], is_auth_required: bool = False) -> 'WSJSONRequest':
        """
        Create WSJSONRequest from dictionary.

        Args:
            data: Request payload dictionary
            is_auth_required: Whether authentication is required

        Returns:
            WSJSONRequest instance
        """
        return cls(payload=data, is_auth_required=is_auth_required)
