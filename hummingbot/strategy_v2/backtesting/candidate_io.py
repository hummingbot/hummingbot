import json
from pathlib import Path
from typing import List, Type, TypeVar


T = TypeVar("T")


def load_parameter_candidates(
    path_value: str,
    parameter_type: Type[T],
    defaults: List[T],
    limit: int,
) -> List[T]:
    """Load isolated candidate parameters, falling back to code defaults.

    The external file is data, not executable configuration. Dataclass
    construction validates the exact parameter names and required values.
    """
    if not path_value:
        return defaults[:limit]
    path = Path(path_value).expanduser().resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("candidates") if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not rows:
        raise ValueError("candidate file must contain a non-empty candidates list")
    candidates = [parameter_type(**row) for row in rows if isinstance(row, dict)]
    if not candidates:
        raise ValueError("candidate file has no valid parameter objects")
    return candidates[:limit]
