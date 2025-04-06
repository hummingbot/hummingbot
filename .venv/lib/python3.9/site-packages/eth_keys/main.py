from eth_utils import (
    ValidationError,
)

from eth_keys.datatypes import (
    BaseSignature,
    LazyBackend,
    NonRecoverableSignature,
    PrivateKey,
    PublicKey,
    Signature,
)
from eth_keys.validation import (
    validate_message_hash,
)

# These must be aliased due to a scoping issue in mypy
# https://github.com/python/mypy/issues/1775
_PublicKey = PublicKey
_PrivateKey = PrivateKey
_Signature = Signature
_NonRecoverableSignature = NonRecoverableSignature


class KeyAPI(LazyBackend):
    PublicKey = PublicKey
    PrivateKey = PrivateKey
    Signature = Signature
    NonRecoverableSignature = NonRecoverableSignature

    #
    # Proxy method calls to the backends
    #
    def ecdsa_sign(self, message_hash: bytes, private_key: _PrivateKey) -> _Signature:
        validate_message_hash(message_hash)
        if not isinstance(private_key, PrivateKey):
            raise ValidationError(
                "The `private_key` must be an instance of "
                "`eth_keys.datatypes.PrivateKey`"
            )
        signature = self.backend.ecdsa_sign(message_hash, private_key)
        if not isinstance(signature, Signature):
            raise ValidationError(
                "Backend returned an invalid signature.  Return value must be "
                "an instance of `eth_keys.datatypes.Signature`"
            )
        return signature

    def ecdsa_sign_non_recoverable(
        self, message_hash: bytes, private_key: _PrivateKey
    ) -> _NonRecoverableSignature:
        validate_message_hash(message_hash)
        if not isinstance(private_key, PrivateKey):
            raise ValidationError(
                "The `private_key` must be an instance of "
                "`eth_keys.datatypes.PrivateKey`"
            )
        signature = self.backend.ecdsa_sign_non_recoverable(message_hash, private_key)
        if not isinstance(signature, NonRecoverableSignature):
            raise ValidationError(
                "Backend returned an invalid signature.  Return value must be "
                "an instance of `eth_keys.datatypes.Signature`"
            )
        return signature

    def ecdsa_verify(
        self, message_hash: bytes, signature: BaseSignature, public_key: _PublicKey
    ) -> bool:
        validate_message_hash(message_hash)
        if not isinstance(public_key, PublicKey):
            raise ValidationError(
                "The `public_key` must be an instance of `eth_keys.datatypes.PublicKey`"
            )
        if not isinstance(signature, BaseSignature):
            raise ValidationError(
                "The `signature` must be an instance of "
                "`eth_keys.datatypes.BaseSignature`"
            )
        return self.backend.ecdsa_verify(message_hash, signature, public_key)

    def ecdsa_recover(self, message_hash: bytes, signature: _Signature) -> _PublicKey:
        validate_message_hash(message_hash)
        if not isinstance(signature, Signature):
            raise ValidationError(
                "The `signature` must be an instance of `eth_keys.datatypes.Signature`"
            )
        public_key = self.backend.ecdsa_recover(message_hash, signature)
        if not isinstance(public_key, _PublicKey):
            raise ValidationError(
                "Backend returned an invalid public_key.  Return value must be "
                "an instance of `eth_keys.datatypes.PublicKey`"
            )
        return public_key

    def private_key_to_public_key(self, private_key: _PrivateKey) -> _PublicKey:
        if not isinstance(private_key, PrivateKey):
            raise ValidationError(
                "The `private_key` must be an instance of "
                "`eth_keys.datatypes.PrivateKey`"
            )
        public_key = self.backend.private_key_to_public_key(private_key)
        if not isinstance(public_key, PublicKey):
            raise ValidationError(
                "Backend returned an invalid public_key.  Return value must be "
                "an instance of `eth_keys.datatypes.PublicKey`"
            )
        return public_key


# This creates an easy to import backend which will lazily fetch whatever
# backend has been configured at runtime (as opposed to import or instantiation time).
lazy_key_api = KeyAPI(backend=None)
