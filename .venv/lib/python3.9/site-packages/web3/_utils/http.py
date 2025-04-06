DEFAULT_HTTP_TIMEOUT = 30.0


def construct_user_agent(
    module: str,
    class_name: str,
) -> str:
    from web3 import (
        __version__ as web3_version,
    )

    return f"web3.py/{web3_version}/{module}.{class_name}"
