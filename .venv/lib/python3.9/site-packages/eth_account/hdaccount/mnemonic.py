# Originally from: https://github.com/trezor/python-mnemonic
#
# Copyright (c) 2013 Pavol Rusnak
# Copyright (c) 2017 mruddy
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do
# so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
import os
from pathlib import (
    Path,
)
import secrets
from typing import (
    Dict,
    List,
    Union,
)
import warnings

from bitarray import (
    bitarray,
)
from bitarray.util import (
    ba2int,
    int2ba,
)
from eth_utils import (
    ValidationError,
)

from eth_account.types import (
    Language,
)

from ._utils import (
    pbkdf2_hmac_sha512,
    sha256,
    unicode_decompose_string,
)

VALID_ENTROPY_SIZES = [16, 20, 24, 28, 32]
VALID_WORD_COUNTS = [12, 15, 18, 21, 24]
WORDLIST_DIR = Path(__file__).parent / "wordlist"
WORDLIST_LEN = 2048

_cached_wordlists: Dict[str, List[str]] = dict()


def get_wordlist(language: str) -> List[str]:
    if language in _cached_wordlists.keys():
        return _cached_wordlists[language]
    with open(WORDLIST_DIR / f"{language}.txt", encoding="utf-8") as f:
        wordlist = [w.strip() for w in f.readlines()]
    if len(wordlist) != WORDLIST_LEN:
        raise ValidationError(
            f"Wordlist should contain {WORDLIST_LEN} words, "
            f"but it contains {len(wordlist)} words."
        )
    _cached_wordlists[language] = wordlist
    return wordlist


class Mnemonic:
    r"""
    Creates and validates BIP39 mnemonics.

    .. doctest:: python

        >>> from eth_account.hdaccount import Language, Mnemonic

        >>> # Create a new Mnemonic instance with Czech language
        >>> cz_mnemonic = Mnemonic(Language.CZECH)

        >>> # English is the default language
        >>> en_mnemonic = Mnemonic()

        >>> # List available languages
        >>> available_languages = Mnemonic.list_languages()
        >>> print(available_languages)
        ['chinese_simplified', 'chinese_traditional', 'czech', 'english', 'french', 'italian', 'japanese', 'korean', 'spanish']

        >>> # List available enumerated languages
        >>> available_languages = Mnemonic.list_languages_enum()
        >>> print(available_languages)
        [<Language.CHINESE_SIMPLIFIED: 'chinese_simplified'>, <Language.CHINESE_TRADITIONAL: 'chinese_traditional'>, <Language.CZECH: 'czech'>, <Language.ENGLISH: 'english'>, <Language.FRENCH: 'french'>, <Language.ITALIAN: 'italian'>, <Language.JAPANESE: 'japanese'>, <Language.KOREAN: 'korean'>, <Language.SPANISH: 'spanish'>]

        >>> # Generate a new mnemonic phrase
        >>> mnemonic_phrase = en_mnemonic.generate()
        >>> print(mnemonic_phrase) # doctest: +SKIP
        'cabin raise oven oven knock fantasy flock letter click empty skate volcano'

        >>> # Validate a mnemonic phrase
        >>> is_valid = en_mnemonic.is_mnemonic_valid(mnemonic_phrase)
        >>> print(is_valid)
        True

        >>> # Convert mnemonic phrase to seed
        >>> seed = en_mnemonic.to_seed(mnemonic_phrase, passphrase="optional passphrase")
        >>> print(seed) # doctest: +SKIP
        b'\x97ii\x07\x12\xf0$\x81\x98\xb6?\x07\x08t7\x18d\x87\xe1\x7f\xbe\xbaL\xb4i%\xeb\x12\xce\xe2h\x1c\xb2\x19\x13\xfb9wtoV\x9c\xb8\xdf;5\xba4X\xa3\xd6b`|\xdc\xb1\x10\xb0\xeeS\x86\x95\xd75'
    """  # noqa: E501

    def __init__(self, raw_language: Union[Language, str] = Language.ENGLISH):
        if isinstance(raw_language, str):
            warnings.warn(
                "The language parameter should be a Language enum, not a string. "
                "This will be enforced in a future version.",
                DeprecationWarning,
                stacklevel=2,
            )

            language = raw_language.lower().replace(" ", "_")
            languages = Mnemonic.list_languages()
            if language not in languages:
                raise ValidationError(
                    f"Invalid language choice '{language}', must be one of {languages}"
                )
        else:
            language = raw_language.value
        self.language = language
        self.wordlist = get_wordlist(self.language)

    @staticmethod
    def list_languages() -> List[str]:
        """
        Returns a list of languages available for the seed phrase
        """
        return sorted(Path(f).stem for f in WORDLIST_DIR.rglob("*.txt"))

    @staticmethod
    def list_languages_enum() -> List[Language]:
        """
        Returns a list of Language objects available for the seed phrase
        """
        return sorted(Language(Path(f).stem) for f in WORDLIST_DIR.rglob("*.txt"))

    @classmethod
    def detect_language(cls, raw_mnemonic: str) -> Language:
        mnemonic = unicode_decompose_string(raw_mnemonic)

        words = set(mnemonic.split(" "))
        matching_languages = {
            lang
            for lang in Mnemonic.list_languages()
            if len(words.intersection(cls(Language(lang)).wordlist)) == len(words)
        }

        # No language had all words match it, so the language can't be fully determined
        if len(matching_languages) < 1:
            raise ValidationError(f"Language not detected for word(s): {raw_mnemonic}")

        # If both chinese simplified and chinese traditional match (because one is a
        # subset of the other) then return simplified. This doesn't hold for
        # other languages.
        if len(matching_languages) == 2 and all(
            "chinese" in lang for lang in matching_languages
        ):
            return Language.CHINESE_SIMPLIFIED

        # Because certain wordlists share some similar words, if we detect multiple
        # languages that the provided mnemonic word(s) could be valid in, we have
        # to throw
        if len(matching_languages) > 1:
            raise ValidationError(
                f"Word(s) are valid in multiple languages: {raw_mnemonic}"
            )

        (language,) = matching_languages
        return Language(language)

    def generate(self, num_words: int = 12) -> str:
        """
        Generate a new mnemonic with the specified number of words.
        """
        if num_words not in VALID_WORD_COUNTS:
            raise ValidationError(
                f"Invalid choice for number of words: {num_words}, should be one of "
                f"{VALID_WORD_COUNTS}"
            )
        return self.to_mnemonic(os.urandom(4 * num_words // 3))  # 4/3 bytes per word

    def to_mnemonic(self, entropy: bytes) -> str:
        entropy_size = len(entropy)
        if entropy_size not in VALID_ENTROPY_SIZES:
            raise ValidationError(
                f"Invalid data length {len(entropy)}, should be one of "
                f"{VALID_ENTROPY_SIZES}"
            )

        bits = bitarray()
        bits.frombytes(entropy)

        checksum = bitarray()
        checksum.frombytes(sha256(entropy))

        # Add enough bits from the checksum to make it modulo 11 (2**11 = 2048)
        bits.extend(checksum[: entropy_size // 4])
        indices = tuple(
            ba2int(bits[i * 11 : (i + 1) * 11]) for i in range(len(bits) // 11)
        )
        words = tuple(self.wordlist[idx] for idx in indices)

        if self.language == "japanese":  # Japanese must be joined by ideographic space.
            phrase = "\u3000".join(words)
        else:
            phrase = " ".join(words)
        return phrase

    def is_mnemonic_valid(self, mnemonic: str) -> bool:
        """
        Checks if mnemonic is valid

        :param str mnemonic: Mnemonic string
        """
        words = unicode_decompose_string(mnemonic).split(" ")
        num_words = len(words)

        if num_words not in VALID_WORD_COUNTS:
            return False

        try:
            indices = tuple(self.wordlist.index(w) for w in words)
        except ValueError:
            return False

        encoded_seed = bitarray()
        for idx in indices:
            # Build bitarray from tightly packing indices (which are 11-bits integers)
            encoded_seed.extend(int2ba(idx, length=11))

        entropy_size = 4 * num_words // 3

        # Checksum the raw entropy bits
        checksum = bitarray()
        checksum.frombytes(sha256(encoded_seed[: entropy_size * 8].tobytes()))
        computed_checksum = checksum[: len(encoded_seed) - entropy_size * 8].tobytes()

        # Extract the stored checksum bits
        stored_checksum = encoded_seed[entropy_size * 8 :].tobytes()

        # Check that the stored matches the relevant slice of the actual checksum
        # NOTE: Use secrets.compare_digest for protection again timing attacks
        return secrets.compare_digest(stored_checksum, computed_checksum)

    def expand_word(self, prefix: str) -> str:
        if prefix in self.wordlist:
            return prefix
        else:
            matches: List[str] = [
                word for word in self.wordlist if word.startswith(prefix)
            ]
            if len(matches) == 1:  # matched exactly one word in the wordlist
                return matches[0]
            else:
                # exact match not found.
                # this is not a validation routine, just return the input
                return prefix

    def expand(self, mnemonic: str) -> str:
        return " ".join(map(self.expand_word, mnemonic.split(" ")))

    @classmethod
    def to_seed(cls, checked_mnemonic: str, passphrase: str = "") -> bytes:
        """
        :param str checked_mnemonic: Must be a correct, fully-expanded BIP39 seed phrase
        :param str passphrase: Encryption passphrase used to secure the mnemonic
        :returns bytes: 64 bytes of raw seed material from PRNG
        """
        mnemonic = unicode_decompose_string(checked_mnemonic)
        # NOTE: This domain separater ("mnemonic") is added per BIP39 spec
        # to the passphrase
        # https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki#from-mnemonic-to-seed  # blocklint: URL pragma  # noqa: E501
        salt = "mnemonic" + unicode_decompose_string(passphrase)
        # From BIP39:
        #   To create a binary seed from the mnemonic, we use the PBKDF2 function with a
        # mnemonic sentence (in UTF-8 NFKD) used as the password and the string
        # "mnemonic" and passphrase (again in UTF-8 NFKD) used as the salt.
        stretched = pbkdf2_hmac_sha512(mnemonic, salt)
        return stretched[:64]
