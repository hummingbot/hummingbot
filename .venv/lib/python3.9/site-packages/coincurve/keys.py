import os
from typing import Optional, Tuple

from asn1crypto.keys import ECDomainParameters, ECPointBitString, ECPrivateKey, PrivateKeyAlgorithm, PrivateKeyInfo

from coincurve.context import GLOBAL_CONTEXT, Context
from coincurve.ecdsa import cdata_to_der, der_to_cdata, deserialize_recoverable, recover, serialize_recoverable
from coincurve.flags import EC_COMPRESSED, EC_UNCOMPRESSED
from coincurve.types import Hasher, Nonce
from coincurve.utils import (
    DEFAULT_NONCE,
    bytes_to_int,
    der_to_pem,
    get_valid_secret,
    hex_to_bytes,
    int_to_bytes_padded,
    pad_scalar,
    pem_to_der,
    sha256,
    validate_secret,
)

from ._libsecp256k1 import ffi, lib


class PrivateKey:
    def __init__(self, secret: Optional[bytes] = None, context: Context = GLOBAL_CONTEXT):
        """
        :param secret: The secret used to initialize the private key.
                       If not provided or `None`, a new key will be generated.
        """
        self.secret: bytes = validate_secret(secret) if secret is not None else get_valid_secret()
        self.context = context
        self.public_key: PublicKey = PublicKey.from_valid_secret(self.secret, self.context)
        self.public_key_xonly: PublicKeyXOnly = PublicKeyXOnly.from_valid_secret(self.secret, self.context)

    def sign(self, message: bytes, hasher: Hasher = sha256, custom_nonce: Nonce = DEFAULT_NONCE) -> bytes:
        """
        Create an ECDSA signature.

        :param message: The message to sign.
        :param hasher: The hash function to use, which must return 32 bytes. By default,
                       the `sha256` algorithm is used. If `None`, no hashing occurs.
        :param custom_nonce: Custom nonce data in the form `(nonce_function, input_data)`. Refer to
                             [secp256k1.h](https://github.com/bitcoin-core/secp256k1/blob/f8c0b57e6ba202b1ce7c5357688de97c9c067697/include/secp256k1.h#L546-L547).
        :return: The ECDSA signature.
        :raises ValueError: If the message hash was not 32 bytes long, the nonce generation
                            function failed, or the private key was invalid.
        """
        msg_hash = hasher(message) if hasher is not None else message
        if len(msg_hash) != 32:
            raise ValueError('Message hash must be 32 bytes long.')

        signature = ffi.new('secp256k1_ecdsa_signature *')
        nonce_fn, nonce_data = custom_nonce

        signed = lib.secp256k1_ecdsa_sign(self.context.ctx, signature, msg_hash, self.secret, nonce_fn, nonce_data)

        if not signed:
            raise ValueError('The nonce generation function failed, or the private key was invalid.')

        return cdata_to_der(signature, self.context)

    def sign_schnorr(self, message: bytes, aux_randomness: bytes = b'') -> bytes:
        """Create a Schnorr signature.

        :param message: The message to sign.
        :param aux_randomness: An optional 32 bytes of fresh randomness. By default (empty bytestring), this
                               will be generated automatically. Set to `None` to disable this behavior.
        :return: The Schnorr signature.
        :raises ValueError: If the message was not 32 bytes long, the optional auxiliary random data was not
                            32 bytes long, signing failed, or the signature was invalid.
        """
        if len(message) != 32:
            raise ValueError('Message must be 32 bytes long.')
        elif aux_randomness == b'':
            aux_randomness = os.urandom(32)
        elif aux_randomness is None:
            aux_randomness = ffi.NULL
        elif len(aux_randomness) != 32:
            raise ValueError('Auxiliary random data must be 32 bytes long.')

        keypair = ffi.new('secp256k1_keypair *')
        res = lib.secp256k1_keypair_create(self.context.ctx, keypair, self.secret)
        if not res:
            raise ValueError('Secret was invalid')

        signature = ffi.new('unsigned char[64]')
        res = lib.secp256k1_schnorrsig_sign32(self.context.ctx, signature, message, keypair, aux_randomness)
        if not res:
            raise ValueError('Signing failed')

        res = lib.secp256k1_schnorrsig_verify(
            self.context.ctx, signature, message, len(message), self.public_key_xonly.public_key
        )
        if not res:
            raise ValueError('Invalid signature')

        return bytes(ffi.buffer(signature))

    def sign_recoverable(self, message: bytes, hasher: Hasher = sha256, custom_nonce: Nonce = DEFAULT_NONCE) -> bytes:
        """
        Create a recoverable ECDSA signature.

        :param message: The message to sign.
        :param hasher: The hash function to use, which must return 32 bytes. By default,
                       the `sha256` algorithm is used. If `None`, no hashing occurs.
        :param custom_nonce: Custom nonce data in the form `(nonce_function, input_data)`. Refer to
                             [secp256k1_recovery.h](https://github.com/bitcoin-core/secp256k1/blob/f8c0b57e6ba202b1ce7c5357688de97c9c067697/include/secp256k1_recovery.h#L78-L79).
        :return: The recoverable ECDSA signature.
        :raises ValueError: If the message hash was not 32 bytes long, the nonce generation
                            function failed, or the private key was invalid.
        """
        msg_hash = hasher(message) if hasher is not None else message
        if len(msg_hash) != 32:
            raise ValueError('Message hash must be 32 bytes long.')

        signature = ffi.new('secp256k1_ecdsa_recoverable_signature *')
        nonce_fn, nonce_data = custom_nonce

        signed = lib.secp256k1_ecdsa_sign_recoverable(
            self.context.ctx, signature, msg_hash, self.secret, nonce_fn, nonce_data
        )

        if not signed:
            raise ValueError('The nonce generation function failed, or the private key was invalid.')

        return serialize_recoverable(signature, self.context)

    def ecdh(self, public_key: bytes) -> bytes:
        """
        Compute an EC Diffie-Hellman secret in constant time.

        !!! note
            This prevents malleability by returning `sha256(compressed_public_key)` instead of the `x` coordinate
            directly. See #9.

        :param public_key: The formatted public key.
        :return: The 32 byte shared secret.
        :raises ValueError: If the public key could not be parsed or was invalid.
        """
        secret = ffi.new('unsigned char [32]')

        lib.secp256k1_ecdh(self.context.ctx, secret, PublicKey(public_key).public_key, self.secret, ffi.NULL, ffi.NULL)

        return bytes(ffi.buffer(secret, 32))

    def add(self, scalar: bytes, update: bool = False):
        """
        Add a scalar to the private key.

        :param scalar: The scalar with which to add.
        :param update: Whether or not to update and return the private key in-place.
        :return: The new private key, or the modified private key if `update` is `True`.
        :rtype: PrivateKey
        :raises ValueError: If the tweak was out of range or the resulting private key was invalid.
        """
        scalar = pad_scalar(scalar)

        secret = ffi.new('unsigned char [32]', self.secret)

        success = lib.secp256k1_ec_seckey_tweak_add(self.context.ctx, secret, scalar)

        if not success:
            raise ValueError('The tweak was out of range, or the resulting private key is invalid.')

        secret = bytes(ffi.buffer(secret, 32))

        if update:
            self.secret = secret
            self._update_public_key()
            return self

        return PrivateKey(secret, self.context)

    def multiply(self, scalar: bytes, update: bool = False):
        """
        Multiply the private key by a scalar.

        :param scalar: The scalar with which to multiply.
        :param update: Whether or not to update and return the private key in-place.
        :return: The new private key, or the modified private key if `update` is `True`.
        :rtype: PrivateKey
        """
        scalar = validate_secret(scalar)

        secret = ffi.new('unsigned char [32]', self.secret)

        lib.secp256k1_ec_seckey_tweak_mul(self.context.ctx, secret, scalar)

        secret = bytes(ffi.buffer(secret, 32))

        if update:
            self.secret = secret
            self._update_public_key()
            return self

        return PrivateKey(secret, self.context)

    def to_hex(self) -> str:
        """
        :return: The private key encoded as a hex string.
        """
        return self.secret.hex()

    def to_int(self) -> int:
        """
        :return: The private key as an integer.
        """
        return bytes_to_int(self.secret)

    def to_pem(self) -> bytes:
        """
        :return: The private key encoded in PEM format.
        """
        return der_to_pem(self.to_der())

    def to_der(self) -> bytes:
        """
        :return: The private key encoded in DER format.
        """
        pk = ECPrivateKey(
            {
                'version': 'ecPrivkeyVer1',
                'private_key': self.to_int(),
                'public_key': ECPointBitString(self.public_key.format(compressed=False)),
            }
        )

        return PrivateKeyInfo(
            {
                'version': 0,
                'private_key_algorithm': PrivateKeyAlgorithm(
                    {
                        'algorithm': 'ec',
                        'parameters': ECDomainParameters(name='named', value='1.3.132.0.10'),
                    }
                ),
                'private_key': pk,
            }
        ).dump()

    @classmethod
    def from_hex(cls, hexed: str, context: Context = GLOBAL_CONTEXT):
        """
        :param hexed: The private key encoded as a hex string.
        :param context:
        :return: The private key.
        :rtype: PrivateKey
        """
        return PrivateKey(hex_to_bytes(hexed), context)

    @classmethod
    def from_int(cls, num: int, context: Context = GLOBAL_CONTEXT):
        """
        :param num: The private key as an integer.
        :param context:
        :return: The private key.
        :rtype: PrivateKey
        """
        return PrivateKey(int_to_bytes_padded(num), context)

    @classmethod
    def from_pem(cls, pem: bytes, context: Context = GLOBAL_CONTEXT):
        """
        :param pem: The private key encoded in PEM format.
        :param context:
        :return: The private key.
        :rtype: PrivateKey
        """
        return PrivateKey(
            int_to_bytes_padded(PrivateKeyInfo.load(pem_to_der(pem)).native['private_key']['private_key']), context
        )

    @classmethod
    def from_der(cls, der: bytes, context: Context = GLOBAL_CONTEXT):
        """
        :param der: The private key encoded in DER format.
        :param context:
        :return: The private key.
        :rtype: PrivateKey
        """
        return PrivateKey(int_to_bytes_padded(PrivateKeyInfo.load(der).native['private_key']['private_key']), context)

    def _update_public_key(self):
        created = lib.secp256k1_ec_pubkey_create(self.context.ctx, self.public_key.public_key, self.secret)

        if not created:
            raise ValueError('Invalid secret.')

    def __eq__(self, other) -> bool:
        return self.secret == other.secret


class PublicKey:
    def __init__(self, data, context: Context = GLOBAL_CONTEXT):
        """
        :param data: The formatted public key. This class supports parsing
                     compressed (33 bytes, header byte `0x02` or `0x03`),
                     uncompressed (65 bytes, header byte `0x04`), or
                     hybrid (65 bytes, header byte `0x06` or `0x07`) format public keys.
        :type data: bytes
        :param context:
        :raises ValueError: If the public key could not be parsed or was invalid.
        """
        if not isinstance(data, bytes):
            self.public_key = data
        else:
            public_key = ffi.new('secp256k1_pubkey *')

            parsed = lib.secp256k1_ec_pubkey_parse(context.ctx, public_key, data, len(data))

            if not parsed:
                raise ValueError('The public key could not be parsed or is invalid.')

            self.public_key = public_key

        self.context = context

    @classmethod
    def from_secret(cls, secret: bytes, context: Context = GLOBAL_CONTEXT):
        """
        Derive a public key from a private key secret.

        :param secret: The private key secret.
        :param context:
        :return: The public key.
        :rtype: PublicKey
        """
        public_key = ffi.new('secp256k1_pubkey *')

        created = lib.secp256k1_ec_pubkey_create(context.ctx, public_key, validate_secret(secret))

        if not created:  # no cov
            raise ValueError(
                'Somehow an invalid secret was used. Please '
                'submit this as an issue here: '
                'https://github.com/ofek/coincurve/issues/new'
            )

        return PublicKey(public_key, context)

    @classmethod
    def from_valid_secret(cls, secret: bytes, context: Context = GLOBAL_CONTEXT):
        public_key = ffi.new('secp256k1_pubkey *')

        created = lib.secp256k1_ec_pubkey_create(context.ctx, public_key, secret)

        if not created:
            raise ValueError('Invalid secret.')

        return PublicKey(public_key, context)

    @classmethod
    def from_point(cls, x: int, y: int, context: Context = GLOBAL_CONTEXT):
        """
        Derive a public key from a coordinate point in the form `(x, y)`.

        :param x:
        :param y:
        :param context:
        :return: The public key.
        :rtype: PublicKey
        """
        return PublicKey(b'\x04' + int_to_bytes_padded(x) + int_to_bytes_padded(y), context)

    @classmethod
    def from_signature_and_message(
        cls, signature: bytes, message: bytes, hasher: Hasher = sha256, context: Context = GLOBAL_CONTEXT
    ):
        """
        Recover an ECDSA public key from a recoverable signature.

        :param signature: The recoverable ECDSA signature.
        :param message: The message that was supposedly signed.
        :param hasher: The hash function to use, which must return 32 bytes. By default,
                       the `sha256` algorithm is used. If `None`, no hashing occurs.
        :param context:
        :return: The public key that signed the message.
        :rtype: PublicKey
        :raises ValueError: If the message hash was not 32 bytes long or recovery of the ECDSA public key failed.
        """
        return PublicKey(
            recover(message, deserialize_recoverable(signature, context=context), hasher=hasher, context=context)
        )

    @classmethod
    def combine_keys(cls, public_keys, context: Context = GLOBAL_CONTEXT):
        """
        Add a number of public keys together.

        :param public_keys: A sequence of public keys.
        :type public_keys: List[PublicKey]
        :param context:
        :return: The combined public key.
        :rtype: PublicKey
        :raises ValueError: If the sum of the public keys was invalid.
        """
        public_key = ffi.new('secp256k1_pubkey *')

        combined = lib.secp256k1_ec_pubkey_combine(
            context.ctx, public_key, [pk.public_key for pk in public_keys], len(public_keys)
        )

        if not combined:
            raise ValueError('The sum of the public keys is invalid.')

        return PublicKey(public_key, context)

    def format(self, compressed: bool = True) -> bytes:
        """
        Format the public key.

        :param compressed: Whether or to use the compressed format.
        :return: The 33 byte formatted public key, or the 65 byte formatted public key if `compressed` is `False`.
        """
        length = 33 if compressed else 65
        serialized = ffi.new('unsigned char [%d]' % length)
        output_len = ffi.new('size_t *', length)

        lib.secp256k1_ec_pubkey_serialize(
            self.context.ctx, serialized, output_len, self.public_key, EC_COMPRESSED if compressed else EC_UNCOMPRESSED
        )

        return bytes(ffi.buffer(serialized, length))

    def point(self) -> Tuple[int, int]:
        """
        :return: The public key as a coordinate point.
        """
        public_key = self.format(compressed=False)
        return bytes_to_int(public_key[1:33]), bytes_to_int(public_key[33:])

    def verify(self, signature: bytes, message: bytes, hasher: Hasher = sha256) -> bool:
        """
        :param signature: The ECDSA signature.
        :param message: The message that was supposedly signed.
        :param hasher: The hash function to use, which must return 32 bytes. By default,
                       the `sha256` algorithm is used. If `None`, no hashing occurs.
        :return: A boolean indicating whether or not the signature is correct.
        :raises ValueError: If the message hash was not 32 bytes long or the DER-encoded signature could not be parsed.
        """
        msg_hash = hasher(message) if hasher is not None else message
        if len(msg_hash) != 32:
            raise ValueError('Message hash must be 32 bytes long.')

        verified = lib.secp256k1_ecdsa_verify(self.context.ctx, der_to_cdata(signature), msg_hash, self.public_key)

        # A performance hack to avoid global bool() lookup.
        return not not verified

    def add(self, scalar: bytes, update: bool = False):
        """
        Add a scalar to the public key.

        :param scalar: The scalar with which to add.
        :param update: Whether or not to update and return the public key in-place.
        :return: The new public key, or the modified public key if `update` is `True`.
        :rtype: PublicKey
        :raises ValueError: If the tweak was out of range or the resulting public key was invalid.
        """
        scalar = pad_scalar(scalar)

        new_key = ffi.new('secp256k1_pubkey *', self.public_key[0])

        success = lib.secp256k1_ec_pubkey_tweak_add(self.context.ctx, new_key, scalar)

        if not success:
            raise ValueError('The tweak was out of range, or the resulting public key is invalid.')

        if update:
            self.public_key = new_key
            return self

        return PublicKey(new_key, self.context)

    def multiply(self, scalar: bytes, update: bool = False):
        """
        Multiply the public key by a scalar.

        :param scalar: The scalar with which to multiply.
        :param update: Whether or not to update and return the public key in-place.
        :return: The new public key, or the modified public key if `update` is `True`.
        :rtype: PublicKey
        """
        scalar = validate_secret(scalar)

        new_key = ffi.new('secp256k1_pubkey *', self.public_key[0])

        lib.secp256k1_ec_pubkey_tweak_mul(self.context.ctx, new_key, scalar)

        if update:
            self.public_key = new_key
            return self

        return PublicKey(new_key, self.context)

    def combine(self, public_keys, update: bool = False):
        """
        Add a number of public keys together.

        :param public_keys: A sequence of public keys.
        :type public_keys: List[PublicKey]
        :param update: Whether or not to update and return the public key in-place.
        :return: The combined public key, or the modified public key if `update` is `True`.
        :rtype: PublicKey
        :raises ValueError: If the sum of the public keys was invalid.
        """
        new_key = ffi.new('secp256k1_pubkey *')

        combined = lib.secp256k1_ec_pubkey_combine(
            self.context.ctx, new_key, [pk.public_key for pk in [self, *public_keys]], len(public_keys) + 1
        )

        if not combined:
            raise ValueError('The sum of the public keys is invalid.')

        if update:
            self.public_key = new_key
            return self

        return PublicKey(new_key, self.context)

    def __eq__(self, other) -> bool:
        return self.format(compressed=False) == other.format(compressed=False)


class PublicKeyXOnly:
    def __init__(self, data, parity: bool = False, context: Context = GLOBAL_CONTEXT):
        """A BIP340 `x-only` public key.

        :param data: The formatted public key.
        :type data: bytes
        :param parity: Whether the encoded point is the negation of the public key.
        :param context:
        """
        if not isinstance(data, bytes):
            self.public_key = data
        else:
            public_key = ffi.new('secp256k1_xonly_pubkey *')
            parsed = lib.secp256k1_xonly_pubkey_parse(context.ctx, public_key, data)
            if not parsed:
                raise ValueError('The public key could not be parsed or is invalid.')

            self.public_key = public_key

        self.parity = parity
        self.context = context

    @classmethod
    def from_secret(cls, secret: bytes, context: Context = GLOBAL_CONTEXT):
        """Derive an x-only public key from a private key secret.

        :param secret: The private key secret.
        :param context:
        :return: The x-only public key.
        """
        keypair = ffi.new('secp256k1_keypair *')
        res = lib.secp256k1_keypair_create(context.ctx, keypair, validate_secret(secret))
        if not res:
            raise ValueError('Secret was invalid')

        xonly_pubkey = ffi.new('secp256k1_xonly_pubkey *')
        pk_parity = ffi.new('int *')
        res = lib.secp256k1_keypair_xonly_pub(context.ctx, xonly_pubkey, pk_parity, keypair)

        return cls(xonly_pubkey, parity=not not pk_parity[0], context=context)

    @classmethod
    def from_valid_secret(cls, secret: bytes, context: Context = GLOBAL_CONTEXT):
        keypair = ffi.new('secp256k1_keypair *')
        res = lib.secp256k1_keypair_create(context.ctx, keypair, secret)
        if not res:
            raise ValueError('Secret was invalid')

        xonly_pubkey = ffi.new('secp256k1_xonly_pubkey *')
        pk_parity = ffi.new('int *')
        res = lib.secp256k1_keypair_xonly_pub(context.ctx, xonly_pubkey, pk_parity, keypair)

        return cls(xonly_pubkey, parity=not not pk_parity[0], context=context)

    def format(self) -> bytes:
        """Serialize the public key.

        :return: The public key serialized as 32 bytes.
        """
        output32 = ffi.new('unsigned char [32]')

        res = lib.secp256k1_xonly_pubkey_serialize(self.context.ctx, output32, self.public_key)
        if not res:
            raise ValueError('Public key in self.public_key must be valid')

        return bytes(ffi.buffer(output32, 32))

    def verify(self, signature: bytes, message: bytes) -> bool:
        """Verify a Schnorr signature over a given message.

        :param signature: The 64-byte Schnorr signature to verify.
        :param message: The message to be verified.
        :return: A boolean indicating whether or not the signature is correct.
        """
        if len(signature) != 64:
            raise ValueError('Signature must be 32 bytes long.')

        return not not lib.secp256k1_schnorrsig_verify(
            self.context.ctx, signature, message, len(message), self.public_key
        )

    def tweak_add(self, scalar: bytes):
        """Add a scalar to the public key.

        :param scalar: The scalar with which to add.
        :return: The modified public key.
        :rtype: PublicKeyXOnly
        :raises ValueError: If the tweak was out of range or the resulting public key was invalid.
        """
        scalar = pad_scalar(scalar)

        out_pubkey = ffi.new('secp256k1_pubkey *')
        res = lib.secp256k1_xonly_pubkey_tweak_add(self.context.ctx, out_pubkey, self.public_key, scalar)
        if not res:
            raise ValueError('The tweak was out of range, or the resulting public key would be invalid')

        pk_parity = ffi.new('int *')
        lib.secp256k1_xonly_pubkey_from_pubkey(self.context.ctx, self.public_key, pk_parity, out_pubkey)
        self.parity = not not pk_parity[0]

    def __eq__(self, other) -> bool:
        res = lib.secp256k1_xonly_pubkey_cmp(self.context.ctx, self.public_key, other.public_key)
        return res == 0
