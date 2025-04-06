from collections.abc import (
    Mapping,
)
from copy import (
    copy,
)
import json
import os
from typing import (
    Any,
    Dict,
    Optional,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from eth_keyfile import (
    create_keyfile_json,
    decode_keyfile_json,
)
from eth_keyfile.keyfile import (
    KDFType,
)
from eth_keys import (
    KeyAPI,
    keys,
)
from eth_keys.backends import (
    CoinCurveECCBackend,
    NativeECCBackend,
)
from eth_keys.datatypes import (
    PrivateKey,
)
from eth_keys.exceptions import (
    ValidationError,
)
from eth_typing import (
    ChecksumAddress,
    Hash32,
    HexStr,
)
from eth_utils import (
    to_canonical_address,
)
from eth_utils.curried import (
    combomethod,
    hexstr_if_str,
    is_dict,
    keccak,
    text_if_str,
    to_bytes,
    to_int,
)
from eth_utils.toolz import (
    dissoc,
)
from hexbytes import (
    HexBytes,
)

from eth_account._utils.legacy_transactions import (
    Transaction,
    vrs_from,
)
from eth_account._utils.signing import (
    hash_of_signed_transaction,
    sign_message_hash,
    sign_transaction_dict,
    to_standard_signature_bytes,
    to_standard_v,
)
from eth_account._utils.validation import (
    validate_and_set_default_kdf,
)
from eth_account.account_local_actions import (
    AccountLocalActions,
)
from eth_account.datastructures import (
    SignedMessage,
    SignedSetCodeAuthorization,
    SignedTransaction,
)
from eth_account.hdaccount import (
    ETHEREUM_DEFAULT_PATH,
    generate_mnemonic,
    key_from_seed,
    seed_from_mnemonic,
)
from eth_account.messages import (
    SignableMessage,
    _hash_eip191_message,
    encode_typed_data,
)
from eth_account.signers.local import (
    LocalAccount,
)
from eth_account.typed_transactions import (
    TypedTransaction,
)
from eth_account.typed_transactions.set_code_transaction import (
    Authorization,
)
from eth_account.types import (
    AuthorizationDict,
    Blobs,
    Language,
    PrivateKeyType,
    TransactionDictType,
)

VRS = TypeVar("VRS", bytes, HexStr, int)


class Account(AccountLocalActions):
    """
    The primary entry point for working with Ethereum private keys.

    It does **not** require a connection to an Ethereum node.
    """

    _keys = keys

    # Enable unaudited features (off by default)
    _use_unaudited_hdwallet_features = False

    _default_kdf: KDFType = validate_and_set_default_kdf()

    @classmethod
    def enable_unaudited_hdwallet_features(cls) -> None:
        """
        Use this flag to enable unaudited HD Wallet features.
        """
        cls._use_unaudited_hdwallet_features = True

    @combomethod
    def create(self, extra_entropy: Union[str, bytes, int] = "") -> LocalAccount:
        r"""
        Creates a new private key, and returns it as a
        :class:`~eth_account.local.LocalAccount`.

        :param extra_entropy: Add extra randomness to whatever randomness your OS
          can provide
        :type extra_entropy: str or bytes or int
        :returns: an object with private key and convenience methods

        .. code-block:: python

            >>> from eth_account import Account
            >>> acct = Account.create('KEYSMASH FJAFJKLDSKF7JKFDJ 1530')
            >>> acct.address
            '0x5ce9454909639D2D17A3F753ce7d93fa0b9aB12E'
            >>> acct.key
            HexBytes('0x8676e9a8c86c8921e922e61e0bb6e9e9689aad4c99082620610b00140e5f21b8')

            # These methods are also available: sign_message(), sign_transaction(),
            # encrypt().
            # They correspond to the same-named methods in Account.*
            # but without the private key argument
        """
        extra_key_bytes = text_if_str(to_bytes, extra_entropy)
        key_bytes = keccak(os.urandom(32) + extra_key_bytes)
        return cast(LocalAccount, self.from_key(key_bytes))

    @staticmethod
    def decrypt(keyfile_json: Union[str, Dict[str, Any]], password: str) -> HexBytes:
        """
        Decrypts a private key.

        The key may have been encrypted using an Ethereum client or
        :meth:`~Account.encrypt`.

        :param keyfile_json: The encrypted key
        :type keyfile_json: dict or str
        :param str password: The password that was used to encrypt the key
        :returns: the raw private key
        :rtype: ~hexbytes.main.HexBytes

        .. doctest:: python

            >>> encrypted = {
            ... 'address': '5ce9454909639D2D17A3F753ce7d93fa0b9aB12E',
            ... 'crypto': {'cipher': 'aes-128-ctr',
            ...  'cipherparams': {'iv': '482ef54775b0cc59f25717711286f5c8'},
            ...  'ciphertext': 'cb636716a9fd46adbb31832d964df2082536edd5399a3393327dc89b0193a2be',
            ...  'kdf': 'scrypt',
            ...  'kdfparams': {},
            ...  'kdfparams': {'dklen': 32,
            ...                'n': 262144,
            ...                'p': 8,
            ...                'r': 1,
            ...                'salt': 'd3c9a9945000fcb6c9df0f854266d573'},
            ...  'mac': '4f626ec5e7fea391b2229348a65bfef532c2a4e8372c0a6a814505a350a7689d'},
            ... 'id': 'b812f3f9-78cc-462a-9e89-74418aa27cb0',
            ... 'version': 3}
            >>> Account.decrypt(encrypted, 'password')
            HexBytes('0xb25c7db31feed9122727bf0939dc769a96564b2de4c4726d035b36ecf1e5b364')

        """  # noqa: E501
        if isinstance(keyfile_json, str):
            keyfile = json.loads(keyfile_json)
        elif is_dict(keyfile_json):
            keyfile = keyfile_json
        else:
            raise TypeError(
                "The keyfile should be supplied as a JSON string, or a dictionary."
            )
        password_bytes = text_if_str(to_bytes, password)
        # type ignored because eth_keyfile appears to be using the wrong type for
        # the password arg.
        # once fixed there, this should error and can be removed
        return HexBytes(decode_keyfile_json(keyfile, password_bytes))  # type: ignore[arg-type]  # noqa: E501

    @classmethod
    def encrypt(
        cls,
        private_key: PrivateKeyType,
        password: str,
        kdf: Optional[KDFType] = None,
        iterations: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Creates a dictionary with an encrypted version of your private key.
        To import this keyfile into Ethereum clients like geth and parity:
        encode this dictionary with :func:`json.dumps` and save it to disk where your
        client keeps key files.

        :param private_key: The raw private key
        :type private_key: hex str, bytes, int or :class:`eth_keys.datatypes.PrivateKey`
        :param str password: The password which you will need to unlock the account
          in your client
        :param str kdf: The key derivation function to use when encrypting your
          private key
        :param int iterations: The work factor for the key derivation function
        :returns: The data to use in your encrypted file
        :rtype: dict

        If kdf is not set, the default key derivation function falls back to the
        environment variable :envvar:`ETH_ACCOUNT_KDF`. If that is not set, then
        'scrypt' will be used as the default.

        .. doctest:: python

            >>> from pprint import pprint
            >>> encrypted = Account.encrypt(
            ...     0xb25c7db31feed9122727bf0939dc769a96564b2de4c4726d035b36ecf1e5b364,
            ...     'password'
            ... )
            >>> pprint(encrypted)
            {'address': '5ce9454909639D2D17A3F753ce7d93fa0b9aB12E',
             'crypto': {'cipher': 'aes-128-ctr',
                        'cipherparams': {'iv': '...'},
                        'ciphertext': '...',
                        'kdf': 'scrypt',
                        'kdfparams': {'dklen': 32,
                                      'n': 262144,
                                      'p': 1,
                                      'r': 8,
                                      'salt': '...'},
                        'mac': '...'},
             'id': '...',
             'version': 3}

            >>> with open('my-keyfile', 'w') as f: # doctest: +SKIP
            ...    f.write(json.dumps(encrypted))
        """
        if isinstance(private_key, keys.PrivateKey):
            key_bytes = private_key.to_bytes()
        else:
            key_bytes = HexBytes(private_key)

        if kdf is None:
            kdf = cls._default_kdf

        password_bytes = text_if_str(to_bytes, password)
        assert len(key_bytes) == 32

        # type ignored because eth_keyfile appears to be using the wrong type for
        # the password arg.
        # once fixed there, this should error and can be removed
        return create_keyfile_json(
            key_bytes, password_bytes, kdf=kdf, iterations=iterations  # type: ignore[arg-type]  # noqa: E501
        )

    @combomethod
    def from_key(self, private_key: PrivateKeyType) -> LocalAccount:
        r"""
        Returns a convenient object for working with the given private key.

        :param private_key: The raw private key
        :type private_key: hex str, bytes, int or :class:`eth_keys.datatypes.PrivateKey`
        :return: object with methods for signing and encrypting
        :rtype: LocalAccount

        .. doctest:: python

            >>> acct = Account.from_key(
            ... 0xb25c7db31feed9122727bf0939dc769a96564b2de4c4726d035b36ecf1e5b364)
            >>> acct.address
            '0x5ce9454909639D2D17A3F753ce7d93fa0b9aB12E'
            >>> acct.key
            HexBytes('0xb25c7db31feed9122727bf0939dc769a96564b2de4c4726d035b36ecf1e5b364')

            # These methods are also available: sign_message(), sign_transaction(),
            # encrypt(). They correspond to the same-named methods in Account.*
            # but without the private key argument
        """
        key = self._parse_private_key(private_key)
        return LocalAccount(key, self)

    @combomethod
    def from_mnemonic(
        self,
        mnemonic: str,
        passphrase: str = "",
        account_path: str = ETHEREUM_DEFAULT_PATH,
    ) -> LocalAccount:
        """
        Generate an account from a mnemonic.

        .. CAUTION:: This feature is experimental, unaudited, and likely to change soon

        :param str mnemonic: space-separated list of BIP39 mnemonic seed words
        :param str passphrase: Optional passphrase used to encrypt the mnemonic
        :param str account_path: Specify an alternate HD path for deriving the seed
            using BIP32 HD wallet key derivation.
        :return: object with methods for signing and encrypting
        :rtype: LocalAccount

        .. doctest:: python

            >>> from eth_account import Account
            >>> Account.enable_unaudited_hdwallet_features()
            >>> acct = Account.from_mnemonic(
            ...  "coral allow abandon recipe top tray caught video climb similar "
            ...  "prepare bracket antenna rubber announce gauge volume "
            ...  "hub hood burden skill immense add acid")
            >>> acct.address
            '0x9AdA5dAD14d925f4df1378409731a9B71Bc8569d'

            # These methods are also available: sign_message(), sign_transaction(),
            #  encrypt(). They correspond to the same-named methods in Account.*
            # but without the private key argument

        Or, generate multiple accounts from a mnemonic.

             >>> from eth_account import Account
             >>> Account.enable_unaudited_hdwallet_features()
             >>> iterator = 0
             >>> for i in range(10):
             ...     acct = Account.from_mnemonic(
             ...         "health embark april buyer eternal leopard "
             ...         "want before nominee head thing tackle",
             ...         account_path=f"m/44'/60'/0'/0/{iterator}")
             ...     iterator = iterator + 1
             ...     acct.address
             '0x61Cc15522D06983Ac7aADe23f9d5433d38e78195'
             '0x1240460F6E370f28079E5F9B52f9DcB759F051b7'
             '0xd30dC9f996539826C646Eb48bb45F6ee1D1474af'
             '0x47e64beb58c9A469c5eD086aD231940676b44e7C'
             '0x6D39032ffEF9987988a069F52EFe4d95D0770555'
             '0x3836A6530D1889853b047799Ecd8827255072e77'
             '0xed5490dEfF8d8FfAe45cb4066C3daC7C6BFF6a22'
             '0xf04F9Ff322799253bcC6B12762AD127570a092c5'
             '0x900F7fa9fbe85BB25b6cdB94Da24D807f7feb213'
             '0xa248e118b0D19010387b1B768686cd9B473FA137'

        .. CAUTION:: For the love of Bob please do not use this mnemonic,
                     it is for testing purposes only.

        """
        if not self._use_unaudited_hdwallet_features:
            raise AttributeError(
                "The use of the Mnemonic features of Account is disabled by "
                "default until its API stabilizes. To use these features, please "
                "enable them by running `Account.enable_unaudited_hdwallet_features()` "
                "and try again."
            )
        seed = seed_from_mnemonic(mnemonic, passphrase)
        private_key = key_from_seed(seed, account_path)
        key = self._parse_private_key(private_key)
        return LocalAccount(key, self)

    @combomethod
    def create_with_mnemonic(
        self,
        passphrase: str = "",
        num_words: int = 12,
        language: Union[Language, str] = Language.ENGLISH,
        account_path: str = ETHEREUM_DEFAULT_PATH,
    ) -> Tuple[LocalAccount, str]:
        r"""
        Create a new private key and related mnemonic.

        .. CAUTION:: This feature is experimental, unaudited, and likely to change soon

        Creates a new private key, and returns it as a
        :class:`~eth_account.local.LocalAccount`, alongside the mnemonic that can
        used to regenerate it using any BIP39-compatible wallet.

        :param str passphrase: Extra passphrase to encrypt the seed phrase
        :param int num_words: Number of words to use with seed phrase.
                              Default is 12 words.
                              Must be one of [12, 15, 18, 21, 24].
        :param (Language, str) language: Language to use for BIP39 mnemonic seed phrase.
                                         The use of a string is deprecated and will be
                                         removed in a future version.
        :param str account_path: Specify an alternate HD path for deriving the
            seed using BIP32 HD wallet key derivation.
        :returns: A tuple consisting of an object with private key and
                  convenience methods, and the mnemonic seed phrase that can be
                  used to restore the account.
        :rtype: (LocalAccount, str)

        .. doctest:: python

            >>> from eth_account import Account
            >>> Account.enable_unaudited_hdwallet_features()
            >>> acct, mnemonic = Account.create_with_mnemonic()
            >>> acct.address # doctest: +SKIP
            '0x5ce9454909639D2D17A3F753ce7d93fa0b9aB12E'
            >>> acct == Account.from_mnemonic(mnemonic)
            True

            # These methods are also available:
            # sign_message(), sign_transaction(), encrypt()
            # They correspond to the same-named methods in Account.*
            # but without the private key argument
        """
        if not self._use_unaudited_hdwallet_features:
            raise AttributeError(
                "The use of the Mnemonic features of Account is disabled by "
                "default until its API stabilizes. To use these features, please "
                "enable them by running `Account.enable_unaudited_hdwallet_features()` "
                "and try again."
            )
        mnemonic = generate_mnemonic(num_words, language)
        return self.from_mnemonic(mnemonic, passphrase, account_path), mnemonic

    @combomethod
    def recover_message(
        self,
        signable_message: SignableMessage,
        vrs: Optional[Tuple[VRS, VRS, VRS]] = None,
        signature: Optional[bytes] = None,
    ) -> ChecksumAddress:
        r"""
        Get the address of the account that signed the given message.
        You must specify exactly one of: vrs or signature

        :param signable_message: the message that was signed
        :param vrs: the three pieces generated by an elliptic curve signature
        :type vrs: tuple(v, r, s), each element is hex str, bytes or int
        :param signature: signature bytes concatenated as r+s+v
        :type signature: hex str or bytes or int
        :returns: address of signer, hex-encoded & checksummed
        :rtype: str

        .. doctest:: python

            >>> from eth_account.messages import encode_defunct
            >>> from eth_account import Account
            >>> message = encode_defunct(text="I♥SF")
            >>> vrs = (
            ...   28,
            ...   '0xe6ca9bba58c88611fad66a6ce8f996908195593807c4b38bd528d2cff09d4eb3',
            ...   '0x3e5bfbbf4d3e39b1a2fd816a7680c19ebebaf3a141b239934ad43cb33fcec8ce')
            >>> Account.recover_message(message, vrs=vrs)
            '0x5ce9454909639D2D17A3F753ce7d93fa0b9aB12E'


            # All of these recover calls are equivalent:

            # variations on vrs
            >>> vrs = (
            ...   '0x1c',
            ...   '0xe6ca9bba58c88611fad66a6ce8f996908195593807c4b38bd528d2cff09d4eb3',
            ...   '0x3e5bfbbf4d3e39b1a2fd816a7680c19ebebaf3a141b239934ad43cb33fcec8ce')
            >>> Account.recover_message(message, vrs=vrs)
            '0x5ce9454909639D2D17A3F753ce7d93fa0b9aB12E'

            >>> # Caution about this approach: likely problems if there are leading 0s
            >>> vrs = (
            ...   0x1c,
            ...   0xe6ca9bba58c88611fad66a6ce8f996908195593807c4b38bd528d2cff09d4eb3,
            ...   0x3e5bfbbf4d3e39b1a2fd816a7680c19ebebaf3a141b239934ad43cb33fcec8ce)
            >>> Account.recover_message(message, vrs=vrs)
            '0x5ce9454909639D2D17A3F753ce7d93fa0b9aB12E'

            >>> vrs = (
            ...   b'\x1c',
            ...   b'\xe6\xca\x9b\xbaX\xc8\x86\x11\xfa\xd6jl\xe8\xf9\x96\x90\x81\x95Y8\x07\xc4\xb3\x8b\xd5(\xd2\xcf\xf0\x9dN\xb3',
            ...   b'>[\xfb\xbfM>9\xb1\xa2\xfd\x81jv\x80\xc1\x9e\xbe\xba\xf3\xa1A\xb29\x93J\xd4<\xb3?\xce\xc8\xce')
            >>> Account.recover_message(message, vrs=vrs)
            '0x5ce9454909639D2D17A3F753ce7d93fa0b9aB12E'

            # variations on signature
            >>> signature = '0xe6ca9bba58c88611fad66a6ce8f996908195593807c4b38bd528d2cff09d4eb33e5bfbbf4d3e39b1a2fd816a7680c19ebebaf3a141b239934ad43cb33fcec8ce1c'
            >>> Account.recover_message(message, signature=signature)
            '0x5ce9454909639D2D17A3F753ce7d93fa0b9aB12E'
            >>> signature = b'\xe6\xca\x9b\xbaX\xc8\x86\x11\xfa\xd6jl\xe8\xf9\x96\x90\x81\x95Y8\x07\xc4\xb3\x8b\xd5(\xd2\xcf\xf0\x9dN\xb3>[\xfb\xbfM>9\xb1\xa2\xfd\x81jv\x80\xc1\x9e\xbe\xba\xf3\xa1A\xb29\x93J\xd4<\xb3?\xce\xc8\xce\x1c'
            >>> Account.recover_message(message, signature=signature)
            '0x5ce9454909639D2D17A3F753ce7d93fa0b9aB12E'
            >>> # Caution about this approach: likely problems if there are leading 0s
            >>> signature = 0xe6ca9bba58c88611fad66a6ce8f996908195593807c4b38bd528d2cff09d4eb33e5bfbbf4d3e39b1a2fd816a7680c19ebebaf3a141b239934ad43cb33fcec8ce1c
            >>> Account.recover_message(message, signature=signature)
            '0x5ce9454909639D2D17A3F753ce7d93fa0b9aB12E'
        """  # noqa: E501
        message_hash = _hash_eip191_message(signable_message)
        return cast(ChecksumAddress, self._recover_hash(message_hash, vrs, signature))

    @combomethod
    def _recover_hash(
        self,
        message_hash: Hash32,
        vrs: Optional[Tuple[VRS, VRS, VRS]] = None,
        signature: Optional[bytes] = None,
    ) -> ChecksumAddress:
        hash_bytes = HexBytes(message_hash)
        if len(hash_bytes) != 32:
            raise ValueError("The message hash must be exactly 32-bytes")
        if vrs is not None:
            v, r, s = map(hexstr_if_str(to_int), vrs)
            v_standard = to_standard_v(v)
            signature_obj = self._keys.Signature(vrs=(v_standard, r, s))
        elif signature is not None:
            signature_bytes = HexBytes(signature)
            signature_bytes_standard = to_standard_signature_bytes(signature_bytes)
            signature_obj = self._keys.Signature(
                signature_bytes=signature_bytes_standard
            )
        else:
            raise TypeError("You must supply the vrs tuple or the signature bytes")
        pubkey = signature_obj.recover_public_key_from_msg_hash(hash_bytes)
        return pubkey.to_checksum_address()

    @combomethod
    def recover_transaction(
        self, serialized_transaction: Union[HexStr, bytes, int]
    ) -> ChecksumAddress:
        """
        Get the address of the account that signed this transaction.

        :param serialized_transaction: the complete signed transaction
        :type serialized_transaction: hex str, bytes or int
        :returns: address of signer, hex-encoded & checksummed
        :rtype: ChecksumAddress

        .. doctest:: python

            >>> raw_transaction = '0xf86a8086d55698372431831e848094f0109fc8df283027b6285cc889f5aa624eac1f55843b9aca008025a009ebb6ca057a0535d6186462bc0b465b561c94a295bdb0621fc19208ab149a9ca0440ffd775ce91a833ab410777204d5341a6f9fa91216a6f3ee2c051fea6a0428'
            >>> Account.recover_transaction(raw_transaction)
            '0x2c7536E3605D9C16a7a3D7b1898e529396a65c23'
        """  # noqa: E501
        txn_bytes = HexBytes(serialized_transaction)
        if len(txn_bytes) > 0 and txn_bytes[0] <= 0x7F:
            # We are dealing with a typed transaction.
            typed_transaction = TypedTransaction.from_bytes(txn_bytes)
            msg_hash = typed_transaction.hash()
            vrs = typed_transaction.vrs()
            return cast(ChecksumAddress, self._recover_hash(msg_hash, vrs=vrs))

        txn = Transaction.from_bytes(txn_bytes)
        msg_hash = hash_of_signed_transaction(txn)
        return cast(ChecksumAddress, self._recover_hash(msg_hash, vrs=vrs_from(txn)))

    def set_key_backend(
        self, backend: Union[CoinCurveECCBackend, NativeECCBackend]
    ) -> None:
        """
        Change the backend used by the underlying eth-keys library.

        *(The default is fine for most users)*

        :param backend: any backend that works in
            `eth_keys.KeyApi(backend)
            <https://github.com/ethereum/eth-keys/#keyapibackendnone>`_

        """
        self._keys = KeyAPI(backend)

    @combomethod
    def sign_message(
        self,
        signable_message: SignableMessage,
        private_key: PrivateKeyType,
    ) -> SignedMessage:
        r"""
        Sign the provided message.

        This API supports any messaging format that will encode to EIP-191 messages.

        If you would like historical compatibility with :meth:`w3.eth.sign() <web3.eth.Eth.sign>`
        you can use :meth:`~eth_account.messages.encode_defunct`.

        Other options are the "validator", or "structured data" standards.
        You can import all supported message encoders in
        ``eth_account.messages``.

        :param signable_message: the encoded message for signing
        :param private_key: the key to sign the message with
        :type private_key: hex str, bytes, int or :class:`eth_keys.datatypes.PrivateKey`
        :returns: Various details about the signature - most importantly the
            fields: v, r, and s
        :rtype: ~eth_account.datastructures.SignedMessage

        .. doctest:: python

            >>> msg = "I♥SF"
            >>> from eth_account.messages import encode_defunct
            >>> msghash = encode_defunct(text=msg)
            >>> msghash
            SignableMessage(version=b'E',
             header=b'thereum Signed Message:\n6',
             body=b'I\xe2\x99\xa5SF')
            >>> # If you're curious about the internal fields of SignableMessage, take a look at EIP-191, linked above
            >>> key = "0xb25c7db31feed9122727bf0939dc769a96564b2de4c4726d035b36ecf1e5b364"
            >>> Account.sign_message(msghash, key)
            SignedMessage(message_hash=HexBytes('0x1476abb745d423bf09273f1afd887d951181d25adc66c4834a70491911b7f750'),
             r=104389933075820307925104709181714897380569894203213074526835978196648170704563,
             s=28205917190874851400050446352651915501321657673772411533993420917949420456142,
             v=28,
             signature=HexBytes('0xe6ca9bba58c88611fad66a6ce8f996908195593807c4b38bd528d2cff09d4eb33e5bfbbf4d3e39b1a2fd816a7680c19ebebaf3a141b239934ad43cb33fcec8ce1c'))



        .. _EIP-191: https://eips.ethereum.org/EIPS/eip-191
        """  # noqa: E501
        message_hash = _hash_eip191_message(signable_message)
        return cast(SignedMessage, self._sign_hash(message_hash, private_key))

    @combomethod
    def unsafe_sign_hash(
        self, message_hash: Union[HexStr, bytes, int], private_key: PrivateKeyType
    ) -> SignedMessage:
        """
        Sign the provided hash.

        .. WARNING:: *Never* sign a hash that you didn't generate,
            it can be an arbitrary transaction. For example, it might
            send all of your account's ether to an attacker.
            Instead, prefer :meth:`~eth_account.account.Account.sign_message`,
            which cannot accidentally sign a transaction.

        :param message_hash: the 32-byte message hash to be signed
        :type message_hash: hex str, bytes or int
        :param private_key: the key to sign the message with
        :type private_key: hex str, bytes, int or :class:`eth_keys.datatypes.PrivateKey`
        :returns: Various details about the signature - most
          importantly the fields: v, r, and s
        :rtype: ~eth_account.datastructures.SignedMessage
        """
        return cast(SignedMessage, self._sign_hash(message_hash, private_key))

    @combomethod
    def _sign_hash(
        self,
        message_hash: Hash32,
        private_key: PrivateKeyType,
    ) -> SignedMessage:
        msg_hash_bytes = HexBytes(message_hash)
        if len(msg_hash_bytes) != 32:
            raise ValueError("The message hash must be exactly 32-bytes")

        key = self._parse_private_key(private_key)

        (v, r, s, eth_signature_bytes) = sign_message_hash(key, msg_hash_bytes)
        return SignedMessage(
            message_hash=msg_hash_bytes,
            r=r,
            s=s,
            v=v,
            signature=HexBytes(eth_signature_bytes),
        )

    @combomethod
    def sign_transaction(
        self,
        transaction_dict: TransactionDictType,
        private_key: PrivateKeyType,
        blobs: Optional[Blobs] = None,
    ) -> SignedTransaction:
        r"""
        Sign a transaction using a local private key.

        It produces signature details and the hex-encoded transaction suitable for
        broadcast using :meth:`w3.eth.send_raw_transaction()<web3.eth.Eth.send_raw_transaction>`.

        To create the transaction dict that calls a contract, use
        :meth:`my_contract.functions.myFunction().build_transaction()<web3.contract.ContractFunction.build_transaction>`.

        Note: For non-legacy (typed) transactions, if the transaction type is not
        explicitly provided, it may be determined from the transaction parameters of
        a well-formed transaction. See below for examples on how to sign with
        different transaction types.

        :param dict transaction_dict: the transaction with available keys, depending
          on the type of transaction: nonce, chainId, to, data, value, gas, gasPrice,
          type, accessList, maxFeePerGas, and maxPriorityFeePerGas
        :param private_key: the private key to sign the data with
        :type private_key: hex str, bytes, int or :class:`eth_keys.datatypes.PrivateKey`
        :param blobs: optional list of blobs to sign in addition to the transaction
        :type blobs: list of bytes or HexBytes
        :returns: Various details about the signature - most
          importantly the fields: v, r, and s
        :rtype: SignedTransaction

        .. doctest:: python

            >>> # EIP-1559 dynamic fee transaction (more efficient and preferred over legacy txn)
            >>> from eth_account import Account
            >>> dynamic_fee_transaction = {
            ...     "type": 2,  # optional - can be implicitly determined based on max fee params
            ...     "gas": 100000,
            ...     "maxFeePerGas": 2000000000,
            ...     "maxPriorityFeePerGas": 2000000000,
            ...     "data": "0x616263646566",
            ...     "nonce": 34,
            ...     "to": "0x09616C3d61b3331fc4109a9E41a8BDB7d9776609",
            ...     "value": "0x5af3107a4000",
            ...     "accessList": (  # optional
            ...         {
            ...             "address": "0x0000000000000000000000000000000000000001",
            ...             "storageKeys": (
            ...                 "0x0100000000000000000000000000000000000000000000000000000000000000",
            ...             )
            ...         },
            ...     ),
            ...     "chainId": 1337,
            ... }
            >>> key = '0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318'
            >>> signed_df_tx = Account.sign_transaction(dynamic_fee_transaction, key)
            >>> signed_df_tx
            SignedTransaction(raw_transaction=HexBytes('0x02f8b28205392284773594008477359400830186a09409616c3d61b3331fc4109a9e41a8bdb7d9776609865af3107...d58b85d5'),
             hash=HexBytes('0x2721b2ac99d878695e410af9e8968859b6f6e94f544840be0eb2935bead7deba'),
             r=48949965662841329840326477994465373664672499148507933176648302825256944281697,
             s=1123041608316060268133200864147951676126406077675157976022772782796802590165,
             v=1)
            >>> w3.eth.send_raw_transaction(signed_df_tx.raw_transaction)  # doctest: +SKIP

        .. doctest:: python

            >>> # legacy transaction (less efficient than EIP-1559 dynamic fee txn)
            >>> from eth_account import Account
            >>> legacy_transaction = {
            ...     # Note that the address must be in checksum format or native bytes:
            ...     'to': '0xF0109fC8DF283027b6285cc889F5aA624EaC1F55',
            ...     'value': 1000000000,
            ...     'gas': 2000000,
            ...     'gasPrice': 234567897654321,
            ...     'nonce': 0,
            ...     'chainId': 1337
            ... }
            >>> key = '0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318'
            >>> signed_legacy_tx = Account.sign_transaction(legacy_transaction, key)
            >>> signed_legacy_tx
            SignedTransaction(raw_transaction=HexBytes('0xf86c8086d55698372431831e848094f0109fc8df283027b6285cc889f5aa624eac1f55843b9aca0080820a95a01a7...c0bfdb52'),
             hash=HexBytes('0xd0a3e5dc7439f260c64cb0220139ec5dc7e016f82ce272a25a0f0b38fe751673'),
             r=11971260903864915610009019893820767192081275151191539081612245320300335068143,
             s=35365272040292958794699923036506252105590820339897221552886630515981233937234,
             v=2709)
            >>> w3.eth.send_raw_transaction(signed_legacy_tx.raw_transaction)  # doctest: +SKIP

        .. doctest:: python

            >>> from eth_account import Account
            >>> access_list_transaction = {
            ...     "type": 1,  # optional - can be implicitly determined based on 'accessList' and 'gasPrice' params
            ...     "gas": 100000,
            ...     "gasPrice": 1000000000,
            ...     "data": "0x616263646566",
            ...     "nonce": 34,
            ...     "to": "0x09616C3d61b3331fc4109a9E41a8BDB7d9776609",
            ...     "value": "0x5af3107a4000",
            ...     "accessList": (
            ...         {
            ...             "address": "0x0000000000000000000000000000000000000001",
            ...             "storageKeys": (
            ...                 "0x0100000000000000000000000000000000000000000000000000000000000000",
            ...             )
            ...         },
            ...     ),
            ...     "chainId": 1337,
            ... }
            >>> key = '0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318'
            >>> signed_al_tx = Account.sign_transaction(access_list_transaction, key)
            >>> signed_al_tx
            SignedTransaction(raw_transaction=HexBytes('0x01f8ad82053922843b9aca00830186a09409616c3d61b3331fc4109a9e41a8bdb7d9776609865af3107a400086616...2b5043ea'),
             hash=HexBytes('0xca9af2ef41691e06eb07e02125938fd9bb5a311e8daf330b264e77d6cdf3d17e'),
             r=107355854401379915513092408112372039746594668141865279802319959599514133709188,
             s=6729502936685237038651223791038758905953302464070244934323623239104475448298,
             v=1)
            >>> w3.eth.send_raw_transaction(signed_al_tx.raw_transaction)  # doctest: +SKIP

        .. doctest:: python

            >>> from eth_account import Account
            >>> blob_transaction = {
            ...    "type": 3,  # optional - can be implicitly determined based on `maxFeePerBlobGas` param
            ...    "gas": 100000,
            ...    "maxFeePerGas": 2000000000,
            ...    "maxPriorityFeePerGas": 2000000000,
            ...    "maxFeePerBlobGas": 2000000000,
            ...    "data": "0x616263646566",
            ...    "nonce": 34,
            ...    "to": "0x09616C3d61b3331fc4109a9E41a8BDB7d9776609",
            ...    "value": "0x5af3107a4000",
            ...    "accessList": (  # optional
            ...        {
            ...            "address": "0x0000000000000000000000000000000000000001",
            ...            "storageKeys": (
            ...                "0x0100000000000000000000000000000000000000000000000000000000000000",
            ...            )
            ...        },
            ...    ),
            ...    "chainId": 1337,
            ... }
            >>> empty_blob = b"\x00" * 32 * 4096  # 4096 empty 32-byte field elements
            >>> key = '0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318'

            >>> # The `blobVersionedHashes` transaction field is calculated from the `blobs` kwarg
            >>> signed_blob_tx = Account.sign_transaction(blob_transaction, key, blobs=[empty_blob])
            >>> signed_blob_tx
            SignedTransaction(raw_transaction=HexBytes('0x03fa020147f8d98205392284773594008477359400830186a09409616c3d61b3331fc4109a9e41a8bdb7d97766098...00000000'),
             hash=HexBytes('0xf9dc8867c4324fd7f4506622aa700989562770f01d7d681cef74a1a1deb9fea9'),
             r=14319949980593194209648175507603206696573324965145502821772573913457715875718,
             s=9129184742597516615341309773045281461399831333162885393648678700392065987233,
             v=1)
            >>> w3.eth.send_raw_transaction(signed_blob_tx.raw_transaction)  # doctest: +SKIP
        """  # noqa: E501
        if not isinstance(transaction_dict, Mapping):
            raise TypeError(
                f"transaction_dict must be dict-like, got {repr(transaction_dict)}"
            )

        account = self.from_key(private_key)

        # allow from field, *only* if it matches the private key
        if "from" in transaction_dict:
            if transaction_dict["from"] == account.address:
                sanitized_transaction = dissoc(transaction_dict, "from")
            else:
                str_from = (
                    transaction_dict["from"].decode()
                    if isinstance(transaction_dict["from"], bytes)
                    else transaction_dict["from"]
                )
                raise TypeError(
                    f"from field must match key's {account.address}, but it was "
                    f"{str_from}"
                )
        else:
            sanitized_transaction = transaction_dict

        # sign transaction
        (
            v,
            r,
            s,
            encoded_transaction,
        ) = sign_transaction_dict(account._key_obj, sanitized_transaction, blobs=blobs)
        transaction_hash = keccak(encoded_transaction)

        return SignedTransaction(
            raw_transaction=HexBytes(encoded_transaction),
            hash=HexBytes(transaction_hash),
            r=r,
            s=s,
            v=v,
        )

    @combomethod
    def _parse_private_key(
        self,
        key: PrivateKeyType,
    ) -> PrivateKey:
        """
        Generate a :class:`eth_keys.datatypes.PrivateKey` from the provided key.

        If the key is already of type :class:`eth_keys.datatypes.PrivateKey`,
        return the key.

        :param key: the private key from which a :class:`eth_keys.datatypes.PrivateKey`
                    will be generated
        :type key: hex str, bytes, int or :class:`eth_keys.datatypes.PrivateKey`
        :returns: the provided key represented as a
                  :class:`eth_keys.datatypes.PrivateKey`
        """
        if isinstance(key, self._keys.PrivateKey):
            return key

        hb_key = HexBytes(key)

        try:
            return self._keys.PrivateKey(hb_key)
        except ValidationError as original_exception:
            raise ValueError(
                "The private key must be exactly 32 bytes long, instead of "
                f"{len(hb_key)} bytes."
            ) from original_exception

    @combomethod
    def sign_typed_data(
        self,
        private_key: PrivateKeyType,
        domain_data: Optional[Dict[str, Any]] = None,
        message_types: Optional[Dict[str, Any]] = None,
        message_data: Optional[Dict[str, Any]] = None,
        full_message: Optional[Dict[str, Any]] = None,
    ) -> SignedMessage:
        r"""
        Sign the provided EIP-712 message with the provided key.

        :param private_key: the key to sign the message with
        :param domain_data: EIP712 domain data
        :param message_types: custom types used by the `value` data
        :param message_data: data to be signed
        :param full_message: a dict containing all data and types
        :type private_key: hex str, bytes, int or :class:`eth_keys.datatypes.PrivateKey`
        :type domain_data: dict
        :type message_types: dict
        :type message_data: dict
        :type full_message: dict
        :returns: Various details about the signature - most importantly the
            fields: v, r, and s
        :rtype: ~eth_account.datastructures.SignedMessage

        You may supply the information to be encoded in one of two ways:

        As exactly three arguments:

            - ``domain_data``, a dict of the EIP-712 domain data
            - ``message_types``, a dict of custom types (do not include a ``EIP712Domain``
              key)
            - ``message_data``, a dict of the data to be signed

        Or as a single argument:

            - ``full_message``, a dict containing the following keys:
                - ``types``, a dict of custom types (may include a ``EIP712Domain`` key)
                - ``primaryType``, (optional) a string of the primary type of the message
                - ``domain``, a dict of the EIP-712 domain data
                - ``message``, a dict of the data to be signed

        .. WARNING:: Note that this code has not gone through an external audit, and
            the test cases are incomplete.

        See documentation for :meth:`~eth_account.messages.encode_typed_data` for usage details

        See the `EIP-712 spec <https://eips.ethereum.org/EIPS/eip-712>`_ for more information.

        .. doctest:: python

            >>> # examples of basic usage
            >>> from eth_account import Account
            >>> # 3-argument usage

            >>> # all domain properties are optional
            >>> domain_data = {
            ...     "name": "Ether Mail",
            ...     "version": "1",
            ...     "chainId": 1,
            ...     "verifyingContract": "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC",
            ...     "salt": b"decafbeef",
            ... }
            >>> # custom types
            >>> message_types = {
            ...     "Person": [
            ...         {"name": "name", "type": "string"},
            ...         {"name": "wallet", "type": "address"},
            ...     ],
            ...     "Mail": [
            ...         {"name": "from", "type": "Person"},
            ...         {"name": "to", "type": "Person"},
            ...         {"name": "contents", "type": "string"},
            ...     ],
            ... }
            >>> # the data to be signed
            >>> message_data = {
            ...     "from": {
            ...         "name": "Cow",
            ...         "wallet": "0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826",
            ...     },
            ...     "to": {
            ...         "name": "Bob",
            ...         "wallet": "0xbBbBBBBbbBBBbbbBbbBbbbbBBbBbbbbBbBbbBBbB",
            ...     },
            ...     "contents": "Hello, Bob!",
            ... }
            >>> key = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            >>> signed_message = Account.sign_typed_data(key, domain_data, message_types, message_data)
            >>> signed_message.message_hash
            HexBytes('0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530')

            >>> # 1-argument usage

            >>> # all domain properties are optional
            >>> full_message = {
            ...     "types": {
            ...         "EIP712Domain": [
            ...             {"name": "name", "type": "string"},
            ...             {"name": "version", "type": "string"},
            ...             {"name": "chainId", "type": "uint256"},
            ...             {"name": "verifyingContract", "type": "address"},
            ...             {"name": "salt", "type": "bytes32"},
            ...         ],
            ...         "Person": [
            ...             {"name": "name", "type": "string"},
            ...             {"name": "wallet", "type": "address"},
            ...         ],
            ...         "Mail": [
            ...             {"name": "from", "type": "Person"},
            ...             {"name": "to", "type": "Person"},
            ...             {"name": "contents", "type": "string"},
            ...         ],
            ...     },
            ...     "primaryType": "Mail",
            ...     "domain": {
            ...         "name": "Ether Mail",
            ...         "version": "1",
            ...         "chainId": 1,
            ...         "verifyingContract": "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC",
            ...         "salt": b"decafbeef"
            ...     },
            ...     "message": {
            ...         "from": {
            ...             "name": "Cow",
            ...             "wallet": "0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826"
            ...         },
            ...         "to": {
            ...             "name": "Bob",
            ...             "wallet": "0xbBbBBBBbbBBBbbbBbbBbbbbBBbBbbbbBbBbbBBbB"
            ...         },
            ...         "contents": "Hello, Bob!",
            ...     },
            ... }
            >>> signed_message_2 = Account.sign_typed_data(key, full_message=full_message)
            >>> signed_message_2.message_hash
            HexBytes('0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530')
            >>> signed_message_2 == signed_message
            True

        .. _EIP-712: https://eips.ethereum.org/EIPS/eip-712
        """  # noqa: E501
        signable_message = encode_typed_data(
            domain_data,
            message_types,
            message_data,
            full_message,
        )
        message_hash = _hash_eip191_message(signable_message)
        return cast(SignedMessage, self._sign_hash(message_hash, private_key))

    @combomethod
    def sign_authorization(
        self,
        authorization_dict: AuthorizationDict,
        private_key: PrivateKeyType,
    ) -> SignedSetCodeAuthorization:
        r"""
        Sign an authorization using a local private key to be included in a EIP-7702 transaction.

        :param dict authorization_dict: the required keys are: ``chainId``, ``address``, and ``nonce``
        :param private_key: the private key to sign the data with
        :type private_key: hex str, bytes, int or :class:`eth_keys.datatypes.PrivateKey`
        :returns: the dictionary with the signature fields added, suitable for inclusion in a EIP-7702 transaction
        :rtype: dict

        .. NOTE::
            You need to sign one or more authorizations from an EOA willing to have a smart contract code associated with the EOA for the life of the transaction.
            The variable ``auth`` in the code below is the authorization dictionary containing the following keys:

            - ``chainId`` is the chain id for the chain where the EOA is located. If ``0`` is specified, authorization is signed for all chains
            - ``address`` is the address of the smart contract code to be associated with the EOA, as bytes
            - ``nonce`` is the nonce of the EOA, used to prevent replay attacks

            To create a transaction that associates the code with the EOA, you need to create a transaction with an ``authorizationList``, representing a list of signed authorizations for the transaction.

        .. doctest:: python

            >>> from eth_account import Account

            >>> key = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            >>> auth = {
            ...     "chainId": 1337,
            ...     "address": "0x5ce9454909639d2d17a3f753ce7d93fa0b9ab12e",
            ...     "nonce": 0,
            ... }

            >>> signed_auth = Account.sign_authorization(auth, key)
            >>> signed_auth
            SignedSetCodeAuthorization(chain_id=1337,
             address=b'\\\xe9EI\tc\x9d-\x17\xa3\xf7S\xce}\x93\xfa\x0b\x9a\xb1.',
             nonce=0,
             y_parity=0,
             r=13559089679153465389530080958732165835506259206033627652019224547096284912193,
             s=4909893498344689684383026337158184903862784607939660326835239278207516636646,
             signature='0x1dfa2c3c5b3bf61e364f7ce7ed744aef498fe26c981de726b139e0461c545a410adae6b7a1ff6137fb698a9973f4706cf8fe56aba87e8241b76042af587175e600',
             authorization_hash=HexBytes('0x5a1bfd35dee8528cbcbe2dad796fec10b7ad15fa67ecc77c427d0d57bc5e2737'))

            >>> tx = {
            ...     "gas": 100000,
            ...     "maxFeePerGas": 2000000000,
            ...     "maxPriorityFeePerGas": 2000000000,
            ...     "data": "0x616263646566",
            ...     "nonce": 34,
            ...     "to": "0x09616C3d61b3331fc4109a9E41a8BDB7d9776609",
            ...     "value": "0x5af3107a4000",
            ...     "accessList": (),
            ...     "authorizationList": [signed_auth],
            ...     "chainId": 1337,
            ... }
            >>> signed = Account.sign_transaction(tx, key)
            >>> w3.eth.send_raw_transaction(signed.raw_transaction)  # doctest: +SKIP

        .. _EIP-7702: https://eips.ethereum.org/EIPS/eip-7702
        """  # noqa: E501
        if not isinstance(authorization_dict, Mapping):
            raise TypeError(
                f"authorization_dict must be dict-like, got {repr(authorization_dict)}"
            )

        authority_key = self._parse_private_key(private_key)

        # prevent mutating the original input
        authorization_dict = copy(authorization_dict)

        chain_id = authorization_dict["chainId"]
        code_address = to_canonical_address(authorization_dict["address"])
        nonce = authorization_dict["nonce"]

        unsigned_authorization = Authorization(chain_id, code_address, nonce)
        authorization_hash = unsigned_authorization.hash()
        signature = authority_key.sign_msg_hash(authorization_hash)
        [v, r, s] = signature.vrs

        return SignedSetCodeAuthorization(
            chain_id=chain_id,
            address=code_address,
            nonce=nonce,
            y_parity=v,
            r=r,
            s=s,
            signature=signature,
            authorization_hash=authorization_hash,
        )
