from os.path import isfile
from hummingbot.cli.settings import (
    EXCHANGES,
    STRATEGIES,
)


# Validators
def is_exchange(value: str) -> bool:
    return value in EXCHANGES


def is_strategy(value: str) -> bool:
    return value in STRATEGIES


def is_path(value: str) -> bool:
    return isfile(value) and value.endswith('.yml')
