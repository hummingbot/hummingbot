"""Utils to parse NFTokenIDs."""

from typing_extensions import TypedDict

from xrpl.constants import XRPLException
from xrpl.core.addresscodec.codec import encode_classic_address


class NFTokenID(TypedDict):
    """A decoded representation of info from the NFTokenID."""

    nftoken_id: str
    flags: int
    transfer_fee: int
    issuer: str
    taxon: int
    sequence: int


def unscramble_taxon(taxon: int, token_seq: int) -> int:
    """
    Unscrambles or rescrambles a taxon in an NFTokenID.

    An issuer may issue several NFTs with the same taxon; to ensure that NFTs
    are spread across multiple pages we lightly mix the taxon up by using the
    sequence (which is not under the issuer's direct control) as the seed for
    a simple linear congruential generator.

    From the Hull-Dobell theorem we know that f(x)=(m*x+c) mod n will yield a
    permutation of [0, n) when n is a power of 2 if m is congruent to 1 mod 4
    and c is odd. By doing a bitwise XOR with this permutation we can
    scramble/unscramble the taxon.

    The XLS-20d proposal fixes m = 384160001 and c = 2459.
    We then take the modulus of 2^32 which is 4294967296.

    Args:
        taxon: The scrambled or unscrambled taxon (The XOR is both the
                encoding and decoding)
        token_seq: The account sequence when the token was minted. Used as a
                pseudorandom seed.

    Returns:
        The opposite taxon. If the taxon was scrambled it becomes unscrambled,
        and vice versa.
    """
    return (taxon ^ (384160001 * token_seq + 2459)) % 4294967296


def parse_nftoken_id(nft_id: str) -> NFTokenID:
    """
    Parse an NFTokenID into the information it is encoding.

    Example decoding:

    000B 0539 C35B55AA096BA6D87A6E6C965A6534150DC56E5E 12C5D09E 0000000C
    +--- +--- +--------------------------------------- +------- +-------
    |    |    |                                        |        |
    |    |    |                                        |        `---> Sequence: 12
    |    |    |                                        |
    |    |    |                                        `---> Scrambled Taxon: 314,953,886
    |    |    |                                              Unscrambled Taxon: 1337
    |    |    |
    |    |    `---> Issuer: rJoxBSzpXhPtAuqFmqxQtGKjA13jUJWthE
    |    |
    |    `---> TransferFee: 1337.0 bps or 13.37%
    |
    `---> Flags: 11 -> lsfBurnable, lsfOnlyXRP and lsfTransferable

    Args:
        nft_id: A hex string which identifies an NFToken on the ledger.

    Raises:
        XRPLException: when given an invalid Token ID as nft_id.

    Returns:
        A decoded nft TokenID with all information encoded within

    # noqa:E501
    """
    expected_length = 64
    if len(nft_id) != expected_length:
        raise XRPLException(
            f"Attempting to parse a tokenID with length"
            f" {len(nft_id)}, but expected a length of {expected_length}`"
        )

    scrambled_taxon = int(nft_id[48:56], base=16)
    sequence = int(nft_id[56:64], base=16)

    nftoken_data: NFTokenID = {
        "nftoken_id": nft_id,
        "flags": int(nft_id[0:4], base=16),
        "transfer_fee": int(nft_id[4:8], base=16),
        "issuer": encode_classic_address(bytes.fromhex(nft_id[8:48])),
        "taxon": unscramble_taxon(scrambled_taxon, sequence),
        "sequence": sequence,
    }

    return nftoken_data
