from eth_utils import (
    big_endian_to_int,
)

from eth_keys.datatypes import (
    BaseSignature,
    NonRecoverableSignature,
    PrivateKey,
    PublicKey,
    Signature,
)
from eth_keys.exceptions import (
    BadSignature,
)
from eth_keys.utils import (
    der,
)
from eth_keys.utils.numeric import (
    coerce_low_s,
)
from eth_keys.validation import (
    validate_uncompressed_public_key_bytes,
)

from .base import (
    BaseECCBackend,
)


def is_coincurve_available() -> bool:
    try:
        import coincurve  # noqa: F401
    except ImportError:
        return False
    else:
        return True


class CoinCurveECCBackend(BaseECCBackend):
    def __init__(self) -> None:
        try:
            import coincurve
        except ImportError:
            raise ImportError(
                "The CoinCurveECCBackend requires the coincurve "
                "library which is not available for import."
            )
        self.keys = coincurve.keys
        self.ecdsa = coincurve.ecdsa
        super().__init__()

    def ecdsa_sign(self, msg_hash: bytes, private_key: PrivateKey) -> Signature:
        private_key_bytes = private_key.to_bytes()
        signature_bytes = self.keys.PrivateKey(private_key_bytes).sign_recoverable(
            msg_hash,
            hasher=None,
        )
        signature = Signature(signature_bytes, backend=self)
        return signature

    def ecdsa_sign_non_recoverable(
        self, msg_hash: bytes, private_key: PrivateKey
    ) -> NonRecoverableSignature:
        private_key_bytes = private_key.to_bytes()

        der_encoded_signature = self.keys.PrivateKey(private_key_bytes).sign(
            msg_hash,
            hasher=None,
        )
        rs = der.two_int_sequence_decoder(der_encoded_signature)

        signature = NonRecoverableSignature(rs=rs, backend=self)
        return signature

    def ecdsa_verify(
        self, msg_hash: bytes, signature: BaseSignature, public_key: PublicKey
    ) -> bool:
        # coincurve rejects signatures with a high s,
        # so convert to the equivalent low s form
        low_s = coerce_low_s(signature.s)
        der_encoded_signature = der.two_int_sequence_encoder(signature.r, low_s)
        coincurve_public_key = self.keys.PublicKey(b"\x04" + public_key.to_bytes())
        return coincurve_public_key.verify(
            der_encoded_signature,
            msg_hash,
            hasher=None,
        )

    def ecdsa_recover(self, msg_hash: bytes, signature: Signature) -> PublicKey:
        signature_bytes = signature.to_bytes()
        try:
            public_key_bytes = self.keys.PublicKey.from_signature_and_message(
                signature_bytes,
                msg_hash,
                hasher=None,
            ).format(compressed=False)[1:]
        except Exception as err:
            raise BadSignature(str(err))
        public_key = PublicKey(public_key_bytes, backend=self)
        return public_key

    def private_key_to_public_key(self, private_key: PrivateKey) -> PublicKey:
        public_key_bytes = self.keys.PrivateKey(
            private_key.to_bytes()
        ).public_key.format(compressed=False,)[1:]
        return PublicKey(public_key_bytes, backend=self)

    def decompress_public_key_bytes(self, compressed_public_key_bytes: bytes) -> bytes:
        public_key = self.keys.PublicKey(compressed_public_key_bytes)
        return public_key.format(compressed=False)[1:]

    def compress_public_key_bytes(self, uncompressed_public_key_bytes: bytes) -> bytes:
        validate_uncompressed_public_key_bytes(uncompressed_public_key_bytes)
        point = (
            big_endian_to_int(uncompressed_public_key_bytes[:32]),
            big_endian_to_int(uncompressed_public_key_bytes[32:]),
        )
        public_key = self.keys.PublicKey.from_point(*point)
        return public_key.format(compressed=True)
