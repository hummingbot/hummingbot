from eth_keys.backends.base import (
    BaseECCBackend,
)
from eth_keys.datatypes import (
    BaseSignature,
    NonRecoverableSignature,
    PrivateKey,
    PublicKey,
    Signature,
)

from .ecdsa import (
    compress_public_key,
    decompress_public_key,
    ecdsa_raw_recover,
    ecdsa_raw_sign,
    ecdsa_raw_verify,
    private_key_to_public_key,
)


class NativeECCBackend(BaseECCBackend):
    def ecdsa_sign(self, msg_hash: bytes, private_key: PrivateKey) -> Signature:
        signature_vrs = ecdsa_raw_sign(msg_hash, private_key.to_bytes())
        signature = Signature(vrs=signature_vrs, backend=self)
        return signature

    def ecdsa_sign_non_recoverable(
        self, msg_hash: bytes, private_key: PrivateKey
    ) -> NonRecoverableSignature:
        _, signature_r, signature_s = ecdsa_raw_sign(msg_hash, private_key.to_bytes())
        signature = NonRecoverableSignature(rs=(signature_r, signature_s), backend=self)
        return signature

    def ecdsa_verify(
        self, msg_hash: bytes, signature: BaseSignature, public_key: PublicKey
    ) -> bool:
        return ecdsa_raw_verify(msg_hash, signature.rs, public_key.to_bytes())

    def ecdsa_recover(self, msg_hash: bytes, signature: Signature) -> PublicKey:
        public_key_bytes = ecdsa_raw_recover(msg_hash, signature.vrs)
        public_key = PublicKey(public_key_bytes, backend=self)
        return public_key

    def private_key_to_public_key(self, private_key: PrivateKey) -> PublicKey:
        public_key_bytes = private_key_to_public_key(private_key.to_bytes())
        public_key = PublicKey(public_key_bytes, backend=self)
        return public_key

    def decompress_public_key_bytes(self, compressed_public_key_bytes: bytes) -> bytes:
        return decompress_public_key(compressed_public_key_bytes)

    def compress_public_key_bytes(self, uncompressed_public_key_bytes: bytes) -> bytes:
        return compress_public_key(uncompressed_public_key_bytes)
