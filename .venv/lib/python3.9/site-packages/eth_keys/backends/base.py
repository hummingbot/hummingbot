from eth_keys.datatypes import (
    BaseSignature,
    NonRecoverableSignature,
    PrivateKey,
    PublicKey,
    Signature,
)


class BaseECCBackend:
    def ecdsa_sign(self, msg_hash: bytes, private_key: PrivateKey) -> Signature:
        raise NotImplementedError()

    def ecdsa_sign_non_recoverable(
        self, msg_hash: bytes, private_key: PrivateKey
    ) -> NonRecoverableSignature:
        raise NotImplementedError()

    def ecdsa_verify(
        self, msg_hash: bytes, signature: BaseSignature, public_key: PublicKey
    ) -> bool:
        raise NotImplementedError()

    def ecdsa_recover(self, msg_hash: bytes, signature: Signature) -> PublicKey:
        raise NotImplementedError()

    def private_key_to_public_key(self, private_key: PrivateKey) -> PublicKey:
        raise NotImplementedError()

    def decompress_public_key_bytes(self, compressed_public_key_bytes: bytes) -> bytes:
        raise NotImplementedError()

    def compress_public_key_bytes(self, uncompressed_public_key_bytes: bytes) -> bytes:
        raise NotImplementedError()
