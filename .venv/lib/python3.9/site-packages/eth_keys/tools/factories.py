try:
    import factory
except ImportError as err:
    raise ImportError(
        "Use of `eth_keys.tools.factories` requires the `factory-boy` package "
        "which does not appear to be installed."
    ) from err

from eth_keys import (
    keys,
)


def _mk_random_bytes(num_bytes: int) -> bytes:
    try:
        import secrets
    except ImportError:
        import os

        return os.urandom(num_bytes)
    else:
        return secrets.token_bytes(num_bytes)


class PrivateKeyFactory(factory.Factory):  # type: ignore
    class Meta:
        model = keys.PrivateKey

    private_key_bytes = factory.LazyFunction(lambda: _mk_random_bytes(32))


class PublicKeyFactory(factory.Factory):  # type: ignore
    class Meta:
        model = keys.PublicKey

    public_key_bytes = factory.LazyFunction(
        lambda: PrivateKeyFactory().public_key.to_bytes()
    )
