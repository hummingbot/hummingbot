from hypothesis import (
    strategies as st,
)
from hypothesis.strategies import (
    SearchStrategy,
)


def hexstr_strategy() -> SearchStrategy[str]:
    return st.from_regex(r"\A(0[xX])?[0-9a-fA-F]*\Z")
