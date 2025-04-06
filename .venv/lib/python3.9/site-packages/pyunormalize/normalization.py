"""Unicode normalization algorithms."""

from pyunormalize._unicode import (
    _COMPOSITION_EXCLUSIONS,
    _DECOMP_BY_CHARACTER,
    _NFC__QC_NO_OR_MAYBE,
    _NFD__QC_NO,
    _NFKC_QC_NO_OR_MAYBE,
    _NFKD_QC_NO,
    _NON_ZERO_CCC_TABLE,
)

# Hangul syllables for modern Korean
_SB = 0xAC00
_SL = 0xD7A3

# Hangul leading consonants (syllable onsets)
_LB = 0x1100
_LL = 0x1112

# Hangul vowels (syllable nucleuses)
_VB = 0x1161
_VL = 0x1175

# Hangul trailing consonants (syllable codas)
_TB = 0x11A8
_TL = 0x11C2

# Number of Hangul vowels
_VCOUNT = 21

# Number of Hangul trailing consonants,
# with the additional case of no trailing consonant
_TCOUNT = 27 + 1

# Dictionary mapping characters to their full canonical decompositions,
# not including Hangul syllables
_FULL_CDECOMP_BY_CHAR = {}

# Dictionary mapping characters to their full compatibility decompositions,
# not including Hangul syllables
_FULL_KDECOMP_BY_CHAR = {}

# Dictionary mapping canonical decompositions to their canonical composite,
# not including Hangul syllables
_COMPOSITE_BY_CDECOMP = {}

# Note: As Hangul compositions and decompositions are algorithmic,
# corresponding operations are performed in code rather than by storing
# the data in general-purpose tables.


def _full_decomposition(decomp_dict):
    # A full decomposition of a character sequence results from decomposing
    # each of the characters in the sequence until no characters can be further
    # decomposed.

    for key in decomp_dict:
        tmp = []
        decomposition = [key]

        while True:
            for x in decomposition:
                if x in decomp_dict:
                    tmp.extend(decomp_dict[x])
                else:
                    tmp.append(x)

            if tmp == decomposition:
                decomp_dict[key] = decomposition  # done with decomposition
                break

            decomposition = tmp
            tmp = []


def _populate_decomposition_dictionaries(decomp_by_character):
    # Populate dictionaries with full canonical decompositions
    # and full compatibility decompositions.

    for key, val in decomp_by_character.items():
        if isinstance(val[0], int):
            # assert len(val) in (1, 2)

            if len(val) == 2 and val[0] not in _NON_ZERO_CCC_TABLE:
                _COMPOSITE_BY_CDECOMP[tuple(val)] = key

            _FULL_CDECOMP_BY_CHAR[key] = _FULL_KDECOMP_BY_CHAR[key] = val
        else:
            _FULL_KDECOMP_BY_CHAR[key] = val[1:]

    # Make full canonical decomposition
    _full_decomposition(_FULL_CDECOMP_BY_CHAR)

    # Make full compatibility decomposition
    _full_decomposition(_FULL_KDECOMP_BY_CHAR)


# Populate full decomposition dictionaries
_populate_decomposition_dictionaries(_DECOMP_BY_CHARACTER)

del _DECOMP_BY_CHARACTER


#
# Public interface
#

def NFC(unistr):
    """Return the canonical equivalent "composed" form of the original Unicode
    string `unistr`. This function transforms the Unicode string into the
    Unicode "normalization form C", where character sequences are replaced by
    canonically equivalent composites, where possible, while compatibility
    characters are unaffected.

    For performance optimization, the function verifies whether the input
    string is already in NFC. If it is, the original string is returned
    directly to avoid unnecessary processing.

    Args:
        unistr (str): The input Unicode string.

    Returns:
        str: The NFC normalized Unicode string.

    Examples:

        >>> unistr = "élève"
        >>> nfc = NFC(unistr)
        >>> unistr, nfc
        ('élève', 'élève')
        >>> nfc == unistr
        False
        >>> " ".join(f"{ord(x):04X}" for x in unistr)
        '0065 0301 006C 0065 0300 0076 0065'
        >>> " ".join(f"{ord(x):04X}" for x in nfc)
        '00E9 006C 00E8 0076 0065'

        >>> unistr = "한국"
        >>> nfc = NFC(unistr)
        >>> unistr, nfc
        ('한국', '한국')
        >>> " ".join(f"{ord(x):04X}" for x in unistr)
        '1112 1161 11AB 1100 116E 11A8'
        >>> " ".join(f"{ord(x):04X}" for x in nfc)
        'D55C AD6D'

        >>> NFC("ﬃ")
        'ﬃ'

    """
    prev_ccc = 0

    for u in unistr:
        u = ord(u)

        if u in _NFC__QC_NO_OR_MAYBE:
            break

        if u not in _NON_ZERO_CCC_TABLE:
            continue

        curr_ccc = _NON_ZERO_CCC_TABLE[u]

        if curr_ccc < prev_ccc:
            break

        prev_ccc = curr_ccc
    else:
        return unistr

    result = map(chr, _compose([*map(ord, NFD(unistr))]))

    return "".join(result)


def NFD(unistr):
    """Return the canonical equivalent "decomposed" form of the original
    Unicode string `unistr`. This function transforms the Unicode string into
    the Unicode "normalization form D", where composite characters are replaced
    by canonically equivalent character sequences, in canonical order, while
    compatibility characters are unaffected.

    For performance optimization, the function verifies whether the input
    string is already in NFD. If it is, the original string is returned
    directly to avoid unnecessary processing.

    Args:
        unistr (str): The input Unicode string.

    Returns:
        str: The NFD normalized Unicode string.

    Examples:

        >>> unistr = "élève"
        >>> nfd = NFD(unistr)
        >>> unistr, nfd
        ('élève', 'élève')
        >>> nfd == unistr
        False
        >>> " ".join(f"{ord(x):04X}" for x in unistr)
        '00E9 006C 00E8 0076 0065'
        >>> " ".join(f"{ord(x):04X}" for x in nfd)
        '0065 0301 006C 0065 0300 0076 0065'

        >>> unistr = "한국"
        >>> nfd = NFD(unistr)
        >>> unistr, nfd
        ('한국', '한국')
        >>> " ".join(f"{ord(x):04X}" for x in unistr)
        'D55C AD6D'
        >>> " ".join(f"{ord(x):04X}" for x in nfd)
        '1112 1161 11AB 1100 116E 11A8'

        >>> NFD("ﬃ")
        'ﬃ'

    """
    prev_ccc = 0

    for u in unistr:
        u = ord(u)

        if u in _NFD__QC_NO:
            break

        if u not in _NON_ZERO_CCC_TABLE:
            continue

        curr_ccc = _NON_ZERO_CCC_TABLE[u]

        if curr_ccc < prev_ccc:
            break

        prev_ccc = curr_ccc
    else:
        return unistr

    result = map(chr, _reorder(_decompose(unistr)))

    return "".join(result)


def NFKC(unistr):
    """Return the compatibility equivalent "composed" form of the original
    Unicode string `unistr`. This function transforms the Unicode string into
    the Unicode "normalization form KC", where character sequences are replaced
    by canonically equivalent composites, where possible, and compatibility
    characters are replaced by their nominal counterparts.

    For performance optimization, the function verifies whether the input
    string is already in NFKC. If it is, the original string is returned
    directly to avoid unnecessary processing.

    Args:
        unistr (str): The input Unicode string.

    Returns:
        str: The NFKC normalized Unicode string.

    Example:
        >>> NFKC("ﬃ")
        'ffi'

    """
    prev_ccc = 0

    for u in unistr:
        u = ord(u)

        if u in _NFKC_QC_NO_OR_MAYBE:
            break

        if u not in _NON_ZERO_CCC_TABLE:
            continue

        curr_ccc = _NON_ZERO_CCC_TABLE[u]

        if curr_ccc < prev_ccc:
            break

        prev_ccc = curr_ccc
    else:
        return unistr

    result = map(chr, _compose([*map(ord, NFKD(unistr))]))

    return "".join(result)


def NFKD(unistr):
    """Return the compatibility equivalent "decomposed" form of the original
    Unicode string `unistr`. This function transforms the Unicode string into
    the Unicode "normalization form KD", where composite characters are
    replaced by canonically equivalent character sequences, in canonical order,
    and compatibility characters are replaced by their nominal counterparts.

    For performance optimization, the function verifies whether the input
    string is already in NFKD. If it is, the original string is returned
    directly to avoid unnecessary processing.

    Args:
        unistr (str): The input Unicode string.

    Returns:
        str: The NFKD normalized Unicode string.

    Example:
        >>> NFKD("⑴")
        '(1)'

    """
    prev_ccc = 0

    for u in unistr:
        u = ord(u)

        if u in _NFKD_QC_NO:
            break

        if u not in _NON_ZERO_CCC_TABLE:
            continue

        curr_ccc = _NON_ZERO_CCC_TABLE[u]

        if curr_ccc < prev_ccc:
            break

        prev_ccc = curr_ccc
    else:
        return unistr

    result = map(chr, _reorder(_decompose(unistr, compatibility=True)))

    return "".join(result)


# Dictionary for normalization forms dispatch
_normalization_forms = {
    "NFC": NFC,
    "NFD": NFD,
    "NFKC": NFKC,
    "NFKD": NFKD,
}

def normalize(form, unistr):
    """Transform the Unicode string `unistr` into the Unicode normalization
    form `form`. Valid values for `form` are "NFC", "NFD", "NFKC", and "NFKD".

    Args:
        form (str): The normalization form to apply, one of "NFC", "NFD",
            "NFKC", or "NFKD".

        unistr (str): The input Unicode string to be normalized.

    Returns:
        str: The normalized Unicode string.

    Examples:

        >>> normalize("NFKD", "⑴ ﬃ ²")
        '(1) ffi 2'

        >>> forms = ["NFC", "NFD", "NFKC", "NFKD"]
        >>> [normalize(f, "\u017F\u0307\u0323") for f in forms]
        ['ẛ̣', 'ẛ̣', 'ṩ', 'ṩ']

    """
    return _normalization_forms[form](unistr)


#
# Internals
#

def _decompose(unistr, *, compatibility=False):
    # Compute the full decomposition of the Unicode string based
    # on the specified normalization form. The type of full decomposition
    # chosen depends on which Unicode normalization form is involved. For NFC
    # or NFD, it performs a full canonical decomposition. For NFKC or NFKD,
    # it performs a full compatibility decomposition.

    result = []
    decomp = _FULL_KDECOMP_BY_CHAR if compatibility else _FULL_CDECOMP_BY_CHAR

    for u in unistr:
        u = ord(u)

        if u in decomp:
            result.extend(decomp[u])
        elif _SB <= u <= _SL:
            result.extend(_decompose_hangul_syllable(u))
        else:
            result.append(u)

    return result


def _decompose_hangul_syllable(cp):
    # Perform Hangul syllable decomposition algorithm to derive the full
    # canonical decomposition of a precomposed Hangul syllable into its
    # constituent jamo characters.

    sindex = cp - _SB
    tindex = sindex % _TCOUNT
    q = (sindex - tindex) // _TCOUNT
    V = _VB + (q  % _VCOUNT)
    L = _LB + (q // _VCOUNT)

    if tindex:
        # LVT syllable
        return (L, V, _TB - 1 + tindex)

    # LV syllable
    return (L, V)


def _reorder(elements):
    # Perform canonical ordering algorithm. Once a string has been fully
    # decomposed, this algorithm ensures that any sequences of combining marks
    # within it are arranged in a well-defined order. Only combining marks with
    # non-zero Canonical_Combining_Class property values are subject to
    # potential reordering. The canonical ordering imposed by both composed
    # and decomposed normalization forms is crucial for ensuring the uniqueness
    # of normal forms.

    n = len(elements)

    while n > 1:
        new_n = 0
        i = 1

        while i < n:
            ccc_b = _NON_ZERO_CCC_TABLE.get(elements[i])

            if not ccc_b:
                i += 2
                continue

            ccc_a = _NON_ZERO_CCC_TABLE.get(elements[i - 1])

            if not ccc_a or ccc_a <= ccc_b:
                i += 1
                continue

            elements[i - 1], elements[i] = elements[i], elements[i - 1]

            new_n = i
            i += 1

        n = new_n

    return elements


def _compose(elements):
    # Canonical composition algorithm to transform a fully decomposed
    # and canonically ordered string into its most fully composed but still
    # canonically equivalent sequence.

    for i, x in enumerate(elements):
        if x is None or x in _NON_ZERO_CCC_TABLE:
            continue

        last_cc = False
        blocked = False

        for j, y in enumerate(elements[i + 1 :], i + 1):
            if y in _NON_ZERO_CCC_TABLE:
                last_cc = True
            else:
                blocked = True

            if blocked and last_cc:
                continue

            prev = elements[j - 1]

            if (prev is None
                    or prev not in _NON_ZERO_CCC_TABLE
                    or _NON_ZERO_CCC_TABLE[prev] < _NON_ZERO_CCC_TABLE[y]):

                pair = (x, y)

                if pair in _COMPOSITE_BY_CDECOMP:
                    precomp = _COMPOSITE_BY_CDECOMP[pair]
                else:
                    precomp = _compose_hangul_syllable(*pair)

                if precomp is None or precomp in _COMPOSITION_EXCLUSIONS:
                    if blocked:
                        break
                else:
                    elements[i] = x = precomp
                    elements[j] = None

                    if blocked:
                        blocked = False
                    else:
                        last_cc = False

    return [*filter(None, elements)]


def _compose_hangul_syllable(x, y):
    # Perform Hangul syllable composition algorithm to derive the mapping
    # of a canonically decomposed sequence of Hangul jamo characters
    # to an equivalent precomposed Hangul syllable.

    if _LB <= x <= _LL and _VB <= y <= _VL:
        # Compose a leading consonant and a vowel into an LV syllable
        return _SB + (((x - _LB) * _VCOUNT) + y - _VB) * _TCOUNT

    if _SB <= x <= _SL and not (x - _SB) % _TCOUNT and _TB <= y <= _TL:
        # Compose an LV syllable and a trailing consonant into an LVT syllable
        return x + y - (_TB - 1)

    return None


if __name__ == "__main__":
    import doctest
    doctest.testmod()
